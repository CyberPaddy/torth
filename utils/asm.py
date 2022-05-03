import re
import subprocess
import sys
from typing import List, Literal, NoReturn, Optional
from utils.defs import Colors, OpType, Op, Token, Program, STACK, REGEX

def get_asm_file_start() -> str:
    return '''default rel
extern printf

%define buffer_len 65535 ; User input buffer length
%define stdin 0
%define stdout 1
%define success 0
%define sys_exit 60
%define sys_read 0
%define sys_write 1

section .rodata
'''

def initialize_asm(asm_file: str) -> None:
    default_asm: str = f'''{get_asm_file_start()}  formatStrInt db "%lld",10,0

section .bss
  int: RESQ 1 ; allocates 8 bytes

section .text
PrintInt:
  global _start
  mov rsi, [rsp+8]
  mov rdi, formatStrInt
  mov rax, 0
  call printf
  ret

global main
main:
'''
    with open(asm_file, 'w') as f:
        f.write(default_asm)

def get_op_comment_asm(op: Op, op_type: OpType) -> str:
    src_file: str   = op.token.location[0]
    row: str        = str(op.token.location[1])
    col: str        = str(op.token.location[2])
    op_name: str    = op_type.name
    if op_name == "INTRINSIC":
        op_name = f'{op_type.name} {op.token.value}'
    return f';; -- {op_name} | File: {src_file}, Row: {row}, Col: {col}' + '\n'

# Only cmov operand changes with different comparison intrinsics
def get_comparison_asm(cmov_operand: str) -> str:
    comparison_asm: str  =  '  pop rax\n'
    comparison_asm      +=  '  pop rbx\n'
    comparison_asm      +=  '  mov rcx, 0\n'
    comparison_asm      +=  '  mov rdx, 1\n'
    comparison_asm      +=  '  cmp rax, rbx\n'
    comparison_asm      += f'  {cmov_operand} rcx, rdx\n'
    comparison_asm      +=  '  push rbx\n'
    comparison_asm      +=  '  push rcx\n'
    return comparison_asm

def get_arithmetic_asm(operand: str) -> str:
    arithmetic_asm: str  =  '  pop rbx\n'
    arithmetic_asm      +=  '  pop rax\n'
    arithmetic_asm      += f'  {operand} rax, rbx\n'
    arithmetic_asm      +=  '  push rax\n'
    return arithmetic_asm

def add_string_variable_asm(asm_file: str, string: str, op: Op, insert_newline: bool, op_type: OpType) -> None:
    with open(asm_file, 'r') as f:
        file_lines: List[str] = f.readlines()
    with open(asm_file, 'w') as f:
        if op_type == OpType.PUSH_STR:
            str_prefix: Literal['s', 'cs'] = 's'
        elif op_type == OpType.PUSH_CSTR:
            str_prefix = 'cs'
        f.write(get_asm_file_start())
        if insert_newline:
            f.write(f'  {str_prefix}{op.id} db "{string}",10,0\n')
        else:
            f.write(f'  {str_prefix}{op.id} db "{string}",0\n')

        # Rewrite lines except for the first line (section .rodata)
        len_asm_file_start: int = len(get_asm_file_start().split('\n')) - 1
        for i in range(len_asm_file_start, len(file_lines)):
            f.write(file_lines[i])

def add_array_asm(asm_file: str, array: list, op: Op) -> None:
    with open(asm_file, 'r') as f:
        file_lines: List[str] = f.readlines()
    with open(asm_file, 'w') as f:
        f.write(get_asm_file_start())
        for i in range(len(array)):
            f.write(f'  s{op.id}_{i}: db {array[i]},0\n')
        f.write(f'  s_arr{op.id}: dq ')
        for i in range(len(array)):
            f.write(f's{op.id}_{i}, ')
        f.write('0\n') # Array ends at NULL byte

        # Rewrite lines
        len_asm_file_start: int = len(get_asm_file_start().split('\n')) - 1
        for i in range(len_asm_file_start, len(file_lines)):
            f.write(file_lines[i])

def add_input_buffer_asm(asm_file: str, op: Op):
    with open(asm_file, 'r') as f:
        file_lines: List[str] = f.readlines()
    with open(asm_file, 'w') as f:
        f.write(get_asm_file_start())
        row: int = len(get_asm_file_start().splitlines()) - 1
        while row < len(file_lines):
            row += 1
            f.write(file_lines[row])
            if file_lines[row] == "section .bss\n":
                break
        f.write(f'  buffer{op.id}: resb buffer_len\n')

        # Rewrite lines
        for i in range(row+1, len(file_lines)):
            f.write(file_lines[i])

def get_stack_after_syscall(stack: List[str], param_count: int) -> List[str]:
    _syscall = stack.pop()
    for _i in range(param_count):
        stack.pop()
    stack.append('0') # Syscall return value is 0 by default
    return stack

def compiler_error(op: Optional[Op], error_type: str, error_message: str) -> NoReturn:
    operand: str    = op.token.value
    file: str       = op.token.location[0]
    row: int        = op.token.location[1]
    col: int        = op.token.location[2]

    print(f'{Colors.HEADER}Compiler error {Colors.FAIL}{error_type}{Colors.NC}' + f":\n{error_message}\n")

    print(f'{Colors.HEADER}Operand{Colors.NC}: {operand}')
    print(f'{Colors.HEADER}File{Colors.NC}: {file}')
    print(f'{Colors.HEADER}Row{Colors.NC}: {row}, ' \
        + f'{Colors.HEADER}Column{Colors.NC}: {col}')
    exit(1)

def check_popped_value_type(op: Op, popped_value: str, expected_type: str) -> None:
    regex: str = REGEX[expected_type]
    error_message: str = f"Wrong type of value popped from the stack.\n\n" + \
        f"{Colors.HEADER}Value{Colors.NC}: {popped_value}\n" + \
        f"{Colors.HEADER}Expected{Colors.NC}: {expected_type}\n" + \
        f"{Colors.HEADER}Regex{Colors.NC}: {regex}"

    # Raise compiler error if the value gotten from the stack does not match with the regex
    assert re.match(regex, popped_value), compiler_error(op, "REGISTER_VALUE_ERROR", error_message)

def get_parent_op_type_do(op: Op, program: Program) -> OpType:
    for i in range(op.id - 1, -1, -1):
        if program[i].type in (OpType.IF, OpType.ELIF, OpType.WHILE):
            return program[i].type
        if program[i].type in (OpType.DO, OpType.END, OpType.ENDIF):
            break
    compiler_error(op, "AMBIGUOUS_DO", "DO operand without parent IF, ELIF or WHILE")

def get_op_asm(op: Op, program: Program) -> str:
    global STACK
    token: Token = op.token
    op_asm: str = ''

    # DO is conditional jump to operand after ELIF, ELSE, END or ENDIF
    if op.type == OpType.DO:
        return get_do_asm(op, program)
    # ELIF is unconditional jump to ENDIF and a keyword for DO to jump to
    elif op.type == OpType.ELIF:
        return get_elif_asm(op, program)
    # ELSE is unconditional jump to ENDIF and a keyword for DO to jump to
    elif op.type == OpType.ELSE:
        for i in range(op.id + 1, len(program)):
            if program[i].type == OpType.ENDIF:
                op_asm += f'  jmp ENDIF{i}\n'
                op_asm += f'ELSE{op.id}:\n'
                break
    # END is unconditional jump to WHILE
    elif op.type == OpType.END:
        for i in range(op.id - 1, -1, -1):
            if program[i].type == OpType.WHILE:
                op_asm += f'  jmp WHILE{i}\n'
                op_asm += f'END{op.id}:\n'
                break
    # ENDIF is a keyword for DO, ELIF or ELSE to jump to
    elif op.type == OpType.ENDIF:
        op_asm += f'ENDIF{op.id}:\n'
    # IF is like DUP, it duplicates the first element in the stack
    elif op.type == OpType.IF:
        op_asm +=  '  pop rax\n'
        op_asm +=  '  push rax\n'
        op_asm +=  '  push rax\n'
        try:
            top = STACK.pop()
        except IndexError:
            compiler_error(op, "POP_FROM_EMPTY_STACK", "Cannot duplicate value from empty stack.")
        STACK.append(top)
        STACK.append(top)
    elif op.type == OpType.PUSH_ARRAY:
        op_asm += f'  mov rsi, s_arr{op.id} ; Pointer to array\n'
        op_asm +=  '  push rsi\n'
        STACK.append(f"*buf s_arr{op.id}")
    elif op.type == OpType.PUSH_CSTR:
        str_val: str = op.token.value[1:-1]  # Take quotes out of the string
        STACK.append(f"*buf cs{op.id}")
        op_asm += f'  mov rsi, cs{op.id} ; Pointer to string\n'
        op_asm +=  '  push rsi\n'
    elif op.type == OpType.PUSH_INT:
        integer: str = token.value
        STACK.append(integer)
        op_asm += f'  mov rax, {integer}\n'
        op_asm +=  '  push rax\n'
    elif op.type == OpType.PUSH_STR:
        return get_push_str_asm(op)
    elif op.type == OpType.WHILE:
        return get_while_asm(op)
    elif op.type == OpType.INTRINSIC:
        intrinsic: str = token.value.upper()
        if intrinsic == "DIV":
            return get_div_asm(op)
        elif intrinsic == "DIVMOD":
            return get_divmod_asm(op)
        elif intrinsic == "DROP":
            return get_drop_asm(op)
        elif intrinsic == "DUP":
            return get_dup_asm(op)
        elif intrinsic == "ENVP":
            return get_envp_asm()
        elif intrinsic == "EXIT":
            return get_exit_asm()
        elif intrinsic == "EQ":
            return get_eq_asm(op)
        elif intrinsic == "GE":
            return get_ge_asm(op)
        elif intrinsic == "GET_NTH":
            return get_nth_asm(op)
        elif intrinsic == "GT":
            return get_gt_asm(op)
        elif intrinsic == "INPUT":
            return get_input_asm(op)
        elif intrinsic == "LE":
            return get_le_asm(op)
        elif intrinsic == "LT":
            return get_lt_asm(op)
        elif intrinsic == "MINUS":
            return get_minus_asm(op)
        elif intrinsic == "MOD":
            return get_mod_asm(op)
        elif intrinsic == "MUL":
            return get_mul_asm(op)
        elif intrinsic == "NE":
            return get_ne_asm(op)
        elif intrinsic == "OVER":
            return get_over_asm(op)
        elif intrinsic == "PLUS":
            return get_plus_asm(op)
        # TODO: Merge PRINT and PRINT_INT
        elif intrinsic == "PRINT":
            return get_string_output_asm(op, intrinsic)
        elif intrinsic == "PRINT_INT":
            return get_print_int_asm()
        elif intrinsic == "PUTS":
            return get_string_output_asm(op, intrinsic)
        elif intrinsic == "ROT":
            return get_rot_asm(op)
        elif intrinsic == "SWAP":
            return get_swap_asm(op)
        elif intrinsic == "SWAP2":
            return get_swap2_asm(op)
        elif intrinsic == "SYSCALL0":
            return get_syscall_asm(op, param_count=0)
        elif intrinsic == "SYSCALL1":
            return get_syscall_asm(op, param_count=1)
        elif intrinsic == "SYSCALL2":
            return get_syscall_asm(op, param_count=2)
        elif intrinsic == "SYSCALL3":
            return get_syscall_asm(op, param_count=3)
        elif intrinsic == "SYSCALL4":
            return get_syscall_asm(op, param_count=4)
        elif intrinsic == "SYSCALL5":
            return get_syscall_asm(op, param_count=5)
        elif intrinsic == "SYSCALL6":
            return get_syscall_asm(op, param_count=6)
        else:
            compiler_error(op, "NOT_IMPLEMENTED", f"Intrinsic {intrinsic} has not been implemented.")
    else:
        compiler_error(op, "NOT_IMPLEMENTED", f"Operation {op.type.name} has not been implemented.")
    return op_asm

def get_push_str_asm(op: Op) -> str:
    str_val: str = op.token.value[1:-1]  # Take quotes out of the string
    str_len: int = len(str_val) + 1      # Add newline
    STACK.append(f"{str_len}")
    STACK.append(f"*buf s{op.id}")
    op_asm: str  = f'  mov rax, {str_len} ; String length\n'
    op_asm      += f'  mov rsi, s{op.id} ; Pointer to string\n'
    op_asm      +=  '  push rax\n'
    op_asm      +=  '  push rsi\n'
    return op_asm

# WHILE is a keyword for ELSE to jump to and also like DUP
# It duplicates the first element in the stack
def get_while_asm(op: Op) -> str:
    op_asm: str  = f'WHILE{op.id}:\n'
    op_asm      +=  '  pop rax\n'
    op_asm      +=  '  push rax\n'
    op_asm      +=  '  push rax\n'
    try:
        top = STACK.pop()
    except IndexError:
        compiler_error(op, "POP_FROM_EMPTY_STACK", "Cannot duplicate value from empty stack.")
    STACK.append(top)
    STACK.append(top)
    return op_asm

def get_div_asm(op: Op) -> str:
    op_asm: str  = '  xor edx, edx ; Do not use floating point arithmetic\n'
    op_asm      += '  pop rbx\n'
    op_asm      += '  pop rax\n'
    op_asm      += '  div rbx\n'
    op_asm      += '  push rax ; Quotient\n'
    try:
        a = STACK.pop()
        b = STACK.pop()
    except IndexError:
        compiler_error(op, "POP_FROM_EMPTY_STACK", "Not enough values in the stack.")
    check_popped_value_type(op, a, expected_type='INT')
    check_popped_value_type(op, b, expected_type='INT')
    try:
        STACK.append(str(int(b) // int(a)))
    except ZeroDivisionError:
        compiler_error(op, "DIVISION_BY_ZERO", "Division by zero is not possible.")
    return op_asm

def get_divmod_asm(op: Op) -> str:
    op_asm: str  = '  xor edx, edx ; Do not use floating point arithmetic\n'
    op_asm      += '  pop rbx\n'
    op_asm      += '  pop rax\n'
    op_asm      += '  div rbx\n'
    op_asm      += '  push rdx ; Remainder\n'
    op_asm      += '  push rax ; Quotient\n'
    try:
        a = STACK.pop()
        b = STACK.pop()
    except IndexError:
        compiler_error(op, "POP_FROM_EMPTY_STACK", "Not enough values in the stack.")
    check_popped_value_type(op, a, expected_type='INT')
    check_popped_value_type(op, b, expected_type='INT')
    STACK.append(str(int(a)% int(b)))
    STACK.append(str(int(a)//int(b)))
    return op_asm

def get_drop_asm(op: Op) -> str:
    try:
        STACK.pop()
    except IndexError:
        compiler_error(op, "POP_FROM_EMPTY_STACK", "Cannot drop value from empty stack.")
    return '  add rsp, 8\n'

def get_dup_asm(op: Op) -> str:
    op_asm: str  = '  pop rax\n'
    op_asm      += '  push rax\n'
    op_asm      += '  push rax\n'
    try:
        top = STACK.pop()
    except IndexError:
        compiler_error(op, "POP_FROM_EMPTY_STACK", "Cannot duplicate value from empty stack.")
    STACK.append(top)
    STACK.append(top)
    return op_asm

def get_envp_asm() -> str:
    op_asm: str  = '  mov rax, [rbp+8]\n'
    op_asm      += '  push rax\n'
    STACK.append('ENVP')
    return op_asm

def get_exit_asm() -> str:
    op_asm: str  = '  mov rax, 60\n'
    op_asm      += '  mov rdi, 0\n'
    op_asm      += '  syscall\n'
    return op_asm

def get_eq_asm(op: Op) -> str:
    try:
        b = STACK.pop()
        a = STACK.pop()
    except IndexError:
        compiler_error(op, "POP_FROM_EMPTY_STACK", "Not enough values in the stack.")
    check_popped_value_type(op, a, expected_type='INT')
    check_popped_value_type(op, b, expected_type='INT')
    STACK.append(a)
    STACK.append(str(int(a==b)))
    return get_comparison_asm("cmove")

def get_ge_asm(op: Op) -> str:
    try:
        b = STACK.pop()
        a = STACK.pop()
    except IndexError:
        compiler_error(op, "POP_FROM_EMPTY_STACK", "Not enough values in the stack.")
    check_popped_value_type(op, a, expected_type='INT')
    check_popped_value_type(op, b, expected_type='INT')
    STACK.append(a)
    STACK.append(str(int(a>=b)))
    return get_comparison_asm("cmovge")

# Copies Nth element from the stack to the top of the stack (first element is 0th)
def get_nth_asm(op: Op) -> str:
    op_asm: str = '  pop rax\n'

    # The top element in the stack is the N
    try:
        n: int = int(STACK.pop())
    except IndexError:
        compiler_error(op, "POP_FROM_EMPTY_STACK", "Not enough values in the stack.")
    except ValueError:
        compiler_error(op, "STACK_VALUE_ERROR", "First element in the stack is not an integer.")
    try:
        stack_index: int = len(STACK) - 1 # Zero based indexes
        nth_element: str = STACK[stack_index - n]
    except IndexError:
        compiler_error(op, "NOT_ENOUGH_ELEMENTS_IN_STACK", \
                    f"Cannot get {n}. element from the stack: Stack only contains {len(STACK)} elements.")

    op_asm += f'  add rsp, {n * 8} ; Stack pointer to the Nth element\n'
    op_asm +=  '  pop rax ; Get Nth element to rax\n'
    op_asm += f'  sub rsp, {n * 8 + 8} ; Return stack pointer\n'
    op_asm +=  '  push rax\n'
    STACK.append(nth_element)
    return op_asm

def get_gt_asm(op: Op) -> str:
    try:
        b = STACK.pop()
        a = STACK.pop()
    except IndexError:
        compiler_error(op, "POP_FROM_EMPTY_STACK", "Not enough values in the stack.")
    check_popped_value_type(op, a, expected_type='INT')
    check_popped_value_type(op, b, expected_type='INT')
    STACK.append(a)
    STACK.append(str(int(a>b)))
    return get_comparison_asm("cmovg")

# User input is essentially a CSTR but the length is also pushed to the stack for possible printing
def get_input_asm(op: Op) -> str:
    op_asm: str  =  '  mov rax, sys_read\n'
    op_asm      +=  '  mov rdi, stdin\n'
    op_asm      += f'  mov rsi, buffer{op.id}\n'
    op_asm      +=  '  mov rdx, buffer_len\n'
    op_asm      +=  '  syscall\n'
    op_asm      +=  '  xor rdx, rdx\n'
    op_asm      += f'  mov [buffer{op.id}+rax-1], dl  ; Change newline character to NULL\n'
    op_asm      +=  '  push rax\n'
    op_asm      += f'  push buffer{op.id}\n'
    STACK.append(f"42") # User input length is not known beforehand
    STACK.append(f"*buf buffer")
    return op_asm

def get_le_asm(op: Op) -> str:
    try:
        b = STACK.pop()
        a = STACK.pop()
    except IndexError:
        compiler_error(op, "POP_FROM_EMPTY_STACK", "Not enough values in the stack.")
    check_popped_value_type(op, a, expected_type='INT')
    check_popped_value_type(op, b, expected_type='INT')
    STACK.append(a)
    STACK.append(str(int(a<=b)))
    return get_comparison_asm("cmovle")

def get_lt_asm(op: Op) -> str:
    try:
        b = STACK.pop()
        a = STACK.pop()
    except IndexError:
        compiler_error(op, "POP_FROM_EMPTY_STACK", "Not enough values in the stack.")
    check_popped_value_type(op, a, expected_type='INT')
    check_popped_value_type(op, b, expected_type='INT')
    STACK.append(a)
    STACK.append(str(int(a<b)))
    return get_comparison_asm("cmovl")

def get_minus_asm(op: Op) -> str:
    ints: List[int] = pop_integers_from_stack(op, pop_count=2)
    STACK.append(str(int(ints[0]) + int(ints[1])))
    return get_arithmetic_asm("sub")

def get_mod_asm(op: Op) -> str:
    op_asm: str  = '  xor edx, edx ; Do not use floating point arithmetic\n'
    op_asm      += '  pop rbx\n'
    op_asm      += '  pop rax\n'
    op_asm      += '  div rbx\n'
    op_asm      += '  push rdx ; Remainder\n'
    try:
        b = STACK.pop()
        a = STACK.pop()
    except IndexError:
        compiler_error(op, "POP_FROM_EMPTY_STACK", "Not enough values in the stack.")
    STACK.append(str(int(a) % int(b)))
    return op_asm

def get_mul_asm(op: Op) -> str:
    op_asm: str  = '  pop rax\n'
    op_asm      += '  pop rbx\n'
    op_asm      += '  mul rbx\n'
    op_asm      += '  push rax\n'
    try:
        b = STACK.pop()
        a = STACK.pop()
    except IndexError:
        compiler_error(op, "POP_FROM_EMPTY_STACK", "Not enough values in the stack.")
    STACK.append(str(int(a) * int(b)))
    return op_asm

def get_ne_asm(op: Op) -> str:
    try:
        b = STACK.pop()
        a = STACK.pop()
    except IndexError:
        compiler_error(op, "POP_FROM_EMPTY_STACK", "Not enough values in the stack.")
    check_popped_value_type(op, a, expected_type='INT')
    check_popped_value_type(op, b, expected_type='INT')
    STACK.append(a)
    STACK.append(str(int(a!=b)))
    return get_comparison_asm("cmovne")

def get_over_asm(op: Op) -> str:
    op_asm: str  = '  pop rax\n'
    op_asm      += '  pop rbx\n'
    op_asm      += '  push rbx\n'
    op_asm      += '  push rax\n'
    op_asm      += '  push rbx\n'
    try:
        b = STACK.pop()
        a = STACK.pop()
    except IndexError:
        compiler_error(op, "POP_FROM_EMPTY_STACK", "The stack does not contain at least two elements.")
    check_popped_value_type(op, a, expected_type='INT')
    check_popped_value_type(op, b, expected_type='INT')
    STACK.append(a)
    STACK.append(b)
    STACK.append(a)
    return op_asm

def get_plus_asm(op: Op) -> str:
    ints: List[int] = pop_integers_from_stack(op, pop_count=2)
    STACK.append(str(int(ints[0]) + int(ints[1])))
    return get_arithmetic_asm("add")

def pop_integers_from_stack(op: Op, pop_count: int) -> List[int]:
    popped_integers: List[int] = []
    for _ in range(pop_count):
        try:
            popped: str = STACK.pop()
            check_popped_value_type(op, popped, expected_type='INT')
            popped_integers.append(popped)
        except IndexError:
            compiler_error(op, "POP_FROM_EMPTY_STACK", "Not enough values in the stack.")
    return popped_integers

def get_print_int_asm() -> str:
    op_asm: str  = '  mov [int], rsi\n'
    op_asm      += '  call PrintInt\n'
    return op_asm

def get_string_output_asm(op: Op, intrinsic: str) -> str:
    op_asm: str  = '  pop rsi    ; *buf\n'
    op_asm      += '  pop rdx    ; count\n'

    # PRINT is the same as PUTS but without newline
    if intrinsic == 'PRINT':
        op_asm +=  '  sub rdx, 1 ; Remove newline\n'
    op_asm      += '  mov rax, sys_write\n'
    op_asm      += '  mov rdi, stdout\n'
    op_asm      += '  syscall\n'
    try:
        buf    = STACK.pop()
        count  = STACK.pop()
    except IndexError:
        compiler_error(op, "POP_FROM_EMPTY_STACK", \
            f"Not enough values in the stack for syscall 'write'.\n{intrinsic} operand requires two values, *buf and count.")

    # Check if the popped values were of the correct type
    check_popped_value_type(op, buf, expected_type='*buf')
    check_popped_value_type(op, count, expected_type='INT')
    return op_asm

def get_rot_asm(op: Op) -> str:
    op_asm: str  = '  pop rax\n'
    op_asm      += '  pop rbx\n'
    op_asm      += '  pop rcx\n'
    op_asm      += '  push rax\n'
    op_asm      += '  push rcx\n'
    op_asm      += '  push rbx\n'
    try:
        a = STACK.pop()
        b = STACK.pop()
        c = STACK.pop()
    except IndexError:
        compiler_error(op, "POP_FROM_EMPTY_STACK", "The stack does not contain at least three elements to rotate.")
    STACK.append(a)
    STACK.append(c)
    STACK.append(b)
    return op_asm

def get_swap_asm(op: Op) -> str:
    op_asm: str  = '  pop rax\n'
    op_asm      += '  pop rbx\n'
    op_asm      += '  push rax\n'
    op_asm      += '  push rbx\n'
    try:
        a = STACK.pop()
        b = STACK.pop()
    except IndexError:
        compiler_error(op, "POP_FROM_EMPTY_STACK", "Not enough values in the stack.")
    STACK.append(a)
    STACK.append(b)
    return op_asm

def get_swap2_asm(op: Op) -> str:
    op_asm: str  = '  pop rax\n'
    op_asm      += '  pop rbx\n'
    op_asm      += '  pop rcx\n'
    op_asm      += '  pop rdx\n'
    op_asm      += '  push rbx\n'
    op_asm      += '  push rax\n'
    op_asm      += '  push rdx\n'
    op_asm      += '  push rcx\n'
    try:
        a = STACK.pop()
        b = STACK.pop()
        c = STACK.pop()
        d = STACK.pop()
    except IndexError:
        compiler_error(op, "POP_FROM_EMPTY_STACK", "Not enough values in the stack.")
    STACK.append(b)
    STACK.append(a)
    STACK.append(d)
    STACK.append(c)
    return op_asm

def get_syscall_asm(op: Op, param_count: int) -> str:
    op_asm: str  = "  pop rax ; syscall\n"

    # Pop arguments to syscall argument registers
    argument_registers: List[str] = ['rdi', 'rsi', 'rdx', 'r10', 'r8', 'r9']
    for i in range(param_count):
        op_asm += f"  pop {argument_registers[i]} ; {i+1}. arg\n"

    # Call the syscall and push return code to RAX
    op_asm      += "  syscall\n"
    op_asm      += "  push rax ; return code\n"

    global STACK
    try:
        STACK = get_stack_after_syscall(STACK, param_count)
    except IndexError:
        compiler_error(op, "POP_FROM_EMPTY_STACK", "Not enough values in the stack.")
    return (op_asm)

def get_do_asm(op: Op, program: Program) -> str:
    parent_op_type: OpType = get_parent_op_type_do(op, program)
    for i in range(op.id + 1, len(program)):
        op_type: OpType = program[i].type
        if ( parent_op_type == OpType.IF and op_type in (OpType.ELIF, OpType.ELSE, OpType.ENDIF) ) \
            or ( parent_op_type == OpType.ELIF and op_type in (OpType.ELIF, OpType.ELSE, OpType.ENDIF) ) \
            or ( parent_op_type == OpType.WHILE and op_type == OpType.END ):
            jump_destination: str = program[i].type.name + str(i)
            op_asm: str  =  '  pop rax\n'
            op_asm      +=  '  add rsp, 8\n'
            op_asm      +=  '  test rax, rax\n'
            op_asm      += f'  jz {jump_destination}\n'
            try:
                STACK.pop()
                STACK.pop()
            except IndexError:
                compiler_error(op, "POP_FROM_EMPTY_STACK", "Not enough values in the stack.")
            break
    return op_asm

def get_elif_asm(op: Op, program: Program) -> str:
    op_asm: str = ''
    for i in range(op.id + 1, len(program)):
        if program[i].type == OpType.ENDIF:
            op_asm += f'  jmp ENDIF{i}\n'
            op_asm += f'ELIF{op.id}:\n'
            break
        # ELIF is like DUP, it duplicates the first element in the stack
    op_asm +=  '  pop rax\n'
    op_asm +=  '  push rax\n'
    op_asm +=  '  push rax\n'
    try:
        top: str = STACK.pop()
    except IndexError:
        compiler_error(op, "POP_FROM_EMPTY_STACK", "Cannot duplicate value from empty stack.")
    STACK.append(top)
    STACK.append(top)
    return op_asm

def generate_asm(program: Program, asm_file: str) -> None:
    for op in program:
        token: Token = op.token

        if op.type in [OpType.PUSH_STR, OpType.PUSH_CSTR]:
            str_val: str = token.value[1:-1]  # Take quotes out of the string
            insert_newline: bool = op.type == OpType.PUSH_STR
            add_string_variable_asm(asm_file, str_val, op, insert_newline, op.type)

        elif op.type == OpType.PUSH_ARRAY:
            value: str = token.value
            elements: List[str] = value[value.find("(")+1:value.rfind(")")].split(',')
            # Remove whitespaces from the elements list
            elements = [element.strip().replace("'", '"') for element in elements]
            add_array_asm(asm_file, elements, op)

        elif token.value.upper() == 'INPUT':
            add_input_buffer_asm(asm_file, op)

        with open(asm_file, 'a') as f:
            f.write(get_op_comment_asm(op, op.type))
            op_asm: str = get_op_asm(op, program=program)
            if op_asm != "":
                f.write(op_asm)

    with open(asm_file, 'a') as f:
        f.write( ';; -- exit syscall\n')
        f.write( '  mov rax, sys_exit\n')
        f.write( '  mov rdi, success\n')
        f.write( '  syscall\n')
        f.close()

def compile_asm(asm_file: str) -> None:
    subprocess.run(['nasm', '-felf64', f'-o{asm_file.replace(".asm", ".o")}', asm_file])

def link_object_file(obj_file: str, output_file: str) -> None:
    subprocess.run(['gcc', '-no-pie', f'-o{output_file}', obj_file])

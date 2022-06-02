"""
Functions used for generating assembly code from Torth code
"""
from typing import Dict, List
from compiler.defs import Constant, Memory, OpType, Op, Program, Token, TokenType
from compiler.utils import compiler_error

def initialize_asm(constants: List[Constant], memories: List[Memory]) -> str:
    """Initialize assembly code file with some common definitions."""
    return f'''{get_asm_file_start(constants)}
section .bss
  args_ptr: resq 1
{get_memory_definitions_asm(memories)}
section .text

;; Joinked from Porth's print function, thank you Tsoding!
print:
  mov     r9, -3689348814741910323
  sub     rsp, 40
  lea     rcx, [rsp+30]
.L2:
  mov     rax, rdi
  lea     r8, [rsp+32]
  mul     r9
  mov     rax, rdi
  sub     r8, rcx
  shr     rdx, 3
  lea     rsi, [rdx+rdx*4]
  add     rsi, rsi
  sub     rax, rsi
  add     eax, 48
  mov     BYTE [rcx], al
  mov     rax, rdi
  mov     rdi, rdx
  mov     rdx, rcx
  sub     rcx, 1
  cmp     rax, 9
  ja      .L2
  lea     rax, [rsp+32]
  mov     edi, 1
  sub     rdx, rax
  xor     eax, eax
  lea     rsi, [rsp+32+rdx]
  dec     r8
  mov     rdx, r8
  mov     rax, 1
  syscall
  add     rsp, 40
  ret

global _start
_start:
  mov [args_ptr], rsp   ; Pointer to argc
'''

def get_asm_file_start(constants: List[Constant]) -> str:
    """Return the contents of the beginning of the generated assembly file."""
    const_defines: str = ''.join(f'%define {const.name} {const.value}\n' for const in constants)

    return f'''default rel

;; DEFINES
%define buffer_len 65535 ; User input buffer length
%define success 0
%define sys_exit 60
{const_defines}
section .data
'''

def get_asm_file_end() -> str:
    """Returns the contents of the beginning of the generated assembly file"""
    return ''';; -- exit syscall
  mov rax, sys_exit
  mov rdi, success
  syscall'''

def get_memory_definitions_asm(memories: List[Memory]) -> str:
    """Generates assembly code of memory definitions. Returns the memory definitions."""
    asm: str = ''
    for memory in memories:
        name: str           = memory[0]
        size: str           = memory[1]
        file, row, col      = memory[2]
        asm += get_token_info_comment_asm(f'MEMORY {name}', file, row, col)
        asm += f'  {name}: RESB {size}\n'
    return asm

def generate_asm(assembly: str, constants: List[Constant], program: Program) -> str:
    """Generate assembly file and write it to a file."""
    for op in program:
        token: Token = op.token

        if op.type == OpType.PUSH_STR:
            assembly = add_string_variable_asm(assembly, token.value, op, constants)
        elif token.value.upper() == 'INPUT':
            assembly = add_input_buffer_asm(assembly, op)

        assembly += get_op_comment_asm(op, op.type)

        # Get assembly for the current Op
        op_asm: str = get_op_asm(op, program=program)
        if op_asm != "":
            assembly += op_asm

    assembly += get_asm_file_end()
    return assembly

def clean_asm(original_assembly: str) -> str:
    """Remove unused code from assembly file"""
    cleaned_assembly: str   = ''
    rows: List[str]         = original_assembly.split('\n')

    for i, row in enumerate(rows):
        words: List[str] = row.split()

        # Remove unused defines
        if words and words[0] == '%define' and all(words[1] not in word.split() for word in rows[:i] + rows[i+1:]):
            continue

        # Append row for the final assembly
        cleaned_assembly += f"{row}\n"
    return cleaned_assembly

def get_op_asm(op: Op, program: Program) -> str:
    """Generate assembly code for certain Op. Return assembly for the Op."""
    if op.type in {
        OpType.CAST_BOOL,   # Casts affect only the type checking
        OpType.CAST_CHAR,
        OpType.CAST_INT,
        OpType.CAST_PTR,
        OpType.CAST_STR,
        OpType.IF           # If is just a keyword which starts an IF-block
        }:
        return ''
    if op.type == OpType.BREAK:
        return get_break_asm(op, program)
    if op.type == OpType.CONTINUE:
        return get_continue_asm(op, program)
    if op.type == OpType.DO:
        return get_do_asm(op, program)
    if op.type == OpType.DONE:
        return get_done_asm(op, program)
    if op.type == OpType.ELIF:
        return get_elif_asm(op, program)
    if op.type == OpType.ELSE:
        return get_else_asm(op, program)
    if op.type == OpType.ENDIF:
        return get_endif_asm(op)
    if op.type == OpType.PUSH_BOOL:
        return get_push_bool_asm(op.token.value.upper())
    if op.type == OpType.PUSH_CHAR:
        return get_push_char_asm(op)
    if op.type == OpType.PUSH_INT:
        return get_push_int_asm(op.token.value)
    if op.type == OpType.PUSH_PTR:
        return get_push_ptr_asm(op.token.value)
    if op.type == OpType.PUSH_STR:
        return get_push_str_asm(op)
    if op.type == OpType.PUSH_UINT8:
        return get_push_int_asm(op.token.value)
    if op.type == OpType.WHILE:
        return get_while_asm(op)
    if op.type == OpType.INTRINSIC:
        intrinsic: str = op.token.value.upper()
        if   intrinsic == "ARGC":
            return get_argc_asm()
        if intrinsic == "ARGV":
            return get_argv_asm()
        if intrinsic == "DIVMOD":
            return get_divmod_asm()
        if intrinsic == "DROP":
            return get_drop_asm()
        if intrinsic == "DUP":
            return get_dup_asm()
        if intrinsic == "EQ":
            return get_eq_asm()
        if intrinsic == "GE":
            return get_ge_asm()
        if intrinsic == "GT":
            return get_gt_asm()
        if intrinsic == "INPUT":
            return get_input_asm(op)
        if intrinsic == "LE":
            return get_le_asm()
        if intrinsic == "LT":
            return get_lt_asm()
        if intrinsic == "LOAD_BOOL":
            return get_load_asm(TokenType.BOOL)
        if intrinsic == "LOAD_CHAR":
            return get_load_asm(TokenType.CHAR)
        if intrinsic == "LOAD_INT":
            return get_load_asm(TokenType.INT)
        if intrinsic == "LOAD_PTR":
            return get_load_asm(TokenType.PTR)
        if intrinsic == "LOAD_STR":
            return get_load_asm(TokenType.STR)
        if intrinsic == "LOAD_UINT8":
            return get_load_asm(TokenType.UINT8)
        if intrinsic == "MINUS":
            return get_minus_asm()
        if intrinsic == "MUL":
            return get_mul_asm()
        if intrinsic == "NE":
            return get_ne_asm()
        if intrinsic == "NTH":
            return get_nth_asm()
        if intrinsic == "OVER":
            return get_over_asm()
        if intrinsic == "PLUS":
            return get_plus_asm()
        if intrinsic == "PRINT":
            return get_print_asm()
        if intrinsic == "PUTS":
            return get_puts_asm()
        if intrinsic == "ROT":
            return get_rot_asm()
        if intrinsic == "STORE_BOOL":
            return get_store_asm(TokenType.BOOL)
        if intrinsic == "STORE_CHAR":
            return get_store_asm(TokenType.CHAR)
        if intrinsic == "STORE_INT":
            return get_store_asm(TokenType.INT)
        if intrinsic == "STORE_PTR":
            return get_store_asm(TokenType.PTR)
        if intrinsic == "STORE_STR":
            return get_store_asm(TokenType.STR)
        if intrinsic == "STORE_UINT8":
            return get_store_asm(TokenType.UINT8)
        if intrinsic == "SWAP":
            return get_swap_asm()
        if intrinsic == "SWAP2":
            return get_swap2_asm()
        if intrinsic == "SYSCALL0":
            return get_syscall_asm(param_count=0)
        if intrinsic == "SYSCALL1":
            return get_syscall_asm(param_count=1)
        if intrinsic == "SYSCALL2":
            return get_syscall_asm(param_count=2)
        if intrinsic == "SYSCALL3":
            return get_syscall_asm(param_count=3)
        if intrinsic == "SYSCALL4":
            return get_syscall_asm(param_count=4)
        if intrinsic == "SYSCALL5":
            return get_syscall_asm(param_count=5)
        if intrinsic == "SYSCALL6":
            return get_syscall_asm(param_count=6)

        # Compiler error for Intrinsic not implemented
        compiler_error("NOT_IMPLEMENTED", f"Intrinsic '{intrinsic}' has not been implemented.", op.token)
    # Compiler error for Op not implemented
    compiler_error("NOT_IMPLEMENTED", f"Operand '{op.type.name}' has not been implemented.", op.token)

def get_op_comment_asm(op: Op, op_type: OpType) -> str:
    """Generate assembly comment for the Op. Return the comment string."""
    src_file: str   = op.token.location[0]
    row: int        = op.token.location[1]
    col: int        = op.token.location[2]
    op_name: str    = op_type.name
    if op_name == "INTRINSIC":
        op_name = f'{op_type.name} {op.token.value}'
    return get_token_info_comment_asm(op_name, src_file, row, col)

def get_token_info_comment_asm(name: str, file: str, row: int, col: int) -> str:
    """Return formatted informative string for the current Op"""
    return f';; -- {name} | File: {file}, Row: {row}, Col: {col}' + '\n'

def get_comparison_asm(cmov_operand: str) -> str:
    """
    Generate assembly code for different comparison Intrinsics, like EQ.
    Only cmov operand changes with different comparison intrinsics.
    Return the assembly code for certain comparison intrinsic.
    """
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
    """Return the assembly code for different arithmetic Intrinsics, like PLUS."""
    arithmetic_asm: str  =  '  pop rbx\n'
    arithmetic_asm      +=  '  pop rax\n'
    arithmetic_asm      += f'  {operand} rax, rbx\n'
    arithmetic_asm      +=  '  push rax\n'
    return arithmetic_asm

def add_string_variable_asm(assembly: str, string: str, op: Op, constants: List[Constant]) -> str:
    """Writes a new string variable to assembly file in the .rodata section."""
    assembly_lines: List[str] = assembly.split('\n')
    assembly = get_asm_file_start(constants)

    # Replace \n with nasm approved 10s for newline
    string = string.replace('\\n','",10,"')
    assembly += f'  s{op.id} db {string},0\n'

    # Rewrite lines except for the first line (section .rodata)
    len_asm_file_start: int = len(assembly.split('\n')) - 2
    for i in range(len_asm_file_start, len(assembly_lines)):
        assembly += f"{assembly_lines[i]}\n"
    return assembly

def add_input_buffer_asm(assembly: str, op: Op) -> str:
    """Writes a new input buffer variable to assembly file in the .rodata section."""
    assembly_lines: List[str] = assembly.split('\n')
    assembly = ''
    bss_index: int = 0
    for i, row in enumerate(assembly_lines):
        assembly += f"{row}\n"
        if row == "section .bss":
            bss_index = i
            break
    assembly += f'  buffer{op.id}: resb buffer_len\n'

    # Rewrite lines
    for i in range(bss_index, len(assembly_lines)):
        assembly += f"{assembly_lines[i]}\n"
    return assembly

def get_end_op_for_while(op: Op, program: Program) -> Op:
    """Returns the END Operand for the current WHILE Operand which closes the WHILE loop."""
    while_count: int = 0
    for i in range(op.id, len(program)):
        if program[i].type == OpType.DONE:
            while_count -= 1
            if while_count == 0:
                return program[i]
        if program[i].type == OpType.WHILE:
            while_count += 1
    compiler_error("AMBIGUOUS_BREAK", "WHILE loop does not have DONE.", op.token)

def get_parent_while(op: Op, program: Program) -> Op:
    """Returns the parent WHILE Operand for the current Operand."""
    done_count: int = 0
    for i in range(op.id - 1, -1, -1):
        if program[i].type == OpType.WHILE:
            if done_count == 0:
                return program[i]
            done_count -= 1
        if program[i].type == OpType.DONE:
            done_count += 1

    compiler_error(f"AMBIGUOUS_{op.token.value.upper()}", \
        f"{op.token.value.upper()} operand without parent WHILE.", op.token)

def get_do_asm(op: Op, program: Program) -> str:
    """DO is conditional jump to operand after ELIF, ELSE, END or ENDIF."""
    parent_op_type: OpType = get_parent_op_type_do(op, program)

    # Keeping the count of duplicate parent Ops allows for nested IF or WHILE blocks
    parent_op_count: int = 0
    op_asm: str = ''
    for i in range(op.id + 1, len(program)):
        op_type: OpType = program[i].type

        # Keep count on the nested IF's or WHILE's
        if (parent_op_type in [OpType.IF, OpType.ELIF] and op_type == OpType.IF) \
        or (parent_op_type == OpType.WHILE and op_type == OpType.WHILE):
            parent_op_count += 1
            continue

        if parent_op_count == 0 and \
            ( ( parent_op_type == OpType.IF and op_type in (OpType.ELIF, OpType.ELSE, OpType.ENDIF)) \
            or ( parent_op_type == OpType.ELIF and op_type in (OpType.ELIF, OpType.ELSE, OpType.ENDIF)) \
            or ( parent_op_type == OpType.WHILE and op_type == OpType.DONE ) ):
            jump_destination: str = program[i].type.name + str(i)
            op_asm = generate_do_asm(jump_destination)
            break

        # Decrement counter when passing another block's ENDIF / DONE
        if (parent_op_type in [OpType.IF, OpType.ELIF] and op_type == OpType.ENDIF) \
        or (parent_op_type == OpType.WHILE and op_type == OpType.DONE):
            parent_op_count -= 1

    if not op_asm:
        compiler_error("UNKNOWN_ERROR", "Unknown error occurred while generating assembly for DO keyword.", op.token)
    return op_asm

def get_parent_op_type_do(op: Op, program: Program) -> OpType:
    """Get the parent OpType for the current DO Operand like IF or WHILE"""
    parent_count: int = 0
    for i in range(op.id - 1, -1, -1):
        if program[i].type in (OpType.IF, OpType.ELIF, OpType.WHILE):
            if parent_count == 0:
                return program[i].type
            parent_count -= 1
        if program[i].type in (OpType.DONE, OpType.ENDIF):
            parent_count += 1
    compiler_error("AMBIGUOUS_DO", "DO operand without parent IF, ELIF or WHILE", op.token)

def get_break_asm(op: Op, program: Program) -> str:
    """BREAK is an unconditional jump to operand after current loop's END."""
    parent_while: Op = get_parent_while(op, program)
    parent_end:   Op = get_end_op_for_while(parent_while, program)
    return f'  jmp DONE{parent_end.id}\n'

def get_continue_asm(op: Op, program: Program) -> str:
    """CONTINUE is an unconditional jump to operand after current loop's WHILE."""
    parent_while: Op = get_parent_while(op, program)
    op_asm: str  = f'  jmp WHILE{parent_while.id}\n'
    op_asm      += f'DONE{op.id}:\n'
    return op_asm

def generate_do_asm(jump_destination: str) -> str:
    """DO removes two elements from the stack and checks if the first element is zero."""
    op_asm: str  =  '  pop rax\n'
    op_asm      +=  '  add rsp, 8\n'
    op_asm      +=  '  test rax, rax\n'
    op_asm      += f'  jz {jump_destination}\n'
    return op_asm

def get_done_asm(op: Op, program: Program) -> str:
    """DONE is an unconditional jump to current loop's WHILE."""
    parent_while: Op = get_parent_while(op, program)
    op_asm: str  = f'  jmp WHILE{parent_while.id}\n'
    op_asm      += f'DONE{op.id}:\n'
    return op_asm

def get_elif_asm(op: Op, program: Program) -> str:
    """ELIF is an unconditional jump to ENDIF and a keyword for DO to jump to."""
    op_asm: str = ''
    for i in range(op.id + 1, len(program)):
        if program[i].type == OpType.ENDIF:
            op_asm += f'  jmp ENDIF{i}\n'
            op_asm += f'ELIF{op.id}:\n'
            break
    return op_asm

def get_else_asm(op: Op, program: Program) -> str:
    """ELSE is an unconditional jump to ENDIF and a keyword for DO to jump to."""
    op_asm: str = ''
    for i in range(op.id + 1, len(program)):
        if program[i].type == OpType.ENDIF:
            op_asm += f'  jmp ENDIF{i}\n'
            op_asm += f'ELSE{op.id}:\n'
            break
    return op_asm

def get_endif_asm(op: Op) -> str:
    """ENDIF is a keyword for DO, ELIF or ELSE to jump to without additional functionality."""
    return f'ENDIF{op.id}:\n'

def get_push_bool_asm(boolean: str) -> str:
    """Return the assembly code for PUSH_BOOL Operand."""
    integer: int = 1 if boolean == 'TRUE' else 0
    op_asm: str  = f'  mov rax, {integer}\n'
    op_asm      +=  '  push rax\n'
    return op_asm

def get_push_char_asm(op: Op) -> str:
    """Return the assembly code for PUSH_CHAR Operand."""
    op_asm: str  = f'  mov rax, {ord(op.token.value[1])}\n'
    op_asm      +=  '  push rax\n'
    return op_asm

def get_push_int_asm(integer: str) -> str:
    """Return the assembly code for PUSH_INT Operand."""
    op_asm: str  = f'  mov rax, {integer}\n'
    op_asm      +=  '  push rax\n'
    return op_asm

def get_push_ptr_asm(memory_name: str) -> str:
    """Return the assembly code for PUSH_PTR Operand."""
    op_asm: str  = f'  mov rax, {memory_name}\n'
    op_asm      +=  '  push rax\n'
    return op_asm

def get_push_str_asm(op: Op) -> str:
    """Pushes a pointer to the string variable to the stack."""
    op_asm: str  = f'  mov rsi, s{op.id} ; Pointer to string\n'
    op_asm      +=  '  push rsi\n'
    return op_asm

def get_while_asm(op: Op) -> str:
    """
    WHILE is a keyword for DONE to jump to.
    Return the assembly code for WHILE Operand.
    """
    return f'WHILE{op.id}:\n'

def get_argc_asm() -> str:
    """ARGC pushes the argument count to the stack."""
    op_asm: str  = '  mov rax, [args_ptr]\n'
    op_asm      += '  mov rax, [rax]\n'
    op_asm      += '  push rax\n'
    return op_asm

def get_argv_asm() -> str:
    """ARGV pushes the pointer to argument array to the stack."""
    op_asm: str  = '  mov rax, [args_ptr]\n'
    op_asm      += '  add rax, 8\n'
    op_asm      += '  push rax\n'
    return op_asm

def get_divmod_asm() -> str:
    """DIVMOD pops two integers from the stack and pushes their remainder and quotient."""
    op_asm: str  = '  xor edx, edx ; Do not use floating point arithmetic\n'
    op_asm      += '  pop rbx\n'
    op_asm      += '  pop rax\n'
    op_asm      += '  div rbx\n'
    op_asm      += '  push rdx ; Remainder\n'
    op_asm      += '  push rax ; Quotient\n'
    return op_asm

def get_drop_asm(count: int = 1) -> str:
    """DROP removes one element from the stack."""
    return f'  add rsp, {8*count}\n'

def get_dup_asm() -> str:
    """
    DUP duplicates the top element in the stack.
    Example with the stack's top element being the rightmost: a -> a a
    """
    op_asm: str  = '  pop rax\n'
    op_asm      += '  push rax\n'
    op_asm      += '  push rax\n'
    return op_asm

def get_eq_asm() -> str:
    """
    EQ takes two elements from the stack and checks if they are equal.
    It pushes the second element to the stack and a boolean value of the comparison.
    """
    return get_comparison_asm("cmove")

def get_ge_asm() -> str:
    """
    GE takes two elements from the stack and checks if the top element >= the other.
    It pushes the second element back to the stack and a boolean value of the comparison.
    """
    return get_comparison_asm("cmovge")

# Copies Nth element from the stack to the top of the stack
def get_nth_asm() -> str:
    """
    NTH pops one integer from the stack and pushes the Nth element from stack back to stack.
    Note that the Nth is counted without the popped integer.
    Example: 30 20 10 3 NTH print  // Output: 30 (because 30 is 3rd element without the popped 3).
    """
    op_asm: str  = '  pop rax\n'
    op_asm      += '  sub rax, 1\n'
    op_asm      += '  mov rbx, 8\n'
    op_asm      += '  mul rbx\n'
    op_asm      += '  add rsp, rax ; Stack pointer to the Nth element\n'
    op_asm      += '  pop rbx      ; Get Nth element to rax\n'
    op_asm      += '  add rax, 8\n'
    op_asm      += '  sub rsp, rax ; Return stack pointer\n'
    op_asm      += '  push rbx\n'
    return op_asm

def get_gt_asm() -> str:
    """
    GT takes two elements from the stack and checks if the top element > the other.
    It pushes the second element back to the stack and a boolean value of the comparison.
    """
    return get_comparison_asm("cmovg")

def get_input_asm(op: Op) -> str:
    """INPUT reads from stdin to buffer and pushes the pointer to the buffer."""
    op_asm: str  =  '  mov rax, 0   ; write\n'
    op_asm      +=  '  mov rdi, 1   ; stdin\n'
    op_asm      += f'  mov rsi, buffer{op.id}\n'
    op_asm      +=  '  mov rdx, 65535\n'
    op_asm      +=  '  syscall\n'
    op_asm      +=  '  xor rdx, rdx\n'
    op_asm      += f'  mov [buffer{op.id}+rax-1], dl  ; Change newline character to NULL\n'
    op_asm      += f'  push buffer{op.id}\n'
    return op_asm

def get_le_asm() -> str:
    """
    LE takes two elements from the stack and checks if the top element <= the other.
    It pushes the second element back to the stack and a boolean value of the comparison.
    """
    return get_comparison_asm("cmovle")

def get_lt_asm() -> str:
    """
    LT takes two elements from the stack and checks if the top element < the other.
    It pushes the second element back to the stack and a boolean value of the comparison.
    """
    return get_comparison_asm("cmovl")

def get_load_asm(token_type: TokenType) -> str:
    """
    LOAD variants load certain size value from where a pointer is pointing to.
    It takes one pointer from the stack and pushes back the dereferenced pointer value.
    Different LOAD variants: LOAD_BOOL, LOAD_CHAR, LOAD_INT, LOAD_PTR, LOAD_STR, LOAD_UINT8.
    """
    type_register_sizes: Dict[TokenType, str] = {
        TokenType.BOOL  : 'bl',
        TokenType.CHAR  : 'bl',
        TokenType.INT   : 'rbx',
        TokenType.PTR   : 'rbx',
        TokenType.STR   : 'rbx',
        TokenType.UINT8 : 'bl'
    }
    register: str = type_register_sizes[token_type]
    op_asm: str  =  '  pop rax\n'
    op_asm      +=  '  xor rbx, rbx\n'
    op_asm      += f'  mov {register}, [rax]\n'
    op_asm      +=  '  push rbx\n'
    return op_asm

def get_minus_asm() -> str:
    """Pop two integers from the stack and decrement the second value from the top one."""
    return get_arithmetic_asm("sub")

def get_mul_asm() -> str:
    """Pop two integers from the stack and push the product of the two values."""
    op_asm: str  = '  pop rax\n'
    op_asm      += '  pop rbx\n'
    op_asm      += '  mul rbx\n'
    op_asm      += '  push rax  ; Product\n'
    return op_asm

def get_ne_asm() -> str:
    """
    NE takes two elements from the stack and checks if the values are not equal.
    It pushes the second element back to the stack and a boolean value of the comparison.
    """
    return get_comparison_asm("cmovne")

def get_over_asm() -> str:
    """
    OVER Intrinsic pushes a copy of the element one behind the top element of the stack.
    Example with the stack's top element being the rightmost: a b -> a b a
    """
    op_asm: str  = '  pop rax\n'
    op_asm      += '  pop rbx\n'
    op_asm      += '  push rbx\n'
    op_asm      += '  push rax\n'
    op_asm      += '  push rbx\n'
    return op_asm

def get_plus_asm() -> str:
    """Pop two integers from the stack and push the sum of the two values."""
    return get_arithmetic_asm("add")

def get_print_asm() -> str:
    """Pop an integer from the stack and print the value of it to the stdout."""
    op_asm: str  =  '  pop rdi\n'
    op_asm      +=  '  call print\n'
    return op_asm

# https://localcoder.org/how-to-print-a-string-to-the-terminal-in-x86-64-assembly-nasm-without-syscall
def get_puts_asm() -> str:
    """Pop a pointer from the stack and print the null-terminated buffer to stdout."""
    op_asm: str  =  '  pop r9\n'
    op_asm      +=  '  mov rdi, r9      ; pointer to string\n'
    op_asm      +=  '  xor rcx, rcx     ; zero rcx\n'
    op_asm      +=  '  not rcx          ; set rcx = -1\n'
    op_asm      +=  '  xor al, al       ; zero the al register (initialize to NUL)\n'
    op_asm      +=  '  cld              ; clear the direction flag\n'
    op_asm      +=  '  repnz scasb      ; get the string length (dec rcx through NUL)\n'
    op_asm      +=  '  not rcx          ; rev all bits of negative results in absolute value\n'
    op_asm      +=  '  dec rcx          ; -1 to skip the null-terminator, rcx contains length\n'
    op_asm      +=  '  mov rdx, rcx     ; put length in rdx\n'
    op_asm      +=  '  mov rsi, r9\n'
    op_asm      +=  '  mov rax, 1       ; stdout\n'
    op_asm      +=  '  mov rdi, rax     ; write syscall\n'
    op_asm      +=  '  syscall\n'
    return op_asm

def get_rot_asm() -> str:
    """
    ROT Intrinsic rotates the top three elements of the stack so that the third becomes first.
    Example with the stack's top element being the rightmost: a b c -> b c a
    """
    op_asm: str  = '  pop rax\n'
    op_asm      += '  pop rbx\n'
    op_asm      += '  pop rcx\n'
    op_asm      += '  push rbx\n'
    op_asm      += '  push rax\n'
    op_asm      += '  push rcx\n'
    return op_asm

def get_store_asm(token_type: TokenType) -> str:
    """
    STORE variants store certain size value from where a pointer is pointing to.
    It takes a pointer and a value from the stack and loads the value to the pointer address.
    Different STORE variants: STORE_BOOL, STORE_CHAR, STORE_INT, STORE_PTR, STORE_STR, STORE_UINT8.
    """
    type_register_sizes: Dict[TokenType, str] = {
        TokenType.BOOL : 'bl',
        TokenType.CHAR : 'bl',
        TokenType.INT  : 'rbx',
        TokenType.PTR  : 'rbx',
        TokenType.STR  : 'rbx',
        TokenType.UINT8 : 'bl'
    }
    register: str = type_register_sizes[token_type]
    op_asm: str  =  '  pop rax\n'
    op_asm      +=  '  pop rbx\n'
    op_asm      += f'  mov [rax], {register}\n'
    return op_asm

def get_swap_asm() -> str:
    """
    SWAP Intrinsic swaps two top elements in the stack.
    Example with the stack's top element being the rightmost: a b -> b a
    """
    op_asm: str  = '  pop rax\n'
    op_asm      += '  pop rbx\n'
    op_asm      += '  push rax\n'
    op_asm      += '  push rbx\n'
    return op_asm

def get_swap2_asm() -> str:
    """
    SWAP2 Intrinsic swaps the two pairs of two top elements in the stack.
    Example with the stack's top element being the rightmost: a b c d -> c d a b
    """
    op_asm: str  = '  pop rax\n'
    op_asm      += '  pop rbx\n'
    op_asm      += '  pop rcx\n'
    op_asm      += '  pop rdx\n'
    op_asm      += '  push rbx\n'
    op_asm      += '  push rax\n'
    op_asm      += '  push rdx\n'
    op_asm      += '  push rcx\n'
    return op_asm

def get_syscall_asm(param_count: int) -> str:
    """
    SYSCALL intrinsic variants call a Linux syscall.
    Syscalls require different amount of arguments from 0 to 6.
    Different variants are named SYSCALL0 - SYSCALL6 by the amount of arguments.
    The different syscall constants required for RAX register can be found from lib/sys.torth.
    Naming convention (case sensitive): SYS_<syscall> - Example: SYS_write

    https://chromium.googlesource.com/chromiumos/docs/+/master/constants/syscalls.md#tables
    """
    op_asm: str  = "  pop rax ; syscall\n"

    # Pop arguments to syscall argument registers
    argument_registers: List[str] = ['rdi', 'rsi', 'rdx', 'r10', 'r8', 'r9']
    for i in range(param_count):
        op_asm += f"  pop {argument_registers[i]} ; {i+1}. arg\n"

    # Call the syscall and push return code to RAX
    op_asm      += "  syscall\n"
    op_asm      += "  push rax ; return code\n"
    return op_asm

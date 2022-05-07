import subprocess
from typing import List
from compiler.defs import Intrinsic, Op, OpType, Program, STACK, TokenType, Token
from compiler.utils import compiler_error

def intrinsic_exists(token: str) -> bool:
    return bool(hasattr(Intrinsic, token))

def generate_program(tokens = List[Token]) -> Program:
    program: List[Op] = []
    for id, token in enumerate(tokens):
        token_value: str = token.value.upper()
        if token.type == TokenType.ARRAY:
            op_type = OpType.PUSH_ARRAY
        elif token.type == TokenType.BOOL:
            op_type = OpType.PUSH_INT
        elif token.type == TokenType.CSTR:
            op_type = OpType.PUSH_CSTR
        elif token.type == TokenType.INT:
            op_type = OpType.PUSH_INT
        elif token.type == TokenType.STR:
            op_type = OpType.PUSH_STR
        elif token_value == 'BREAK':
            op_type = OpType.BREAK
        elif token_value == 'DO':
            op_type = OpType.DO
        elif token_value == 'END':
            op_type = OpType.END
        elif token_value == 'ENDIF':
            op_type = OpType.ENDIF
        elif token_value == 'IF':
            op_type = OpType.IF
        elif token_value == 'ELIF':
            op_type = OpType.ELIF
        elif token_value == 'ELSE':
            op_type = OpType.ELSE
        elif token_value == 'WHILE':
            op_type = OpType.WHILE
        elif intrinsic_exists(token_value):
            op_type = OpType.INTRINSIC
        else:
            raise AttributeError (f"Operation '{token.value}' is not found")

        operand: Op = Op(id, op_type, token)
        program.append(operand)
    return program

def run_code(exe_file: str) -> None:
    subprocess.run([f'./{exe_file}'])

# Type check all operations which
def type_check_program(program: Program) -> None:
    global STACK
    NOT_TYPED_TOKENS: List[Token] = [ 'BREAK', 'ELSE', 'END', 'ENDIF', 'EXIT', 'PRINT_INT' ]
    for op in program:
        token: Token = op.token
        if token.value.upper() in NOT_TYPED_TOKENS:
            continue
        elif op.type == OpType.DO:
            return type_check_do(op)
        elif op.type == OpType.ELIF:
            return type_check_elif(op)
        elif op.type == OpType.ELSE:
            continue #return type_check_else(op, program)
        elif op.type == OpType.END:
            continue #return type_check_end(op, program)
        elif op.type == OpType.ENDIF:
            continue #return type_check_endif(op)
        elif op.type == OpType.IF:
            continue #return type_check_if(op)
        elif op.type == OpType.PUSH_ARRAY:
            continue #return type_check_push_array(op)
        elif op.type == OpType.PUSH_CSTR:
            continue #return type_check_push_cstr(op)
        elif op.type == OpType.PUSH_INT:
            continue #return type_check_push_int(token)
        elif op.type == OpType.PUSH_STR:
            continue #return type_check_push_str(op)
        elif op.type == OpType.WHILE:
            continue #return type_check_while(op)
        elif op.type == OpType.INTRINSIC:
            intrinsic: str = token.value.upper()
            if intrinsic == "AND":
                continue #return type_check_and(op)
            elif intrinsic == "DIV":
                continue #return type_check_div(op)
            elif intrinsic == "DIVMOD":
                continue #return type_check_divmod(op)
            elif intrinsic == "DROP":
                continue #return type_check_drop(op)
            elif intrinsic == "DUP":
                continue #return type_check_dup(op)
            elif intrinsic == "DUP2":
                continue #return type_check_dup2(op)
            elif intrinsic == "ENVP":
                continue #return type_check_envp()
            elif intrinsic == "EXIT":
                continue #return type_check_exit()
            elif intrinsic == "EQ":
                continue #return type_check_eq(op)
            elif intrinsic == "GE":
                continue #return type_check_ge(op)
            elif intrinsic == "GET_NTH":
                continue #return type_check_nth(op)
            elif intrinsic == "GT":
                continue #return type_check_gt(op)
            elif intrinsic == "INPUT":
                continue #return type_check_input(op)
            elif intrinsic == "LE":
                continue #return type_check_le(op)
            elif intrinsic == "LT":
                continue #return type_check_lt(op)
            elif intrinsic == "MINUS":
                continue #return type_check_minus(op)
            elif intrinsic == "MOD":
                continue #return type_check_mod(op)
            elif intrinsic == "MUL":
                continue #return type_check_mul(op)
            elif intrinsic == "NE":
                continue #return type_check_ne(op)
            elif intrinsic == "OVER":
                continue #return type_check_over(op)
            elif intrinsic == "PLUS":
                continue #return type_check_plus(op)
            elif intrinsic == "POW":
                continue #return type_check_pow(op)
            # TODO: Merge PRINT and PRINT_INT
            elif intrinsic == "PRINT":
                continue #return type_check_string_output(op, intrinsic)
            elif intrinsic == "PRINT_INT":
                continue #return type_check_print_int()
            elif intrinsic == "PUTS":
                continue #return type_check_string_output(op, intrinsic)
            elif intrinsic == "ROT":
                continue #return type_check_rot(op)
            elif intrinsic == "SWAP":
                continue #return type_check_swap(op)
            elif intrinsic == "SWAP2":
                continue #return type_check_swap2(op)
            elif intrinsic == "SYSCALL0":
                continue #return type_check_syscall(op, param_count=0)
            elif intrinsic == "SYSCALL1":
                continue #return type_check_syscall(op, param_count=1)
            elif intrinsic == "SYSCALL2":
                continue #return type_check_syscall(op, param_count=2)
            elif intrinsic == "SYSCALL3":
                continue #return type_check_syscall(op, param_count=3)
            elif intrinsic == "SYSCALL4":
                continue #return type_check_syscall(op, param_count=4)
            elif intrinsic == "SYSCALL5":
                continue #return type_check_syscall(op, param_count=5)
            elif intrinsic == "SYSCALL6":
                continue #return type_check_syscall(op, param_count=6)
            else:
                compiler_error(op, "NOT_IMPLEMENTED", f"Type checking for {intrinsic} has not been implemented.")
        else:
            compiler_error(op, "NOT_IMPLEMENTED", f"Type checking for {op.type.name} has not been implemented.")
    raise NotImplementedError("Type checking is not implemented yet.")

def type_check_do(op: Op) -> str:
    try:
        STACK.pop()
        STACK.pop()
    except IndexError:
        compiler_error(op, "POP_FROM_EMPTY_STACK", "Not enough values in the stack.")

# ELIF is like DUP, it duplicates the first element in the stack
def type_check_elif(op: Op) -> str:
    try:
        top: str = STACK.pop()
    except IndexError:
        compiler_error(op, "POP_FROM_EMPTY_STACK", "Cannot duplicate value from empty stack.")
    STACK.append(top)
    STACK.append(top)

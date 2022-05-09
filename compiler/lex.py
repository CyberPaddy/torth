import itertools
import os
import re
from typing import List
from compiler.defs import Function, Keyword, Location, Signature, Token, TokenType, TOKEN_REGEXES

def get_tokens_from_code(code: str, file: str) -> List[Token]:
    token_matches: List[re.Match[str]] = get_token_matches(code)
    # Newlines are used to determine when a comment ends and when new line starts
    newline_indexes: List[int] = [nl.start() for nl in re.finditer('\n', code)]

    functions: List[Function] = get_functions(file, token_matches, newline_indexes)
    print(functions)
    tokens: List[Token] = []
    for match in token_matches:
        token = get_token_from_match(match, os.path.basename(file), newline_indexes)
        tokens.append(token)

    return tokens

def get_functions(file: str, token_matches: List[re.Match[str]], newline_indexes: List[int]) -> Signature:
    functions: List[Function]       = []
    current_part: int               = 0
    name: str                       = ''
    param_types: List[str]          = []
    return_types: List[str]         = []
    tokens: List[Token]             = []

    function_parts: List[int] = list(range(5)) # Not in function, name, param types, return types, location
    function_part: itertools.cycle = itertools.cycle(function_parts)
    next(function_part)

    for match in token_matches:
        token_value: str = match.group(0)
        if token_value.upper() in {'FUNCTION', '--', '->', ':', 'END'}:
            current_part = next(function_part)
            if token_value.upper() == 'END':
                signature: Signature = Signature( (param_types, return_types) )
                functions.append( Function(name, signature, tokens) )
                # Empty variable names
                name            = ''
                param_types     = []
                return_types    = []
                tokens          = []
        elif current_part == 1:
            name = token_value
        elif current_part == 2:
            param_types.append(token_value.upper())
        elif current_part == 3:
            return_types.append(token_value.upper())
        elif current_part == 4:
            token: Token = get_token_from_match(match, file, newline_indexes)
            tokens.append(token)

    return functions

# Returns all tokens with comments taken out
def get_token_matches(code: str) -> List[re.Match[str]]:
    TOKEN_REGEX: re.Pattern[str] = re.compile(r'''\[.*\]|".*?"|'.*?'|\S+''')

    matches: List[re.Match[str]]            = list(re.finditer(TOKEN_REGEX, code))
    code_without_comments: str              = re.sub(r'\s*\/\/.*', '', code)
    final_code_matches: List[re.Match[str]] = list(re.finditer(TOKEN_REGEX, code_without_comments))

    # Take comments and macros out of matches
    i: int = 0
    while i < len(matches):
        match: str = matches[i].group(0)

        # If i >= size of matches_without_comments list then the rest is comments
        if i >= len(final_code_matches) or match != final_code_matches[i].group(0):
            matches.pop(i)
            i -= 1
        i += 1
    return matches

# Constructs and returns a Token object from a regex match
def get_token_from_match(match: re.Match[str], file: str, newline_indexes: List[int]) -> Token:
    token_value: str        = get_token_value(match.group(0))
    token_type: TokenType   = get_token_type(token_value)
    token_location          = get_token_location(file, match.start(), newline_indexes)
    return Token(token_value, token_type, token_location)

# Returns the Intrinsic class value from token
def get_token_value(token: str) -> str:
    if token == '%':
        return 'MOD'
    if token == '/':
        return 'DIV'
    if token == '==':
        return 'EQ'
    if token == '>=':
        return 'GE'
    if token == '>':
        return 'GT'
    if token == '<=':
        return 'LE'
    if token == '<':
        return 'LT'
    if token == '-':
        return 'MINUS'
    if token == '*':
        return 'MUL'
    if token == '!=':
        return 'NE'
    if token == '+':
        return 'PLUS'
    if token == '^':
        return 'POW'
    if token == '.':
        return 'PRINT_INT'
    if token.upper() == 'TRUE':
        return '1'
    if token.upper() == 'FALSE':
        return '0'
    return token

def get_token_type(token_text: str) -> TokenType:
    keywords: List[str] = ['BREAK', 'DO', 'DONE', 'ELIF', 'ELSE', 'END', 'ENDIF', 'IF', 'MACRO', 'WHILE']
    # Check if all keywords are taken into account
    assert len(Keyword) == len(keywords) , f"Wrong number of keywords in get_token_type function! Expected {len(Keyword)}, got {len(keywords)}"

    # Keywords are case insensitive
    if token_text.upper() in keywords:
        return TokenType.KEYWORD
    if re.search(r'ARRAY\(.+\)', token_text.upper()):
        return TokenType.ARRAY
    if token_text.upper() in {'TRUE', 'FALSE'}:
        return TokenType.BOOL
    if token_text[0] == token_text[-1] == '"':
        return TokenType.STR
    if token_text[0] == token_text[-1] == "'":
        return TokenType.CSTR
    try:
        _integer = int(token_text)
        return TokenType.INT
    except ValueError:
        return TokenType.WORD

# Returns tuple containing the row and the column where the token was found
def get_token_location(filename: str, position: int, newline_indexes: List[int]) -> Location:
    col: int = position
    row: int = 1
    for i in range(len(newline_indexes)):
        if i > 0:
            col = position - newline_indexes[i-1] - 1
            row +=1
        if newline_indexes[i] > position:
            return (filename, row, col+1)

    if newline_indexes:
        row += 1
        col = position - newline_indexes[-1] - 1
    return (filename, row, col+1)

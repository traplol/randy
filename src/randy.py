import os
import sys
import inspect
import subprocess
import pathlib
import re
import time
from enum import Enum, auto
from types import MappingProxyType
from typing import List, Tuple, Optional, Union, Any
from dataclasses import dataclass


########################################################################################
#                                     LEXER
########################################################################################

class TK(Enum):
    Integer   = auto()
    String    = auto()
    Char      = auto()
    Ident     = auto()
    KW_proc   = auto()
    KW_do     = auto()
    KW_var    = auto()
    KW_in     = auto()
    KW_if     = auto()
    KW_else   = auto()
    KW_then   = auto()
    KW_end    = auto()
    KW_while  = auto()
    KW_done   = auto()
    KW_return = auto()
    KW_and    = auto()
    KW_or     = auto()
    KW_not    = auto()
    KW_u8r    = auto()
    KW_u16r   = auto()
    KW_u32r   = auto()
    KW_u64r   = auto()
    KW_u8w    = auto()
    KW_u16w   = auto()
    KW_u32w   = auto()
    KW_u64w   = auto()
    KW_const  = auto()
    KW_extern = auto()
    KW_asm    = auto()
    Plus      = auto()
    Minus     = auto()
    Star      = auto()
    Slash     = auto()
    Percent   = auto()
    Semicolon = auto()
    Less      = auto()
    LessEq    = auto()
    Greater   = auto()
    GreaterEq = auto()
    Assign    = auto()
    EqEq      = auto()
    NotEq     = auto()
    Tilde     = auto()
    Comma     = auto()
    LParen    = auto()
    RParen    = auto()
    Bar       = auto()
    Amper     = auto()
    Caret     = auto()
    Ellipsis  = auto()
    

class Token:
    def __init__(self, kind: TK, value, src_loc: Tuple[str, int, int]):
        self.kind = kind
        self.value = value
        self.src_loc = src_loc

    def fmt_src_loc(self) -> str:
        return f"  File \"{self.src_loc[0]}\", line {self.src_loc[1]}" #:{self.src_loc[2]}"

    def __repr__(self):
        return f"Token({repr(self.kind)}, {repr(self.value)}, {repr(self.fmt_src_loc())})"

    def __str__(self):
        return f"{self.value}"

class TokenStream:
    def __init__(self, tokens: List[Token]):
        self._tokens = tokens
        self._idx = 0

    def peek(self) -> Token:
        return self._tokens[self._idx]

    def peekks(self, kind_sequence: List[TK]) -> bool:
        if self._idx + len(kind_sequence) >= len(self._tokens):
            return False

        for i in range(len(kind_sequence)):
            if self._tokens[self._idx+i].kind != kind_sequence[i]:
                return False
        return True

    def peekk(self, kind: TK) -> bool:
        if self._idx >= len(self._tokens):
            return False
        return self._tokens[self._idx].kind == kind

    def peekk_one_of(self, kinds: List[TK]) -> bool:
        if self._idx >= len(self._tokens):
            return False
        return self._tokens[self._idx].kind in kinds

    def next(self) -> Token:
        tmp = self.peek()
        self._idx += 1
        return tmp

    def accept(self, kind: TK) -> Optional[Token]:
        tmp = self.peek()
        if tmp is not None and tmp.kind == kind:
            self._idx += 1
            return tmp
        return None

    def expect(self, kind: TK):
        tmp = self.peek()
        if tmp is not None and tmp.kind != kind:
            print(f"ERROR: Expected token kind {kind}, got {tmp.kind}")
            print(tmp.fmt_src_loc())
            exit(1)
        elif tmp is None:
            print(f"ERROR: Expected token but got None")
            exit(1)
        self._idx += 1
        return tmp

    def expect_one_of(self, kinds: List[TK]) -> Optional[Token]:
        tmp = self.peek()
        if tmp is not None and tmp.kind not in kinds:
            print(f"ERROR: Expected token kind to be one of {kinds}, got {tmp.kind}")
            print(tmp.fmt_src_loc())
            exit(1)
        elif tmp is None:
            print(f"ERROR: Expected token but got None")
            exit(1)
        self._idx += 1
        return tmp
            

    def empty(self) -> bool:
        return self._idx >= len(self._tokens)

def digit(c) -> bool:
    return c in "0123456789"

def whitespace(c) -> bool:
    return c in [" ", "\t", "\r", "\n"]

def ident_start(c) -> bool:
    x = ord(c)
    return c == "_" or (ord("a") <= x <= ord("z")) or (ord("A") <= x <= ord("Z"))

def ident_char(c) -> bool:
    return ident_start(c) or digit(c) or c == "@" or c == "!"

def get_escaped_char(c) -> str:
    if c == "n":
        return "\n"
    elif c == "t":
        return "\t"
    elif c == "0":
        return "\0"
    return c


keywords : dict[str, TK] = {
    "proc": TK.KW_proc,
    "do" : TK.KW_do,
    "var" : TK.KW_var,
    "in" : TK.KW_in,
    "if" : TK.KW_if,
    "else" : TK.KW_else,
    "then" : TK.KW_then,
    "end" : TK.KW_end,
    "while" : TK.KW_while,
    "done" : TK.KW_done,
    "return" : TK.KW_return,
    "and": TK.KW_and,
    "or": TK.KW_or,
    "not": TK.KW_not,
    "u8@": TK.KW_u8r,
    "u16@": TK.KW_u16r,
    "u32@": TK.KW_u32r,
    "u64@": TK.KW_u64r,
    "u8!": TK.KW_u8w,
    "u16!": TK.KW_u16w,
    "u32!": TK.KW_u32w,
    "u64!": TK.KW_u64w,
    #"syscall": TK.KW_syscall,
    "const": TK.KW_const,
    "extern": TK.KW_extern,
    "asm": TK.KW_asm,
}
def ident_kind(tok: str) -> TK:
    if tok in keywords:
        return keywords[tok]
    return TK.Ident

def is_readable_file(filename: str) -> bool:
    if not os.path.isfile(filename):
        return False
    if not os.access(filename, os.R_OK):
        return False
    return True

include_paths : List[str] = []
already_included = set()
def directive_include(library: str, tokens: List[Token], src_loc: Tuple[str, int, int]):
    # search the include paths for "<library>.randy" and then lex that file
    # and inject those tokens into <tokens>
    libfile = None
    for path in reversed(include_paths):
        p = f"{path}/{library}.randy"
        if is_readable_file(p):
            libfile = p
            break

    if libfile is None:
        print(f"ERROR: `#include {library}`, file does not exist or is unreadable")
        filename, line_no, col_no = src_loc
        print(f" {filename}:{line_no}")
        exit(1)

    if libfile in already_included:
        return
    
    already_included.add(libfile) # stop circular includes
    libtoks = lex_file(libfile)
    for tok in libtoks:
        tokens.append(tok)

def run_directive(src_loc: Tuple[str, int, int], code: str, i: int, tokens: List[Token], directive: str):
    if directive == "#include":
        start = i
        while i < len(code) and code[i] != "\n":
            i += 1
        library = code[start:i].strip()
        directive_include(library, tokens, src_loc)
        return i
    else:
        assert False, f"compiler directive not supported yet: {directive}"

def lex(filename: str, code: str) -> List[Token]:
    tokens: List[Token] = []
    line_no = 1
    col_no = 0
    i = 0
    while i < len(code):
        while i < len(code) and whitespace(code[i]):
            if code[i] == "\n":
                line_no += 1
                col_no = 0
            else:
                col_no += 1
            i += 1

        if i > len(code):
            break

        if i+1 < len(code) and code[i] == "/" and code[i+1] == "/":
            while i < len(code) and code[i] != "\n":
                i += 1
            continue

        if i >= len(code):
            break
        c = code[i]
        if c == "#" or ident_start(c):
            is_directive = c == "#"
            chars = []
            chars.append(c)
            i += 1
            while i < len(code):
                c = code[i]
                if not ident_char(c):
                    break
                chars.append(c)
                i += 1
            tok = "".join(chars)
            if is_directive:
                i = run_directive((filename, line_no, col_no), code, i, tokens, tok)
            else:
                tokens.append(Token(ident_kind(tok), tok, (filename, line_no, col_no))) 
            col_no += len(tok)
            continue
        elif c == '"':
            i += 1
            chars = []
            while i < len(code):
                c = code[i]
                if c == "\\":
                    assert i+1 < len(code), f"Unexpected EOF in string L{line_no}:{col_no}"
                    col_no += 1
                    i += 1       # eat \
                    c = code[i]
                    col_no += 1
                    i += 1       # eat escaped
                    chars.append(get_escaped_char(c))
                elif c == '"':
                    i += 1
                    col_no += 1
                    break
                else:
                    chars.append(c)
                    i += 1
                    if c == "\n":
                        line_no += 1
                        col_no = 0
                    else:
                        col_no += 1
                assert i < len(code), f"Unexpected EOF in string L{line_no}:{col_no}"
            tokens.append(Token(TK.String, "".join(chars), (filename, line_no, col_no)))
            continue
        elif c == "'":
            i += 1
            char = None
            c = code[i]
            if c == "\\":
                assert i+1 < len(code), f"Unexpected EOF in character L{line_no}:{col_no}"
                col_no += 1
                i += 1          # eat \
                c = code[i]
                col_no += 1
                i += 1          # eat escaped
                char = get_escaped_char(c)
                assert i < len(code), f"Unexpected EOF in character L{line_no}:{col_no}"
                assert code[i] == "'", f"Expected close ' for character L{line_no}:{col_no} -- {repr(code[i])}"
                i += 1
                col_no += 1
            else:
                char = c
                i += 1
                col_no += 1
                assert i < len(code), f"Unexpected EOF in character L{line_no}:{col_no}"
                assert code[i] == "'", f"Expected close ' for character L{line_no}:{col_no} -- {repr(code[i])}"
                i += 1
                col_no += 1
            tokens.append(Token(TK.Char, char, (filename, line_no, col_no)))
            continue
        elif digit(c):
            chars = []
            chars.append(c)
            i += 1
            while i < len(code):
                c = code[i]
                if not digit(c):
                    break
                chars.append(c)
                i += 1
            tok = "".join(chars)
            tokens.append(Token(TK.Integer, int(tok), (filename, line_no, col_no))) 
            col_no += len(tok)
            continue
            assert False, f"Integer parsing NYI L{line_no}:{col_no}"
        elif c == ";":
            tokens.append(Token(TK.Semicolon, ";", (filename, line_no, col_no)))
            i += 1
            col_no += 1
        elif c == ",":
            tokens.append(Token(TK.Comma, ",", (filename, line_no, col_no)))
            i += 1
            col_no += 1
        elif c == "(":
            tokens.append(Token(TK.LParen, "(", (filename, line_no, col_no)))
            i += 1
            col_no += 1
        elif c == ")":
            tokens.append(Token(TK.RParen, ")", (filename, line_no, col_no)))
            i += 1
            col_no += 1
        elif c == "+":
            tokens.append(Token(TK.Plus, "+", (filename, line_no, col_no)))
            i += 1
            col_no += 1
        elif c == "-":
            tokens.append(Token(TK.Minus, "-", (filename, line_no, col_no)))
            i += 1
            col_no += 1
        elif c == "*":
            tokens.append(Token(TK.Star, "*", (filename, line_no, col_no)))
            i += 1
            col_no += 1
        elif c == "/":
            tokens.append(Token(TK.Slash, "/", (filename, line_no, col_no)))
            i += 1
            col_no += 1
        elif c == "%":
            tokens.append(Token(TK.Percent, "%", (filename, line_no, col_no)))
            i += 1
            col_no += 1
        elif c == "|":
            tokens.append(Token(TK.Bar, "|", (filename, line_no, col_no)))
            i += 1
            col_no += 1
        elif c == "&":
            tokens.append(Token(TK.Amper, "&", (filename, line_no, col_no)))
            i += 1
            col_no += 1
        elif c == "^":
            tokens.append(Token(TK.Caret, "^", (filename, line_no, col_no)))
            i += 1
            col_no += 1
        elif c == "~":
            tokens.append(Token(TK.Tilde, "~", (filename, line_no, col_no)))
            i += 1
            col_no += 1
        elif c == ".":
            if code[i+1] == "." and code[i+2] == ".":
                token = Token(TK.Ellipsis, "...", (filename, line_no, col_no))
                tokens.append(token)
                i += 3
        elif c == "<":
            if code[i+1] == "=":
                token = Token(TK.LessEq, "<=", (filename, line_no, col_no))
            else:
                token = Token(TK.Less, "<", (filename, line_no, col_no))
            tokens.append(token)
            i += len(token.value)
            col_no += len(token.value)
        elif c == ">":
            if code[i+1] == "=":
                token = Token(TK.GreaterEq, ">=", (filename, line_no, col_no))
            else:
                token = Token(TK.Greater, ">", (filename, line_no, col_no))
            tokens.append(token)
            i += len(token.value)
            col_no += len(token.value)
        elif c == "=":
            if code[i+1] == "=":
                token = Token(TK.EqEq, "==", (filename, line_no, col_no))
            else:
                token = Token(TK.Assign, "=", (filename, line_no, col_no))
            tokens.append(token)
            i += len(token.value)
            col_no += len(token.value)
        elif c == "!":
            if code[i+1] == "=":
                token = Token(TK.NotEq, "!=", (filename, line_no, col_no))
            else:
                assert False, f"Cannot lex L{line_no}:{col_no}, {repr(c)} ({ord(c)}) yet"
            tokens.append(token)
            i += len(token.value)
            col_no += len(token.value)
        else:
            assert False, f"Cannot lex L{line_no}:{col_no}, {repr(c)} ({ord(c)}) yet"
    return tokens

def lex_file(path: str) -> List[Token]:
    with open(path, "r") as f:
        code = f.read()
    return lex(path, code)

class AstK(Enum):
    Ident     = auto()
    Integer   = auto()
    String    = auto()
    Call      = auto()
    BinOp     = auto()
    Return    = auto()
    VarDecl   = auto()
    VarAssign = auto()
    Assign    = auto()
    Procedure = auto()
    IfElse    = auto()
    While     = auto()
    PointerOp = auto()
    Prefix    = auto()
    Const     = auto()
    Extern    = auto()
    InlineAsm = auto()

class Ast:
    def __init__(self, kind: AstK, token: Token, **kwargs):
        self.kind: AstK = kind
        self.token: Token = token
        self.ident: Any = None
        self.value: Any = None
        self.args: Any = None
        self.expr: Any = None
        self.op: Any = None
        self.lhs: Any = None
        self.rhs: Any = None
        self.val_tok: Any = None
        self.name: Any = None
        self.params: Any = None
        self.body: Any = None
        self.test: Any = None
        self.consequence: Any = None
        self.alternative: Any = None
        self.size: Any = None
        self.varargs: Any = None
        self.asm: Any = None
        self.keys = []
        for k, v in kwargs.items():
            self.keys.append(k)
            setattr(self, k, v)

    def __repr__(self):
        return f"Ast of {self.kind} keys={self.keys}"

########################################################################################
#                                     PARSER
########################################################################################

def parse_primary(tokens: TokenStream) -> Optional[Ast]:
    if tokens.accept(TK.LParen):
        expr = parse_expression(tokens)
        tokens.expect(TK.RParen)
        return expr
    peek = tokens.peek()
    if tokens.peekk(TK.Ident):
        return Ast(AstK.Ident, peek, ident=tokens.next().value)
    if tokens.peekk(TK.Integer):
        return Ast(AstK.Integer, peek, value=tokens.next().value)
    if tokens.peekk(TK.Char):
        return Ast(AstK.Integer, peek, value=ord(tokens.next().value))
    if tokens.peekk(TK.String):
        return Ast(AstK.String, peek, value=tokens.next().value)
    if tokens.peekk_one_of([TK.KW_u8r, TK.KW_u16r, TK.KW_u32r, TK.KW_u64r]):
        return parse_pointer_op(tokens)
    return None

def parse_postfix(tokens: TokenStream) -> Optional[Ast]:
    peek = tokens.peek()
    expr = parse_primary(tokens)
    if expr is None:
        return None

    if not tokens.peekk(TK.LParen):
        return expr
    args = []
    tokens.accept(TK.LParen)
    while True:
        if tokens.peekk(TK.RParen):
            break
        arg = parse_expression(tokens)
        if arg is None:
            return None
        args.append(arg)
        if tokens.accept(TK.Comma):
            if tokens.peekk(TK.RParen):
                print(f"ERROR: Unexpected ')' after ','")
                print(tokens.peek().fmt_src_loc())
                exit(1)
    tokens.expect(TK.RParen)
    return Ast(AstK.Call, peek, expr=expr, args=args)

def parse_prefix(tokens: TokenStream) -> Optional[Ast]:
    postfix = parse_postfix(tokens)
    if postfix: return postfix

    if tokens.peekk_one_of([TK.Tilde, TK.KW_not]):
        tok = tokens.next()
        prefix = parse_prefix(tokens)
        return Ast(AstK.Prefix, tok, op=tok.kind, expr=prefix)
    return None
        

def parse_binary_multiplicative(tokens: TokenStream) -> Optional[Ast]:
    lhs = parse_prefix(tokens)
    if lhs is None:
        return None

    while tokens.peekk_one_of([TK.Star, TK.Slash, TK.Percent]):
        tok = tokens.next()
        rhs = parse_prefix(tokens)
        if rhs is None:
            return None
        lhs = Ast(AstK.BinOp, tok, lhs=lhs, op=tok.kind, rhs=rhs)
    return lhs

def parse_binary_additive(tokens: TokenStream) -> Optional[Ast]:
    lhs = parse_binary_multiplicative(tokens)
    if lhs is None:
        return None

    while tokens.peekk_one_of([TK.Plus, TK.Minus]):
        tok = tokens.next()
        rhs = parse_binary_multiplicative(tokens)
        if rhs is None:
            return None
        lhs = Ast(AstK.BinOp, tok, lhs=lhs, op=tok.kind, rhs=rhs)
    return lhs

def parse_binary_relational(tokens: TokenStream) -> Optional[Ast]:
    lhs = parse_binary_additive(tokens)
    if lhs is None:
        return None

    while tokens.peekk_one_of([TK.Less, TK.Greater, TK.LessEq, TK.GreaterEq]):
        tok = tokens.next()
        rhs = parse_binary_additive(tokens)
        if rhs is None:
            return None
        lhs = Ast(AstK.BinOp, tok, lhs=lhs, op=tok.kind, rhs=rhs)
    return lhs

def parse_binary_equality(tokens: TokenStream) -> Optional[Ast]:
    lhs = parse_binary_relational(tokens)
    if lhs is None:
        return None

    while tokens.peekk_one_of([TK.EqEq, TK.NotEq]):
        tok = tokens.next()
        rhs = parse_binary_relational(tokens)
        if rhs is None:
            return None
        lhs = Ast(AstK.BinOp, tok, lhs=lhs, op=tok.kind, rhs=rhs)
    return lhs

def parse_binary_land(tokens: TokenStream) -> Optional[Ast]:
    lhs = parse_binary_equality(tokens)
    if lhs is None:
        return None

    while tokens.peekk(TK.KW_and):
        tok = tokens.next()
        rhs = parse_binary_equality(tokens)
        if rhs is None:
            return None
        lhs = Ast(AstK.BinOp, tok, lhs=lhs, op=tok.kind, rhs=rhs)
    return lhs

def parse_binary_lor(tokens: TokenStream) -> Optional[Ast]:
    lhs = parse_binary_land(tokens)
    if lhs is None:
        return None

    while tokens.peekk(TK.KW_or):
        tok = tokens.next()
        rhs = parse_binary_land(tokens)
        if rhs is None:
            return None
        lhs = Ast(AstK.BinOp, tok, lhs=lhs, op=tok.kind, rhs=rhs)
    return lhs

def parse_expression(tokens: TokenStream) -> Optional[Ast]:
    return parse_binary_lor(tokens)

def parse_if_stmt(tokens: TokenStream) -> Optional[Ast]:
    peek = tokens.peek()
    test = parse_expression(tokens)
    if test is None:
        return None
    tokens.expect(TK.KW_then)
    conseq = parse_statements_until(tokens, [TK.KW_else, TK.KW_end])
    if tokens.accept(TK.KW_end):
        return Ast(AstK.IfElse, peek, test=test, consequence=conseq, alternative=[])
    tokens.expect(TK.KW_else)
    if tokens.peekk(TK.KW_if):
        peek = tokens.next()
        altern = [parse_if_stmt(tokens)]
        return Ast(AstK.IfElse, peek, test=test, consequence=conseq, alternative=altern)
    altern = parse_statements_until(tokens, [TK.KW_end])
    tokens.accept(TK.KW_end)
    return Ast(AstK.IfElse, peek, test=test, consequence=conseq, alternative=altern)

def parse_while_stmt(tokens: TokenStream) -> Optional[Ast]:
    peek = tokens.peek()
    test = parse_expression(tokens)
    if test is None:
        return None
    tokens.expect(TK.KW_do)
    body = parse_statements_until(tokens, [TK.KW_done])
    tokens.expect(TK.KW_done)
    return Ast(AstK.While, peek, test=test, body=body)

def parse_pointer_op(tokens: TokenStream) -> Optional[Ast]:
    peek = tokens.peek()
    if tokens.accept(TK.KW_u8w):
        size = 8
        op = "WRITE"
    elif tokens.accept(TK.KW_u16w):
        size = 16
        op = "WRITE"
    elif tokens.accept(TK.KW_u32w):
        size = 32
        op = "WRITE"
    elif tokens.accept(TK.KW_u64w):
        size = 64
        op = "WRITE"
    elif tokens.accept(TK.KW_u8r):
        size = 8
        op = "READ"
    elif tokens.accept(TK.KW_u16r):
        size = 16
        op = "READ"
    elif tokens.accept(TK.KW_u32r):
        size = 32
        op = "READ"
    elif tokens.accept(TK.KW_u64r):
        size = 64
        op = "READ"
    tokens.expect(TK.LParen)
    args = []
    while True:
        if tokens.peekk(TK.RParen):
            break
        arg = parse_expression(tokens)
        if arg is None:
            return None
        args.append(arg)
        if tokens.accept(TK.Comma):
            if tokens.peekk(TK.RParen):
                print(f"ERROR: Unexpected ')' after ','")
                print(tokens.peek().fmt_src_loc())
                exit(1)
    tokens.expect(TK.RParen)
    if op == "READ" and len(args) != 1:
        print(f"ERROR: Expected pointer read (u{size}@) to have exactly one argument")
        print(f"  got: {args}")
        print(tokens.peek().fmt_src_loc())
        exit(1)
    elif op == "WRITE" and len(args) != 2:
        print(f"ERROR: Expected pointer write (u{size}!) to have exactly two arguments")
        print(f"  got: {args}")
        print(tokens.peek().fmt_src_loc())
        exit(1)
        
    return Ast(AstK.PointerOp, peek, size=size, op=op, args=args)

def parse_statement(tokens: TokenStream) -> Optional[Ast]:
    peek = tokens.peek()
    if tokens.accept(TK.KW_var):
        ident = tokens.expect(TK.Ident)
        if tokens.accept(TK.Semicolon):
            return Ast(AstK.VarDecl, peek, ident=ident)
        tokens.expect(TK.Assign)
        expr = parse_expression(tokens)
        if expr is None:
            return None
        tokens.expect(TK.Semicolon)
        return Ast(AstK.VarAssign, peek, ident=ident, expr=expr)
    if tokens.accept(TK.KW_if):
        return parse_if_stmt(tokens)
    if tokens.accept(TK.KW_while):
        return parse_while_stmt(tokens)
    if tokens.accept(TK.KW_return):
        if tokens.accept(TK.Semicolon):
            return Ast(AstK.Return, peek, expr=None)
        expr = parse_expression(tokens)
        tokens.expect(TK.Semicolon)
        return Ast(AstK.Return, peek, expr=expr)
    if tokens.peekks([TK.Ident, TK.Assign]):
        ident = tokens.expect(TK.Ident)
        tokens.expect(TK.Assign)
        expr = parse_expression(tokens)
        tokens.expect(TK.Semicolon)
        return Ast(AstK.Assign, peek, ident=ident, expr=expr)
    if tokens.peekk_one_of([TK.KW_u8w, TK.KW_u16w, TK.KW_u32w,  TK.KW_u64w]):
        stmt = parse_pointer_op(tokens)
        tokens.expect(TK.Semicolon)
        return stmt
    expr = parse_expression(tokens)
    if expr is not None:
        tokens.expect(TK.Semicolon)
    return expr

def parse_statements_until(tokens: TokenStream, kinds: List[TK]) -> List[Optional[Ast]]:
    stmts: List[Optional[Ast]] = []
    if tokens.peekk_one_of(kinds):
        return stmts
    stmt = parse_statement(tokens)
    while stmt:
        stmts.append(stmt)
        if tokens.peekk_one_of(kinds):
            break
        stmt = parse_statement(tokens)
    return stmts

def parse_proc(tokens: TokenStream) -> Optional[Ast]:
    ident = tokens.expect(TK.Ident)
    params = []
    body = []
    while tokens.peekk(TK.Ident):
        params.append(tokens.expect(TK.Ident))
        if tokens.peekk(TK.KW_in):
            break
        tokens.expect(TK.Comma)
    tokens.expect(TK.KW_in)

    body = parse_statements_until(tokens, [TK.KW_end])

    if tokens.expect(TK.KW_end):
        return Ast(AstK.Procedure, ident, name=ident, params=params, body=body)
    return None

def parse_const(tokens: TokenStream) -> Optional[Ast]:
    ident = tokens.expect(TK.Ident)
    tokens.expect(TK.Assign)
    value = tokens.expect_one_of([TK.Ident, TK.Integer, TK.String, TK.Char])
    return Ast(AstK.Const, ident, ident=ident, val_tok=value)

def parse_extern(tokens: TokenStream) -> Optional[Ast]:
    ident = tokens.expect(TK.Ident)
    params = []
    varargs = False
    while tokens.peekk(TK.Ident):
        params.append(tokens.expect(TK.Ident))
        if tokens.peekk(TK.Semicolon):
            break
        tokens.expect(TK.Comma)
    if tokens.peekk(TK.Ellipsis):
        tokens.next()
        varargs = True
    return Ast(AstK.Extern, ident, ident=ident, params=params, varargs=varargs)

def parse_asm(tokens: TokenStream) -> Optional[Ast]:
    ident = tokens.expect(TK.Ident)
    tokens.expect(TK.KW_in)
    asmcode = tokens.expect(TK.String)
    tokens.expect(TK.KW_end)
    return Ast(AstK.InlineAsm, ident, name=ident, asm=asmcode)

def parse(tokens: TokenStream) -> List[Ast]:
    roots: List[Ast] = []
    while not tokens.empty():
        if tokens.accept(TK.KW_proc):
            p = parse_proc(tokens)
            assert p, "procedure did not parse."
            roots.append(p)
        elif tokens.accept(TK.KW_const):
            p = parse_const(tokens)
            assert p, "const statement did not parse."
            roots.append(p)
            tokens.expect(TK.Semicolon)
        elif tokens.accept(TK.KW_extern):
            p = parse_extern(tokens)
            assert p, "extern statement did not parse."
            roots.append(p)
            tokens.expect(TK.Semicolon)
        elif tokens.accept(TK.KW_asm):
            p = parse_asm(tokens)
            assert p, "inline asm block did not parse."
            roots.append(p)
        else:
            tk = tokens.peek()
            print(f"Error: Unexpected token in top-level: {repr(tk.kind)} : {repr(tk.value)}")
            print(tk.fmt_src_loc())
            exit(1)
    return roots

########################################################################################
#                             INTERMEDIATE REPRESENTATION
########################################################################################
class IRK(Enum):
    GetLocal     = auto()
    PushLabel    = auto()
    PushInt      = auto()
    AllocTemps   = auto()
    FreeTemps    = auto()
    StoreTemp    = auto()
    SetArgTemp   = auto()
    Call         = auto()
    PopCall      = auto()
    Plus         = auto()
    OpAdd        = auto()
    OpSub        = auto()
    OpMul        = auto()
    OpDiv        = auto()
    OpMod        = auto()
    OpEq         = auto()
    OpNotEq      = auto()
    OpLess       = auto()
    OpLessEq     = auto()
    OpGreater    = auto()
    OpGreaterEq  = auto()
    PopReturn    = auto()
    ReturnVoid   = auto()
    SetLocal     = auto()
    NewProc      = auto()
    SetLocalArg  = auto()
    CloseProc    = auto()
    GotoTopFalse = auto()
    GotoTopTrue  = auto()
    GotoFalse    = auto()
    Goto         = auto()
    Label        = auto()
    PtrRead      = auto()
    PtrWrite     = auto()
    BitNot       = auto()
    LogicNot     = auto()
    LogicAnd     = auto()
    LogicOr      = auto()
    InlineAsm    = auto()
    LazyIdent    = auto()
    CallLazyIdent = auto()

class IRInstr:
    def __init__(self, kind: IRK, **kwargs):
        self.kind: IRK = kind
        self.locals: Any = None
        self.name: Any = None
        self.params: Any = None
        self.n: Any = None
        self.local: Any = None
        self.label: Any = None
        self.value: Any = None
        self.size: Any = None
        self.varargs: Any = None
        self.asm: Any = None
        self.keys = []
        for k, v in kwargs.items():
            self.keys.append(k)
            setattr(self, k, v)

    def __repr__(self):
        if len(self.keys) > 0:
            vars = ", ".join([f"{k}={repr(getattr(self, k))}" for k in self.keys])
            return f" ({repr(self.kind)}, {vars})"
        return f" ({repr(self.kind)})"
        
class IRContext:
    def __init__(self, **kwargs):
        self.quiet = False
        self.procs: dict[str, Tuple[str, List[str], bool]] = {}
        self.label_id = 0
        self.data = []
        self.strings = {}
        self.externs = {}
        self.labels = set()
        self.constants = {}
        self.instructions = []

        self.file_map = {}
        self.src_locs = []
        self.file_idx = 0
        self.files = []
        for k, v in kwargs.items():
            setattr(self, k, v)

    def push_src_loc(self, loc: Tuple[str, int, int]) -> int:
        self.src_locs.append(loc)
        if loc[0] not in self.file_map:
            self.file_map[loc[0]] = self.file_idx
            self.file_idx += 1
            self.files.append(loc[0])
        return self.file_map[loc[0]]

    def pop_src_loc(self) -> None:
        self.src_locs.pop()

    def get_src_loc(self) -> Tuple[int, int, int, str]:
        src_loc = self.src_locs[-1]
        id = self.file_map[src_loc[0]]
        return id, src_loc[1], src_loc[2], src_loc[0]

    def append(self, kind: IRK, **kwargs) -> IRInstr:
        instr = IRInstr(kind, src_loc=self.get_src_loc(), **kwargs)
        if not self.quiet:
            print(instr)
        self.instructions.append(instr)
        return instr

    def declare_proc(self, name: str, params: List[str]) -> str:
        label = "_proc_" + name
        self.labels.add(label)
        p = {}
        for i, param in enumerate(params):
            p[param] = i
        self.procs[name] = (label, params, False)
        self.proc_params = p
        return label

    def declare_asm(self, name: str) -> None:
        self.procs[name] = (name, [], True)

    def get_proc(self, name: str) -> Tuple[Optional[str], Optional[List[str]], Optional[bool]]:
        if name in self.procs:
            return self.procs[name]
        return None, None, None

    def new_proc(self, name: str, params: List[str]) -> str:
        self.proc_locals: dict[str, int] = {}
        return self.declare_proc(name, params)

    def new_local(self, name: str) -> int:
        idx = len(self.proc_locals)
        self.proc_locals[name] = idx
        return idx

    def get_local(self, name: str) -> Optional[int]:
        if name in self.proc_locals:
            return self.proc_locals[name]
        return None

    def add_data(self, label: str, size: int, bytes: bytearray) -> None:
        self.labels.add(label)
        self.data.append((label, size, bytes))

    def add_string(self, string: str) -> str:
        if string in self.strings:
            return self.strings[string]
        str_label = "__string__" + str(len(self.data))
        str_bytes = bytearray(string, "utf-8")
        str_bytes.append(0)
        self.add_data(str_label, len(str_bytes), str_bytes)
        self.strings[string] = str_label
        return str_label

    def add_extern(self, ident: str, params: List[str], is_varargs: bool) -> None:
        self.externs[ident] = (ident, params, is_varargs)

    def get_extern(self, ident: str) -> Tuple[Optional[str], Optional[List[str]], Optional[bool]]:
        if ident in self.externs:
            return self.externs[ident]
        return None, None, None

    def new_label(self, hint: str) -> str:
        label = f".L{hint}_{self.label_id}"
        self.labels.add(label)
        self.label_id += 1
        return label

    def get_const(self, name: str) -> Union[None, str, int]:
        if name in self.constants:
            return self.constants[name]
        return None

    def add_const(self, name: str, value: Union[None, str, int]) -> None:
        # if not self.quiet:
        #     print(f"Define const {name} = {repr(value)}")
        assert value is not None, f"Setting const {name}"
        if isinstance(value, str):
            self.constants[name] = self.add_string(value)
        else:
            self.constants[name] = value

    def is_label(self, name: str) -> bool:
        return (name in self.externs) or (name in self.labels) or (name in self.procs)

    def is_local(self, name: str) -> bool:
        return name in self.proc_locals
    

def ir_emit_ident(ast: Ast, ir: IRContext) -> None:
    ident = ast.ident
    local = ir.get_local(ident)
    if local is not None:
        ir.append(IRK.GetLocal, local=ident, n=local)
        return

    const = ir.get_const(ident)
    if isinstance(const, str):
        ir.append(IRK.PushLabel, label=const)
        return
    elif isinstance(const, int):
        ir.append(IRK.PushInt, value=const)
        return
    elif const is not None:
        assert False, f"TODO: {inspect.currentframe().f_code.co_name} : {const}"

    proc, _, _ = ir.get_proc(ident)
    if proc is not None:
        ir.append(IRK.PushLabel, label=proc)
        return

    extern, _, _ = ir.get_extern(ident)
    if extern is not None:
        ir.append(IRK.PushLabel, label=extern)
        return

    ir.append(IRK.LazyIdent, ident=ast.token)


def ir_emit_integer(ast: Ast, ir: IRContext) -> None:
    ir.append(IRK.PushInt, value=ast.value)

def ir_emit_string(ast: Ast, ir: IRContext) -> None:
    string = ir.add_string(ast.value)
    ir.append(IRK.PushLabel, label=string)

def ir_emit_call(ast: Ast, ir: IRContext) -> None:
    ir.append(IRK.AllocTemps, n=len(ast.args))
    for i, arg in enumerate(ast.args):
        ir_compile(arg, ir)
        ir.append(IRK.StoreTemp, n=i)

    for i, _ in enumerate(ast.args):
        ir.append(IRK.SetArgTemp, n=i)
    ir.append(IRK.FreeTemps, n=len(ast.args))
    if ast.expr.kind == AstK.Ident:
        ident = ast.expr.ident
        if ident in ir.procs:
            proc_name, params, varargs = ir.procs[ident]
            if (not varargs and len(ast.args) != len(params)) or \
               (varargs and len(ast.args) < len(params)):
                print(f"ERROR: Call to `{ident}` expects {len(params)} arguments, got {len(ast.args)}")
                print(ast.token.fmt_src_loc())
                exit(1)
            ir.append(IRK.Call, label=proc_name, varargs=False)
        elif ident in ir.externs:
            id, params, varargs = ir.get_extern(ident)
            if (not varargs and len(ast.args) != len(params)) or \
               (varargs and len(ast.args) < len(params)):
                print(f"ERROR: Call to `{ident}` expects {len(params)} arguments, got {len(ast.args)}")
                print(ast.token.fmt_src_loc())
                exit(1)
            ir.append(IRK.Call, label=id, varargs=varargs)
        elif ir.is_label(ident):
            ir.append(IRK.Call, label=ident, varargs=False)
        elif ir.is_local(ident):
            ir_compile(ast.expr, ir)
            ir.append(IRK.PopCall)
        else:
            ir.append(IRK.CallLazyIdent, ident=ast.expr.token, nargs=len(ast.args))
    else:
        ir_compile(ast.expr, ir)
        ir.append(IRK.PopCall)

def ir_emit_logic_and(ast: Ast, ir: IRContext) -> None:
    l_skip = ir.new_label("and_skip")
    ir_compile(ast.lhs, ir)
    ir.append(IRK.GotoTopFalse, label=l_skip)
    ir_compile(ast.rhs, ir)
    ir.append(IRK.Label, label=l_skip)

def ir_emit_logic_or(ast: Ast, ir: IRContext) -> None:
    l_skip = ir.new_label("or_skip")
    ir_compile(ast.lhs, ir)
    ir.append(IRK.GotoTopTrue, label=l_skip)
    ir_compile(ast.rhs, ir)
    ir.append(IRK.Label, label=l_skip)

def ir_emit_binop(ast: Ast, ir: IRContext) -> None:
    op = ast.op
    simple = {
        TK.Plus: IRK.OpAdd,
        TK.Minus: IRK.OpSub,
        TK.Star: IRK.OpMul,
        TK.Slash: IRK.OpDiv,
        TK.Percent: IRK.OpMod,
        TK.EqEq: IRK.OpEq,
        TK.NotEq: IRK.OpNotEq,
        TK.Less: IRK.OpLess,
        TK.Greater: IRK.OpGreater,
        TK.LessEq: IRK.OpLessEq,
        TK.GreaterEq: IRK.OpGreaterEq,
    }
    if op in simple:
        ir_compile(ast.lhs, ir)
        ir_compile(ast.rhs, ir)
        ir.append(simple[op])
    elif op == TK.KW_and:
        ir_emit_logic_and(ast, ir)
    elif op == TK.KW_or:
        ir_emit_logic_or(ast, ir)
    else:
        assert False, f"TODO: {inspect.currentframe().f_code.co_name}: op({op})"

def ir_emit_return(ast: Ast, ir: IRContext) -> None:
    if ast.expr is not None:
        ir_compile(ast.expr, ir)
        ir.append(IRK.PopReturn)
    else:
        ir.append(IRK.ReturnVoid)

def ir_emit_var_decl(ast: Ast, ir: IRContext) -> None:
    ir.new_local(ast.ident.value)

def ir_emit_var_assign(ast: Ast, ir: IRContext) -> None:
    ir_compile(ast.expr, ir)
    local = ir.new_local(ast.ident.value)
    ir.append(IRK.SetLocal, local=ast.ident.value, n=local)

def ir_emit_assign(ast: Ast, ir: IRContext) -> None:
    ir_compile(ast.expr, ir)
    local = ir.get_local(ast.ident.value)
    if local is None:
        print(f"ERROR: No local named '{ast.ident.value}' exists.")
        print(ast.ident.fmt_src_loc())
        exit(1)
    ir.append(IRK.SetLocal, local=ast.ident.value, n=local)
    
def ir_emit_procedure(ast: Ast, ir: IRContext) -> None:
    name = ast.name.value
    params = list(map((lambda x: x.value), ast.params))
    label = ir.new_proc(name, params)
    instr = ir.append(IRK.NewProc, src_name=name, name=label, params=params, locals=None)

    for i, param in enumerate(params):
        local = ir.new_local(param)
        ir.append(IRK.SetLocalArg, local=param, arg=i)

    for stmt in ast.body:
        ir_compile(stmt, ir)

    instr.locals = ir.proc_locals
    ir.append(IRK.CloseProc, name=label)

def ir_emit_if_else(ast: Ast, ir: IRContext) -> None:
    l_then = ir.new_label("then")
    l_else = ir.new_label("else")
    l_out = ir.new_label("out")
    ir_compile(ast.test, ir)
    ir.append(IRK.GotoFalse, label=l_else)
    ir.append(IRK.Label, label=l_then)
    for stmt in ast.consequence:
        ir_compile(stmt, ir)
    ir.append(IRK.Goto, label=l_out)
    ir.append(IRK.Label, label=l_else)
    for stmt in ast.alternative:
        ir_compile(stmt, ir)
    ir.append(IRK.Label, label=l_out)

def ir_emit_while(ast: Ast, ir: IRContext) -> None:
    l_test = ir.new_label("while")
    l_out = ir.new_label("out")
    ir.append(IRK.Label, label=l_test)
    ir_compile(ast.test, ir)
    ir.append(IRK.GotoFalse, label=l_out)
    for stmt in ast.body:
        ir_compile(stmt, ir)
    ir.append(IRK.Goto, label=l_test)
    ir.append(IRK.Label, label=l_out)

def ir_emit_pointer_op(ast: Ast, ir: IRContext) -> None:
    op = ast.op
    size = ast.size
    if op == "READ":
        ptr = ast.args[0]
        ir_compile(ptr, ir)
        ir.append(IRK.PtrRead, size=size)
    else:
        # PTR_WRITE expects the pointer to be write to be at the top of the stack
        val = ast.args[1]
        ir_compile(val, ir)
        ptr = ast.args[0]
        ir_compile(ptr, ir)
        ir.append(IRK.PtrWrite, size=size)

def ir_emit_prefix_op(ast: Ast, ir: IRContext) -> None:
    ir_compile(ast.expr, ir)
    if ast.op == TK.Tilde:
        ir.append(IRK.BitNot)
    elif ast.op == TK.KW_not:
        ir.append(IRK.LogicNot)
    else:
        assert False, f"TODO: {inspect.currentframe().f_code.co_name} : {ast.op}"
        

def ir_emit_const(ast: Ast, ir: IRContext) -> None:
    exists = ir.get_const(ast.ident.value)
    k = ast.val_tok.kind
    val = None
    if k == TK.Ident:
        val = ir.get_const(ast.val_tok.value)
    elif k == TK.String:
        val = ast.val_tok.value
    elif k == TK.Integer:
        val = ast.val_tok.value
    elif k == TK.Char:
        val = ord(ast.val_tok.value)
    else:
        assert False, f"TODO: {inspect.currentframe().f_code.co_name} : {k}"

    if exists is not None and exists != val:
        print(f"ERROR: Cannot redefine 'const {ast.ident.value}'")
        print(ast.ident.fmt_src_loc())
        exit(1)
    ir.add_const(ast.ident.value, val)

def ir_emit_extern(ast: Ast, ir: IRContext) -> None:
    ident = ast.ident.value
    exists, params, varargs = ir.get_extern(ident)
    if exists is not None:
        if len(params) != len(ast.params) or varargs != ast.varargs:
            print(f"ERROR: Redefinition of `extern {ident}` with different number of arguments.")
            print(ast.ident.fmt_src_loc())
            exit(1)
    ir.add_extern(ident, ast.params, ast.varargs)

def ir_emit_asm(ast: Ast, ir: IRContext) -> None:
    ir.declare_asm(ast.name.value)
    ir.append(IRK.InlineAsm, name=ast.name.value, asm=ast.asm)
    
ir_emitters = MappingProxyType({
    AstK.Ident: ir_emit_ident,
    AstK.Integer: ir_emit_integer,
    AstK.String: ir_emit_string,
    AstK.Call: ir_emit_call,
    AstK.BinOp: ir_emit_binop,
    AstK.Return: ir_emit_return,
    AstK.VarDecl: ir_emit_var_decl,
    AstK.VarAssign: ir_emit_var_assign,
    AstK.Assign: ir_emit_assign,
    AstK.Procedure: ir_emit_procedure,
    AstK.IfElse: ir_emit_if_else,
    AstK.While: ir_emit_while,
    AstK.PointerOp: ir_emit_pointer_op,
    AstK.Prefix: ir_emit_prefix_op,
    AstK.Const: ir_emit_const,
    AstK.Extern: ir_emit_extern,
    AstK.InlineAsm: ir_emit_asm,
})
def ir_compile(ast: Ast, ir: IRContext) -> None:
    k = ast.kind
    if k in ir_emitters:
        ir.push_src_loc(ast.token.src_loc)
        ir_emitters[k](ast, ir)
        ir.pop_src_loc()
    else:
        assert False, f"TODO: compile Ast({k})"

########################################################################################
#                                     COMPILER
########################################################################################

class CompilerContext:
    def __init__(self, **kwargs):
        self.no_comments = False
        self.quiet = False
        self.out_lines = []
        self.all_procs = {}
        for k, v in kwargs.items():
            setattr(self, k, v)

    def new_proc(self, src_name: str, name: str, params: List[str], locals: dict[str, int]) -> None:
        self.name = name
        self.params = params
        self.locals = locals

    def proc_name(self, src_name: str) -> Tuple[Optional[str], Optional[List[str]], Optional[bool]]:
        if src_name in self.all_procs:
            return self.all_procs[src_name]
        return None, None, None

    def out(self, msg: str) -> None:
        if self.no_comments and len(msg) >= 3 and msg[0:3] == "# (":
            return
        if self.no_comments and len(msg) >= 8 and msg[0:8] == "    .loc":
            return
            
        if not self.quiet:
            print(msg)
        self.out_lines.append(msg)

    def full_listing(self) -> str:
        return "\n".join(self.out_lines)

    def optimize1(self, verbose: bool) -> None:
        # we just remove redundant push / pop pairs and mov instructions.
        push = re.compile(r"    pushq (%r..?)")
        pop = re.compile(r"    popq (%r..?)")

        movNR = re.compile(r"    movq (\$[0-9]+), (%r..?)")
        movRR = re.compile(r"    movq (%r..?), (%r..?)")
        movRM = re.compile(r"    movq (%r..?), (-?\d+\(%r..?\))")
                           
        made_changes = True
        removed = 0
        replaced = 0
        while made_changes:
            made_changes = False
            i = 1
            while i < len(self.out_lines):
                prev = self.out_lines[i-1]
                cur = self.out_lines[i]
                if popm := pop.match(cur):
                    if pushm := push.match(prev):
                        dest = popm.groups()[0]
                        src = pushm.groups()[0]
                        if dest == src:
                            del self.out_lines[i-1]
                            del self.out_lines[i-1]
                            removed += 2
                            made_changes = True
                        else:
                            self.out_lines[i-1] = f"    movq {src}, {dest}"
                            replaced += 1
                            del self.out_lines[i]
                            removed += 1
                            made_changes = True
                if movNRm := movNR.match(prev):
                    if movRRm := movRR.match(cur):
                        nr_n, nr_dst = movNRm.groups()
                        rr_src, rr_dst = movRRm.groups()
                        if nr_dst == rr_src:
                            self.out_lines[i-1] = f"    movq {nr_n}, {rr_dst}"
                            replaced += 1
                            del self.out_lines[i]
                            removed += 1
                            made_changes = True
                    elif movRMm := movRM.match(cur):
                        nr_n, nr_dst = movNRm.groups()
                        rm_src, rm_dst = movRMm.groups()
                        if nr_dst == rm_src:
                            self.out_lines[i-1] = f"    movq {nr_n}, {rm_dst}"
                            replaced += 1
                            del self.out_lines[i]
                            removed += 1
                            made_changes = True
                i += 1
        if verbose:
            print(f"Removed {removed} and replaced {replaced} useless instructions.")
        


systemv_args = ["%rdi", "%rsi", "%rdx", "%rcx", "%r8", "%r9"]
registers = {"%rax", "%rcx", "%rdx", "%rbx", "%rsi", "%rdi", "%rsp", "%rbp",
             "%r8", "%r9", "%r10", "%r11", "%r12", "%r13", "%r14", "%r15"}

meta_map = {64 : {
    "%rax": "%rax", "%rcx": "%rcx", "%rdx": "%rdx", "%rbx": "%rbx",
    "%rsi": "%rsi", "%rdi": "%rdi", "%rsp": "%rsp", "%rbp": "%rbp",
    "%r8" : "%r8", "%r9" : "%r9", "%r10": "%r10", "%r11": "%r11",
    "%r12": "%r12", "%r13": "%r13", "%r14": "%r14", "%r15": "%r15"
}, 32 : {
    "%rax": "%eax", "%rcx": "%ecx", "%rdx": "%edx", "%rbx": "%ebx",
    "%rsi": "%esi", "%rdi": "%edi", "%rsp": "%esp", "%rbp": "%ebp",
    "%r8":  "%r8d", "%r9":  "%r9d", "%r10": "%r10d", "%r11": "%r11d",
    "%r12": "%r12d", "%r13": "%r13d", "%r14": "%r14d", "%r15": "%r15d"
}, 16: {
    "%rax": "%ax", "%rcx": "%cx", "%rdx": "%dx", "%rbx": "%bx",
    "%rsi": "%si", "%rdi": "%di", "%rsp": "%sp", "%rbp": "%bp",
    "%r8":  "%r8w", "%r9":  "%r9w", "%r10": "%r10w", "%r11": "%r11w",
    "%r12": "%r12w", "%r13": "%r13w", "%r14": "%r14w", "%r15": "%r15w"
}, 8: {
    "%rax": "%al", "%rcx": "%cl", "%rdx": "%dl", "%rbx": "%bl",
    "%rsi": "%sil", "%rdi": "%dil", "%rsp": "%spl", "%rbp": "%bpl",
    "%r8":  "%r8b", "%r9":  "%r9b", "%r10": "%r10b", "%r11": "%r11b",
    "%r12": "%r12b", "%r13": "%r13b", "%r14": "%r14b", "%r15": "%r15b"
}}

def sized_register(size: int, reg: str) -> str:
    return meta_map[size][reg]

def emit_new_proc(ctx: CompilerContext, ir: IRInstr) -> None:
    ctx.new_proc(ir.src_name, ir.name, ir.params, ir.locals)
    ctx.out(f"    .globl {ir.name}")
    ctx.out(f"    .align 16")
    id, line, col, file = ir.src_loc
    ctx.out(f"    .loc {id} {line} {col}")
    ctx.out(f"{ir.name}: # params={ir.params}")
    ctx.out(f"#{ir}")
    ctx.out(f"    pushq %rbp")
    ctx.out(f"    movq %rsp, %rbp")
    if len(ir.locals) > 0:
        ctx.out(f"    subq ${8 * len(ir.locals)}, %rsp")

def emit_close_proc(ctx: CompilerContext, ir: IRInstr) -> None:
    ctx.out(f"#{ir}")
    id, line, col, file = ir.src_loc
    ctx.out(f"    .loc {id} {line} {col}")
    ctx.out(f"    movq %rbp, %rsp")
    ctx.out(f"    popq %rbp")
    ctx.out(f"    ret")
    ctx.out(f"### close {ir.name}")

def emit_get_local(ctx: CompilerContext, ir: IRInstr) -> None:
    offs = 8 * (ir.n+1)
    ctx.out(f"#{ir}")
    id, line, col, file = ir.src_loc
    ctx.out(f"    .loc {id} {line} {col}")
    ctx.out(f"    movq -{offs}(%rbp), %rax")
    ctx.out(f"    pushq %rax")

def emit_set_local_arg(ctx: CompilerContext, ir: IRInstr) -> None:
    idx = ctx.locals[ir.local]
    offs = 8 * (idx+1)
    ctx.out(f"#{ir}")
    id, line, col, file = ir.src_loc
    ctx.out(f"    .loc {id} {line} {col}")
    if idx < len(systemv_args):
        ctx.out(f"    movq {systemv_args[idx]}, -{offs}(%rbp)")
    else:
        n = (idx-len(systemv_args)+2)*8
        ctx.out(f"   movq {n}(%rbp), %rax")
        ctx.out(f"   movq %rax, -{offs}(%rbp)")

def emit_set_local(ctx: CompilerContext, ir: IRInstr) -> None:
    idx = ctx.locals[ir.local]
    offs = 8 * (idx+1)
    ctx.out(f"#{ir}")
    id, line, col, file = ir.src_loc
    ctx.out(f"    .loc {id} {line} {col}")
    ctx.out(f"    popq %rax")
    ctx.out(f"    movq %rax, -{offs}(%rbp)")
    
def emit_alloc_temps(ctx: CompilerContext, ir: IRInstr) -> None:
    if ir.n > 0:
        ctx.out(f"#{ir}")
        id, line, col, file = ir.src_loc
        ctx.out(f"    .loc {id} {line} {col}")
        ctx.out(f"    subq ${8 * (1+ir.n)}, %rsp")

def emit_free_temps(ctx: CompilerContext, ir: IRInstr) -> None:
    if ir.n > 0:
        ctx.out(f"#{ir}")
        id, line, col, file = ir.src_loc
        ctx.out(f"    .loc {id} {line} {col}")
        ctx.out(f"    addq ${8 * (1+ir.n)}, %rsp")

def emit_push_label(ctx: CompilerContext, ir: IRInstr) -> None:
    ctx.out(f"#{ir}")
    id, line, col, file = ir.src_loc
    ctx.out(f"    .loc {id} {line} {col}")
    ctx.out(f"    leaq {ir.label}, %rax")
    ctx.out(f"    pushq %rax")

def emit_store_temp(ctx: CompilerContext, ir: IRInstr) -> None:
    offs = 8 * (1+ir.n)
    ctx.out(f"#{ir}")
    id, line, col, file = ir.src_loc
    ctx.out(f"    .loc {id} {line} {col}")
    ctx.out(f"    popq %rax")
    ctx.out(f"    movq %rax, {offs}(%rsp)")

def emit_set_arg_temp(ctx: CompilerContext, ir: IRInstr) -> None:
    offs = 8 * (1+ir.n)
    ctx.out(f"#{ir}")
    id, line, col, file = ir.src_loc
    ctx.out(f"    .loc {id} {line} {col}")
    if ir.n < len(systemv_args):
        ctx.out(f"    movq {offs}(%rsp), {systemv_args[ir.n]}")
    else:
        ctx.out(f"    pushq {offs}(%rsp)")
        #assert False, f"TODO: {inspect.currentframe().f_code.co_name} : too many args"
        
def emit_lazy_ident(ctx: CompilerContext, ir: IRInstr) -> None:
    name, _, _ = ctx.proc_name(ir.ident.value)
    if name is None:
        print(f"ERROR: Undeclared identifier: `{ir.ident.value}`")
        print(f"    did you forget to declare 'extern {ir.ident.value} ...;'?")
        print(ir.ident.fmt_src_loc())
        exit(1)
    ctx.out(f"#{ir}")
    id, line, col, file = ir.src_loc
    ctx.out(f"    .loc {id} {line} {col}")
    ctx.out(f"    leaq {name}, %rax")
    ctx.out(f"    pushq %rax")

def emit_call_lazy_ident(ctx: CompilerContext, ir: IRInstr) -> None:
    name, params, varargs = ctx.proc_name(ir.ident.value)
    if name is None:
        print(f"ERROR: Undeclared identifier: `{ir.ident.value}`")
        print(f"    did you forget to declare 'extern {ir.ident.value} ...;'?")
        print(ir.ident.fmt_src_loc())
        exit(1)

    if (not varargs and ir.nargs != len(params)) or \
       (varargs and ir.nargs < len(params)):
        print(f"ERROR: Call to `{ir.ident.value}` expects {len(params)} arguments, got {ir.nargs}")
        print(ir.ident.fmt_src_loc())
        exit(1)

    ctx.out(f"#{ir}")
    id, line, col, file = ir.src_loc
    ctx.out(f"    .loc {id} {line} {col}")
    if ir.varargs:
        ctx.out(f"    xor %al, %al")
    ctx.out(f"    call {name}")
    ctx.out(f"    pushq %rax")

def emit_call(ctx: CompilerContext, ir: IRInstr) -> None:
    ctx.out(f"#{ir}")
    id, line, col, file = ir.src_loc
    ctx.out(f"    .loc {id} {line} {col}")
    if ir.varargs:
        ctx.out(f"    xor %al, %al")
    ctx.out(f"    call {ir.label}")
    ctx.out(f"    pushq %rax")

def emit_pop_call(ctx: CompilerContext, ir: IRInstr) -> None:
    ctx.out(f"#{ir}")
    id, line, col, file = ir.src_loc
    ctx.out(f"    .loc {id} {line} {col}")
    ctx.out(f"    popq %rcx")
    ctx.out(f"    xor %al, %al")
    ctx.out(f"    call *%rcx")
    ctx.out(f"    pushq %rax")

def emit_push_int(ctx: CompilerContext, ir: IRInstr) -> None:
    ctx.out(f"#{ir}")
    id, line, col, file = ir.src_loc
    ctx.out(f"    .loc {id} {line} {col}")
    if ~(1<<31) < ir.value < 1<<32:
        instr = "movq"
    else:
        instr = "movabsq"
    ctx.out(f"    {instr} ${ir.value}, %rax")
    ctx.out(f"    pushq %rax")

def emit_pop_return(ctx: CompilerContext, ir: IRInstr) -> None:
    ctx.out(f"#{ir}")
    id, line, col, file = ir.src_loc
    ctx.out(f"    .loc {id} {line} {col}")
    ctx.out(f"    popq %rax")
    ctx.out(f"    leave")
    ctx.out(f"    ret")

def emit_return_void(ctx: CompilerContext, ir: IRInstr) -> None:
    ctx.out(f"#{ir}")
    id, line, col, file = ir.src_loc
    ctx.out(f"    .loc {id} {line} {col}")
    ctx.out(f"    xorq %rax, %rax")
    ctx.out(f"    leave")
    ctx.out(f"    ret")

def emit_logic_not(ctx: CompilerContext, ir: IRInstr) -> None:
    ctx.out(f"#{ir}")
    id, line, col, file = ir.src_loc
    ctx.out(f"    .loc {id} {line} {col}")
    ctx.out(f"    popq %rax") # -- a
    ctx.out(f"    cmpq $0, %rax")
    ctx.out(f"    sete %al")
    ctx.out(f"    movzbl %al, %eax")
    ctx.out(f"    pushq %rax")

def emit_bit_not(ctx: CompilerContext, ir: IRInstr) -> None:
    ctx.out(f"#{ir}")
    id, line, col, file = ir.src_loc
    ctx.out(f"    .loc {id} {line} {col}")
    ctx.out(f"    popq %rax") # -- a
    ctx.out(f"    not %rax")
    ctx.out(f"    pushq %rax")

def emit_op_compare(ctx: CompilerContext, ir: IRInstr) -> None:
    instr = {IRK.OpEq: "sete",
             IRK.OpNotEq: "setne",
             IRK.OpLess: "setl",
             IRK.OpLessEq: "setle",
             IRK.OpGreater: "setg",
             IRK.OpGreaterEq: "setge"}[ir.kind]
    ctx.out(f"#{ir}")
    id, line, col, file = ir.src_loc
    ctx.out(f"    .loc {id} {line} {col}")
    ctx.out(f"    popq %r10") # -- a
    ctx.out(f"    popq %r11") # -- b
    ctx.out(f"    xorl %eax, %eax")
    ctx.out(f"    cmpq %r10, %r11") # cmp compares first to second.
    ctx.out(f"    {instr} %al")
    ctx.out(f"    pushq %rax")

def emit_op_add(ctx: CompilerContext, ir: IRInstr) -> None:
    ctx.out(f"#{ir}")
    id, line, col, file = ir.src_loc
    ctx.out(f"    .loc {id} {line} {col}")
    ctx.out(f"    popq %rdx") # -- b
    ctx.out(f"    popq %rax") # -- a
    ctx.out(f"    addq %rdx, %rax")
    ctx.out(f"    pushq %rax")

def emit_op_sub(ctx: CompilerContext, ir: IRInstr) -> None:
    ctx.out(f"#{ir}")
    id, line, col, file = ir.src_loc
    ctx.out(f"    .loc {id} {line} {col}")
    ctx.out(f"    popq %rdx") # -- b
    ctx.out(f"    popq %rax") # -- a
    ctx.out(f"    subq %rdx, %rax")
    ctx.out(f"    pushq %rax")

def emit_op_mod(ctx: CompilerContext, ir: IRInstr) -> None:
    ctx.out(f"#{ir}")
    id, line, col, file = ir.src_loc
    ctx.out(f"    .loc {id} {line} {col}")
    ctx.out(f"    popq %rcx") # -- b
    ctx.out(f"    popq %rax") # -- a
    ctx.out(f"    cqto")
    ctx.out(f"    idivq %rcx")
    ctx.out(f"    pushq %rdx")

def emit_op_div(ctx: CompilerContext, ir: IRInstr) -> None:
    ctx.out(f"#{ir}")
    id, line, col, file = ir.src_loc
    ctx.out(f"    .loc {id} {line} {col}")
    ctx.out(f"    popq %rcx") # -- b
    ctx.out(f"    popq %rax") # -- a
    ctx.out(f"    cqto")
    ctx.out(f"    idivq %rcx")
    ctx.out(f"    pushq %rax")

def emit_op_mul(ctx: CompilerContext, ir: IRInstr) -> None:
    ctx.out(f"#{ir}")
    id, line, col, file = ir.src_loc
    ctx.out(f"    .loc {id} {line} {col}")
    ctx.out(f"    popq %rdx") # -- b
    ctx.out(f"    popq %rax") # -- a
    ctx.out(f"    imulq %rdx, %rax")
    ctx.out(f"    pushq %rax")

def emit_label(ctx: CompilerContext, ir: IRInstr) -> None:
    ctx.out(f"#{ir}")
    id, line, col, file = ir.src_loc
    ctx.out(f"    .loc {id} {line} {col}")
    ctx.out(f"{ir.label}:")

def emit_goto(ctx: CompilerContext, ir: IRInstr) -> None:
    ctx.out(f"#{ir}")
    id, line, col, file = ir.src_loc
    ctx.out(f"    .loc {id} {line} {col}")
    ctx.out(f"    jmp {ir.label}")

def emit_goto_false(ctx: CompilerContext, ir: IRInstr) -> None:
    ctx.out(f"#{ir}")
    id, line, col, file = ir.src_loc
    ctx.out(f"    .loc {id} {line} {col}")
    ctx.out(f"    popq %rax")
    ctx.out(f"    cmpq $0, %rax")
    ctx.out(f"    je {ir.label}")

def emit_goto_top_true(ctx: CompilerContext, ir: IRInstr) -> None:
    ctx.out(f"#{ir}")
    id, line, col, file = ir.src_loc
    ctx.out(f"    .loc {id} {line} {col}")
    ctx.out(f"    cmpq $0, (%rsp)")
    ctx.out(f"    jne {ir.label}")

def emit_goto_top_false(ctx: CompilerContext, ir: IRInstr) -> None:
    ctx.out(f"#{ir}")
    id, line, col, file = ir.src_loc
    ctx.out(f"    .loc {id} {line} {col}")
    ctx.out(f"    cmpq $0, (%rsp)")
    ctx.out(f"    je {ir.label}")

def emit_ptr_write(ctx: CompilerContext, ir: IRInstr) -> None:
    ctx.out(f"#{ir}")
    id, line, col, file = ir.src_loc
    ctx.out(f"    .loc {id} {line} {col}")
    ctx.out(f"    popq %rax") # -- ptr
    ctx.out(f"    popq %rdx") # -- value
    suffix = {8:"b", 16:"w", 32:"l", 64:"q"}[ir.size]
    register = sized_register(ir.size, "%rdx")
    ctx.out(f"    mov{suffix} {register}, (%rax)")

def emit_ptr_read(ctx: CompilerContext, ir: IRInstr) -> None:
    ctx.out(f"#{ir}")
    id, line, col, file = ir.src_loc
    ctx.out(f"    .loc {id} {line} {col}")
    suffix = {8:"b", 16:"w", 32:"l", 64:"q"}[ir.size]
    register = sized_register(ir.size, "%rdx")
    ctx.out(f"    popq %rax") # -- ptr
    ctx.out(f"    xorl %edx, %edx")
    ctx.out(f"    mov{suffix} (%rax), {register}")
    ctx.out(f"    movq %rdx, %rax")
    ctx.out(f"    pushq %rax")

def emit_inline_asm(ctx: CompilerContext, ir: IRInstr) -> None:
    code = [line.strip() for line in ir.asm.value.split("\n")]
    ctx.out(f".align 16")
    ctx.out(f"{ir.name}:")
    id, line, col, file = ir.src_loc
    ctx.out(f"    .loc {id} {line} {col}")
    for asm in code:
        if asm != "":
            ctx.out(f"    {asm}")

x86_64_emitters = MappingProxyType({
    IRK.NewProc: emit_new_proc,
    IRK.SetLocalArg: emit_set_local_arg,
    IRK.SetLocal: emit_set_local,
    IRK.AllocTemps: emit_alloc_temps,
    IRK.FreeTemps: emit_free_temps,
    IRK.PushLabel: emit_push_label,
    IRK.StoreTemp: emit_store_temp,
    IRK.SetArgTemp: emit_set_arg_temp,
    IRK.Call: emit_call,
    IRK.PopCall: emit_pop_call,
    IRK.CloseProc: emit_close_proc,
    IRK.PushInt: emit_push_int,
    IRK.GetLocal: emit_get_local,
    IRK.PopReturn: emit_pop_return,
    IRK.ReturnVoid: emit_return_void,
    IRK.OpAdd: emit_op_add,
    IRK.OpSub: emit_op_sub,
    IRK.OpMul: emit_op_mul,
    IRK.OpDiv: emit_op_div,
    IRK.OpMod: emit_op_mod,
    IRK.OpEq: emit_op_compare,
    IRK.OpNotEq: emit_op_compare,
    IRK.OpLess: emit_op_compare,
    IRK.OpLessEq: emit_op_compare,
    IRK.OpGreater: emit_op_compare,
    IRK.OpGreaterEq: emit_op_compare,
    IRK.LogicNot: emit_logic_not,
    IRK.BitNot: emit_bit_not,
    IRK.Label: emit_label,
    IRK.Goto: emit_goto,
    IRK.GotoFalse: emit_goto_false,
    IRK.GotoTopFalse: emit_goto_top_false,
    IRK.GotoTopTrue: emit_goto_top_true,
    IRK.PtrWrite: emit_ptr_write,
    IRK.PtrRead: emit_ptr_read,
    IRK.InlineAsm: emit_inline_asm,
    IRK.LazyIdent: emit_lazy_ident,
    IRK.CallLazyIdent: emit_call_lazy_ident,
})
def emit_instruction(ctx: CompilerContext, ir: IRInstr) -> None:
    k = ir.kind
    if k in x86_64_emitters:
        x86_64_emitters[k](ctx, ir)
    else: assert False, f"TODO: compile {ir}"

def emit_start_proc(ctx: CompilerContext, main_proc: str, exit_proc: Optional[str]) -> None:
    ctx.out(".globl _start")
    ctx.out(f".align 16")
    ctx.out("_start:")
    ctx.out(f"    movq (%rsp), {systemv_args[0]}")
    ctx.out(f"    movq %rsp, {systemv_args[1]}")
    ctx.out(f"    addq $8, {systemv_args[1]}")
    ctx.out(f"    movq {systemv_args[0]}, (__argc__)")
    ctx.out(f"    movq {systemv_args[1]}, (__argv__)")
    for arg in systemv_args[2:]:
        ctx.out(f"    xorq {arg}, {arg}")
    ctx.out(f"    call {main_proc}")
    ctx.out(f"    movq %rax, %rdi")
    if exit_proc is not None:
        ctx.out(f"    call {exit_proc}")
    ctx.out(f"    movq $60, %rax            # exit syscall is 60")
    ctx.out(f"    syscall")
    ctx.out(f"    int3")

def assemble_and_link(asm_path: str, exe_path: str, ld_flags: List[str], verbose: bool) -> None:
    without_ext = os.path.splitext(asm_path)[0]
    obj_path = f"{without_ext}.o"
    obj_dir = str(pathlib.Path(obj_path).parent.resolve())
    ld_flags = ["-o", without_ext, obj_path] + ld_flags;
    if verbose:
        print(f"asm file   = {asm_path}")
        print(f"obj dir    = {obj_dir}")
        print(f"obj file   = {obj_path}")
        print(f"executable = {exe_path}")
        print(f"ld_flags = {ld_flags}")
    assemble = subprocess.run(["gcc", "-g3", "-c", asm_path, "-o", obj_path])
    if assemble.returncode != 0:
        exit(assemble.returncode)
        return
    if obj_dir != "/" and obj_dir != "":
        ld = subprocess.run(["ld"] + ld_flags)
        if ld.returncode != 0:
            exit(ld.returncode)

class Config:
    def __init__(self, **kwargs):
        self.source_path: str = ""
        self.out_path: str = ""
        self.ld_flags: List[str] = []
        self.include_paths: List[str] = []
        self.ir_comments: bool = False
        self.verbosity: int = 0
        for k, v in kwargs.items():
            setattr(self, k, v)

def main(config: Config):
    source_path = config.source_path
    source_base = pathlib.Path(source_path).stem
    out_path = config.out_path
    if os.path.isdir(out_path):
        out_path += f"/{source_base}"
    out_asm = f"{out_path}.s"
    include_paths.append(str(pathlib.Path(source_path).parent.resolve()))
    include_paths.append(str(pathlib.Path(source_path).parent.resolve()) + "/include")
    include_paths.append("/home/max/workspace/randy/include")
    for path in config.include_paths:
        include_paths.append(str(pathlib.Path(path).parent.resolve()))

    start = time.time()
    tokens = lex_file(source_path)
    end = time.time()
    if config.verbosity > 0:
        print(f"Lexing took {(end-start)*1000}ms")

    start = time.time()
    roots = parse(TokenStream(tokens))
    end = time.time()
    if config.verbosity > 0:
        print(f"Parsing took {(end-start)*1000}ms")

    ctx = CompilerContext(quiet=config.verbosity < 3, no_comments=not config.ir_comments)
    ir = IRContext(quiet=config.verbosity < 3)

    start = time.time()

    for ast in roots:
        ir_compile(ast, ir)
    assert len(ir.src_locs) == 0, f"Forgot to pop ir src_loc for something: len={len(ir.src_locs)} last={ir.src_locs[-1]}"
    end = time.time()
    if config.verbosity > 0:
        print(f"IR compile took {(end-start)*1000}ms")

    for k, v in ir.procs.items():
        ctx.all_procs[k] = v

    start = time.time()
    ctx.out(".text")
    for file, id in ir.file_map.items():
        ctx.out(f"    .file {id} \"{file}\"")

    for insn in ir.instructions:
        emit_instruction(ctx, insn)

    main_proc, _, _ = ir.get_proc("main")
    exit_proc, _, _ = ir.get_proc("exit")
    if main_proc is None:
        print("ERROR: no `main` procedure.")
        exit(1)
    else:
        emit_start_proc(ctx, main_proc, exit_proc)
    
    ctx.out("\n")

    for ext in ir.externs:
        ctx.out(f".extern {ext}")

    ctx.out("\n")

    ctx.out('.data')
    ctx.out('.align 8')
    ctx.out('__argc__: .quad 0')
    ctx.out('__argv__: .quad 0')

    ctx.out('.section .rodata, "a"')
    for data in ir.data:
        label, size, bytes = data
        bytestr = ", ".join([hex(x) for x in bytes])
        ctx.out(f".align 8")
        ctx.out(f"{label}: .byte {bytestr}")

    ctx.out("\n")
    end = time.time()
    if config.verbosity > 0:
        print(f"ASM compile took {(end-start)*1000}ms")

    start = time.time()
    ctx.optimize1(config.verbosity > 0)
    end = time.time()
    if config.verbosity > 0:
        print(f"ASM optimize took {(end-start)*1000}ms")

    with open(out_asm, "w") as f:
        f.write(ctx.full_listing())

    start = time.time()
    assemble_and_link(out_asm, out_path, config.ld_flags, config.verbosity > 1)
    end = time.time()
    if config.verbosity > 0:
        print(f"Linking took {(end-start)*1000}ms")

def print_usage() -> None:
    print("usage: python randy.py [flags]")
    print("Options and arguments:")
    print("-c file       : Compile file")
    print("-o path       : The path to compile the file provided by the -c flag.")
    print("                When no -o path specified, the current directory is used.")
    print("-I path       : Specify a path to search for #include directives.")
    print("-ld flags...  : Everything after -ld will be passed to the linker directly.")
    print("                see 'man ld' for linker flags.")
    print("-v -vv -vvv   : Compiler verbosity level")
    print("--ir-comments : Include intermediate representation comments in generated assembly.")

def parse_args() -> Config:
    source_path: Optional[str] = None
    out_path: Optional[str] = None
    ld_flags: List[str] = []
    includes: List[str] = []
    ir_comments = False
    verbosity = 0

    args = sys.argv
    i = 1;
    while i < len(args):
        arg = args[i]
        if arg == "-h" or arg == "--help":
            print_usage()
            exit(0)
        if arg == "-c":
            if i + 1 == len(args):
                source_path = "-"
                break
            if source_path is not None:
                print("Multiple -c flags not supported\n")
                print_usage()
            source_path = args[i+1]
            i += 2
            continue
        if arg == "-o":
            if i + 1 == len(args):
                out_path = "-"
                break
            if out_path is not None:
                print("Multiple -o flags not supported\n")
                print_usage()
            out_path = args[i+1]
            i += 2
            continue
        if arg == "-I":
            if i + 1 == len(args):
                print("No path provided with -I flag")
                print_usage()
                exit(1)
            includes.append(args[i+1])
            i += 2
            continue
        if arg == "-ld":
            ld_flags = args[i+1:]
            break
        if arg == "--ir-comments":
            ir_comments = True
            i += 1
            continue
        if arg == "--no-ir-comments":
            ir_comments = False
            i += 1
            continue
        if arg == "-v":
            verbosity = 1
            i += 1
            continue
        if arg == "-vv":
            verbosity = 2
            i += 1
            continue
        if arg == "-vvv":
            verbosity = 3
            i += 1
            continue
        i += 1

    if source_path is None:
        print_usage()
        exit(1)
    elif source_path[0] == "-":
        print("No file provided with -c flag")
        print_usage()
        exit(1)
    else:
        source_path = os.path.abspath(source_path)

    if out_path is None:
        out_path = os.getcwd()
    elif out_path[0] == "-":
        print("No path provided with -o flag")
        print_usage()
        exit(1)
    else:
        out_path = os.path.abspath(out_path)

    return Config(source_path=source_path,
                  out_path=out_path,
                  ld_flags=ld_flags,
                  include_paths=includes,
                  ir_comments=ir_comments,
                  verbosity=verbosity)

if __name__ == "__main__":
    main(parse_args())

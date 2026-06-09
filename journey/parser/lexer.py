"""
Lexer for the Journey language.

Tokenizes .journey source into a stream of tokens for the parser.
"""

import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional


class TokenType(Enum):
    # Structural
    LBRACE = auto()       # {
    RBRACE = auto()       # }
    LPAREN = auto()       # (
    RPAREN = auto()       # )
    COMMA = auto()         # ,
    COLON = auto()         # :
    ARROW = auto()         # ->
    PIPE = auto()          # |
    DOT = auto()           # .
    DASH = auto()          # - (standalone, not part of ->)

    # Keywords
    JOURNEY = auto()
    DESCRIPTION = auto()
    ENTITY = auto()
    STEP = auto()
    TEST = auto()
    INPUT = auto()
    OUTPUT = auto()
    ACTION = auto()
    ERRORS = auto()
    ACTOR = auto()
    REQUIRES = auto()
    STATE = auto()
    ENUM = auto()
    DO = auto()
    EXPECT = auto()
    CAPTURE = auto()
    AS = auto()
    AUTHENTICATED = auto()

    # Natural-language section keywords
    MISSION = auto()
    PAGE = auto()
    PAGES = auto()
    FLOWS = auto()
    ACCEPTANCE = auto()
    CREW = auto()
    DONE = auto()
    WHEN = auto()
    PURPOSE = auto()
    RULES = auto()
    USER = auto()
    SEES = auto()
    DESIGN = auto()
    FIRST = auto()
    THEN = auto()

    # Modifiers
    UNIQUE = auto()
    HASHED = auto()
    AUTO = auto()
    REQUIRED = auto()
    FORMAT = auto()
    MIN = auto()
    MAX = auto()
    DEFAULT = auto()

    # Action keywords
    CREATE = auto()
    FIND = auto()
    SEND = auto()
    VERIFY = auto()

    # Literals
    STRING = auto()        # "quoted string"
    NUMBER = auto()        # 123, 409
    IDENTIFIER = auto()    # any unquoted word

    # Special
    NEWLINE = auto()
    EOF = auto()


KEYWORDS = {
    "journey": TokenType.JOURNEY,
    "description": TokenType.DESCRIPTION,
    "entity": TokenType.ENTITY,
    "step": TokenType.STEP,
    "test": TokenType.TEST,
    "input": TokenType.INPUT,
    "output": TokenType.OUTPUT,
    "action": TokenType.ACTION,
    "errors": TokenType.ERRORS,
    "actor": TokenType.ACTOR,
    "requires": TokenType.REQUIRES,
    "state": TokenType.STATE,
    "enum": TokenType.ENUM,
    "do": TokenType.DO,
    "expect": TokenType.EXPECT,
    "capture": TokenType.CAPTURE,
    "as": TokenType.AS,
    "authenticated": TokenType.AUTHENTICATED,
    "unique": TokenType.UNIQUE,
    "hashed": TokenType.HASHED,
    "auto": TokenType.AUTO,
    "required": TokenType.REQUIRED,
    "format": TokenType.FORMAT,
    "min": TokenType.MIN,
    "max": TokenType.MAX,
    "default": TokenType.DEFAULT,
    "create": TokenType.CREATE,
    "find": TokenType.FIND,
    "send": TokenType.SEND,
    "verify": TokenType.VERIFY,
    # Natural-language section keywords
    "mission": TokenType.MISSION,
    "page": TokenType.PAGE,
    "pages": TokenType.PAGES,
    "flows": TokenType.FLOWS,
    "acceptance": TokenType.ACCEPTANCE,
    "crew": TokenType.CREW,
    "done": TokenType.DONE,
    "when": TokenType.WHEN,
    "purpose": TokenType.PURPOSE,
    "rules": TokenType.RULES,
    "user": TokenType.USER,
    "sees": TokenType.SEES,
    "design": TokenType.DESIGN,
    "first": TokenType.FIRST,
    "then": TokenType.THEN,
}

# Keywords that should only be treated as keywords in hybrid parsing mode.
# In structured mode, these are treated as plain identifiers to avoid
# breaking existing .journey files that use these words as field names.
HYBRID_ONLY_KEYWORDS = {
    "mission", "page", "pages", "flows", "acceptance", "crew",
    "done", "when", "purpose", "rules", "user", "sees", "design",
    "first", "then",
}


@dataclass
class Token:
    type: TokenType
    value: str
    line: int
    col: int

    def __repr__(self) -> str:
        return f"Token({self.type.name}, {self.value!r}, L{self.line}:{self.col})"


class LexerError(Exception):
    def __init__(self, message: str, line: int, col: int, filename: str):
        self.line = line
        self.col = col
        self.filename = filename
        super().__init__(f"{filename}:{line}:{col}: {message}")


class Lexer:
    def __init__(self, source: str, filename: str = "<string>", *, hybrid: bool = False):
        self.source = source
        self.filename = filename
        self.hybrid = hybrid
        self.pos = 0
        self.line = 1
        self.col = 1
        self.tokens: list[Token] = []

    def error(self, msg: str) -> LexerError:
        return LexerError(msg, self.line, self.col, self.filename)

    def peek(self) -> Optional[str]:
        if self.pos < len(self.source):
            return self.source[self.pos]
        return None

    def advance(self) -> str:
        ch = self.source[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def skip_whitespace_and_comments(self):
        while self.pos < len(self.source):
            ch = self.source[self.pos]
            if ch == "#":
                # Skip to end of line
                while self.pos < len(self.source) and self.source[self.pos] != "\n":
                    self.advance()
            elif ch in (" ", "\t", "\r"):
                self.advance()
            else:
                break

    def read_string(self) -> str:
        """Read a quoted string (double quotes)."""
        self.advance()  # skip opening quote
        result = []
        while self.pos < len(self.source):
            ch = self.source[self.pos]
            if ch == "\\":
                self.advance()
                if self.pos < len(self.source):
                    escape = self.advance()
                    if escape == "n":
                        result.append("\n")
                    elif escape == "t":
                        result.append("\t")
                    elif escape == '"':
                        result.append('"')
                    elif escape == "\\":
                        result.append("\\")
                    else:
                        result.append("\\" + escape)
            elif ch == '"':
                self.advance()  # skip closing quote
                return "".join(result)
            elif ch == "\n":
                raise self.error("Unterminated string literal")
            else:
                result.append(self.advance())
        raise self.error("Unterminated string literal")

    def read_number(self) -> str:
        result = []
        while self.pos < len(self.source) and self.source[self.pos].isdigit():
            result.append(self.advance())
        return "".join(result)

    def read_identifier(self) -> str:
        result = []
        while self.pos < len(self.source) and (
            self.source[self.pos].isalnum() or self.source[self.pos] == "_"
        ):
            result.append(self.advance())
        return "".join(result)

    def tokenize(self) -> list[Token]:
        while self.pos < len(self.source):
            self.skip_whitespace_and_comments()
            if self.pos >= len(self.source):
                break

            ch = self.source[self.pos]
            line, col = self.line, self.col

            if ch == "\n":
                self.advance()
                self.tokens.append(Token(TokenType.NEWLINE, "\\n", line, col))
                continue

            if ch == "{":
                self.advance()
                self.tokens.append(Token(TokenType.LBRACE, "{", line, col))
            elif ch == "}":
                self.advance()
                self.tokens.append(Token(TokenType.RBRACE, "}", line, col))
            elif ch == "(":
                self.advance()
                self.tokens.append(Token(TokenType.LPAREN, "(", line, col))
            elif ch == ")":
                self.advance()
                self.tokens.append(Token(TokenType.RPAREN, ")", line, col))
            elif ch == ",":
                self.advance()
                self.tokens.append(Token(TokenType.COMMA, ",", line, col))
            elif ch == ":":
                self.advance()
                self.tokens.append(Token(TokenType.COLON, ":", line, col))
            elif ch == ".":
                self.advance()
                self.tokens.append(Token(TokenType.DOT, ".", line, col))
            elif ch == "|":
                self.advance()
                self.tokens.append(Token(TokenType.PIPE, "|", line, col))
            elif ch == "-" and self.pos + 1 < len(self.source) and self.source[self.pos + 1] == ">":
                self.advance()
                self.advance()
                self.tokens.append(Token(TokenType.ARROW, "->", line, col))
            elif ch == "-" and self.hybrid:
                self.advance()
                self.tokens.append(Token(TokenType.DASH, "-", line, col))
            elif ch == "=":
                self.advance()
                self.tokens.append(Token(TokenType.IDENTIFIER, "=", line, col))
            elif ch == '"':
                value = self.read_string()
                self.tokens.append(Token(TokenType.STRING, value, line, col))
            elif ch.isdigit():
                value = self.read_number()
                self.tokens.append(Token(TokenType.NUMBER, value, line, col))
            elif ch.isalpha() or ch == "_":
                value = self.read_identifier()
                ttype = KEYWORDS.get(value, TokenType.IDENTIFIER)
                # In structured mode, hybrid-only keywords are plain identifiers
                if not self.hybrid and value in HYBRID_ONLY_KEYWORDS:
                    ttype = TokenType.IDENTIFIER
                self.tokens.append(Token(ttype, value, line, col))
            else:
                raise self.error(f"Unexpected character: {ch!r}")

        self.tokens.append(Token(TokenType.EOF, "", self.line, self.col))
        return self.tokens

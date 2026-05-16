from .ast_nodes import *  # noqa: F401,F403
from .lexer import Lexer
from .parser import Parser

__all__ = ["Lexer", "Parser", "parse_file", "parse_string"]


def parse_file(path: str) -> "JourneySpec":
    with open(path) as f:
        source = f.read()
    return parse_string(source, filename=path)


def parse_string(source: str, filename: str = "<string>") -> "JourneySpec":
    lexer = Lexer(source, filename)
    tokens = lexer.tokenize()
    parser = Parser(tokens, filename)
    return parser.parse()

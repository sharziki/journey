from .ast_nodes import *  # noqa: F401,F403
from .hybrid import HybridParseError, is_hybrid_source, parse_hybrid
from .lexer import Lexer
from .parser import Parser

__all__ = [
    "Lexer",
    "Parser",
    "parse_file",
    "parse_string",
    "parse_hybrid",
    "parse_file_auto",
    "parse_string_auto",
    "is_hybrid_source",
    "HybridParseError",
]


def parse_file(path: str) -> "JourneySpec":
    """Parse a structured .journey file (braced format only)."""
    with open(path) as f:
        source = f.read()
    return parse_string(source, filename=path)


def parse_string(source: str, filename: str = "<string>") -> "JourneySpec":
    """Parse a structured .journey string (braced format only)."""
    lexer = Lexer(source, filename)
    tokens = lexer.tokenize()
    parser = Parser(tokens, filename)
    return parser.parse()


def parse_file_auto(path: str):
    """Parse a .journey file, auto-detecting structured vs hybrid format.

    Returns JourneySpec for structured files or HybridJourneySpec for hybrid.
    """
    with open(path) as f:
        source = f.read()
    return parse_string_auto(source, filename=path)


def parse_string_auto(source: str, filename: str = "<string>"):
    """Parse a .journey string, auto-detecting structured vs hybrid format.

    Returns JourneySpec for structured files or HybridJourneySpec for hybrid.
    """
    if is_hybrid_source(source):
        return parse_hybrid(source, filename)
    return parse_string(source, filename)

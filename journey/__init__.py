"""Journey: an executable story format for software agents."""

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import tomllib

from .core import normalize, validate
from .parser import parse_file, parse_string


def _version() -> str:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    if pyproject.exists():
        data = tomllib.loads(pyproject.read_text())
        return data["project"]["version"]
    try:
        return version("journey-lang")
    except PackageNotFoundError:
        return "0.0.0"


__version__ = _version()

__all__ = ["__version__", "normalize", "parse_file", "parse_string", "validate"]

"""
Code generator: AST -> FastAPI project.

Takes a parsed JourneySpec and produces a complete, runnable Python project:
  - models.py     (SQLAlchemy models + state machines)
  - schemas.py    (Pydantic request/response schemas)
  - routes.py     (FastAPI endpoints for each step)
  - database.py   (DB engine + session factory)
  - app.py        (FastAPI app entrypoint)
  - test_journey.py (pytest tests from journey test blocks)
"""

import os
from pathlib import Path

from ..parser.ast_nodes import (
    Entity,
    EnumType,
    Field,
    JourneySpec,
    Step,
)
from .gen_models import generate_models
from .gen_schemas import generate_schemas
from .gen_routes import generate_routes
from .gen_database import generate_database
from .gen_app import generate_app
from .gen_tests import generate_tests


def generate(spec: JourneySpec, output_dir: str) -> list[str]:
    """Generate a complete FastAPI project from a JourneySpec.

    Returns list of generated file paths.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    files = []

    def write(name: str, content: str) -> str:
        path = out / name
        path.write_text(content)
        files.append(str(path))
        return str(path)

    write("__init__.py", "")
    write("models.py", generate_models(spec))
    write("schemas.py", generate_schemas(spec))
    write("database.py", generate_database(spec))
    write("routes.py", generate_routes(spec))
    write("app.py", generate_app(spec))
    write("test_journey.py", generate_tests(spec))

    return files

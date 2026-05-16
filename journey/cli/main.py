"""
Journey CLI — compile, test, and run journey specs.

Usage:
    journey compile <file.journey> [-o output_dir]
    journey test <file.journey>
    journey run <file.journey> [--port 8000]
    journey inspect <file.journey>
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def cmd_compile(args):
    """Parse a .journey file and generate a FastAPI project."""
    from ..parser import parse_file
    from ..codegen import generate

    source = args.file
    output = args.output or _default_output_dir(source)

    print(f"Parsing {source}...")
    spec = parse_file(source)
    print(f"  Journey: {spec.name}")
    print(f"  Entities: {len(spec.entities)}")
    print(f"  Steps: {len(spec.steps)}")
    print(f"  Tests: {len(spec.tests)}")

    print(f"\nGenerating to {output}/...")
    files = generate(spec, output)
    for f in files:
        print(f"  {f}")

    print(f"\nDone. {len(files)} files generated.")
    print(f"\nNext steps:")
    print(f"  journey test {source}    # run tests")
    print(f"  journey run {source}     # start the server")


def cmd_test(args):
    """Compile and run tests for a .journey file."""
    from ..parser import parse_file
    from ..codegen import generate

    source = args.file
    output = args.output or _default_output_dir(source)

    print(f"Compiling {source}...")
    spec = parse_file(source)
    generate(spec, output)

    print(f"Running tests...")
    output_path = Path(output).resolve()
    test_file = output_path / "test_journey.py"
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-xvs", str(test_file)],
        cwd=str(output_path.parent),
    )
    sys.exit(result.returncode)


def cmd_run(args):
    """Compile and start the FastAPI server."""
    from ..parser import parse_file
    from ..codegen import generate

    source = args.file
    output = args.output or _default_output_dir(source)
    port = args.port or 8000

    print(f"Compiling {source}...")
    spec = parse_file(source)
    generate(spec, output)

    # Determine the module path
    output_path = Path(output)
    module_name = output_path.name

    print(f"\nStarting server on port {port}...")
    print(f"  API docs: http://localhost:{port}/docs")
    print(f"  Journey routes: http://localhost:{port}/journey/")

    result = subprocess.run(
        [sys.executable, "-m", "uvicorn", f"{module_name}.app:app",
         "--reload", "--port", str(port)],
        cwd=str(output_path.parent),
    )
    sys.exit(result.returncode)


def cmd_inspect(args):
    """Parse and display the AST for a .journey file."""
    from ..parser import parse_file

    spec = parse_file(args.file)

    print(f"Journey: {spec.name}")
    if spec.description:
        print(f"  {spec.description}")
    print()

    print("Entities:")
    for entity in spec.entities:
        print(f"  {entity.name}")
        for field in entity.fields:
            mods = []
            if field.modifiers.unique:
                mods.append("unique")
            if field.modifiers.hashed:
                mods.append("hashed")
            if field.modifiers.auto:
                mods.append("auto")
            mod_str = f" [{', '.join(mods)}]" if mods else ""
            if field.state_type:
                states = " -> ".join(field.state_type.states)
                print(f"    {field.name}: state({states}){mod_str}")
            elif field.enum_type:
                vals = ", ".join(field.enum_type.values)
                print(f"    {field.name}: enum({vals}){mod_str}")
            else:
                print(f"    {field.name}: {field.type_name}{mod_str}")

    print()
    print("Steps:")
    for step in spec.steps:
        req = f" (requires {step.requires})" if step.requires else ""
        auth = " [authenticated]" if step.actor.authenticated else ""
        print(f"  {step.name}{req}{auth}")
        for inp in step.inputs:
            req_str = " required" if inp.required else ""
            print(f"    input:  {inp.name} ({inp.type_name}){req_str}")
        for out in step.outputs:
            print(f"    output: {out.name} = {out.expression}")
        for err in step.errors:
            print(f"    error:  {err.code_name} [{err.http_status}]")

    print()
    print("Tests:")
    for test in spec.tests:
        print(f"  \"{test.name}\" ({len(test.commands)} steps)")


def _default_output_dir(source: str) -> str:
    """Derive output directory from source file."""
    name = Path(source).stem
    return os.path.join("generated", name)


def main():
    parser = argparse.ArgumentParser(
        prog="journey",
        description="Journey — a language for backend workflows"
    )
    sub = parser.add_subparsers(dest="command")

    # compile
    p_compile = sub.add_parser("compile", help="Compile a .journey file to FastAPI")
    p_compile.add_argument("file", help="Path to .journey file")
    p_compile.add_argument("-o", "--output", help="Output directory")

    # test
    p_test = sub.add_parser("test", help="Compile and run tests")
    p_test.add_argument("file", help="Path to .journey file")
    p_test.add_argument("-o", "--output", help="Output directory")

    # run
    p_run = sub.add_parser("run", help="Compile and start server")
    p_run.add_argument("file", help="Path to .journey file")
    p_run.add_argument("-o", "--output", help="Output directory")
    p_run.add_argument("--port", type=int, default=8000, help="Server port")

    # inspect
    p_inspect = sub.add_parser("inspect", help="Parse and display journey AST")
    p_inspect.add_argument("file", help="Path to .journey file")

    args = parser.parse_args()

    if args.command == "compile":
        cmd_compile(args)
    elif args.command == "test":
        cmd_test(args)
    elif args.command == "run":
        cmd_run(args)
    elif args.command == "inspect":
        cmd_inspect(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

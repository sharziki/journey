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

from ..core.config import RobustnessConfig


def cmd_compile(args):
    """Parse a .journey file and generate a FastAPI project."""
    from ..parser import parse_file
    from ..adapters.fastapi import generate

    source = args.file
    output = args.output or _default_output_dir(source)
    config = _config_from_args(args)

    print(f"Parsing {source}...")
    spec = parse_file(source)
    print(f"  Journey: {spec.name}")
    print(f"  Entities: {len(spec.entities)}")
    print(f"  Steps: {len(spec.steps)}")
    print(f"  Tests: {len(spec.tests)}")

    print(f"\nGenerating to {output}/...")
    result = generate(spec, output, config=config)
    files = result.files
    for f in files:
        print(f"  {f}")

    print(f"\nDone. {len(files)} files generated.")
    print(f"\nNext steps:")
    print(f"  journey test {source}    # run tests")
    print(f"  journey run {source}     # start the server")


def cmd_test(args):
    """Compile and run tests for a .journey file."""
    from ..parser import parse_file
    from ..adapters.fastapi import generate

    source = args.file
    output = args.output or _default_output_dir(source)
    config = _config_from_args(args).with_overrides(run_generated_tests=True)

    print(f"Compiling {source}...")
    spec = parse_file(source)
    generate(spec, output, config=config)

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
    from ..adapters.fastapi import generate

    source = args.file
    output = args.output or _default_output_dir(source)
    port = args.port or 8000
    config = _config_from_args(args)

    print(f"Compiling {source}...")
    spec = parse_file(source)
    generate(spec, output, config=config)

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
    from ..core import normalize, validate

    spec = parse_file(args.file)
    report = validate(spec, strict=args.strict)
    journey = normalize(spec)

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

    print()
    print("Agent checklist:")
    for item in journey.checklist():
        print(f"  [ ] {item}")

    print()
    print("Validation:")
    if report.ok and not report.warnings:
        print("  ok")
    else:
        for issue in report.issues:
            print(f"  {issue.severity}: {issue.code} at {issue.path} — {issue.message}")
        report.raise_for_errors()


def cmd_validate(args):
    """Validate a .journey file."""
    from ..parser import parse_file
    from ..core import validate

    report = validate(parse_file(args.file), strict=args.strict)
    if report.ok and not report.warnings:
        print("ok")
        return
    for issue in report.issues:
        print(f"{issue.severity}: {issue.code} at {issue.path} — {issue.message}")
    report.raise_for_errors()


def cmd_manifest(args):
    """Generate agent-readable manifest files without the FastAPI app."""
    from ..parser import parse_file
    from ..adapters.markdown import write_markdown
    from ..adapters.fastapi import _write_agent_manifest

    source = args.file
    output = args.output or _default_output_dir(source)
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    spec = parse_file(source)
    files = [
        write_markdown(spec, out),
        _write_agent_manifest(spec, out, _config_from_args(args)),
    ]
    for path in files:
        print(path)


def _default_output_dir(source: str) -> str:
    """Derive output directory from source file."""
    name = Path(source).stem
    return os.path.join("generated", name)


def _add_robustness_args(parser):
    parser.add_argument(
        "--robustness",
        choices=["fast", "standard", "strict"],
        default="standard",
        help="Generation robustness profile. Use strict before publishing.",
    )
    parser.add_argument("--strict", action="store_true", help="Treat validator warnings as errors")
    parser.add_argument("--clean", action="store_true", help="Delete the output directory before generating")
    parser.add_argument("--no-agent-manifest", action="store_true", help="Skip journey.agent.json")
    parser.add_argument("--no-markdown-summary", action="store_true", help="Skip JOURNEY.md")


def _config_from_args(args) -> RobustnessConfig:
    config = RobustnessConfig.from_profile(getattr(args, "robustness", "standard"))
    return config.with_overrides(
        strict_validation=True if getattr(args, "strict", False) else None,
        fail_on_warnings=True if getattr(args, "strict", False) else None,
        clean_output=True if getattr(args, "clean", False) else None,
        generate_agent_manifest=False if getattr(args, "no_agent_manifest", False) else None,
        generate_markdown_summary=False if getattr(args, "no_markdown_summary", False) else None,
    )


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
    _add_robustness_args(p_compile)

    # test
    p_test = sub.add_parser("test", help="Compile and run tests")
    p_test.add_argument("file", help="Path to .journey file")
    p_test.add_argument("-o", "--output", help="Output directory")
    _add_robustness_args(p_test)

    # run
    p_run = sub.add_parser("run", help="Compile and start server")
    p_run.add_argument("file", help="Path to .journey file")
    p_run.add_argument("-o", "--output", help="Output directory")
    p_run.add_argument("--port", type=int, default=8000, help="Server port")
    _add_robustness_args(p_run)

    # inspect
    p_inspect = sub.add_parser("inspect", help="Parse and display journey AST")
    p_inspect.add_argument("file", help="Path to .journey file")
    p_inspect.add_argument("--strict", action="store_true", help="Treat validator warnings as errors")

    # validate
    p_validate = sub.add_parser("validate", help="Validate a journey file")
    p_validate.add_argument("file", help="Path to .journey file")
    p_validate.add_argument("--strict", action="store_true", help="Treat warnings as errors")

    # manifest
    p_manifest = sub.add_parser("manifest", help="Generate agent-readable Journey artifacts")
    p_manifest.add_argument("file", help="Path to .journey file")
    p_manifest.add_argument("-o", "--output", help="Output directory")
    _add_robustness_args(p_manifest)

    args = parser.parse_args()

    if args.command == "compile":
        cmd_compile(args)
    elif args.command == "test":
        cmd_test(args)
    elif args.command == "run":
        cmd_run(args)
    elif args.command == "inspect":
        cmd_inspect(args)
    elif args.command == "validate":
        cmd_validate(args)
    elif args.command == "manifest":
        cmd_manifest(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

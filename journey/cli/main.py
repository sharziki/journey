"""
Journey CLI — compile, test, and run journey specs.

Usage:
    journey compile <file.journey> [-o output_dir]
    journey test <file.journey>
    journey run <file.journey> [--port 8000]
    journey inspect <file.journey>
"""

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from .. import __version__
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
    from ..core.graph import load_journey_graph, validate_journey_graph

    if _is_hybrid_journey(args.file):
        _inspect_hybrid(args)
        return

    if not _is_structured_journey(args.file):
        graph = load_journey_graph(args.file)
        issues = validate_journey_graph(graph)
        print(f"Journey Graph: {graph.root.name}")
        print(f"  Root: {graph.root.path}")
        print(f"  Files: {len(graph.nodes)}")
        print()
        print("Journeys:")
        for node in graph.nodes:
            rel = node.path.relative_to(graph.root.path.parent)
            level = f" [{node.level}]" if node.level else ""
            print(f"  {rel}{level}")
            if node.parent:
                print(f"    parent: {node.parent}")
            for child in node.children:
                print(f"    child:  {child}")
        print()
        print("Agent checklist:")
        for item in graph.checklist():
            print(f"  [ ] {item}")
        print()
        print("Validation:")
        if not issues:
            print("  ok")
            return
        for issue in issues:
            print(f"  {issue.severity}: {issue.code} at {issue.path} — {issue.message}")
        if any(issue.severity == "error" for issue in issues):
            sys.exit(1)
        return

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
    from ..core.graph import load_journey_graph, validate_journey_graph

    if _is_hybrid_journey(args.file):
        from ..parser.hybrid import parse_hybrid
        from ..core.validation import validate_hybrid

        spec = parse_hybrid(Path(args.file).read_text(), filename=args.file)
        report = validate_hybrid(spec, strict=args.strict)
        if report.ok and not report.warnings:
            print("ok")
            return
        for issue in report.issues:
            print(f"{issue.severity}: {issue.code} at {issue.path} — {issue.message}")
        report.raise_for_errors()
        return

    if not _is_structured_journey(args.file):
        graph = load_journey_graph(args.file)
        issues = validate_journey_graph(graph)
        if not issues:
            print("ok")
            return
        for issue in issues:
            print(f"{issue.severity}: {issue.code} at {issue.path} — {issue.message}")
        if any(issue.severity == "error" for issue in issues):
            sys.exit(1)
        return

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
    from ..core.graph import load_journey_graph, write_graph_handoff

    source = args.file

    if _is_hybrid_journey(source):
        output = args.output or str(Path(".journey") / "handoff")
        out = Path(output)
        out.mkdir(parents=True, exist_ok=True)
        files = _write_hybrid_handoff(source, out)
        for path in files:
            print(path)
        return

    structured = _is_structured_journey(source)
    output = args.output or (_default_output_dir(source) if structured else str(Path(".journey") / "handoff"))
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    if not structured:
        graph = load_journey_graph(source)
        files = write_graph_handoff(graph, out)
        for path in files:
            print(path)
        return

    spec = parse_file(source)
    files = [
        write_markdown(spec, out),
        _write_agent_manifest(spec, out, _config_from_args(args)),
    ]
    for path in files:
        print(path)


def cmd_create(args):
    """Create a Journey file tree or a flow document for an existing journey."""
    from ..parser import parse_file
    from ..adapters.flow import write_flow_markdown
    from ..core.scaffold import scaffold_journeys

    source = Path(args.file or ".")
    if source.is_file() and source.suffix == ".journey":
        output = args.output or _default_output_dir(str(source))
        spec = parse_file(str(source))
        path = write_flow_markdown(spec, output, args.filename)

        print(f"Created journey flow document: {path}")
        print("Use it to review routes, features, data, and acceptance walkthroughs without opening the app.")
        return

    target = source if source.is_dir() or source.suffix == "" else source.parent
    result = scaffold_journeys(target, name=args.name, force=args.force, flow_filename=args.filename)
    print(f"Created folder-level journeys in {result.root}/")
    for path in result.files:
        print(f"  {path}")
    print("Read repo.journey first, then follow children to the page-level journeys.")


def cmd_sync(args):
    """Sync a folder-level Journey graph with the project tree."""
    from ..core.scaffold import sync_journeys

    source = Path(args.file or ".")
    target = source if source.is_dir() or source.suffix == "" else source.parent
    result = sync_journeys(target, name=args.name, force=args.force)
    print(f"Synced folder-level journeys in {result.root}/")
    for path in result.files:
        print(f"  {path}")
    print("Existing child journeys were preserved unless --force was used.")


def cmd_doctor(args):
    """Check whether a lightweight Journey graph is healthy."""
    from ..core.doctor import doctor_journey

    issues = doctor_journey(args.file or ".")
    if not issues:
        print("Journey doctor: ok")
        return

    print("Journey doctor found issues:")
    for issue in issues:
        print(f"{issue.severity}: {issue.code} at {issue.path} — {issue.message}")
    if any(issue.severity == "error" for issue in issues):
        sys.exit(1)
    if getattr(args, "strict", False):
        sys.exit(1)


def cmd_diff(args):
    """Show drift between the project tree and lightweight Journey graph."""
    from ..core.doctor import doctor_journey

    issues = doctor_journey(args.file or ".")
    drift_codes = {
        "missing_child",
        "missing_parent",
        "missing_journey",
        "orphan_journey",
        "stale_route",
        "stale_source",
        "unloaded_child",
    }
    drift = [issue for issue in issues if issue.code in drift_codes]
    if not drift:
        print("Journey diff: no drift")
        return

    print("Journey diff:")
    for issue in drift:
        marker = _diff_marker(issue.code)
        print(f"{marker} {issue.code}: {issue.message}")
        print(f"  {issue.path}")
    print()
    print("Suggested next step:")
    print(f"  journey sync {args.file or '.'}")
    if getattr(args, "check", False):
        sys.exit(1)


def cmd_status(args):
    """Print a concise Journey status summary."""
    if _is_hybrid_journey(args.file):
        from ..parser.hybrid import parse_hybrid
        from ..core.validation import validate_hybrid
        from ..core.normalize import normalize_hybrid

        spec = parse_hybrid(Path(args.file).read_text(), filename=args.file)
        report = validate_hybrid(spec, strict=False)
        journey = normalize_hybrid(spec)
        print(f"Journey: {spec.name}")
        print("Mode: hybrid")
        print(f"Pages: {len(journey.pages)}")
        print(f"Flows: {len(journey.flows)}")
        print(f"Entities: {len(spec.entities)}")
        print(f"Steps: {len(spec.steps)}")
        print(f"Tests: {len(spec.tests)}")
        print(f"Acceptance: {len(spec.acceptance)} item(s)")
        print(f"Validation: {'ok' if report.ok else 'issues'}")
        print(f"Next: journey inspect {args.file}")
        return

    if _is_structured_journey(args.file):
        from ..parser import parse_file
        from ..core import validate

        spec = parse_file(args.file)
        report = validate(spec, strict=False)
        print(f"Journey: {spec.name}")
        print("Mode: structured backend")
        print(f"Entities: {len(spec.entities)}")
        print(f"Steps: {len(spec.steps)}")
        print(f"Tests: {len(spec.tests)}")
        print(f"Validation: {'ok' if report.ok else 'issues'}")
        print(f"Next: journey agent {args.file}")
        return

    from ..core.doctor import doctor_journey
    from ..core.graph import load_journey_graph
    from ..core.scaffold import detect_candidates

    source = args.file or "."
    graph = load_journey_graph(source)
    project = _project_root_for_status(source)
    candidates = detect_candidates(project)
    issues = doctor_journey(source)
    missing = [issue for issue in issues if issue.code == "missing_journey"]
    drift = [
        issue
        for issue in issues
        if issue.code
        in {"missing_child", "missing_parent", "missing_journey", "orphan_journey", "stale_route", "stale_source", "unloaded_child"}
    ]
    pages_total = sum(1 for candidate in candidates if candidate.level == "page")
    apis_total = sum(1 for candidate in candidates if candidate.level == "api")
    pages_missing = sum(1 for issue in missing if _issue_level(issue) == "page")
    apis_missing = sum(1 for issue in missing if _issue_level(issue) == "api")

    print(f"Journey: {graph.root.name}")
    print("Mode: lightweight graph")
    print(f"Files: {len(graph.nodes)} journeys")
    print(f"Pages: {pages_total - pages_missing} covered / {pages_missing} missing")
    print(f"APIs: {apis_total - apis_missing} covered / {apis_missing} missing")
    print(f"Drift: {'none' if not drift else str(len(drift)) + ' issue(s)'}")
    print(f"Warnings: {len([issue for issue in issues if issue.severity == 'warning'])}")
    print(f"Errors: {len([issue for issue in issues if issue.severity == 'error'])}")
    print(f"Next: {_status_next(args.file, drift)}")


def cmd_agent(args):
    """Prepare and verify a journey for coding agents."""
    source = args.file

    if _is_hybrid_journey(source):
        output = args.output or str(Path(".journey") / "handoff")
        out = Path(output)
        out.mkdir(parents=True, exist_ok=True)
        files = _write_hybrid_handoff(source, out)
        print("\nAgent handoff:")
        for i, path in enumerate(files, 1):
            print(f"  {i}. Read {path}")
        print(f"  {len(files) + 1}. Implement or repair the app against the journey spec")
        print(f"  {len(files) + 2}. Re-run: journey agent {source}")
        if args.no_test:
            print("\nSkipped project QA (--no-test).")
            return
        returncode = _run_project_qa()
        if returncode == 0:
            print("\nJourney handoff accepted: hybrid journey is ready for agents.")
        else:
            print("\nProject QA failed. Use the failure output as the next agent work item.")
        sys.exit(returncode)

    structured = _is_structured_journey(source)
    output = args.output or (_default_output_dir(source) if structured else str(Path(".journey") / "handoff"))
    if not structured:
        markdown_path, manifest_path = _prepare_lightweight_agent_workspace(source, output)
        print("\nAgent handoff:")
        print(f"  1. Read {markdown_path}")
        print(f"  2. Read {manifest_path}")
        print("  3. Implement or repair the app against the linked journey map")
        print(f"  4. Re-run: journey agent {source}")
        if args.no_test:
            print("\nSkipped project QA (--no-test).")
            return
        returncode = _run_project_qa()
        if returncode == 0:
            print("\nJourney handoff accepted: lightweight graph is ready for agents.")
        else:
            print("\nProject QA failed. Use the failure output as the next agent work item.")
        sys.exit(returncode)

    config = _config_from_args(args).with_overrides(
        strict_validation=True,
        fail_on_warnings=True,
        generate_agent_manifest=True,
        generate_markdown_summary=True,
    )

    _prepare_agent_workspace(source, output, config)

    print("\nAgent handoff:")
    print(f"  1. Read {Path(output) / 'JOURNEY.md'}")
    print(f"  2. Read {Path(output) / 'journey.agent.json'}")
    print("  3. Implement or repair the code until acceptance passes")
    print(f"  4. Re-run: journey agent {source}")

    if args.no_test:
        print("\nSkipped generated tests (--no-test).")
        return

    returncode = _run_agent_qa(output)
    if returncode == 0:
        print("\nJourney accepted: generated implementation satisfies current acceptance tests.")
    else:
        print("\nJourney needs repair: use the failure output as the next agent work item.")
    sys.exit(returncode)


def cmd_watch(args):
    """Run the journey builder/QA loop deliverable by deliverable."""
    from ..parser import parse_file
    from ..core import normalize
    from ..core.graph import load_journey_graph

    if _is_hybrid_journey(args.file):
        from ..parser.hybrid import parse_hybrid
        from ..core.normalize import normalize_hybrid

        spec = parse_hybrid(Path(args.file).read_text(), filename=args.file)
        journey = normalize_hybrid(spec)
        output = args.output or str(Path(".journey") / "handoff" / journey.slug)
        _run_watch_loop(
            args=args,
            source=args.file,
            output=output,
            journey_name=journey.name,
            journey_slug=journey.slug,
            checklist=list(journey.checklist()),
            prepare=lambda: _write_hybrid_handoff(args.file, Path(output)),
            qa_label="project checks",
            qa_runner=_run_project_qa,
            success_label="Deliverable accepted",
        )
        return

    if not _is_structured_journey(args.file):
        graph = load_journey_graph(args.file)
        checklist = graph.checklist()
        output = args.output or str(Path(".journey") / "handoff")
        _run_watch_loop(
            args=args,
            source=args.file,
            output=output,
            journey_name=graph.root.name,
            journey_slug=graph.slug,
            checklist=checklist,
            prepare=lambda: _prepare_lightweight_agent_workspace(args.file, output),
            qa_label="project checks",
            qa_runner=_run_project_qa,
            success_label="Journey handoff accepted",
        )
        return

    source = args.file
    output = args.output or _default_output_dir(source)
    config = _config_from_args(args).with_overrides(
        strict_validation=True,
        fail_on_warnings=True,
        generate_agent_manifest=True,
        generate_markdown_summary=True,
    )

    spec = parse_file(source)
    journey = normalize(spec)
    checklist = list(journey.checklist())
    _run_watch_loop(
        args=args,
        source=source,
        output=output,
        journey_name=journey.name,
        journey_slug=journey.slug,
        checklist=checklist,
        prepare=lambda: _prepare_agent_workspace(source, output, config),
        qa_label="generated acceptance tests",
        qa_runner=lambda: _run_agent_qa(output),
        success_label="Deliverable accepted",
    )


def cmd_execute(args):
    """Execute a journey, optionally with an autonomous coding agent loop."""
    if _is_hybrid_journey(args.file):
        _execute_hybrid(args)
        return
    if not _is_structured_journey(args.file):
        if Path(args.file).is_dir() or _looks_linked_journey(Path(args.file)):
            if not args.autonomous:
                agent_args = argparse.Namespace(**vars(args))
                agent_args.no_test = False
                cmd_agent(agent_args)
                return

            command = _autonomous_agent_command()
            if command is None:
                print("No supported autonomous coding agent runtime found.")
                print("Install Codex CLI or set JOURNEY_AGENT_COMMAND, then rerun:")
                print(f"  journey execute {args.file} --autonomous")
                sys.exit(2)

            watch_args = argparse.Namespace(**vars(args))
            watch_args.agent_command = command
            watch_args.once = args.once
            watch_args.max_cycles = args.max_cycles
            cmd_watch(watch_args)
            return
        cmd_execute_natural(args)
        return

    if not args.autonomous:
        agent_args = argparse.Namespace(**vars(args))
        agent_args.no_test = False
        cmd_agent(agent_args)
        return

    command = _autonomous_agent_command()
    if command is None:
        print("No supported autonomous coding agent runtime found.")
        print("Install Codex CLI or set JOURNEY_AGENT_COMMAND, then rerun:")
        print(f"  journey execute {args.file} --autonomous")
        sys.exit(2)

    watch_args = argparse.Namespace(**vars(args))
    watch_args.agent_command = command
    watch_args.once = args.once
    watch_args.max_cycles = args.max_cycles
    cmd_watch(watch_args)


def cmd_execute_natural(args):
    """Shape and execute a handwritten natural-language journey."""
    from ..core.natural import shape_unstructured_journey, write_natural_handoff

    source = Path(args.file)
    journey = shape_unstructured_journey(source.read_text(), filename=str(source))
    output = args.output or str(Path(".journey") / "handoff" / journey.slug)
    shaped_path, markdown_path, manifest_path = write_natural_handoff(journey, output)
    checklist = journey.checklist()
    state_path = _watch_state_path(args.state_dir, journey.slug)
    state = _load_watch_state(state_path)
    completed = set(state.get("completed", []))

    print("Shaped handwritten journey:")
    print(f"  {shaped_path}")
    print("Agent handoff:")
    print(f"  {markdown_path}")
    print(f"  {manifest_path}")

    if not args.autonomous:
        print("\nRun autonomously with:")
        print(f"  journey execute {args.file} --autonomous")
        return

    command = _autonomous_agent_command()
    if command is None:
        print("No supported autonomous coding agent runtime found.")
        print("Install Codex CLI or set JOURNEY_AGENT_COMMAND, then rerun:")
        print(f"  journey execute {args.file} --autonomous")
        sys.exit(2)

    cycles = 0
    while cycles < args.max_cycles:
        current_index = _next_incomplete_index(checklist, completed)
        _print_watch_dashboard(journey.name, checklist, completed, current_index)
        if current_index is None:
            print("\nJourney complete: all deliverables are marked complete.")
            return

        item = checklist[current_index]
        print(f"\nBuilder session target [{current_index + 1}/{len(checklist)}]: {item}")
        builder_args = argparse.Namespace(agent_command=command)
        builder_code = _run_builder_session(
            builder_args,
            str(source),
            output,
            item,
            current_index,
            len(checklist),
        )
        if builder_code != 0:
            print("\nBuilder session failed. Fix that before QA can advance the journey.")
            sys.exit(builder_code)

        print("\nQA agent: running available project checks...")
        qa_code = _run_project_qa()
        if qa_code != 0:
            print("\nQA failed. Keeping the current deliverable active for repair.")
            sys.exit(qa_code)

        completed.add(item)
        _save_watch_state(state_path, {"journey": journey.name, "slug": journey.slug, "completed": sorted(completed)})
        print(f"\nQA passed. Deliverable accepted: {item}")
        print("Triggering next deliverable...")
        cycles += 1
        if args.once:
            break

    next_index = _next_incomplete_index(checklist, completed)
    _print_watch_dashboard(journey.name, checklist, completed, next_index)
    if next_index is None:
        print("\nJourney complete: all deliverables are marked complete.")
    else:
        print("\nPaused. Re-run the same execute command to continue.")


def cmd_shape(args):
    """Convert loose handwritten text into a readable Journey brief."""
    from ..core.natural import shape_unstructured_journey, write_natural_handoff

    source = Path(args.file)
    journey = shape_unstructured_journey(source.read_text(), filename=str(source))
    output = args.output or str(Path(".journey") / "handoff" / journey.slug)
    shaped_path, markdown_path, manifest_path = write_natural_handoff(journey, output)
    print(shaped_path)
    print(markdown_path)
    print(manifest_path)


def _default_output_dir(source: str) -> str:
    """Derive output directory from source file."""
    name = Path(source).stem
    return os.path.join("generated", name)


def _prepare_agent_workspace(source: str, output: str, config: RobustnessConfig):
    from ..parser import parse_file
    from ..adapters.fastapi import generate

    print(f"Reading journey source of truth: {source}")
    spec = parse_file(source)

    print(f"Preparing agent workspace: {output}/")
    result = generate(spec, output, config=config)
    for path in result.files:
        print(f"  {path}")
    return result


def _prepare_lightweight_agent_workspace(source: str, output: str) -> tuple[str, str]:
    from ..core.graph import load_journey_graph, write_graph_handoff
    from ..core.natural import shape_unstructured_journey, write_natural_handoff
    from ..core.scaffold import scaffold_journeys

    path = Path(source)
    if path.is_dir() and not (path / ".journey" / "repo.journey").exists() and not (path / "repo.journey").exists():
        print(f"No journey graph found in {source}; scaffolding lightweight journeys first.")
        scaffold_journeys(path)
    if path.is_dir() or _looks_linked_journey(path):
        print(f"Reading lightweight journey graph: {source}")
        graph = load_journey_graph(source)
        print(f"Preparing lightweight agent handoff: {output}/")
        markdown_path, manifest_path = write_graph_handoff(graph, output)
        print(f"  {markdown_path}")
        print(f"  {manifest_path}")
        return markdown_path, manifest_path

    print(f"Shaping handwritten journey: {source}")
    journey = shape_unstructured_journey(path.read_text(), filename=str(path))
    print(f"Preparing lightweight agent handoff: {output}/")
    _, markdown_path, manifest_path = write_natural_handoff(journey, output)
    print(f"  {markdown_path}")
    print(f"  {manifest_path}")
    return markdown_path, manifest_path


def _run_agent_qa(output: str) -> int:
    output_path = Path(output).resolve()
    if not output_path.name.isidentifier():
        print(
            f"Cannot run generated QA for {output_path}: output directory "
            "must be a valid Python package name."
        )
        return 2
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", str(output_path.name)],
        cwd=str(output_path.parent),
    )
    return result.returncode


def _run_project_qa() -> int:
    if os.environ.get("JOURNEY_SKIP_PROJECT_QA") == "1":
        print("Project QA skipped by JOURNEY_SKIP_PROJECT_QA=1.")
        return 0
    if Path("tests").exists():
        return subprocess.run([sys.executable, "-m", "pytest", "-q"]).returncode
    print("No project test suite found; QA recorded as handoff-only for this pass.")
    return 0


def _watch_state_path(state_dir: str, slug: str) -> Path:
    return Path(state_dir) / f"{slug}.json"


def _load_watch_state(path: Path) -> dict:
    if not path.exists():
        return {"completed": []}
    return json.loads(path.read_text())


def _save_watch_state(path: Path, state: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n")


def _next_incomplete_index(checklist: list[str], completed: set[str]) -> int | None:
    for index, item in enumerate(checklist):
        if item not in completed:
            return index
    return None


def _run_watch_loop(
    *,
    args,
    source: str,
    output: str,
    journey_name: str,
    journey_slug: str,
    checklist: list[str],
    prepare,
    qa_label: str,
    qa_runner,
    success_label: str,
) -> None:
    state_path = _watch_state_path(args.state_dir, journey_slug)
    state = _load_watch_state(state_path)
    completed = set(state.get("completed", []))
    cycles = 0

    while cycles < args.max_cycles:
        current_index = _next_incomplete_index(checklist, completed)
        _print_watch_dashboard(journey_name, checklist, completed, current_index)

        if current_index is None:
            print("\nJourney complete: all deliverables are marked complete.")
            return

        item = checklist[current_index]
        print(f"\nBuilder session target [{current_index + 1}/{len(checklist)}]: {item}")
        prepare()

        builder_code = _run_builder_session(args, source, output, item, current_index, len(checklist))
        if builder_code != 0:
            print("\nBuilder session failed. Fix that before QA can advance the journey.")
            sys.exit(builder_code)

        print(f"\nQA agent: running {qa_label}...")
        qa_code = qa_runner()
        if qa_code != 0:
            print("\nQA failed. Keeping the current deliverable active for repair.")
            sys.exit(qa_code)

        completed.add(item)
        state = {"journey": journey_name, "slug": journey_slug, "completed": sorted(completed)}
        _save_watch_state(state_path, state)
        print(f"\nQA passed. {success_label}: {item}")
        print("Triggering next deliverable...")

        cycles += 1
        if args.once:
            break

    next_index = _next_incomplete_index(checklist, completed)
    _print_watch_dashboard(journey_name, checklist, completed, next_index)
    if next_index is None:
        print("\nJourney complete: all deliverables are marked complete.")
    else:
        print("\nPaused. Re-run the same watch command to continue.")


def _run_builder_session(args, source: str, output: str, item: str, index: int, total: int) -> int:
    command = args.agent_command or os.environ.get("JOURNEY_AGENT_COMMAND")
    if not command:
        print("\nNo builder command configured.")
        print("Set JOURNEY_AGENT_COMMAND or pass --agent-command to spawn a coding agent per deliverable.")
        print("Example:")
        print('  journey watch examples/auth_workspaces.journey --agent-command "codex exec ..."')
        print("Continuing directly to QA because the generated implementation is already present.")
        return 0

    values = {
        "journey_file": source,
        "output_dir": output,
        "item": item,
        "index": str(index + 1),
        "total": str(total),
        "handoff_md": str(Path(output) / "JOURNEY.md"),
        "handoff_json": str(Path(output) / "journey.agent.json"),
        "cwd": os.getcwd(),
    }
    formatted = command.format(**values)
    print("\nSpawning builder session:")
    print(f"  {formatted}")
    result = subprocess.run(shlex.split(formatted))
    return result.returncode


def _autonomous_agent_command() -> str | None:
    configured = os.environ.get("JOURNEY_AGENT_COMMAND")
    if configured:
        return configured
    if shutil.which("codex"):
        return (
            'codex exec -C "{cwd}" -s workspace-write '
            '"You are a Journey builder agent. Work only on deliverable {index}/{total}: {item}. '
            'Read {handoff_md} and {handoff_json}. Make the smallest correct changes needed, '
            'then stop so Journey can run QA."'
        )
    return None


def _is_hybrid_journey(path: str) -> bool:
    """Return True if the file is a hybrid (natural-language + structured) journey."""
    if Path(path).is_dir():
        return False
    try:
        from ..parser.hybrid import is_hybrid_source
        return is_hybrid_source(Path(path).read_text())
    except Exception:
        return False


def _is_structured_journey(path: str) -> bool:
    if Path(path).is_dir():
        return False
    try:
        from ..parser import parse_file

        parse_file(path)
        return True
    except Exception:
        return False


def _is_parseable_journey(path: str) -> bool:
    """Return True if the file can be parsed as either structured or hybrid."""
    return _is_structured_journey(path) or _is_hybrid_journey(path)


def _looks_linked_journey(path: Path) -> bool:
    if not path.exists() or not path.is_file():
        return False
    text = path.read_text()
    return "children:" in text or _contains_mapping_key(text, "parent") or _contains_mapping_key(text, "level")


def _contains_mapping_key(text: str, key: str) -> bool:
    import re

    return bool(re.search(rf"^\s*{re.escape(key)}\s*:", text, re.MULTILINE))


def _diff_marker(code: str) -> str:
    if code == "missing_journey":
        return "+"
    if code in {"missing_child", "missing_parent", "stale_route", "stale_source", "unloaded_child"}:
        return "-"
    if code == "orphan_journey":
        return "?"
    return "!"


def _project_root_for_status(source: str | None) -> Path:
    path = Path(source or ".").resolve()
    if path.is_dir():
        if path.name == ".journey":
            return path.parent
        return path
    parts = path.parts
    if ".journey" in parts:
        index = parts.index(".journey")
        return Path(*parts[:index]) if index > 0 else Path("/")
    return path.parent


def _issue_level(issue) -> str | None:
    path = issue.path.replace("\\", "/")
    if "/api/" in path or "/apis/" in path:
        return "api"
    if "/page." in path or "/pages/" in path:
        return "page"
    return None


def _status_next(source: str | None, drift: list) -> str:
    target = source or "."
    if drift:
        return f"journey diff {target}"
    return f"journey watch {target} --once"


def _execute_hybrid(args):
    """Execute a hybrid journey through the agent/QA loop."""
    from ..parser.hybrid import parse_hybrid
    from ..core.normalize import normalize_hybrid

    source = Path(args.file)
    spec = parse_hybrid(source.read_text(), filename=str(source))
    journey = normalize_hybrid(spec)
    output = args.output or str(Path(".journey") / "handoff" / journey.slug)
    checklist = list(journey.checklist())

    if not args.autonomous:
        agent_args = argparse.Namespace(**vars(args))
        agent_args.no_test = False
        cmd_agent(agent_args)
        return

    command = _autonomous_agent_command()
    if command is None:
        print("No supported autonomous coding agent runtime found.")
        print("Install Codex CLI or set JOURNEY_AGENT_COMMAND, then rerun:")
        print(f"  journey execute {args.file} --autonomous")
        sys.exit(2)

    _run_watch_loop(
        args=args,
        source=str(source),
        output=output,
        journey_name=journey.name,
        journey_slug=journey.slug,
        checklist=checklist,
        prepare=lambda: _write_hybrid_handoff(str(source), Path(output)),
        qa_label="project checks",
        qa_runner=_run_project_qa,
        success_label="Deliverable accepted",
    )


def _write_hybrid_handoff(source: str, output_dir: Path) -> list[str]:
    """Write agent handoff files for a hybrid journey."""
    from ..parser.hybrid import parse_hybrid
    from ..adapters.markdown import write_markdown
    from ..core.normalize import normalize_hybrid

    spec = parse_hybrid(Path(source).read_text(), filename=source)
    journey = normalize_hybrid(spec)

    output_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = write_markdown(spec, output_dir)
    manifest_path = output_dir / "journey.agent.json"
    payload = {
        "schema": "journey.agent.v1",
        "mode": "hybrid",
        "name": journey.name,
        "slug": journey.slug,
        "mission": journey.mission,
        "design": journey.design,
        "checklist": list(journey.checklist()),
        "pages": [
            {
                "name": page.name,
                "slug": page.slug,
                "purpose": page.purpose,
                "acceptance": list(page.acceptance),
            }
            for page in journey.pages
        ],
        "flows": [
            {
                "name": flow.name,
                "slug": flow.slug,
                "steps": list(flow.steps),
            }
            for flow in journey.flows
        ],
        "acceptance": list(journey.acceptance),
        "done_when": list(journey.done_when),
        "entities": [
            {
                "name": entity.name,
                "slug": entity.slug,
                "fields": [
                    {"name": f.name, "type_name": f.type_name, "modifiers": list(f.modifiers)}
                    for f in entity.fields
                ],
            }
            for entity in journey.entities
        ],
        "steps": [
            {
                "name": step.name,
                "slug": step.slug,
                "requires": step.requires,
                "actor": step.actor,
                "authenticated": step.authenticated,
            }
            for step in journey.steps
        ],
        "tests": [
            {"name": test.name, "slug": test.slug, "steps": list(test.steps)}
            for test in journey.tests
        ],
    }
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n")
    return [markdown_path, str(manifest_path)]


def _inspect_hybrid(args):
    """Inspect a hybrid journey file."""
    from ..parser.hybrid import parse_hybrid
    from ..core.normalize import normalize_hybrid
    from ..core.validation import validate_hybrid

    spec = parse_hybrid(Path(args.file).read_text(), filename=args.file)
    report = validate_hybrid(spec, strict=getattr(args, "strict", False))
    journey = normalize_hybrid(spec)

    print(f"Journey: {spec.name}")
    print("Mode: hybrid")
    if spec.mission:
        print(f"  Mission: {spec.mission}")
    if spec.design:
        print(f"  Design: {spec.design}")
    print()

    if spec.page_names or spec.pages:
        print("Pages:")
        all_names = list(spec.page_names)
        page_specs = {p.name for p in spec.pages}
        for p in spec.pages:
            if p.name not in set(spec.page_names):
                all_names.append(p.name)
        for name in all_names:
            has_spec = " (specified)" if name in page_specs else ""
            print(f"  {name}{has_spec}")
        print()

    if spec.flows:
        print("Flows:")
        for flow in spec.flows:
            if flow.steps:
                print(f"  {flow.name}: " + " -> ".join(flow.steps))
            else:
                print(f"  {flow.name}")
        print()

    if spec.entities:
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

    if spec.steps:
        print("Steps:")
        for step in spec.steps:
            req = f" (requires {step.requires})" if step.requires else ""
            auth = " [authenticated]" if step.actor.authenticated else ""
            print(f"  {step.name}{req}{auth}")
        print()

    if spec.tests:
        print("Tests:")
        for test in spec.tests:
            print(f"  \"{test.name}\" ({len(test.commands)} steps)")
        print()

    if spec.acceptance:
        print("Acceptance:")
        for item in spec.acceptance:
            print(f"  - {item}")
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


def _print_watch_dashboard(journey_name: str, checklist: list[str], completed: set[str], current_index: int | None):
    width = 78
    print()
    print("+" + "-" * width + "+")
    print("|" + " JOURNEY WATCH ".center(width) + "|")
    print("|" + journey_name.center(width) + "|")
    print("+" + "-" * width + "+")
    for index, item in enumerate(checklist):
        if item in completed:
            marker = "[x]"
        elif current_index == index:
            marker = "[>]"
        else:
            marker = "[ ]"
        label = f"{marker} {index + 1:02d}. {item}"
        print("| " + label[: width - 2].ljust(width - 2) + " |")
    print("+" + "-" * width + "+")
    if current_index is not None:
        print(f"current: {checklist[current_index]}")


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
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
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

    # create
    p_create = sub.add_parser("create", help="Create Journey files or a readable flow document")
    p_create.add_argument("file", nargs="?", help="Path to a .journey file or project directory")
    p_create.add_argument("-o", "--output", help="Output directory")
    p_create.add_argument("--name", help="Name to use when scaffolding a new journey tree")
    p_create.add_argument("--force", action="store_true", help="Overwrite scaffolded Journey files if they already exist")
    p_create.add_argument("--filename", default="JOURNEY_FLOW.md", help="Output markdown filename")

    # sync
    p_sync = sub.add_parser("sync", help="Sync linked Journey files with discovered pages and API routes")
    p_sync.add_argument("file", nargs="?", help="Path to a project directory")
    p_sync.add_argument("--name", help="Name to use for the repo journey")
    p_sync.add_argument("--force", action="store_true", help="Overwrite existing Journey files")

    # doctor
    p_doctor = sub.add_parser("doctor", help="Check lightweight Journey graph health")
    p_doctor.add_argument("file", nargs="?", help="Path to a project directory or Journey graph")
    p_doctor.add_argument("--strict", action="store_true", help="Exit non-zero on warnings")

    # diff
    p_diff = sub.add_parser("diff", help="Show drift between code files and linked Journey files")
    p_diff.add_argument("file", nargs="?", help="Path to a project directory or Journey graph")
    p_diff.add_argument("--check", action="store_true", help="Exit non-zero when drift is found")

    # status
    p_status = sub.add_parser("status", help="Show a concise Journey project summary")
    p_status.add_argument("file", nargs="?", default=".", help="Path to a project directory or .journey file")

    # agent
    p_agent = sub.add_parser("agent", help="Prepare a journey for an AI coding agent")
    p_agent.add_argument("file", help="Path to .journey file")
    p_agent.add_argument("-o", "--output", help="Output directory")
    p_agent.add_argument("--no-test", action="store_true", help="Prepare agent artifacts without running generated tests")
    _add_robustness_args(p_agent)

    # watch
    p_watch = sub.add_parser("watch", help="Run the builder/QA journey loop")
    p_watch.add_argument("file", help="Path to .journey file")
    p_watch.add_argument("-o", "--output", help="Output directory")
    p_watch.add_argument("--state-dir", default=".journey/state", help="Directory for journey watch state")
    p_watch.add_argument("--agent-command", help="Command template for one builder session per deliverable")
    p_watch.add_argument("--once", action="store_true", help="Run one deliverable and stop")
    p_watch.add_argument("--max-cycles", type=int, default=1, help="Maximum deliverables to advance in one run")
    _add_robustness_args(p_watch)

    # execute
    p_execute = sub.add_parser("execute", help="Execute a journey through the agent/QA loop")
    p_execute.add_argument("file", help="Path to .journey file")
    p_execute.add_argument("-o", "--output", help="Output directory")
    p_execute.add_argument("--autonomous", action="store_true", help="Auto-detect a coding agent runtime and run deliverables autonomously")
    p_execute.add_argument("--state-dir", default=".journey/state", help="Directory for journey execution state")
    p_execute.add_argument("--once", action="store_true", help="Run one deliverable and stop")
    p_execute.add_argument("--max-cycles", type=int, default=999, help="Maximum deliverables to advance in one autonomous run")
    _add_robustness_args(p_execute)

    # shape
    p_shape = sub.add_parser("shape", help="Shape unstructured writing into a readable Journey handoff")
    p_shape.add_argument("file", help="Path to handwritten .journey or text file")
    p_shape.add_argument("-o", "--output", help="Output directory")

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
    elif args.command == "create":
        cmd_create(args)
    elif args.command == "sync":
        cmd_sync(args)
    elif args.command == "doctor":
        cmd_doctor(args)
    elif args.command == "diff":
        cmd_diff(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "agent":
        cmd_agent(args)
    elif args.command == "watch":
        cmd_watch(args)
    elif args.command == "execute":
        cmd_execute(args)
    elif args.command == "shape":
        cmd_shape(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

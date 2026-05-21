"""Health checks for lightweight Journey graphs."""

from __future__ import annotations

import re
from pathlib import Path

from journey.core.graph import GraphIssue, JourneyGraph, load_journey_graph, validate_journey_graph
from journey.core.scaffold import _route_from_candidate, detect_candidates


def doctor_journey(source: str | Path) -> tuple[GraphIssue, ...]:
    project = _project_root(source)
    graph = load_journey_graph(source)
    issues = list(validate_journey_graph(graph))
    issues.extend(_missing_candidate_issues(project, graph))
    issues.extend(_orphan_journey_issues(project, graph))
    issues.extend(_stale_source_issues(project, graph))
    issues.extend(_stale_route_issues(project, graph))
    issues.extend(_missing_acceptance_issues(graph))
    return tuple(issues)


def _missing_candidate_issues(project: Path, graph: JourneyGraph) -> list[GraphIssue]:
    linked_sources = {
        source
        for node in graph.nodes
        if (source := _source_path(project, node)) is not None
    }
    issues = []
    for candidate in detect_candidates(project):
        if candidate.source is None:
            continue
        source = (project / candidate.source).resolve()
        if source not in linked_sources:
            issues.append(
                GraphIssue(
                    severity="warning",
                    code="missing_journey",
                    path=str(source),
                    message=f"Discovered {candidate.level} source has no linked journey: {candidate.source}",
                )
            )
    return issues


def _orphan_journey_issues(project: Path, graph: JourneyGraph) -> list[GraphIssue]:
    loaded = {node.path.resolve() for node in graph.nodes}
    journey_root = project / ".journey"
    if not journey_root.exists():
        return []
    issues = []
    for path in journey_root.rglob("*.journey"):
        resolved = path.resolve()
        if resolved not in loaded:
            issues.append(
                GraphIssue(
                    severity="warning",
                    code="orphan_journey",
                    path=str(path),
                    message="Journey file is not linked from the root journey graph",
                )
            )
    return issues


def _stale_source_issues(project: Path, graph: JourneyGraph) -> list[GraphIssue]:
    issues = []
    for node in graph.nodes:
        source = _source_path(project, node)
        if source is not None and not source.exists():
            issues.append(
                GraphIssue(
                    severity="warning",
                    code="stale_source",
                    path=str(node.path),
                    message=f"Journey source file no longer exists: {source.relative_to(project)}",
                )
            )
    return issues


def _stale_route_issues(project: Path, graph: JourneyGraph) -> list[GraphIssue]:
    routes_by_source = {
        (project / candidate.source).resolve(): _route_from_candidate(candidate)
        for candidate in detect_candidates(project)
        if candidate.source is not None
    }
    issues = []
    for node in graph.nodes:
        if node.level not in {"page", "api"}:
            continue
        source = _source_path(project, node)
        if source is None or source not in routes_by_source:
            continue
        expected = routes_by_source[source]
        if node.route != expected:
            issues.append(
                GraphIssue(
                    severity="warning",
                    code="stale_route",
                    path=str(node.path),
                    message=f"Journey route is `{node.route or 'missing'}` but source maps to `{expected}`",
                )
            )
    return issues


def _missing_acceptance_issues(graph: JourneyGraph) -> list[GraphIssue]:
    issues = []
    for node in graph.nodes:
        if node.level in {"page", "api"} and not re.search(r"^\s*acceptance\s*:", node.body, re.MULTILINE):
            issues.append(
                GraphIssue(
                    severity="warning",
                    code="missing_acceptance",
                    path=str(node.path),
                    message="Journey should include an acceptance section",
                )
            )
    return issues


def _project_root(source: str | Path) -> Path:
    path = Path(source).resolve()
    if path.is_dir():
        if path.name == ".journey":
            return path.parent
        return path
    parts = path.parts
    if ".journey" in parts:
        index = parts.index(".journey")
        return Path(*parts[:index]) if index > 0 else Path("/")
    return path.parent


def _source_path(project: Path, node) -> Path | None:
    match = re.search(r"^\s*source\s*:\s*(.+)$", node.body, re.MULTILINE)
    if not match:
        return None
    value = match.group(1).strip()
    if value == "unknown":
        return None
    path = (node.path.parent / value).resolve()
    try:
        path.relative_to(project)
    except ValueError:
        return None
    return path

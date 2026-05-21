"""Resolve lightweight linked Journey files."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from journey.core.normalize import slugify


@dataclass(frozen=True)
class JourneyNode:
    path: Path
    name: str
    level: str | None
    parent: str | None
    children: tuple[str, ...]
    body: str


@dataclass(frozen=True)
class JourneyGraph:
    root: JourneyNode
    nodes: tuple[JourneyNode, ...]

    @property
    def slug(self) -> str:
        return slugify(self.root.name)

    def checklist(self) -> list[str]:
        items = [f"Read root journey '{self.root.name}'"]
        for node in self.nodes:
            if node.path != self.root.path:
                items.append(f"Read linked {node.level or 'child'} journey '{node.name}'")
        items.extend(f"Resolve acceptance for '{node.name}'" for node in self.nodes)
        items.append("Repair drift between linked journeys and code")
        return items


@dataclass(frozen=True)
class GraphIssue:
    severity: str
    code: str
    path: str
    message: str


def load_journey_graph(source: str | Path) -> JourneyGraph:
    root = _resolve_root(source)
    nodes: list[JourneyNode] = []
    seen: set[Path] = set()
    _walk(root, nodes, seen)
    return JourneyGraph(root=nodes[0], nodes=tuple(nodes))


def write_graph_handoff(graph: JourneyGraph, output_dir: str | Path) -> tuple[str, str]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    markdown_path = out / "JOURNEY.md"
    manifest_path = out / "journey.agent.json"
    markdown_path.write_text(render_graph_markdown(graph))
    manifest_path.write_text(json.dumps(graph_manifest(graph), indent=2) + "\n")
    return str(markdown_path), str(manifest_path)


def render_graph_markdown(graph: JourneyGraph) -> str:
    lines = [
        f"# {graph.root.name}",
        "",
        "Lightweight Journey graph. This handoff is file-based and does not require an app runtime, database, or code generator.",
        "",
        "## Agent Checklist",
        "",
    ]
    lines.extend(f"- [ ] {item}" for item in graph.checklist())
    lines.extend(["", "## Journey Files", ""])
    for node in graph.nodes:
        rel = node.path.relative_to(graph.root.path.parent)
        level = f" ({node.level})" if node.level else ""
        lines.append(f"- `{rel}` - {node.name}{level}")
    lines.extend(["", "## Linked Content", ""])
    for node in graph.nodes:
        rel = node.path.relative_to(graph.root.path.parent)
        lines.extend([f"### {node.name}", "", f"Source: `{rel}`", "", "```journey", node.body.strip(), "```", ""])
    return "\n".join(lines)


def graph_manifest(graph: JourneyGraph) -> dict:
    return {
        "schema": "journey.agent.v1",
        "mode": "lightweight",
        "name": graph.root.name,
        "slug": graph.slug,
        "root": str(graph.root.path),
        "journeys": [
            {
                "name": node.name,
                "level": node.level,
                "path": str(node.path),
                "parent": node.parent,
                "children": list(node.children),
            }
            for node in graph.nodes
        ],
        "checklist": graph.checklist(),
    }


def validate_journey_graph(graph: JourneyGraph) -> tuple[GraphIssue, ...]:
    issues: list[GraphIssue] = []
    paths = {node.path.resolve() for node in graph.nodes}
    for node in graph.nodes:
        for child in node.children:
            child_path = (node.path.parent / child).resolve()
            if not child_path.exists():
                issues.append(
                    GraphIssue(
                        severity="error",
                        code="missing_child",
                        path=str(node.path),
                        message=f"Linked child journey does not exist: {child}",
                    )
                )
            elif child_path not in paths:
                issues.append(
                    GraphIssue(
                        severity="error",
                        code="unloaded_child",
                        path=str(node.path),
                        message=f"Linked child journey could not be loaded: {child}",
                    )
                )
        if node.parent:
            parent_path = (node.path.parent / node.parent).resolve()
            if not parent_path.exists():
                issues.append(
                    GraphIssue(
                        severity="error",
                        code="missing_parent",
                        path=str(node.path),
                        message=f"Linked parent journey does not exist: {node.parent}",
                    )
                )
    return tuple(issues)


def _resolve_root(source: str | Path) -> Path:
    path = Path(source)
    if path.is_dir():
        candidate = path / ".journey" / "repo.journey"
        if candidate.exists():
            return candidate.resolve()
        candidate = path / "repo.journey"
        if candidate.exists():
            return candidate.resolve()
    return path.resolve()


def _walk(path: Path, nodes: list[JourneyNode], seen: set[Path]) -> None:
    if path in seen:
        return
    seen.add(path)
    node = _parse_node(path)
    nodes.append(node)
    for child in node.children:
        child_path = (path.parent / child).resolve()
        if child_path.exists():
            _walk(child_path, nodes, seen)


def _parse_node(path: Path) -> JourneyNode:
    body = path.read_text()
    name_match = re.search(r'^\s*journey\s+"([^"]+)"', body, re.MULTILINE)
    name = name_match.group(1).strip() if name_match else path.stem.replace("_", " ").replace("-", " ").title()
    level = _scalar(body, "level")
    parent = _scalar(body, "parent")
    children = tuple(_list_values(body, "children"))
    return JourneyNode(path=path, name=name, level=level, parent=parent, children=children, body=body)


def _scalar(body: str, key: str) -> str | None:
    match = re.search(rf"^\s*{re.escape(key)}\s*:\s*(.+)$", body, re.MULTILINE)
    return match.group(1).strip() if match else None


def _list_values(body: str, key: str) -> list[str]:
    match = re.search(rf"^\s*{re.escape(key)}\s*:\s*$", body, re.MULTILINE)
    if not match:
        return []
    values = []
    for line in body[match.end():].splitlines():
        item = re.match(r"^\s*-\s+(.+)$", line)
        if item:
            values.append(item.group(1).strip())
            continue
        if line.strip() and not line.startswith((" ", "\t")):
            break
    return values

"""Scaffold folder-level Journey files from a project tree."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


PAGE_MARKERS = {
    "page.js",
    "page.jsx",
    "page.ts",
    "page.tsx",
}

API_MARKERS = {
    "route.js",
    "route.jsx",
    "route.ts",
    "route.tsx",
}

PAGE_SUFFIXES = {".html", ".jsx", ".tsx", ".vue", ".svelte"}
SKIP_DIRS = {".git", ".journey", ".next", ".nuxt", ".venv", "__pycache__", "dist", "generated", "node_modules"}
HTTP_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")


@dataclass(frozen=True)
class ScaffoldResult:
    root: str
    files: tuple[str, ...]


@dataclass(frozen=True)
class JourneyCandidate:
    name: str
    level: str
    source: Path | None

    @property
    def slug(self) -> str:
        return _slugify(self.name)

    @property
    def child_path(self) -> str:
        return f"./{self.level}s/{self.slug}.journey"


@dataclass(frozen=True)
class SourceSignals:
    api_calls: tuple[str, ...] = ()
    actions: tuple[str, ...] = ()
    links: tuple[str, ...] = ()
    states: tuple[str, ...] = ()
    methods: tuple[str, ...] = ()
    request_hints: tuple[str, ...] = ()
    response_hints: tuple[str, ...] = ()


def scaffold_journeys(
    root: str | Path,
    *,
    name: str | None = None,
    force: bool = False,
    flow_filename: str = "JOURNEY_FLOW.md",
) -> ScaffoldResult:
    project = Path(root).resolve()
    project.mkdir(parents=True, exist_ok=True)
    title = name or _project_name(project)
    out = project / ".journey"
    candidates = detect_candidates(project)
    if not candidates:
        candidates = [JourneyCandidate("Main Page", "page", None)]

    out.mkdir(parents=True, exist_ok=True)

    written = []
    root_path = out / "repo.journey"
    _write_once(root_path, _render_repo_journey(title, candidates), force=force)
    written.append(str(root_path))

    for candidate in candidates:
        candidate_dir = out / f"{candidate.level}s"
        candidate_dir.mkdir(parents=True, exist_ok=True)
        path = candidate_dir / f"{candidate.slug}.journey"
        _write_once(path, _render_child_journey(title, candidate, project), force=force)
        written.append(str(path))

    index_path = out / "README.md"
    _write_once(index_path, _render_index(title, root_path, candidates), force=force)
    written.append(str(index_path))

    flow_path = out / flow_filename
    _write_once(flow_path, _render_flow_document(title, candidates, project), force=force)
    written.append(str(flow_path))

    return ScaffoldResult(root=str(out), files=tuple(written))


def sync_journeys(
    root: str | Path,
    *,
    name: str | None = None,
    force: bool = False,
    flow_filename: str = "JOURNEY_FLOW.md",
) -> ScaffoldResult:
    """Update the Journey tree with newly discovered pages and API routes.

    Existing child journey files are preserved unless force=True. repo.journey and
    README.md are regenerated so links stay current.
    """

    project = Path(root).resolve()
    project.mkdir(parents=True, exist_ok=True)
    title = name or _project_name(project)
    out = project / ".journey"
    candidates = detect_candidates(project)
    if not candidates:
        candidates = [JourneyCandidate("Main Page", "page", None)]

    out.mkdir(parents=True, exist_ok=True)

    written = []
    root_path = out / "repo.journey"
    root_path.write_text(_render_repo_journey(title, candidates))
    written.append(str(root_path))

    for candidate in candidates:
        candidate_dir = out / f"{candidate.level}s"
        candidate_dir.mkdir(parents=True, exist_ok=True)
        path = candidate_dir / f"{candidate.slug}.journey"
        if force or not path.exists():
            path.write_text(_render_child_journey(title, candidate, project))
        else:
            _refresh_child_metadata(path, candidate)
        written.append(str(path))

    index_path = out / "README.md"
    index_path.write_text(_render_index(title, root_path, candidates))
    written.append(str(index_path))

    flow_path = out / flow_filename
    flow_path.write_text(_render_flow_document(title, candidates, project))
    written.append(str(flow_path))

    return ScaffoldResult(root=str(out), files=tuple(written))


def detect_candidates(project: str | Path) -> list[JourneyCandidate]:
    project = Path(project).resolve()
    candidates: dict[tuple[str, str], JourneyCandidate] = {}
    for path in project.rglob("*"):
        if _is_skipped(path, project) or not path.is_file():
            continue
        candidate = _candidate_from_path(path, project)
        if candidate:
            candidates.setdefault((candidate.level, candidate.slug), candidate)
    return sorted(candidates.values(), key=lambda item: (item.level, item.name))


def _candidate_from_path(path: Path, project: Path) -> JourneyCandidate | None:
    rel = path.relative_to(project)
    if path.name in PAGE_MARKERS:
        parts = [part for part in rel.parent.parts if part not in {"app", "pages", "src", "routes"}]
        name = " ".join(parts) if parts else "Home"
        return JourneyCandidate(_title(name), "page", rel)
    if path.name in API_MARKERS and "api" in rel.parts:
        parts = [part for part in rel.parent.parts if part not in {"app", "src", "api", "routes"}]
        name = " ".join(parts) if parts else "API"
        return JourneyCandidate(_title(name), "api", rel)
    if _under_page_dir(rel) and path.suffix.lower() in PAGE_SUFFIXES:
        return JourneyCandidate(_title(_route_name_from_path(rel)), "page", rel)
    return None


def _under_page_dir(path: Path) -> bool:
    return any(part in {"pages", "routes"} for part in path.parts)


def _is_skipped(path: Path, project: Path) -> bool:
    try:
        parts = path.relative_to(project).parts
    except ValueError:
        return True
    return any(part in SKIP_DIRS for part in parts)


def _write_once(path: Path, text: str, *, force: bool) -> None:
    if path.exists() and not force:
        return
    path.write_text(text)


def _refresh_child_metadata(path: Path, candidate: JourneyCandidate) -> None:
    text = path.read_text()
    updates = {
        "parent": "../repo.journey",
        "level": candidate.level,
        "route": _route_from_candidate(candidate),
        "source": f"../../{candidate.source.as_posix()}" if candidate.source else "unknown",
    }
    for key, value in updates.items():
        text = _upsert_scalar(text, key, value)
    path.write_text(text)


def _upsert_scalar(text: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^(\s*{re.escape(key)}\s*:\s*).*$", re.MULTILINE)
    replacement = rf"\g<1>{value}"
    if pattern.search(text):
        return pattern.sub(replacement, text, count=1)

    lines = text.splitlines()
    insert_at = _metadata_insert_index(lines, key)
    lines.insert(insert_at, f"{key}: {value}")
    trailing_newline = "\n" if text.endswith("\n") else ""
    return "\n".join(lines) + trailing_newline


def _metadata_insert_index(lines: list[str], key: str) -> int:
    order = {
        "parent": ("journey",),
        "level": ("parent", "journey"),
        "route": ("level", "parent", "journey"),
        "source": ("route", "level", "parent", "journey"),
    }
    for previous in order.get(key, ()):
        for index, line in enumerate(lines):
            if previous == "journey" and re.match(r'\s*journey\s+"', line):
                return index + 1
            if re.match(rf"\s*{re.escape(previous)}\s*:", line):
                return index + 1
    return min(1, len(lines))


def _render_repo_journey(title: str, candidates: list[JourneyCandidate]) -> str:
    pages = [candidate for candidate in candidates if candidate.level == "page"]
    apis = [candidate for candidate in candidates if candidate.level == "api"]
    lines = [
        f'journey "{title}"',
        "",
        "mission:",
        f"  Map the product at the repository level so agents and humans can understand the whole flow before editing code.",
        "",
        "level: repo",
        "",
        "children:",
    ]
    lines.extend(f"  - {candidate.child_path}" for candidate in candidates)
    lines.extend([
        "",
        "pages:",
    ])
    lines.extend(f"  - {page.name}" for page in pages)
    if apis:
        lines.extend(["", "apis:"])
        lines.extend(f"  - {api.name}" for api in apis)
    lines.extend([
        "",
        "flows:",
        "  - Read this repo journey first, then read the linked page journeys for detailed behavior.",
        "",
        "acceptance:",
        "  - every important page has a linked page journey",
        "  - routes and user-visible behavior are documented before implementation work starts",
        "  - page journeys stay synced with the code they describe",
        "",
        "done when:",
        "  - repo-level intent is clear",
        "  - each page/API-level journey has purpose, rules, and acceptance",
        "  - open questions are written down instead of hidden in code",
        "",
    ])
    return "\n".join(lines)


def _render_child_journey(title: str, candidate: JourneyCandidate, project: Path) -> str:
    source = f"source: ../../{candidate.source.as_posix()}" if candidate.source else "source: unknown"
    signals = _source_signals(project, candidate)
    if candidate.level == "api":
        return _render_api_journey(title, candidate, source, signals)
    return _render_page_journey(title, candidate, source, signals)


def _render_page_journey(title: str, page: JourneyCandidate, source: str, signals: SourceSignals) -> str:
    lines = [
        f'journey "{title} / {page.name}"',
        "",
        "parent: ../repo.journey",
        "level: page",
        f"route: {_route_from_candidate(page)}",
        source,
        "",
        "mission:",
        f"  Describe what the {page.name} page does, how users move through it, and what must be true when it is done.",
        "",
        f'page "{page.name}":',
        "  purpose:",
        f"    Explain the job this page performs in the product journey.",
        "",
        "  user sees:",
    ]
    if signals.actions:
        lines.extend(f"    - action `{action}`" for action in signals.actions)
    else:
        lines.append("    - primary actions available from this page")
    if signals.links:
        lines.extend(f"    - link to `{link}`" for link in signals.links)
    if signals.states:
        lines.extend(f"    - {state} state" for state in signals.states)
    else:
        lines.append("    - loading, empty, and error states where relevant")
    lines.extend(["", "  rules:"])
    if signals.api_calls:
        lines.extend(f"    - calls `{api_call}`" for api_call in signals.api_calls)
    else:
        lines.append("    - document business rules, permissions, validation, and state changes here")
    lines.extend([
        "",
        "  acceptance:",
        f"    - {page.name} supports its intended user flow",
        f"    - {page.name} handles important failure states",
        "    - tests or QA notes cover the expected behavior",
        "",
        "done when:",
        "  - page behavior matches this journey",
        "  - links to adjacent journeys are current",
        "  - unresolved product questions are listed explicitly",
        "",
    ])
    return "\n".join(lines)


def _render_api_journey(title: str, api: JourneyCandidate, source: str, signals: SourceSignals) -> str:
    lines = [
        f'journey "{title} / {api.name} API"',
        "",
        "parent: ../repo.journey",
        "level: api",
        f"route: {_route_from_candidate(api)}",
        source,
        "",
        "mission:",
        f"  Describe what the {api.name} API route does, who calls it, and what data or side effects it owns.",
        "",
        f'api "{api.name}":',
        "  purpose:",
        f"    Explain the job this API performs in the product journey.",
        "",
        "  request:",
    ]
    if signals.methods:
        lines.extend(f"    - method `{method}`" for method in signals.methods)
    if signals.request_hints:
        lines.extend(f"    - {hint}" for hint in signals.request_hints)
    if not signals.methods and not signals.request_hints:
        lines.append("    - document required inputs, params, headers, auth, and validation")
    lines.extend(["", "  response:"])
    if signals.response_hints:
        lines.extend(f"    - {hint}" for hint in signals.response_hints)
    else:
        lines.append("    - document success shape, status, and important error states")
    lines.extend([
        "",
        "  rules:",
        "    - document business rules, permissions, validation, and state changes here",
        "",
        "  acceptance:",
        f"    - {api.name} API supports its intended caller flow",
        f"    - {api.name} API handles important failure states",
        "    - tests or QA notes cover the expected behavior",
        "",
        "done when:",
        "  - API behavior matches this journey",
        "  - links to adjacent journeys are current",
        "  - unresolved product questions are listed explicitly",
        "",
    ])
    return "\n".join(lines)


def _render_index(title: str, root_path: Path, candidates: list[JourneyCandidate]) -> str:
    lines = [
        f"# {title} Journey Map",
        "",
        f"- Repo journey: `{root_path.name}`",
        "",
        "## Journeys",
        "",
    ]
    lines.extend(
        f"- `{Path(candidate.level + 's') / (candidate.slug + '.journey')}` - {candidate.name} ({candidate.level})"
        for candidate in candidates
    )
    lines.append("")
    return "\n".join(lines)


def _render_flow_document(title: str, candidates: list[JourneyCandidate], project: Path) -> str:
    pages = [candidate for candidate in candidates if candidate.level == "page"]
    apis = [candidate for candidate in candidates if candidate.level == "api"]
    lines = [
        f"# {title} Journey Flow",
        "",
        "A single read-through map of the project journey. Use this before clicking through the app or opening implementation files.",
        "",
        "## Journey Graph",
        "",
        "- `.journey/repo.journey` is the repository-level source of truth.",
        "- Child journeys live under `.journey/pages/` and `.journey/apis/`.",
        "- Run `journey sync .` after adding or moving routes.",
        "",
        "## Route Map",
        "",
        "| Type | Route | Journey | Source |",
        "| --- | --- | --- | --- |",
    ]
    for candidate in candidates:
        route = _route_from_candidate(candidate)
        source = candidate.source.as_posix() if candidate.source else "unknown"
        lines.append(f"| {candidate.level} | `{route}` | `{candidate.child_path}` | `{source}` |")

    lines.extend([
        "",
        "## Feature Flow",
        "",
    ])
    if pages:
        lines.append("### Pages")
        lines.append("")
        for index, page in enumerate(pages, start=1):
            route = _route_from_candidate(page)
            signals = _source_signals(project, page)
            lines.extend([
                f"{index}. **{page.name}** (`{route}`)",
                f"   - Journey: `{page.child_path}`",
                "   - Captures visible states, primary actions, rules, and page-level acceptance.",
            ])
            if signals.actions:
                lines.append(f"   - Actions: {', '.join(f'`{action}`' for action in signals.actions)}")
            if signals.api_calls:
                lines.append(f"   - Calls: {', '.join(f'`{api_call}`' for api_call in signals.api_calls)}")
        lines.append("")
    if apis:
        lines.append("### APIs")
        lines.append("")
        for index, api in enumerate(apis, start=1):
            route = _route_from_candidate(api)
            signals = _source_signals(project, api)
            lines.extend([
                f"{index}. **{api.name} API** (`{route}`)",
                f"   - Journey: `{api.child_path}`",
                "   - Captures caller intent, request shape, response shape, side effects, and API-level acceptance.",
            ])
            if signals.methods:
                lines.append(f"   - Methods: {', '.join(f'`{method}`' for method in signals.methods)}")
            if signals.response_hints:
                lines.append(f"   - Responses: {', '.join(signals.response_hints)}")
        lines.append("")

    lines.extend([
        "## End-to-End Walkthrough",
        "",
        "1. Start with `.journey/repo.journey` to understand the product mission and linked child journeys.",
        "2. Read page journeys in route order to understand what users see and do.",
        "3. Read API journeys beside the pages that call them to understand data flow and side effects.",
        "4. Update acceptance notes before changing code so agents can implement against product intent.",
        "",
        "## Acceptance Outline",
        "",
        "- every discovered page or API route has a linked child journey",
        "- every child journey names its source file",
        "- visible states, business rules, failures, and tests/QA notes are documented where relevant",
        "- unresolved product questions are written in the journey instead of hidden in implementation",
        "",
    ])
    return "\n".join(lines)


def _source_signals(project: Path, candidate: JourneyCandidate) -> SourceSignals:
    if not candidate.source:
        return SourceSignals()
    path = project / candidate.source
    if not path.exists() or not path.is_file():
        return SourceSignals()
    try:
        text = path.read_text(errors="ignore")
    except OSError:
        return SourceSignals()
    if candidate.level == "api":
        return _api_source_signals(text)
    return _page_source_signals(text)


def _page_source_signals(text: str) -> SourceSignals:
    return SourceSignals(
        api_calls=_unique(_api_calls(text)),
        actions=_unique(_button_labels(text)),
        links=_unique(_hrefs(text)),
        states=_unique(_state_words(text)),
    )


def _api_source_signals(text: str) -> SourceSignals:
    methods = _unique(
        method
        for method in HTTP_METHODS
        if re.search(rf"\bfunction\s+{method}\b|\bconst\s+{method}\b|\bexport\s+\{{[^}}]*\b{method}\b", text)
    )
    request_hints = []
    if re.search(r"\.json\s*\(", text):
        request_hints.append("reads JSON request body")
    if re.search(r"\.formData\s*\(", text):
        request_hints.append("reads form data")
    if "searchParams" in text:
        request_hints.append("reads query params")
    if re.search(r"\bparams\b", text):
        request_hints.append("uses route params")

    response_hints = []
    if re.search(r"Response\.json|NextResponse\.json|json\s*\(", text):
        response_hints.append("returns JSON response")
    for status in _unique(re.findall(r"status\s*:\s*(\d{3})", text)):
        response_hints.append(f"can return status `{status}`")

    return SourceSignals(
        methods=methods,
        request_hints=tuple(request_hints),
        response_hints=tuple(response_hints),
    )


def _api_calls(text: str) -> tuple[str, ...]:
    calls = []
    patterns = [
        r"\bfetch\s*\(\s*['\"]([^'\"]+)['\"]",
        r"\baxios\.(?:get|post|put|patch|delete)\s*\(\s*['\"]([^'\"]+)['\"]",
        r"\baxios\s*\(\s*['\"]([^'\"]+)['\"]",
    ]
    for pattern in patterns:
        calls.extend(match for match in re.findall(pattern, text) if match.startswith("/"))
    return tuple(calls)


def _button_labels(text: str) -> tuple[str, ...]:
    labels = [
        _clean_inline_text(match)
        for match in re.findall(r"<button\b[^>]*>(.*?)</button>", text, flags=re.IGNORECASE | re.DOTALL)
    ]
    aria_labels = re.findall(r"aria-label\s*=\s*['\"]([^'\"]+)['\"]", text, flags=re.IGNORECASE)
    return tuple(label for label in labels + aria_labels if label)


def _hrefs(text: str) -> tuple[str, ...]:
    return tuple(match for match in re.findall(r"\bhref\s*=\s*['\"]([^'\"]+)['\"]", text) if match.startswith("/"))


def _state_words(text: str) -> tuple[str, ...]:
    states = []
    lower = text.lower()
    for state in ("loading", "empty", "error", "success"):
        if state in lower:
            states.append(state)
    return tuple(states)


def _clean_inline_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\{[^}]+\}", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _unique(values) -> tuple[str, ...]:
    seen = set()
    result = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return tuple(result)


def _route_from_candidate(candidate: JourneyCandidate) -> str:
    if not candidate.source:
        return "/"
    source = candidate.source
    parts = list(source.parts)
    if candidate.source.name in PAGE_MARKERS | API_MARKERS:
        parts = parts[:-1]
    elif source.suffix.lower() in PAGE_SUFFIXES:
        parts = list(source.with_suffix("").parts)
    while parts and parts[0] in {"src", "app", "pages", "routes"}:
        parts = parts[1:]
    if candidate.level == "api" and parts and parts[0] != "api":
        parts.insert(0, "api")
    if candidate.level == "page" and parts and parts[-1] == "index":
        parts = parts[:-1]
    route_parts = []
    for part in parts:
        if part in {"page", "route"} or (part.startswith("(") and part.endswith(")")):
            continue
        route_parts.extend(_route_segment(part))
    route = "/" + "/".join(part for part in route_parts if part)
    return route.rstrip("/") or "/"


def _route_segment(part: str) -> tuple[str, ...]:
    if part in {"index", "_index"}:
        return ()
    if part.startswith("[[...") and part.endswith("]]"):
        return (f"*{part[5:-2]}",)
    if part.startswith("[...") and part.endswith("]"):
        return (f"*{part[4:-1]}",)
    if part.startswith("[") and part.endswith("]"):
        return (f":{part[1:-1]}",)
    segments = []
    for segment in part.split("."):
        if not segment or segment in {"index", "_index"}:
            continue
        if segment.startswith("$") and len(segment) > 1:
            segments.append(f":{segment[1:]}")
        else:
            segments.append(segment.lstrip("_"))
    return tuple(segments)


def _route_name_from_path(path: Path) -> str:
    words = []
    for segment in path.stem.split("."):
        if not segment:
            continue
        segment = segment.lstrip("_")
        if segment.startswith("$"):
            segment = segment[1:]
        words.extend(_split_words(segment))
    return " ".join(words) or path.stem


def _split_words(value: str) -> list[str]:
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value)
    value = value.replace("-", " ").replace("_", " ")
    return [part for part in value.split() if part]


def _project_name(project: Path) -> str:
    raw = project.name.replace("_", " ").replace("-", " ").strip()
    return _title(raw) if raw else "Product Journey"


def _title(value: str) -> str:
    value = value.replace("_", " ").replace("-", " ").replace("[", "").replace("]", "")
    value = re.sub(r"\s+", " ", value).strip()
    return value.title() if value else "Home"


def _slugify(value: str) -> str:
    value = value.replace("_", "-").replace(" ", "-")
    value = re.sub(r"[^a-zA-Z0-9-]+", "", value).strip("-").lower()
    value = re.sub(r"-+", "-", value)
    return value or "page"

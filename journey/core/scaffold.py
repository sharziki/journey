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


def scaffold_journeys(root: str | Path, *, name: str | None = None, force: bool = False) -> ScaffoldResult:
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
        _write_once(path, _render_child_journey(title, candidate), force=force)
        written.append(str(path))

    index_path = out / "README.md"
    _write_once(index_path, _render_index(title, root_path, candidates), force=force)
    written.append(str(index_path))

    return ScaffoldResult(root=str(out), files=tuple(written))


def sync_journeys(root: str | Path, *, name: str | None = None, force: bool = False) -> ScaffoldResult:
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
        _write_once(path, _render_child_journey(title, candidate), force=force)
        written.append(str(path))

    index_path = out / "README.md"
    index_path.write_text(_render_index(title, root_path, candidates))
    written.append(str(index_path))

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
        return JourneyCandidate(_title(path.stem), "page", rel)
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


def _render_child_journey(title: str, candidate: JourneyCandidate) -> str:
    source = f"source: ../../{candidate.source.as_posix()}" if candidate.source else "source: unknown"
    if candidate.level == "api":
        return _render_api_journey(title, candidate, source)
    return _render_page_journey(title, candidate, source)


def _render_page_journey(title: str, page: JourneyCandidate, source: str) -> str:
    return "\n".join([
        f'journey "{title} / {page.name}"',
        "",
        "parent: ../repo.journey",
        "level: page",
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
        "    - primary information needed on this page",
        "    - primary actions available from this page",
        "    - loading, empty, and error states where relevant",
        "",
        "  rules:",
        "    - document business rules, permissions, validation, and state changes here",
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


def _render_api_journey(title: str, api: JourneyCandidate, source: str) -> str:
    return "\n".join([
        f'journey "{title} / {api.name} API"',
        "",
        "parent: ../repo.journey",
        "level: api",
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
        "    - document required inputs, params, headers, auth, and validation",
        "",
        "  response:",
        "    - document success shape, status, and important error states",
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

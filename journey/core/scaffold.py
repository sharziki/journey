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
class PageCandidate:
    name: str
    source: Path | None

    @property
    def slug(self) -> str:
        return _slugify(self.name)


def scaffold_journeys(root: str | Path, *, name: str | None = None, force: bool = False) -> ScaffoldResult:
    project = Path(root).resolve()
    project.mkdir(parents=True, exist_ok=True)
    title = name or _project_name(project)
    out = project / ".journey"
    pages_out = out / "pages"
    pages = _detect_pages(project)
    if not pages:
        pages = [PageCandidate("Main Page", None)]

    out.mkdir(parents=True, exist_ok=True)
    pages_out.mkdir(parents=True, exist_ok=True)

    written = []
    root_path = out / "repo.journey"
    _write_once(root_path, _render_repo_journey(title, pages), force=force)
    written.append(str(root_path))

    for page in pages:
        path = pages_out / f"{page.slug}.journey"
        _write_once(path, _render_page_journey(title, page), force=force)
        written.append(str(path))

    index_path = out / "README.md"
    _write_once(index_path, _render_index(title, root_path, pages), force=force)
    written.append(str(index_path))

    return ScaffoldResult(root=str(out), files=tuple(written))


def _detect_pages(project: Path) -> list[PageCandidate]:
    candidates: dict[str, PageCandidate] = {}
    for path in project.rglob("*"):
        if _is_skipped(path, project) or not path.is_file():
            continue
        page = _candidate_from_path(path, project)
        if page:
            candidates.setdefault(page.slug, page)
    return sorted(candidates.values(), key=lambda item: item.name)


def _candidate_from_path(path: Path, project: Path) -> PageCandidate | None:
    rel = path.relative_to(project)
    if path.name in PAGE_MARKERS:
        parts = [part for part in rel.parent.parts if part not in {"app", "pages", "src", "routes"}]
        name = " ".join(parts) if parts else "Home"
        return PageCandidate(_title(name), rel)
    if _under_page_dir(rel) and path.suffix.lower() in PAGE_SUFFIXES:
        return PageCandidate(_title(path.stem), rel)
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


def _render_repo_journey(title: str, pages: list[PageCandidate]) -> str:
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
    lines.extend(f"  - ./pages/{page.slug}.journey" for page in pages)
    lines.extend([
        "",
        "pages:",
    ])
    lines.extend(f"  - {page.name}" for page in pages)
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
        "  - each page-level journey has purpose, user sees, rules, and acceptance",
        "  - open questions are written down instead of hidden in code",
        "",
    ])
    return "\n".join(lines)


def _render_page_journey(title: str, page: PageCandidate) -> str:
    source = f"source: ../../{page.source.as_posix()}" if page.source else "source: unknown"
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


def _render_index(title: str, root_path: Path, pages: list[PageCandidate]) -> str:
    lines = [
        f"# {title} Journey Map",
        "",
        f"- Repo journey: `{root_path.name}`",
        "",
        "## Page Journeys",
        "",
    ]
    lines.extend(f"- `{Path('pages') / (page.slug + '.journey')}` - {page.name}" for page in pages)
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

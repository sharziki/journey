"""Natural-language Journey shaping utilities."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class NaturalJourney:
    name: str
    slug: str
    mission: str
    design: str | None
    pages: tuple[str, ...]
    flows: tuple[str, ...]
    acceptance: tuple[str, ...]
    shaped_text: str

    def checklist(self) -> list[str]:
        items = [f"Read journey '{self.name}'"]
        if self.design:
            items.append(f"Read design reference '{self.design}'")
        items.extend(f"Specify page '{page}'" for page in self.pages)
        items.extend(f"Implement flow '{flow}'" for flow in self.flows)
        items.extend(f"Prove acceptance: {item}" for item in self.acceptance)
        items.append("Run cleanup and repair drift")
        return items


def shape_unstructured_journey(source: str, *, filename: str = "<string>") -> NaturalJourney:
    """Turn loose product writing into a readable handwritten Journey."""
    clean = source.strip()
    name = _infer_name(clean, filename)
    slug = _slugify(name)
    design = _infer_design(clean)
    pages = tuple(_infer_pages(clean))
    flows = tuple(_infer_flows(clean, pages))
    acceptance = tuple(_infer_acceptance(clean))
    mission = _infer_mission(clean, name)
    shaped_text = _render_shaped_journey(name, mission, design, pages, flows, acceptance)
    return NaturalJourney(
        name=name,
        slug=slug,
        mission=mission,
        design=design,
        pages=pages,
        flows=flows,
        acceptance=acceptance,
        shaped_text=shaped_text,
    )


def write_natural_handoff(journey: NaturalJourney, output_dir: str | Path) -> tuple[str, str, str]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    shaped_path = out / "shaped.journey"
    markdown_path = out / "JOURNEY.md"
    manifest_path = out / "journey.agent.json"

    shaped_path.write_text(journey.shaped_text)
    markdown_path.write_text(_render_markdown(journey))
    manifest_path.write_text(json.dumps(_manifest(journey), indent=2) + "\n")
    return str(shaped_path), str(markdown_path), str(manifest_path)


def _infer_name(source: str, filename: str) -> str:
    journey_match = re.search(r'^\s*journey\s+"([^"]+)"', source, re.IGNORECASE | re.MULTILINE)
    if journey_match:
        return journey_match.group(1).strip()
    heading_match = re.search(r"^\s*#\s+(.+)$", source, re.MULTILINE)
    if heading_match:
        return heading_match.group(1).strip()
    return Path(filename).stem.replace("_", " ").replace("-", " ").title() or "Untitled Journey"


def _infer_design(source: str) -> str | None:
    match = re.search(r"^\s*design\s*:\s*(.+)$", source, re.IGNORECASE | re.MULTILINE)
    if match:
        return match.group(1).strip()
    for candidate in ("design.md", "./design.md", "docs/design.md"):
        if candidate in source:
            return candidate
    return None


def _infer_pages(source: str) -> list[str]:
    explicit = _items_after_label(source, "pages")
    if explicit:
        return [_title(item) for item in explicit]

    page_matches = re.findall(r'^\s*page\s+"?([^":\n]+)"?\s*:?', source, re.IGNORECASE | re.MULTILINE)
    if page_matches:
        return [_title(page.strip()) for page in page_matches]

    known = [
        "landing",
        "signup",
        "login",
        "dashboard",
        "home",
        "settings",
        "profile",
        "checkout",
        "invite",
        "workspace",
        "admin",
    ]
    found = []
    lower = source.lower()
    for word in known:
        if word in lower:
            found.append(_title(word))
    return found or ["Main Page"]


def _infer_flows(source: str, pages: tuple[str, ...] | list[str]) -> list[str]:
    explicit = _items_after_label(source, "flows")
    if explicit:
        return [_clean_sentence(item) for item in explicit]

    flow_matches = re.findall(r'^\s*flow\s+"?([^":\n]+)"?\s*:?', source, re.IGNORECASE | re.MULTILINE)
    if flow_matches:
        return [_clean_sentence(flow) for flow in flow_matches]

    if len(pages) > 1:
        return [" -> ".join(pages)]
    return [f"Use {pages[0]}"]


def _infer_acceptance(source: str) -> list[str]:
    explicit = _items_after_label(source, "acceptance") or _items_after_label(source, "done when")
    if explicit:
        return [_clean_sentence(item) for item in explicit]

    bullets = re.findall(r"^\s*[-*]\s+(.+)$", source, re.MULTILINE)
    acceptance = [
        _clean_sentence(item)
        for item in bullets
        if re.search(r"\b(should|must|can|cannot|works|passes|done|rejects|creates|shows)\b", item, re.IGNORECASE)
    ]
    return acceptance[:8] or ["Core flow works end to end", "Important failure states are handled", "Tests prove the journey works"]


def _infer_mission(source: str, name: str) -> str:
    for label in ("mission", "story", "goal", "overview"):
        block = _paragraph_after_label(source, label)
        if block:
            return _clean_sentence(block)
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", source) if p.strip()]
    for paragraph in paragraphs:
        if not paragraph.lower().startswith(("journey", "pages:", "flows:", "acceptance:", "done when:")):
            return _clean_sentence(paragraph)
    return f"Build {name} so the described product flow works clearly and reliably."


def _items_after_label(source: str, label: str) -> list[str]:
    pattern = re.compile(rf"^\s*{re.escape(label)}\s*:\s*$", re.IGNORECASE | re.MULTILINE)
    match = pattern.search(source)
    if not match:
        return []
    lines = source[match.end():].splitlines()
    items = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith(("-", "*")) and re.match(r"^[^:\n]+:\s*$", stripped):
            break
        bullet = re.match(r"^\s*[-*]\s+(.+)$", line)
        if bullet:
            items.append(bullet.group(1).strip())
        elif stripped and not line.startswith((" ", "\t")):
            break
    return items


def _paragraph_after_label(source: str, label: str) -> str:
    pattern = re.compile(rf"^\s*{re.escape(label)}\s*:\s*$", re.IGNORECASE | re.MULTILINE)
    match = pattern.search(source)
    if not match:
        return ""
    lines = []
    for line in source[match.end():].splitlines():
        if re.match(r"^\S[^:\n]*:\s*$", line):
            break
        if line.strip():
            lines.append(line.strip())
        elif lines:
            break
    return " ".join(lines)


def _render_shaped_journey(
    name: str,
    mission: str,
    design: str | None,
    pages: tuple[str, ...],
    flows: tuple[str, ...],
    acceptance: tuple[str, ...],
) -> str:
    lines = [f'journey "{name}"', ""]
    if design:
        lines.extend([f"design: {design}", ""])
    lines.extend(["mission:", _indent(mission), "", "pages:"])
    lines.extend(f"  - {page}" for page in pages)
    lines.extend(["", "flows:"])
    lines.extend(f"  - {flow}" for flow in flows)
    for page in pages:
        lines.extend([
            "",
            f'page "{page}":',
            "  purpose:",
            _indent(f"Define what {page} must do for the product journey.", 4),
            "",
            "  user sees:",
            "    - the information needed to complete this part of the flow",
            "    - clear actions and useful empty/error states",
            "",
            "  acceptance:",
            f"    - {page} supports the intended user flow",
            f"    - {page} handles important failure states",
        ])
    lines.extend(["", "acceptance:"])
    lines.extend(f"  - {item}" for item in acceptance)
    lines.extend([
        "",
        "crew:",
        "  planner: Find the next missing page, flow, or acceptance item.",
        "  builder: Implement the missing behavior.",
        "  tester: Turn acceptance into checks.",
        "  cleanup: Compare the implementation against this journey and repair drift.",
        "",
        "done when:",
        "  - every page and flow has implementation or an explicit open question",
        "  - every acceptance item is covered by tests or QA notes",
        "  - cleanup reports no open drift",
        "",
    ])
    return "\n".join(lines)


def _render_markdown(journey: NaturalJourney) -> str:
    lines = [
        f"# {journey.name}",
        "",
        journey.mission,
        "",
        "## Agent Checklist",
        "",
    ]
    lines.extend(f"- [ ] {item}" for item in journey.checklist())
    lines.extend(["", "## Pages", ""])
    lines.extend(f"- {page}" for page in journey.pages)
    lines.extend(["", "## Flows", ""])
    lines.extend(f"- {flow}" for flow in journey.flows)
    lines.extend(["", "## Acceptance", ""])
    lines.extend(f"- {item}" for item in journey.acceptance)
    lines.append("")
    return "\n".join(lines)


def _manifest(journey: NaturalJourney) -> dict:
    return {
        "schema": "journey.agent.v1",
        "mode": "natural",
        "name": journey.name,
        "slug": journey.slug,
        "mission": journey.mission,
        "design": journey.design,
        "checklist": journey.checklist(),
        "pages": list(journey.pages),
        "flows": list(journey.flows),
        "acceptance": list(journey.acceptance),
    }


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "journey"


def _title(value: str) -> str:
    return value.strip().replace("_", " ").replace("-", " ").title()


def _clean_sentence(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" -")


def _indent(value: str, spaces: int = 2) -> str:
    prefix = " " * spaces
    return "\n".join(prefix + line if line else line for line in value.splitlines())

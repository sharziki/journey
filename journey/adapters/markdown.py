"""Markdown adapter for agent-readable Journey summaries."""

from __future__ import annotations

from pathlib import Path

from journey.core.normalize import NormalizedJourney, normalize
from journey.parser.ast_nodes import JourneySpec


def generate_markdown(spec: JourneySpec) -> str:
    journey = normalize(spec)
    lines = [
        f"# {journey.name}",
        "",
        journey.description or "No description provided.",
        "",
        "## Agent Checklist",
        "",
    ]
    lines.extend(f"- [ ] {item}" for item in journey.checklist())
    lines.extend(["", "## Entities", ""])
    for entity in journey.entities:
        lines.append(f"### {entity.name}")
        for field in entity.fields:
            suffix = f" ({', '.join(field.modifiers)})" if field.modifiers else ""
            lines.append(f"- `{field.name}`: `{field.type_name}`{suffix}")
        lines.append("")
    lines.extend(["## Steps", ""])
    for step in journey.steps:
        auth = " authenticated" if step.authenticated else ""
        requires = f", requires `{step.requires}`" if step.requires else ""
        lines.append(f"### {step.name}")
        lines.append(f"- Actor: `{step.actor}`{auth}{requires}")
        if step.inputs:
            lines.append("- Inputs: " + ", ".join(_field_label(field) for field in step.inputs))
        if step.outputs:
            lines.append("- Outputs: " + ", ".join(f"`{name}`" for name in step.outputs))
        if step.errors:
            lines.append("- Errors: " + ", ".join(f"`{name}`" for name in step.errors))
        lines.append("")
    lines.extend(["## Acceptance Tests", ""])
    for test in journey.tests:
        lines.append(f"- `{test.name}`: " + " -> ".join(test.steps))
    lines.append("")
    return "\n".join(lines)


def write_markdown(spec: JourneySpec, output_dir: str | Path, filename: str = "JOURNEY.md") -> str:
    path = Path(output_dir) / filename
    path.write_text(generate_markdown(spec))
    return str(path)


def _field_label(field) -> str:
    required = " required" if field.required else ""
    return f"`{field.name}: {field.type_name}{required}`"

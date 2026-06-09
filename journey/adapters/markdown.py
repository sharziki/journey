"""Markdown adapter for agent-readable Journey summaries."""

from __future__ import annotations

from pathlib import Path

from journey.core.normalize import (
    NormalizedHybridJourney,
    NormalizedJourney,
    normalize,
    normalize_hybrid,
)
from journey.parser.ast_nodes import HybridJourneySpec, JourneySpec


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


def generate_hybrid_markdown(spec: HybridJourneySpec) -> str:
    """Generate a markdown summary for a hybrid journey spec."""
    journey = normalize_hybrid(spec)
    lines = [
        f"# {journey.name}",
        "",
    ]
    if journey.mission:
        lines.extend([journey.mission, ""])
    elif journey.description:
        lines.extend([journey.description, ""])

    if journey.design:
        lines.extend([f"**Design reference:** `{journey.design}`", ""])

    lines.extend(["## Agent Checklist", ""])
    lines.extend(f"- [ ] {item}" for item in journey.checklist())

    if journey.pages:
        lines.extend(["", "## Pages", ""])
        for page in journey.pages:
            lines.append(f"### {page.name}")
            if page.purpose:
                lines.append(f"- Purpose: {page.purpose}")
            if page.acceptance:
                lines.append("- Acceptance:")
                lines.extend(f"  - {item}" for item in page.acceptance)
            lines.append("")

    if journey.flows:
        lines.extend(["## Flows", ""])
        for flow in journey.flows:
            if flow.steps:
                lines.append(f"- **{flow.name}**: " + " -> ".join(flow.steps))
            else:
                lines.append(f"- **{flow.name}**")
        lines.append("")

    if journey.entities:
        lines.extend(["## Entities", ""])
        for entity in journey.entities:
            lines.append(f"### {entity.name}")
            for field in entity.fields:
                suffix = f" ({', '.join(field.modifiers)})" if field.modifiers else ""
                lines.append(f"- `{field.name}`: `{field.type_name}`{suffix}")
            lines.append("")

    if journey.steps:
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

    if journey.acceptance:
        lines.extend(["## Acceptance", ""])
        lines.extend(f"- {item}" for item in journey.acceptance)
        lines.append("")

    if journey.tests:
        lines.extend(["## Acceptance Tests", ""])
        for test in journey.tests:
            lines.append(f"- `{test.name}`: " + " -> ".join(test.steps))
        lines.append("")

    if journey.done_when:
        lines.extend(["## Done When", ""])
        lines.extend(f"- {item}" for item in journey.done_when)
        lines.append("")

    return "\n".join(lines)


def write_markdown(spec, output_dir: str | Path, filename: str = "JOURNEY.md") -> str:
    path = Path(output_dir) / filename
    if isinstance(spec, HybridJourneySpec):
        path.write_text(generate_hybrid_markdown(spec))
    else:
        path.write_text(generate_markdown(spec))
    return str(path)


def _field_label(field) -> str:
    required = " required" if field.required else ""
    return f"`{field.name}: {field.type_name}{required}`"

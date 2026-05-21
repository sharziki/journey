"""Generate reader-friendly Journey flow documents."""

from __future__ import annotations

from pathlib import Path

from journey.codegen.gen_routes import _http_method, _route_path, _status_code
from journey.core.normalize import normalize
from journey.parser.ast_nodes import Action, JourneySpec


def generate_flow_markdown(spec: JourneySpec) -> str:
    journey = normalize(spec)
    prefix = f"/journey/{journey.slug}"
    lines = [
        f"# {journey.name} Journey Flow",
        "",
        journey.description or "This document maps the product flow from the Journey source of truth.",
        "",
        "## Route Map",
        "",
    ]

    if spec.steps:
        lines.append("| Method | Route | Feature | Success |")
        lines.append("|--------|-------|---------|---------|")
        for step in spec.steps:
            method = _http_method(step).upper()
            route = prefix + _route_path(step)
            lines.append(f"| `{method}` | `{route}` | `{step.name}` | `{_status_code(step)}` |")
    else:
        lines.append("No routes are defined.")

    lines.extend(["", "## Feature Flow", ""])
    for index, step in enumerate(spec.steps, start=1):
        requires = f" after `{step.requires}`" if step.requires else ""
        actor = step.actor.name + (" authenticated" if step.actor.authenticated else "")
        lines.append(f"### {index}. {step.name}")
        lines.append(f"- Actor: `{actor}`{requires}")
        lines.append(f"- Route: `{prefix + _route_path(step)}`")
        if step.inputs:
            lines.append("- Inputs: " + ", ".join(_input_label(field) for field in step.inputs))
        if step.actions:
            lines.append("- Behavior:")
            lines.extend(f"  - {_action_label(action)}" for action in step.actions)
        if step.outputs:
            lines.append("- Outputs: " + ", ".join(f"`{field.name}` from `{field.expression}`" for field in step.outputs))
        if step.errors:
            lines.append("- Error states:")
            lines.extend(f"  - `{error.code_name}` ({error.http_status}): {error.message}" for error in step.errors)
        lines.append("")

    lines.extend(["## Data Model", ""])
    for entity in spec.entities:
        lines.append(f"### {entity.name}")
        if not entity.fields:
            lines.append("No fields are defined.")
        for field in entity.fields:
            lines.append(f"- `{field.name}`: `{_field_type(field)}`{_modifier_suffix(field)}")
        lines.append("")

    lines.extend(["## Acceptance Walkthroughs", ""])
    if spec.tests:
        for test in spec.tests:
            lines.append(f"### {test.name}")
            for command in test.commands:
                args = ", ".join(f"{key}: {value}" for key, value in command.args.items())
                auth = f" as `{command.auth_token_var}`" if command.auth_token_var else ""
                lines.append(f"- Run `{command.step_name}({args})`{auth}")
                for expectation in command.expectations:
                    lines.append(f"  - Expect {_expectation_label(expectation)}")
                if command.capture:
                    lines.append(f"  - Capture `{command.capture}`")
            lines.append("")
    else:
        lines.append("No acceptance walkthroughs are defined.")
        lines.append("")

    lines.extend(["## Agent Checklist", ""])
    lines.extend(f"- [ ] {item}" for item in journey.checklist())
    lines.append("")
    return "\n".join(lines)


def write_flow_markdown(spec: JourneySpec, output_dir: str | Path, filename: str = "JOURNEY_FLOW.md") -> str:
    path = Path(output_dir) / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(generate_flow_markdown(spec))
    return str(path)


def _input_label(field) -> str:
    required = " required" if field.required else ""
    return f"`{field.name}: {_field_type(field)}{required}`"


def _field_type(field) -> str:
    if getattr(field, "state_type", None):
        return "state(" + " -> ".join(field.state_type.states) + ")"
    if getattr(field, "enum_type", None):
        return "enum(" + ", ".join(field.enum_type.values) + ")"
    return field.type_name


def _modifier_suffix(field) -> str:
    modifiers = []
    source = getattr(field, "modifiers", None)
    if not source:
        return ""
    for attr in ("unique", "hashed", "auto"):
        if getattr(source, attr, False):
            modifiers.append(attr)
    if getattr(source, "format_type", None):
        modifiers.append(f"format({source.format_type})")
    if getattr(source, "min_val", None) is not None:
        modifiers.append(f"min({source.min_val})")
    if getattr(source, "max_val", None) is not None:
        modifiers.append(f"max({source.max_val})")
    return " (" + ", ".join(modifiers) + ")" if modifiers else ""


def _action_label(action: Action) -> str:
    if action.kind == "create":
        target = f"`{action.variable}` = " if action.variable else ""
        return f"{target}create `{action.target}` with {_params_label(action.params)}"
    if action.kind == "find":
        target = f"`{action.variable}` = " if action.variable else ""
        return f"{target}find `{action.target}` using {_params_label(action.params)}"
    if action.kind == "transition":
        field = action.params.get("field")
        destination = action.params.get("to")
        if field and destination:
            return f"transition `{action.target}.{field}` to `{destination}`"
        return f"transition `{action.raw}`"
    if action.kind == "call":
        return f"call `{action.target}` with {_params_label(action.params)}"
    if action.kind in {"send", "verify", "access", "reference"}:
        return f"{action.kind} `{action.target or action.raw}`"
    return f"`{action.raw}`"


def _params_label(params: dict[str, str]) -> str:
    if not params:
        return "no parameters"
    return ", ".join(f"`{key}: {value}`" for key, value in params.items())


def _expectation_label(expectation) -> str:
    if expectation.value is None:
        return f"`{expectation.kind}` `{expectation.target}`"
    return f"`{expectation.kind}` `{expectation.target}` = `{expectation.value}`"

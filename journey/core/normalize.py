"""Normalization helpers for Journey specs.

Normalization does not mutate the parsed AST. It creates a stable summary that
agents, CLIs, docs, and adapters can use to navigate the journey consistently.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from journey.parser.ast_nodes import JourneySpec


@dataclass(frozen=True)
class NormalizedField:
    name: str
    type_name: str
    required: bool = False
    modifiers: tuple[str, ...] = ()


@dataclass(frozen=True)
class NormalizedEntity:
    name: str
    slug: str
    fields: tuple[NormalizedField, ...]


@dataclass(frozen=True)
class NormalizedStep:
    name: str
    slug: str
    requires: str | None
    actor: str
    authenticated: bool
    inputs: tuple[NormalizedField, ...]
    outputs: tuple[str, ...]
    errors: tuple[str, ...]


@dataclass(frozen=True)
class NormalizedTest:
    name: str
    slug: str
    steps: tuple[str, ...]


@dataclass(frozen=True)
class NormalizedJourney:
    name: str
    slug: str
    description: str | None
    entities: tuple[NormalizedEntity, ...]
    steps: tuple[NormalizedStep, ...]
    tests: tuple[NormalizedTest, ...]

    def checklist(self) -> tuple[str, ...]:
        """Return an agent-readable completion checklist."""

        items = [f"Parse journey '{self.name}'"]
        items.extend(f"Implement entity '{entity.name}'" for entity in self.entities)
        items.extend(f"Implement step '{step.name}'" for step in self.steps)
        items.extend(f"Pass acceptance test '{test.name}'" for test in self.tests)
        return tuple(items)


def normalize(spec: JourneySpec) -> NormalizedJourney:
    """Create a deterministic normalized view of a Journey spec."""

    return NormalizedJourney(
        name=spec.name,
        slug=slugify(spec.name),
        description=spec.description,
        entities=tuple(
            NormalizedEntity(
                name=entity.name,
                slug=slugify(entity.name),
                fields=tuple(
                    NormalizedField(
                        name=field.name,
                        type_name=_field_type(field),
                        modifiers=_field_modifiers(field),
                    )
                    for field in entity.fields
                ),
            )
            for entity in spec.entities
        ),
        steps=tuple(
            NormalizedStep(
                name=step.name,
                slug=slugify(step.name),
                requires=step.requires,
                actor=step.actor.name,
                authenticated=step.actor.authenticated,
                inputs=tuple(
                    NormalizedField(
                        name=field.name,
                        type_name=_input_type(field),
                        required=field.required,
                        modifiers=_field_modifiers(field),
                    )
                    for field in step.inputs
                ),
                outputs=tuple(output.name for output in step.outputs),
                errors=tuple(error.code_name for error in step.errors),
            )
            for step in spec.steps
        ),
        tests=tuple(
            NormalizedTest(
                name=test.name,
                slug=slugify(test.name),
                steps=tuple(command.step_name for command in test.commands),
            )
            for test in spec.tests
        ),
    )


def slugify(value: str) -> str:
    value = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1-\2", value)
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", value)
    value = value.replace("_", "-").replace(" ", "-")
    value = re.sub(r"[^a-zA-Z0-9-]+", "", value).strip("-").lower()
    value = re.sub(r"-+", "-", value)
    return value or "journey"


def _field_type(field) -> str:
    if field.state_type:
        return "state(" + " -> ".join(field.state_type.states) + ")"
    if field.enum_type:
        return "enum(" + ", ".join(field.enum_type.values) + ")"
    return field.type_name


def _input_type(field) -> str:
    if field.enum_type:
        return "enum(" + ", ".join(field.enum_type.values) + ")"
    return field.type_name


def _field_modifiers(field) -> tuple[str, ...]:
    modifiers = []
    source = getattr(field, "modifiers", None)
    if not source:
        return tuple()
    for attr in ("unique", "hashed", "auto"):
        if getattr(source, attr, False):
            modifiers.append(attr)
    if getattr(source, "format_type", None):
        modifiers.append(f"format({source.format_type})")
    if getattr(source, "min_val", None) is not None:
        modifiers.append(f"min({source.min_val})")
    if getattr(source, "max_val", None) is not None:
        modifiers.append(f"max({source.max_val})")
    return tuple(modifiers)

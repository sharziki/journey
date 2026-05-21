"""Shared code generation helpers."""

from ..parser.ast_nodes import Action, JourneySpec, Step


def snake(name: str) -> str:
    result = []
    for i, ch in enumerate(name):
        if ch.isupper() and i > 0:
            result.append("_")
        result.append(ch.lower())
    return "".join(result)


def plural(name: str) -> str:
    if name.endswith("s"):
        return name + "es"
    if name.endswith("y"):
        return name[:-1] + "ies"
    return name + "s"


def primary_create_action(step: Step) -> Action | None:
    return next((action for action in step.actions if action.kind == "create" and action.target), None)


def route_path(step: Step) -> str:
    """Derive a stable route from step semantics instead of example names."""
    create_action = primary_create_action(step)
    if create_action and create_action.target:
        return f"/{plural(snake(create_action.target)).replace('_', '-')}"
    return f"/{step.name.replace('_', '-')}"


def authenticated_actor_entity(spec: JourneySpec) -> str | None:
    for step in spec.steps:
        if step.actor.authenticated and spec.get_entity(step.actor.name):
            return step.actor.name
    return None

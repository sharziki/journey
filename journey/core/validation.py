"""Validation for Journey specs.

The validator is intentionally framework-neutral. It checks the portable
Journey contract before any adapter generates code from it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from journey.parser.ast_nodes import JourneySpec, Step


BUILTIN_TYPES = {"string", "id", "timestamp", "number", "int", "boolean", "enum", "state"}
ACTION_KINDS = {"create", "find", "transition", "send", "verify", "call", "access", "reference"}


@dataclass(frozen=True)
class ValidationIssue:
    """A single validation finding."""

    severity: str
    code: str
    message: str
    path: str


@dataclass(frozen=True)
class ValidationReport:
    """Validation output suitable for CLI display or agent consumption."""

    issues: tuple[ValidationIssue, ...]

    @property
    def errors(self) -> tuple[ValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "error")

    @property
    def warnings(self) -> tuple[ValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "warning")

    @property
    def ok(self) -> bool:
        return not self.errors

    def raise_for_errors(self) -> None:
        if self.errors:
            rendered = "\n".join(
                f"{issue.severity.upper()} {issue.code} at {issue.path}: {issue.message}"
                for issue in self.errors
            )
            raise JourneyValidationError(rendered, self)


class JourneyValidationError(ValueError):
    """Raised when a Journey spec fails validation."""

    def __init__(self, message: str, report: ValidationReport):
        self.report = report
        super().__init__(message)


def validate(spec: JourneySpec, *, strict: bool = False) -> ValidationReport:
    """Validate cross-references and structural invariants in a Journey spec."""

    issues: list[ValidationIssue] = []

    entity_names = [entity.name for entity in spec.entities]
    step_names = [step.name for step in spec.steps]

    _duplicates(entity_names, "entity", "entities", issues)
    _duplicates(step_names, "step", "steps", issues)

    entities = {entity.name: entity for entity in spec.entities}
    steps = {step.name: step for step in spec.steps}

    for entity in spec.entities:
        field_names = [field.name for field in entity.fields]
        _duplicates(field_names, "field", f"entity.{entity.name}", issues)
        for field in entity.fields:
            path = f"entity.{entity.name}.{field.name}"
            if field.ref_entity and field.ref_entity not in entities:
                issues.append(_error("unknown_entity", f"Unknown entity reference '{field.ref_entity}'", path))
            elif field.type_name not in BUILTIN_TYPES and field.type_name not in entities:
                issues.append(_error("unknown_type", f"Unknown field type '{field.type_name}'", path))
            if field.state_type:
                _duplicates(field.state_type.states, "state", path, issues)
                for source, targets in field.state_type.transitions.items():
                    if source not in field.state_type.states:
                        issues.append(_error("unknown_state", f"Transition source '{source}' is not declared", path))
                    for target in targets:
                        if target not in field.state_type.states:
                            issues.append(_error("unknown_state", f"Transition target '{target}' is not declared", path))
            if field.enum_type:
                _duplicates(field.enum_type.values, "enum value", path, issues)

    for step in spec.steps:
        path = f"step.{step.name}"
        if step.requires and step.requires not in steps:
            issues.append(_error("unknown_step", f"Step requires unknown step '{step.requires}'", path))
        if step.actor.name != "anonymous" and step.actor.name not in entities:
            issues.append(_error("unknown_actor", f"Actor '{step.actor.name}' is not an entity", path))
        if step.actor.authenticated and not _session_steps(spec):
            issues.append(
                _error(
                    "missing_session_step",
                    f"Authenticated step '{step.name}' requires a session-producing action such as create_session(...)",
                    path,
                )
            )
        _duplicates([field.name for field in step.inputs], "input", f"{path}.input", issues)
        _duplicates([field.name for field in step.outputs], "output", f"{path}.output", issues)
        _duplicates([error.code_name for error in step.errors], "error", f"{path}.errors", issues)
        _validate_step_refs(step, entities, issues)

    session_token_outputs = _session_token_outputs(spec)
    for test in spec.tests:
        if not test.commands:
            issues.append(_warning("empty_test", f"Test '{test.name}' has no commands", f"test.{test.name}"))
        captured: set[str] = set()
        for index, command in enumerate(test.commands):
            path = f"test.{test.name}.command[{index}]"
            step = steps.get(command.step_name)
            if not step:
                issues.append(_error("unknown_step", f"Test calls unknown step '{command.step_name}'", path))
                continue
            if step.actor.authenticated and not command.auth_token_var and not (captured & session_token_outputs):
                issues.append(
                    _error(
                        "missing_auth_token",
                        f"Test command for authenticated step '{step.name}' must use 'as authenticated(token)' or follow a captured session token",
                        path,
                    )
                )
            input_names = {field.name for field in step.inputs}
            for key in command.args:
                if not key.isdigit() and key not in input_names:
                    issues.append(_warning("unknown_input", f"Argument '{key}' is not declared by step '{step.name}'", path))
            required_inputs = {field.name for field in step.inputs if field.required}
            missing = sorted(required_inputs - {key for key in command.args if not key.isdigit()})
            for name in missing:
                issues.append(_error("missing_input", f"Missing required input '{name}'", path))
            if command.capture:
                captured.add(command.capture)

    if strict:
        issues = [
            ValidationIssue("error" if issue.severity == "warning" else issue.severity, issue.code, issue.message, issue.path)
            for issue in issues
        ]

    return ValidationReport(tuple(issues))


def _validate_step_refs(step: Step, entities: dict[str, object], issues: list[ValidationIssue]) -> None:
    input_names = {field.name for field in step.inputs}
    variables: dict[str, str] = {}
    for action in step.actions:
        path = f"step.{step.name}.action"
        if action.kind not in ACTION_KINDS:
            issues.append(_error("unknown_action", f"Unsupported action kind '{action.kind}'", path))
        if action.kind in {"create", "find"}:
            if action.target not in entities:
                issues.append(_error("unknown_entity", f"Action targets unknown entity '{action.target}'", path))
            if action.variable:
                variables[action.variable] = action.target or ""
        if action.kind == "transition":
            variable = action.target or ""
            if variable not in variables:
                issues.append(_warning("unknown_variable", f"Transition references variable '{variable}' before it is created or found", path))
        for value in action.params.values():
            _validate_value_ref(value, input_names, variables, path, issues)

    for output in step.outputs:
        if "." in output.expression:
            var = output.expression.split(".", 1)[0]
            if var not in variables and var != "session":
                issues.append(_warning("unknown_output", f"Output references unknown variable '{var}'", f"step.{step.name}.output.{output.name}"))


def _session_steps(spec: JourneySpec) -> list[Step]:
    return [
        step
        for step in spec.steps
        if any(action.kind == "call" and action.target == "create_session" for action in step.actions)
    ]


def _session_token_outputs(spec: JourneySpec) -> set[str]:
    outputs = set()
    for step in _session_steps(spec):
        for output in step.outputs:
            if output.expression == "session.token":
                outputs.add(output.name)
    return outputs


def _validate_value_ref(
    value: str,
    input_names: set[str],
    variables: dict[str, str],
    path: str,
    issues: list[ValidationIssue],
) -> None:
    if value.startswith("input."):
        name = value.split(".", 1)[1]
        if name not in input_names:
            issues.append(_error("unknown_input", f"Action references unknown input '{name}'", path))
    elif "." in value:
        var = value.split(".", 1)[0]
        if var not in variables and var not in {"actor", "current_user", "last_email", "session"}:
            issues.append(_warning("unknown_variable", f"Action references unknown variable '{var}'", path))


def _duplicates(values: Iterable[str], label: str, path: str, issues: list[ValidationIssue]) -> None:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            issues.append(_error("duplicate_name", f"Duplicate {label} '{value}'", path))
        seen.add(value)


def _error(code: str, message: str, path: str) -> ValidationIssue:
    return ValidationIssue("error", code, message, path)


def _warning(code: str, message: str, path: str) -> ValidationIssue:
    return ValidationIssue("warning", code, message, path)

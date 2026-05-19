# Contributing

Journey is early and intentionally open to new adapters, stricter validators,
and journey examples that reveal gaps in the compiler.

## Local Setup

```bash
python -m pip install -e ".[dev]"
python -m pytest
```

## Before Opening a PR

Run the same checks CI runs:

```bash
journey validate examples/auth_workspaces.journey --strict
journey validate examples/journey_spine.journey --strict
journey test examples/auth_workspaces.journey --robustness strict --clean
journey test examples/journey_spine.journey --robustness strict --clean
python -m build
python -m twine check dist/*
```

## Useful Contributions

- Add `.journey` examples that break assumptions in codegen.
- Improve `journey.core.validation` so errors are caught before generation.
- Add adapters that implement `journey.adapters.base.JourneyAdapter`.
- Make generated tests stricter without making the Journey DSL harder to read.

# Contributing

Journey is early and intentionally open to lightweight graph improvements, new
route/page detectors, stricter validators, adapters, and examples that reveal
gaps in how agents use product intent.

## Local Setup

```bash
python -m pip install -e ".[dev]"
python -m pytest
```

## Before Opening a PR

Run the same checks CI runs:

```bash
python -m pytest
journey validate examples/lightweight_client_portal
journey doctor examples/lightweight_client_portal
journey diff examples/lightweight_client_portal --check
for file in examples/*.journey; do
  journey validate "$file" --strict
  journey test "$file" --robustness strict --clean
done
python -m build
python -m twine check dist/*
```

## Useful Contributions

- Add lightweight `.journey` graph examples for real app structures.
- Add page/API route detectors for more frameworks.
- Improve `journey.core.validation` so errors are caught before generation.
- Add adapters that implement `journey.adapters.base.JourneyAdapter`.
- Make generated tests stricter without making the Journey DSL harder to read.

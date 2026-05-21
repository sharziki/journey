# Production Readiness

Journey `v0.2.3` is the current production-ready beta release for:

- lightweight `.journey` repo/page/API graphs
- agent handoff generation
- graph health and drift checks
- structured backend journeys through the FastAPI adapter
- generated pytest acceptance tests

## Install

```bash
python -m pip install https://github.com/sharziki/journey/releases/download/v0.2.3/journey_lang-0.2.3-py3-none-any.whl
```

PyPI publishing is not enabled yet because PyPI Trusted Publishing still needs to be configured for this repository. Until then, the GitHub release wheel is the production install artifact.

## Release Artifact

- Release: <https://github.com/sharziki/journey/releases/tag/v0.2.3>
- Wheel: `journey_lang-0.2.3-py3-none-any.whl`
- Source distribution: `journey_lang-0.2.3.tar.gz`

## E2E Verification

The production install path was verified from a fresh virtual environment using the public GitHub release wheel:

```bash
python -m venv /tmp/journey-verify/venv
/tmp/journey-verify/venv/bin/python -m pip install \
  https://github.com/sharziki/journey/releases/download/v0.2.3/journey_lang-0.2.3-py3-none-any.whl
/tmp/journey-verify/venv/bin/journey validate library_borrowing.journey --strict
/tmp/journey-verify/venv/bin/journey test library_borrowing.journey --robustness strict --clean
```

Expected result:

```text
ok
library_borrowing/test_journey.py::TestMemberBorrowsAndReturnsABook::test_member_borrows_and_returns_a_book PASSED
```

## Release Checks

- `python -m pytest -q`
- `python -m pytest tests/test_cli_e2e.py -q`
- `journey validate examples/lightweight_client_portal`
- `journey doctor examples/lightweight_client_portal`
- `journey diff examples/lightweight_client_portal --check`
- strict validation and generated acceptance tests for every `examples/*.journey`
- clean install from the public `v0.2.3` GitHub release wheel
- built-wheel smoke test via `scripts/e2e_wheel_smoke.sh`
- `python -m build`
- `python -m twine check dist/*`

## Known Boundaries

- FastAPI is the only codegen adapter today.
- Natural-language journeys are useful for handoffs but are not yet a full codegen target.
- Autonomous execution depends on a configured local agent runtime.
- PyPI publishing is prepared but not enabled until Trusted Publishing is configured.

# Changelog

## 0.2.0

- Repositioned Journey around a lightweight core workflow for linked repo, page, and API journeys.
- Added `journey create .` scaffolding for `.journey/repo.journey`, `.journey/pages/`, and `.journey/apis/`.
- Added `journey sync`, `journey doctor`, `journey diff`, and `journey status` for keeping journey graphs healthy.
- Made `journey agent`, `journey manifest`, `journey inspect`, `journey validate`, `journey watch`, and `journey execute` work with lightweight journey graphs.
- Added the `examples/lightweight_client_portal` graph example.
- Added package and CI coverage for the lightweight graph workflow.
- Kept the FastAPI backend generator as an optional structured journey adapter.
- Added runtime configuration hooks for generated FastAPI database URL and session TTL.

## 0.1.0

- Initial Journey parser, AST, CLI, and FastAPI code generator.
- Added framework-neutral validation and normalized agent navigation graph.
- Added FastAPI and Markdown adapters.
- Added robustness profiles: `fast`, `standard`, and `strict`.
- Added generated `JOURNEY.md` and `journey.agent.json` artifacts for agents.
- Added source tests, CI workflow, MIT license, and Python package metadata.

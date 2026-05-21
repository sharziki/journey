# Changelog

## Unreleased

- Added `JOURNEY_FLOW.md` generation for lightweight folder journeys so `journey create .` and `journey sync .` produce a single route, feature, source, and acceptance walkthrough.
- Added route fields to generated page/API child journeys so each tier is readable without jumping back to the flow summary.
- Added lightweight source signal extraction for generated journey docs: page actions, links, API calls, state words, API methods, request hints, and response statuses.
- Added route and source metadata to lightweight agent manifests so agents can reason about linked journeys without scraping document bodies.
- Improved flat-file route normalization for Remix/React Router-style files such as `_index.tsx` and `dashboard.$id.tsx`.
- Made `journey sync` refresh child journey metadata without overwriting hand-edited journey content.
- Made `journey doctor` and `journey diff --check` report stale route metadata.
- Removed FastAPI route generation assumptions tied to the auth example: create routes now derive from the created entity, duplicate checks use the target entity's unique field, and auth sessions resolve the authenticated actor entity.
- Added auth/session validation for structured journeys and made generated tests auto-thread captured session tokens into authenticated calls.

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

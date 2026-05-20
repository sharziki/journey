# Journey Vision

Journey is natural-language project memory for software agents.

The core idea is simple: software should start from a durable, readable product story. A `.journey` file captures that story as mission, workflows, entities, rules, acceptance cases, crew roles, open questions, and repair notes. Humans edit the journey. Agents and tools use it as the project spine.

Journey must stay abstract. It is not a FastAPI format, a frontend format, or a task format. It is an intent format with adapters.

## Product Promise

Write what should exist. Agents keep working until the journey is done.

Journey should let someone describe an idea in natural language, add structure only where precision matters, then have agents turn that description into working implementation, tests, docs, cleanup passes, and ongoing repairs.

## What A Journey File Is

A `.journey` file is:

- a product story
- an agent briefing
- an executable spec
- a test contract
- a crew assignment file
- a repair target
- a cleanup ledger
- a portable handoff format
- a neutral intermediate representation for tools

It should be readable like a short design paper and strict enough in the right places that agents and compilers can act on it.

## Plug-In Model

Anyone should be able to plug anything into Journey:

- coding agents that read journeys as standing context
- generators that turn journeys into code
- validators that compare journeys against real behavior
- documentation tools that explain journeys to humans
- planners that break journeys into tasks
- repair loops that use journeys as the source of truth
- cleanup agents that inspect the repo, find drift, remove stale work, and write repair notes
- framework adapters for FastAPI, Django, Next.js, mobile apps, infra, data jobs, or internal tools

The stable contract is:

```text
.journey file -> Journey AST -> adapters
```

Adapters can produce anything. The journey remains the portable spine.

## The Loop

```text
write or update the journey
planner picks the next unfinished slice
builder updates implementation
tester turns acceptance into checks
reviewer compares behavior to the journey
cleanup finds drift and stale work
agent records gaps or repairs them
loop continues until the journey is done
```

This is the important part: Journey is not meant to be a one-shot code generator. It is meant to be the file an agent crew keeps returning to. The crew should be able to ask, "What still does not match the journey?", do the work, verify it, clean up after itself, and mark the journey closer to done.

## First Target

The current proof of concept compiles backend workflows into tested FastAPI apps. That is one adapter. It is the wedge, not the ceiling.

The broader direction is multi-target agent development:

- backend APIs
- frontend flow hints
- OpenAPI specs
- end-to-end tests
- product docs
- QA checklists
- migrations
- agent onboarding context
- infrastructure plans
- support workflows
- data pipelines
- cleanup reports
- repair ledgers

## Design Principles

Natural language first. Journey should feel like writing the product behavior, not like filling out framework config.

Target-neutral core. The Journey AST should not know or care whether an adapter outputs Python, TypeScript, docs, tasks, prompts, or runtime configuration.

Structured where it matters. Inputs, outputs, entities, state transitions, errors, permissions, acceptance cases, and crew handoff points need deterministic shape.

Agents are first-class users. The format should brief agents, coordinate agents, assign cleanup work, and give them a stable memory of the project.

Generated code is disposable. The journey is the asset. Implementation can be regenerated, repaired, or replaced.

Tests are part of the story. A journey should say what happens and prove it happens.

Self-healing is a product requirement. When implementation drifts, Journey should help identify whether the code, tests, docs, generated artifacts, or story needs to change.

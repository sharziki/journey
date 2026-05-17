# Journey Vision

Journey is a universal story format for software agents.

The core idea is simple: software should start from a durable, readable product story. A `.journey` file captures that story as workflows, entities, rules, acceptance cases, open questions, and repair notes. Humans edit the journey. Agents and tools use it as the project spine.

Journey must stay abstract. It is not a FastAPI format, a frontend format, or a task format. It is an intent format with adapters.

## Product Promise

Write the journey. Agents build the software.

Journey should let someone describe an idea in structured natural language, then have agents turn that description into working implementation, tests, docs, and ongoing repairs.

## What A Journey File Is

A `.journey` file is:

- a product story
- an agent briefing
- an executable spec
- a test contract
- a repair target
- a portable handoff format
- a neutral intermediate representation for tools

It should be readable like a short design paper and strict enough that agents and compilers can act on it.

## Plug-In Model

Anyone should be able to plug anything into Journey:

- coding agents that read journeys as standing context
- generators that turn journeys into code
- validators that compare journeys against real behavior
- documentation tools that explain journeys to humans
- planners that break journeys into tasks
- repair loops that use journeys as the source of truth
- framework adapters for FastAPI, Django, Next.js, mobile apps, infra, data jobs, or internal tools

The stable contract is:

```text
.journey file -> Journey AST -> adapters
```

Adapters can produce anything. The journey remains the portable spine.

## The Loop

```text
write journey
agent reads spine
agent updates implementation
tests verify acceptance
agent reports gaps
agent repairs drift
journey remains source of truth
```

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

## Design Principles

Readable first. Journey should feel like writing the product behavior, not like filling out framework config.

Target-neutral core. The Journey AST should not know or care whether an adapter outputs Python, TypeScript, docs, tasks, prompts, or runtime configuration.

Structured where it matters. Inputs, outputs, entities, state transitions, errors, permissions, and acceptance cases need deterministic shape.

Agents are first-class users. The format should brief agents, coordinate agents, and give them a stable memory of the project.

Generated code is disposable. The journey is the asset. Implementation can be regenerated, repaired, or replaced.

Tests are part of the story. A journey should say what happens and prove it happens.

Self-healing is a product requirement. When implementation drifts, Journey should help identify whether the code, tests, or story needs to change.

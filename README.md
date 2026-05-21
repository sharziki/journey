<p align="center">
  <h1 align="center">Journey</h1>
  <p align="center">
    <strong>Executable product stories for coding agents.</strong><br/>
    Write the workflow once. Journey turns it into code, tests, docs, and an agent handoff.
  </p>
</p>

<p align="center">
  <a href="https://github.com/sharziki/journey/actions/workflows/ci.yml"><img alt="CI" src="https://img.shields.io/github/actions/workflow/status/sharziki/journey/ci.yml?branch=main&label=CI"></a>
  <img alt="Python 3.11+" src="https://img.shields.io/badge/python-3.11%2B-3776AB">
  <img alt="Status: alpha" src="https://img.shields.io/badge/status-alpha-f59e0b">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-0f766e"></a>
</p>

<p align="center">
  <a href="#2-minute-quickstart">Quickstart</a> &bull;
  <a href="#before-journey--after-journey">Before/After</a> &bull;
  <a href="#demo">Demo</a> &bull;
  <a href="#examples">Examples</a> &bull;
  <a href="#adapters-roadmap">Adapters</a> &bull;
  <a href="#contributing">Contributing</a>
</p>

<p align="center">
  <img src="docs/assets/journey-hero.png" alt="Journey turns product stories into generated code, tests, and agent workflows." width="100%">
</p>

Journey is a small open-source language and CLI for mapping product intent in `.journey` files.

Core Journey is lightweight: it creates, links, validates, and summarizes repo/page/flow journeys without requiring a database, server, or generated app.

The optional FastAPI adapter compiles structured journeys into a working backend with SQLAlchemy models, Pydantic schemas, route handlers, generated pytest acceptance tests, and agent-readable handoff files.

The bigger idea is simple: agents should not start from scattered prompts. They should read the project spine, build against it, test against it, and repair drift when the code no longer matches the story.

## 2 Minute Quickstart

```bash
git clone https://github.com/sharziki/journey.git
cd journey
python -m pip install -e ".[dev]"
journey create .
journey agent .
```

Those commands create a linked `.journey` map for the project, then write an agent handoff from that file graph. No database, server, or code generator is required.

When files change, rescan without overwriting edited journey specs:

```bash
journey sync .
journey doctor .
```

For the optional FastAPI backend adapter, run:

```bash
journey agent examples/auth_workspaces.journey
```

That command reads a structured backend journey, generates the FastAPI implementation, writes the agent handoff, and runs the generated acceptance tests.

You should see:

```text
3 passed
Journey accepted: generated implementation satisfies current acceptance tests.
```

Run the generated API:

```bash
journey run examples/auth_workspaces.journey
```

Open:

```text
http://127.0.0.1:8000/docs
```

Create a readable route and feature map without opening the app:

```bash
journey create examples/auth_workspaces.journey
```

If a project does not have a journey yet, scaffold a linked journey tree:

```bash
journey create .
```

That writes `.journey/repo.journey` plus page-level journeys under `.journey/pages/` and API journeys under `.journey/apis/`. The repo journey links to the child journeys so people can read the product flow by folder, page, and route instead of clicking through the running app.

The generated project lives at:

```text
generated/auth_workspaces/
├── JOURNEY.md
├── journey.agent.json
├── app.py
├── database.py
├── models.py
├── routes.py
├── schemas.py
└── test_journey.py
```

## Before Journey / After Journey

| Before Journey | After Journey |
|----------------|---------------|
| Product behavior lives in prompts, tickets, docs, and memory | Product behavior lives in one `.journey` source of truth |
| Agents repeatedly ask for context | Agents read `JOURNEY.md` and `journey.agent.json` |
| Backend routes, models, and tests drift apart | Code and acceptance tests are generated from the same workflow |
| "Done" is subjective | `journey agent` and `journey test` prove the current contract |
| New contributors must reverse-engineer intent | New contributors start with the journey file and examples |

## Demo

<p align="center">
  <img src="docs/assets/journey-terminal-demo.svg" alt="Terminal demo showing Journey generating files and passing acceptance tests." width="100%">
</p>

The current demo is a screenshot-style terminal capture. A short GIF belongs here next: write a journey, run `journey agent`, open `/docs`, and show the generated acceptance test passing.

## How It Works

Core mode:

```text
repo folder
     |
     v
.journey/repo.journey + linked page journeys
     |
     v
Journey graph resolver
     |
     v
JOURNEY.md + journey.agent.json
     |
     v
Agent implementation / repair loop
```

Adapter mode:

```text
.journey file
     |
     v
Parser + validator
     |
     v
FastAPI codegen + agent manifest
     |
     v
Generated pytest acceptance tests
     |
     v
Agent repair loop
```

The `.journey` file is the portable contract. The generated code is ordinary app code that you can inspect, edit, test, deploy, or replace with another adapter later.

## A Tiny Journey

```journey
journey "Auth API" {
  entity User {
    email     string unique
    password  string hashed
    status    state(pending -> active -> suspended)
  }

  step signup {
    actor anonymous
    input {
      email     string required format(email)
      password  string required min(8)
    }
    action {
      user = create User(email: input.email, password: input.password, status: pending)
    }
    output {
      user_id user.id
    }
  }
}
```

Journey turns structured flows like this into:

- SQLAlchemy models
- Pydantic request/response schemas
- FastAPI route handlers
- state transition guards
- password hashing for `hashed` fields
- generated pytest scenarios
- `JOURNEY.md` for humans and agents
- `journey.agent.json` for tools and coding agents

## Examples

The repo includes working journeys you can run today:

| Example | What it proves | Try it |
|---------|----------------|--------|
| `examples/auth_workspaces.journey` | SaaS signup, email verification, login, workspace creation, invitations | `journey agent examples/auth_workspaces.journey` |
| `examples/crm_sales_pipeline.journey` | CRM accounts, contacts, deals, and qualification | `journey test examples/crm_sales_pipeline.journey --clean` |
| `examples/ai_receptionist_backend.journey` | AI receptionist call capture and appointment booking | `journey test examples/ai_receptionist_backend.journey --clean` |
| `examples/car_dealership_leads.journey` | Dealer lead capture, contact, and test-drive scheduling | `journey test examples/car_dealership_leads.journey --clean` |
| `examples/journey_spine.journey` | Journey dogfooding itself as an agent-readable project spine | `journey agent examples/journey_spine.journey` |

Run every shipped example:

```bash
for f in examples/*.journey; do
  journey test "$f" --clean
done
```

## Dogfooding Journey

Journey uses `.journey` files as its own project spine.

When an agent enters this repo, it should:

```bash
find . -name "*.journey" -not -path "./generated/*"
journey agent examples/journey_spine.journey
journey agent examples/auth_workspaces.journey
```

Then it should read:

```text
generated/<journey>/JOURNEY.md
generated/<journey>/journey.agent.json
```

That handoff tells the agent what the product is, what still needs to be built, and what acceptance tests must pass.

## Agent Mode

Use this when you want Journey to prepare the workspace and run acceptance without spawning another agent:

```bash
journey agent <file.journey>
```

Use this when a local coding-agent runtime is configured and you want the deliverable loop:

```bash
journey execute <file.journey> --autonomous
```

`execute --autonomous` currently auto-detects Codex CLI when available. If you use another runtime, set `JOURNEY_AGENT_COMMAND` or use `journey watch`.

```bash
journey watch product.journey \
  --agent-command "codex exec \"Work on: {item}. Read {handoff_md} and {handoff_json}.\""
```

## CLI Reference

| Command | What it does |
|---------|--------------|
| `journey agent <path>` | Write agent handoff files from a lightweight journey graph, or run adapter generation for a structured backend journey |
| `journey create [path]` | Create linked repo/page journeys, or write a route and feature flow document for an existing `.journey` |
| `journey sync [path]` | Rescan a project and add missing page/API journeys without overwriting edited specs |
| `journey doctor [path]` | Check graph health: missing links, orphan journeys, stale sources, missing specs, and acceptance gaps |
| `journey execute <file> --autonomous` | Run the deliverable-by-deliverable builder/QA loop with a local agent runtime |
| `journey watch <file>` | Lower-level watch loop for custom agent commands |
| `journey compile <file>` | Optional adapter: generate a FastAPI project |
| `journey test <file>` | Optional adapter: compile and run generated pytest scenarios |
| `journey run <file>` | Optional adapter: compile and start the generated FastAPI app with uvicorn |
| `journey inspect <path>` | Print a lightweight journey graph or structured journey AST |
| `journey validate <path>` | Validate graph links or structured cross-references before generation |
| `journey manifest <path>` | Generate `JOURNEY.md` and `journey.agent.json` from a lightweight graph or structured journey |
| `journey shape <file>` | Shape loose natural-language input into a handoff |

## Handwritten Journeys

The long-term format is natural-language first:

```journey
journey "Workspace Invite"

design: ./design.md

mission:
  Let a workspace owner invite a teammate and know exactly what happened.

pages:
  - Signup
  - Verify Email
  - Workspace Home
  - Invite Teammate

page "Invite Teammate":
  purpose:
    Let a workspace owner invite another person by email and role.

  acceptance:
    - owner can invite a teammate
    - non-owner cannot invite
    - duplicate invitation is rejected
```

The v0.1 compiler generates code from the structured backend syntax in `examples/*.journey`. Loose handwritten journeys can already be shaped into a readable handoff:

```bash
journey shape idea.journey
```

See [docs/handwritten-journey-format.md](docs/handwritten-journey-format.md) and [docs/design.md](docs/design.md).

## Adapters Roadmap

FastAPI is the first working adapter. The point of Journey is that the `.journey` file should outlive any one framework.

Planned adapters:

| Adapter | Target |
|---------|--------|
| Next.js frontend generation | Pages, forms, route handlers, flow-aware UI states |
| Supabase | Auth, Postgres schema, row-level security policies, edge functions |
| Prisma | Schema generation and typed model access |
| Django | Models, views, serializers, admin, and tests |
| Node/Express | Routes, middleware, validation, and integration tests |

Other useful targets:

- OpenAPI export
- QA checklists
- seed data
- browser automation scripts
- support and operations playbooks
- agent task plans

## Project Structure

```text
journey/
├── parser/      # lexer, recursive descent parser, AST dataclasses
├── core/        # validation, normalization, config
├── codegen/     # FastAPI, SQLAlchemy, Pydantic, pytest generation
├── adapters/    # adapter wrappers and markdown handoff output
└── cli/         # journey command line interface
```

## Status

Journey is v0.1 alpha.

Working today:

- lightweight linked repo/page journeys under `.journey/`
- API route journeys under `.journey/apis/`
- folder-level agent handoffs with no database or runtime requirement
- graph-aware `inspect` and `validate` commands for linked journeys
- `doctor` health checks for missing links, orphan journeys, stale sources, missing specs, and acceptance gaps
- structured `.journey` syntax
- parser and semantic validation
- FastAPI backend generation
- SQLAlchemy model generation
- Pydantic schema generation
- generated pytest acceptance tests
- agent-facing `JOURNEY.md`
- machine-readable `journey.agent.json`
- `agent`, `execute`, `watch`, `shape`, `compile`, `test`, `run`, `inspect`, `validate`, and `manifest` commands
- `create` for linked folder-level journeys and existing-journey flow documents
- `sync` for adding newly discovered page/API journeys without overwriting edited specs
- `doctor` for checking whether the lightweight journey map is healthy

Still early:

- natural-language journeys are a direction, not the main compiler target yet
- FastAPI is the only production codegen adapter today
- autonomous execution depends on a configured local agent runtime
- the codegen needs more examples to force generalization

## Roadmap

- [x] Structured v0.1 syntax: entities, steps, state machines, tests
- [x] Parser: lexer + recursive descent to typed AST
- [x] FastAPI code generation: models, schemas, routes, tests
- [x] Agent handoff files: `JOURNEY.md` and `journey.agent.json`
- [x] Lightweight folder-level Journey graph handoff
- [x] SaaS auth/workspaces example
- [x] CRM example
- [x] AI receptionist backend example
- [x] Car dealership lead system example
- [x] Journey dogfoods itself with `examples/journey_spine.journey`
- [ ] GIF demo for README
- [ ] Natural-language journey sections as first-class compiler input
- [ ] Generic action/event system for emails, webhooks, tasks, and side effects
- [ ] Repair ledger for failed checks and drift
- [ ] OpenAPI export
- [ ] Next.js frontend generation
- [ ] Supabase adapter
- [ ] Prisma adapter
- [ ] Django adapter
- [ ] Node/Express adapter

## Contributing

The best contributions right now are examples that make Journey more general.

Good first PRs:

1. Add a `.journey` file for a real workflow.
2. Run `journey test examples/your_file.journey --clean`.
3. If it fails, improve the parser, validator, or codegen without deleting acceptance coverage.
4. Add the example to this README.

Useful example areas:

- SaaS onboarding and billing
- CRM workflows
- receptionist and appointment systems
- dealership lead routing
- marketplace orders
- clinic intake
- field service scheduling

## Release Checks

```bash
python -m pytest
for f in examples/*.journey; do journey test "$f" --clean; done
python -m build
python -m twine check dist/*
```

## License

MIT

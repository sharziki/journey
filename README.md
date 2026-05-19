<p align="center">
  <h1 align="center">Journey</h1>
  <p align="center">A universal story format for software agents.<br/>Write the journey. Agents build, test, and repair the software.</p>
</p>

<p align="center">
  <a href="#vision">Vision</a> &bull;
  <a href="#quickstart">Quickstart</a> &bull;
  <a href="#journey-files">Journey Files</a> &bull;
  <a href="#abstraction-model">Abstraction Model</a> &bull;
  <a href="#cli-reference">CLI</a> &bull;
  <a href="#roadmap">Roadmap</a>
</p>

---

## Vision

Journey is a portable intent format for making ideas real.

A `.journey` file is the spine of a project: the product story, domain vocabulary, user workflows, rules, acceptance cases, and repair loop in one agent-readable document. Humans edit the journey. Agents read it as standing context and continuously move the codebase toward it.

The first working adapter generates backends, but Journey itself is intentionally target-neutral. The bigger goal is broader: a universal format that any coding agent, generator, validator, framework, runtime, or workflow tool can use to understand what should exist, what done means, and how to self-heal when implementation drifts.

## The Problem

Software starts as stories, but implementation scatters those stories across routes, models, schemas, permissions, tests, docs, tickets, and prompts. Once AI agents enter the loop, that fragmentation gets worse: agents repeatedly re-learn context, hallucinate contracts, and patch symptoms instead of preserving product intent.

Journey gives agents a stable abstraction above the code. Instead of prompting an agent from scratch, you drop in a `.journey` file. It briefs the agent, defines the workflows, names the acceptance criteria, and gives the implementation a durable source of truth.

## The Idea

**Instead of editing code first, edit the journey.**

Journey files are structured enough to compile and test, but readable enough to feel like product writing. They declare:
- The **story** of what the product should do
- The **entities** and vocabulary of the domain
- The **steps** users or agents take
- The **rules**, states, permissions, errors, and side effects
- The **acceptance tests** that prove the story came to life

Today, one adapter turns a Journey backend workflow into a complete FastAPI project: models, schemas, routes, database, and a test harness that runs against a real database. Tomorrow, the same spine can guide frontend flows, docs, QA, migrations, agent onboarding, robots, data pipelines, internal tools, and self-healing repair loops.

## Quickstart

```bash
pip install -e .
journey compile examples/auth_workspaces.journey
journey test examples/auth_workspaces.journey
journey run examples/auth_workspaces.journey
```

Three commands. Parse, generate, validate, serve.

The repo also includes a self-referential example that describes Journey itself as an agent spine:

```bash
journey inspect examples/journey_spine.journey
journey test examples/journey_spine.journey
```

For a publish/CI-grade pass:

```bash
python -m pytest
journey validate examples/auth_workspaces.journey --strict
journey test examples/auth_workspaces.journey --robustness strict --clean
python -m build
python -m twine check dist/*
```

## Journey Files

A `.journey` file is an executable product story. This example describes a backend workflow, which is the first compiler target:

```journey
journey "User Onboarding" {
  description "Signup through workspace creation and team invitation"

  entity User {
    email       string  unique
    password    string  hashed
    status      state(pending -> active -> suspended)
    created_at  timestamp  auto
  }

  entity Workspace {
    name        string
    owner       User
    created_at  timestamp  auto
  }

  step signup {
    actor anonymous
    input {
      email     string  required  format(email)
      password  string  required  min(8)
    }
    action {
      user = create User(email: input.email, password: input.password, status: pending)
      send email(template: "verify_email", to: user.email)
    }
    output {
      user_id   user.id
      message   "Check your email to verify your account"
    }
    errors {
      email_taken  "A user with this email already exists"  409
    }
  }

  step login {
    requires verify_email
    actor anonymous
    input {
      email     string  required  format(email)
      password  string  required
    }
    action {
      user = find User(email: input.email)
      verify password(input.password, user.password)
      session = create_session(user)
    }
    output {
      token       session.token
      user_id     user.id
    }
    errors {
      invalid_credentials  "Email or password is incorrect"  401
      account_pending      "Please verify your email first"  403
    }
  }

  test "full onboarding" {
    do signup(email: "alice@example.com", password: "securepass123")
      expect status 201
      capture user_id

    do login(email: "alice@example.com", password: "securepass123")
      expect status 200
      capture token
  }
}
```

This compiles to a working FastAPI app with SQLAlchemy models, Pydantic schemas, route handlers, state machine validation, password hashing, session management, and end-to-end tests.

Journey can also describe the bigger agent loop itself:

```journey
journey "Journey Spine" {
  description "A living agent-readable product spine that turns stories into working software"

  entity JourneyFile {
    title   string  unique
    body    string
    status  state(draft -> normalized -> implemented -> verified -> healing)
  }

  step write_journey {
    input {
      title  string  required
      body   string  required
    }
    action {
      spine = create JourneyFile(title: input.title, body: input.body, status: draft)
    }
    output {
      journey_id  spine.id
      status      spine.status
    }
  }
}
```

## Abstraction Model

Journey should stay abstract at the core:

```text
          agents
            |
            v
  ┌──────────────────┐
  │   .journey file  │  human-readable intent
  └──────────────────┘
            |
            v
  ┌──────────────────┐
  │   Journey AST    │  normalized product graph
  └──────────────────┘
      |       |       |
      v       v       v
 generators validators agents
      |       |       |
      v       v       v
 backend   tests    repairs
 frontend  docs     plans
 infra     QA       briefings
```

The `.journey` file is the portable contract. Everything else is a plugin around it.

| Layer | Role |
|-------|------|
| **Journey file** | Human-editable story, workflow, rules, and acceptance |
| **Journey AST** | Normalized intermediate representation tools can consume |
| **Adapters** | Convert the AST into code, docs, plans, tests, prompts, or runtime config |
| **Validators** | Check whether an implementation satisfies the journey |
| **Agents** | Read the journey, update the world, report gaps, and repair drift |

The current repo includes one concrete compiler adapter:

```
.journey file
     |
     v
  [ Parser ]  ─── Lexer + Recursive Descent ──> AST
     |
     v
  [ Codegen ]  ─── AST Walkers ──> Python files
     |
     v
  ┌─────────────────────────────────────┐
  │  generated/                          │
  │  ├── models.py      (SQLAlchemy)     │
  │  ├── schemas.py     (Pydantic)       │
  │  ├── routes.py      (FastAPI)        │
  │  ├── database.py    (Engine/Session) │
  │  ├── app.py         (Entrypoint)     │
  │  └── test_journey.py (pytest)        │
  └─────────────────────────────────────┘
     |
     v
  [ Test Runner ]  ─── pytest ──> All scenarios pass ✓
     |
     v
  [ Server ]  ─── uvicorn ──> API live at /docs
```

| Component | What it does |
|-----------|-------------|
| **Journey file** | Acts as the agent-readable source of intent |
| **Entities** | Compile to SQLAlchemy models with auto-generated IDs, timestamps, foreign keys, and state machine validation |
| **State fields** | Generate enum classes with transition guards — invalid transitions raise at runtime |
| **Steps** | Become FastAPI route handlers with typed request/response schemas |
| **Actions** | `create` → INSERT + commit, `find` → SELECT + 404, `verify` → comparison + error, `transition` → state machine advancement |
| **Errors** | Become HTTPException raises with correct status codes |
| **Tests** | Compile to pytest classes that walk the full journey against an in-memory SQLite database |

This FastAPI path proves the shape, but it should not define the ceiling. A good Journey adapter could target Django, Next.js, mobile flows, Terraform, a design system, a browser automation script, a support playbook, or another agent's memory format.

## CLI Reference

| Command | What it does |
|---------|-------------|
| `journey compile <file>` | Parse and generate FastAPI project |
| `journey test <file>` | Compile + run all test scenarios |
| `journey run <file>` | Compile + start uvicorn with hot reload |
| `journey inspect <file>` | Pretty-print the parsed AST |
| `journey validate <file>` | Validate cross-references before generation |
| `journey manifest <file>` | Generate `JOURNEY.md` and `journey.agent.json` for agents |

Robustness profiles are designed to map cleanly to checkboxes in tools:

```bash
journey compile examples/auth_workspaces.journey --robustness strict --clean
journey test examples/auth_workspaces.journey --strict
```

| Profile | Intended use |
|---------|--------------|
| `fast` | Quick parse/generate loop while drafting |
| `standard` | Default open-source workflow: validate, generate app, generate agent manifest |
| `strict` | Publish/CI mode: clean output, run generated tests, fail on warnings |

Generated projects include:

- `JOURNEY.md` — an agent-readable implementation checklist
- `journey.agent.json` — structured entities, steps, tests, and robustness settings
- `test_journey.py` — acceptance tests generated from the journey

## Project Structure

```
journey/
├── parser/
│   ├── lexer.py        # Tokenizer — keywords, strings, operators
│   ├── parser.py       # Recursive descent parser → AST
│   └── ast_nodes.py    # Typed AST dataclasses
├── codegen/
│   ├── gen_models.py   # Entities → SQLAlchemy + state machines
│   ├── gen_schemas.py  # Steps → Pydantic request/response
│   ├── gen_routes.py   # Steps → FastAPI handlers
│   ├── gen_tests.py    # Test blocks → pytest harness
│   ├── gen_database.py # DB engine + session setup
│   └── gen_app.py      # FastAPI app entrypoint
├── adapters/
│   ├── fastapi.py      # Adapter wrapper + agent manifest output
│   └── markdown.py     # Agent-readable markdown summaries
├── core/
│   ├── config.py       # Robustness profiles
│   ├── normalize.py    # Stable normalized graph for agents
│   └── validation.py   # Framework-neutral semantic checks
└── cli/
    └── main.py         # compile, test, run, inspect commands
```

## Why This Exists

The AI agent workflow for building software needs a shared spine:

| Without Journey | With Journey |
|----------------|-------------|
| Intent spread across prompts, code, docs, and tests | Intent lives in a `.journey` spine |
| Agents repeatedly re-learn the product | Agents can be briefed by the same file |
| Endpoints and types get hallucinated | Contracts are generated and tested from the journey |
| Refactors drift from the product story | Changes flow through the source-of-truth journey |
| Debugging starts from code symptoms | Repair starts from acceptance failures against the journey |

Journey is designed to be the **first thing an agent reads or writes**. It is a project constitution, an executable spec, and eventually a persistent goal file that agents can watch.

## Journey is right for you if

- You're building AI agents that generate full-stack apps
- You want a portable format for product intent
- You want to build software by editing stories and workflows
- You want backend contracts validated before frontend work starts
- You want agents to share context instead of repeating long prompts
- You want state machines, permissions, errors, and tests captured in one place
- You want a path toward self-healing implementation loops

## What Journey is NOT

| It's not... | Because... |
|-------------|-----------|
| A no-code platform | You get real code you can read, extend, and deploy |
| A magic app generator | The journey is source of truth; agents and compilers still verify the work |
| A framework | The first output target is standard FastAPI — no runtime dependency on Journey |
| An ORM | It generates SQLAlchemy code. You own the output. |
| A testing framework | It generates pytest tests. Standard tooling, no lock-in. |
| Only a backend tool | Backend workflows are the first target, not the ceiling. |

## Status

This is v0.1 — a working proof of concept for the first compiler target. The parser, DSL, backend codegen, and generated test harness work for the included auth/workspaces journey and the self-describing Journey spine example.

The big vision is active-agent development: edit `.journey` files, have agents normalize the story, generate or update implementation, run acceptance tests, report gaps, and repair drift.

## Roadmap

- [x] DSL design — entities, steps, state machines, tests
- [x] Parser — lexer + recursive descent → typed AST
- [x] Code generation — models, schemas, routes, tests
- [x] CLI — compile, test, run, inspect
- [x] End-to-end validation — auth+workspaces journey passes all tests
- [x] Self-referential Journey spine example — Journey described as a journey
- [ ] Generic codegen — eliminate hardcoded patterns, make it work for any journey
- [ ] Agent spine sections — intent, vocabulary, principles, open questions, acceptance, repair notes
- [ ] Watch mode — edit `.journey`, auto-regenerate + re-test
- [ ] Repair mode — diagnose failing acceptance cases and update code or journey with a trace
- [ ] Multi-target outputs — backend, frontend flow hints, docs, QA checklists, OpenAPI
- [ ] Enriched DSL — explicit routes, error conditions, hooks, auth config
- [ ] Event system — side effects (email, webhooks) as emittable events
- [ ] Second validation spec — e-commerce journey compiles with zero new special cases
- [ ] Plugin system — custom action handlers, auth strategies, DB backends
- [ ] Universal handoff format — drop a `.journey` into any compatible agent and get project context

## Contributing

This is early. If the idea resonates, open an issue or PR. The most impactful contributions right now:

1. **Write a new `.journey` spec** that breaks the codegen — this reveals where generalization is needed
2. **Propose story syntax** for intent, vocabulary, principles, open questions, and repair notes
3. **Improve the codegen** to handle more patterns generically
4. **Design agent loops** that watch a journey, implement missing behavior, verify, and self-heal

## License

MIT

## Publishing

Build artifacts are standard Python distributions:

```bash
python -m pip install -e ".[dev]"
rm -rf dist build *.egg-info
python -m build
python -m twine check dist/*
python -m twine upload dist/*
```

The generated `journey.agent.json` file is the intended machine-readable handoff for coding agents. The generated `JOURNEY.md` file is the intended human/agent checklist for implementation progress.

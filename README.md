<p align="center">
  <h1 align="center">Journey</h1>
  <p align="center">A programming language for backend workflows.<br/>Write specs in structured English. Get tested FastAPI apps.</p>
</p>

<p align="center">
  <a href="#quickstart">Quickstart</a> &bull;
  <a href="#the-language">The Language</a> &bull;
  <a href="#how-it-works">How It Works</a> &bull;
  <a href="#cli-reference">CLI</a> &bull;
  <a href="#roadmap">Roadmap</a>
</p>

---

## The Problem

Building backends today means doing two things at once: figuring out **what** the system should do and **how** to implement it. These get tangled together — routes mixed with business logic, data models coupled to framework boilerplate, test coverage bolted on after the fact.

When AI agents build software, this gets worse. They burn tokens generating frontend and backend simultaneously, hallucinating endpoints that don't exist yet, fighting type mismatches across boundaries.

## The Idea

**What if you could describe your backend as a user journey — and get a working, tested API from it?**

Journey is a structured DSL where you declare:
- The **entities** in your system (with types, state machines, and relationships)
- The **steps** a user takes (with inputs, actions, outputs, and error cases)
- The **tests** that validate the whole flow end-to-end

The compiler turns this into a complete FastAPI project — models, schemas, routes, database, and a test harness that runs the journey against a real database. No mocks. No UI. Just the workflow, validated.

Once the backend contract is locked, building frontends is trivial. You're just skinning known endpoints.

## Quickstart

```bash
pip install -e .
journey compile examples/auth_workspaces.journey
journey test examples/auth_workspaces.journey
journey run examples/auth_workspaces.journey
```

Three commands. Parse, generate, validate, serve.

## The Language

A `.journey` file describes a complete backend workflow in ~100 lines:

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

## How It Works

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
| **Entities** | Compile to SQLAlchemy models with auto-generated IDs, timestamps, foreign keys, and state machine validation |
| **State fields** | Generate enum classes with transition guards — invalid transitions raise at runtime |
| **Steps** | Become FastAPI route handlers with typed request/response schemas |
| **Actions** | `create` → INSERT + commit, `find` → SELECT + 404, `verify` → comparison + error, `transition` → state machine advancement |
| **Errors** | Become HTTPException raises with correct status codes |
| **Tests** | Compile to pytest classes that walk the full journey against an in-memory SQLite database |

## CLI Reference

| Command | What it does |
|---------|-------------|
| `journey compile <file>` | Parse and generate FastAPI project |
| `journey test <file>` | Compile + run all test scenarios |
| `journey run <file>` | Compile + start uvicorn with hot reload |
| `journey inspect <file>` | Pretty-print the parsed AST |

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
└── cli/
    └── main.py         # compile, test, run, inspect commands
```

## Why This Exists

The AI agent workflow for building apps is broken:

| Without Journey | With Journey |
|----------------|-------------|
| Agent generates frontend + backend together | Agent writes a `.journey` spec first |
| Endpoints hallucinated, types mismatched | Backend contract validated by tests before any UI |
| Debugging spans two layers simultaneously | Backend is proven correct, frontend is just wiring |
| Refactoring breaks unknown dependencies | Change the spec, regenerate, re-test |
| 10,000 tokens to describe a signup flow | 30 lines of `.journey` spec |

Journey is designed to be the **first thing an agent writes** — before any React, before any CSS, before any deployment config. Lock the backend. Then skin it however you want.

## Journey is right for you if

- You're building AI agents that generate full-stack apps
- You want backend contracts validated before writing any frontend
- You're tired of mocking APIs that don't exist yet
- You want to describe workflows in near-English and get production code
- You need to rapidly prototype and test different user journeys
- You want state machines and error handling without the boilerplate

## What Journey is NOT

| It's not... | Because... |
|-------------|-----------|
| A no-code platform | You get real Python code you can read, extend, and deploy anywhere |
| A framework | It's a compiler. The output is standard FastAPI — no runtime dependency on Journey |
| An ORM | It generates SQLAlchemy code. You own the output. |
| A testing framework | It generates pytest tests. Standard tooling, no lock-in. |
| A frontend tool | Deliberately. Backend first. Frontend is someone else's problem (or your next step). |

## Status

This is v0.1 — a working proof of concept. The parser and DSL are solid. The codegen works for the auth+workspaces pattern but needs generalization to handle arbitrary journey specs without special-casing. See the roadmap.

## Roadmap

- [x] DSL design — entities, steps, state machines, tests
- [x] Parser — lexer + recursive descent → typed AST
- [x] Code generation — models, schemas, routes, tests
- [x] CLI — compile, test, run, inspect
- [x] End-to-end validation — auth+workspaces journey passes all tests
- [ ] Generic codegen — eliminate hardcoded patterns, make it work for any journey
- [ ] Enriched DSL — explicit routes, error conditions, hooks, auth config
- [ ] Event system — side effects (email, webhooks) as emittable events
- [ ] Second validation spec — e-commerce journey compiles with zero new special cases
- [ ] Plugin system — custom action handlers, auth strategies, DB backends
- [ ] Watch mode — edit `.journey`, auto-regenerate + re-test
- [ ] OpenAPI export — generate spec from journey without running the server

## Contributing

This is early. If the idea resonates, open an issue or PR. The most impactful contributions right now:

1. **Write a new `.journey` spec** that breaks the codegen — this reveals where generalization is needed
2. **Propose DSL syntax** for things the current language can't express
3. **Improve the codegen** to handle more patterns generically

## License

MIT

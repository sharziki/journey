# Handwritten Journey Format

This is the target direction for `.journey` files.

Journey should feel like a product brief a founder, designer, PM, or engineer would actually write. It should be natural-language first, then structured where agents need stable handles.

The v0.1 parser currently supports the structured backend syntax shown in `examples/*.journey`. The format below is the product direction for the natural-language agent spine.

## Shape

A good handwritten journey has three layers:

1. **Project spine** — high-level product intent, design reference, pages, flows, constraints, and done criteria.
2. **Page specs** — each page gets readable but structured requirements.
3. **Acceptance and cleanup** — what agents must prove, inspect, repair, and keep in sync.

## Example

```journey
journey "Workspace Invite"

design: ./design.md

mission:
  Let a workspace owner invite a teammate and know exactly what happened.
  The system should feel clear, trustworthy, and hard to misuse.

pages:
  - Signup
  - Verify Email
  - Workspace Home
  - Invite Teammate
  - Accept Invite

flows:
  onboarding:
    first: Signup
    then: Verify Email
    then: Workspace Home

  invite teammate:
    first: Workspace Home
    then: Invite Teammate
    then: Accept Invite

page "Signup":
  purpose:
    Create a pending user account.

  user sees:
    - email input
    - password input
    - create account button
    - clear duplicate-email error

  rules:
    - email is required
    - password must be at least 8 characters
    - duplicate emails are rejected

  acceptance:
    - valid signup creates a pending user
    - duplicate signup returns a 409-style error
    - generated tests cover both cases

page "Invite Teammate":
  purpose:
    Let a workspace owner invite another person by email and role.

  user sees:
    - teammate email
    - role selector
    - send invite button
    - invitation status

  rules:
    - only workspace owners can invite
    - role is admin, member, or viewer
    - already-invited emails show a useful error

  acceptance:
    - owner can invite a teammate
    - non-owner cannot invite
    - duplicate invitation is rejected

crew:
  planner:
    Find the next page, flow, or acceptance item not represented in code.

  builder:
    Implement the missing behavior.

  tester:
    Turn acceptance bullets into repeatable checks.

  cleanup:
    Compare code, tests, docs, and generated artifacts against this journey.
    Record drift and repair it before calling the journey done.

done when:
  - every page has implementation or an explicit open question
  - every flow has acceptance coverage
  - design.md has been followed or cited exceptions are written down
  - cleanup reports no open drift
```

## Design References

A journey may own or cite a design file:

```journey
design: ./design.md
```

Agents should read that file before implementation. The design file can define:

- visual principles
- layout rules
- components
- tone
- navigation
- accessibility requirements
- responsive behavior
- screenshots, links, or external references

If the journey and design file conflict, agents should stop and record the conflict instead of silently choosing one.

## Agent Rules

When an agent sees a handwritten journey:

- Treat the journey as the source of truth.
- Treat `design.md` as the visual/product design source if referenced.
- Preserve natural-language intent.
- Add structured anchors only where they help implementation, validation, or repair.
- Do not flatten the journey into framework config.
- Do not delete open questions just to make the project look done.
- Turn acceptance bullets into tests whenever possible.
- Keep looping until acceptance passes and cleanup finds no drift.

## Watch Runner

Use the runner when you want the journey to advance deliverable by deliverable:

```bash
journey execute product.journey --autonomous
```

That command auto-detects a local coding agent runtime, currently Codex CLI when available.

For custom runtimes, use the lower-level watch command:

```bash
journey watch product.journey \
  --agent-command "codex exec \"Work on: {item}. Read {handoff_md} and {handoff_json}.\""
```

The runner:

- prints the current journey board
- picks the next incomplete deliverable
- prepares `JOURNEY.md` and `journey.agent.json`
- runs one builder command for that deliverable
- runs QA
- marks the deliverable complete only after QA passes
- triggers the next deliverable on the next loop

## Current Implementation Note

The v0.1 compiler does not yet parse this full natural-language format.

Today, use structured journey blocks for code generation and use the handwritten format as the product target. The roadmap item is to let both live together:

```journey
journey "Product"

mission:
  Natural-language project intent.

page "Dashboard":
  Human-readable page spec.

entity User {
  email string unique
}

step signup {
  input {
    email string required
  }
}
```

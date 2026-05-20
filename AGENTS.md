# Journey Agent Instructions

This repository uses `.journey` files as the source of truth for agent work.

When an AI coding agent or coding terminal enters this repo, it should treat any `.journey` file as the project spine. Do not start from scattered code context alone.

If a journey cites a design file, such as `design: ./design.md`, read that design file before implementing product-facing behavior.

## Default Loop

1. Find journey files:

   ```bash
   find . -name "*.journey" -not -path "./generated/*"
   ```

2. Prepare the agent handoff and run acceptance:

   ```bash
   journey agent examples/auth_workspaces.journey
   ```

   If the package is not installed as a command, use:

   ```bash
   python -m journey agent examples/auth_workspaces.journey
   ```

3. Read the generated handoff files:

   - `generated/<journey>/JOURNEY.md`
   - `generated/<journey>/journey.agent.json`

4. Implement, repair, or update the code until the journey acceptance tests pass.

5. Re-run the same command:

   ```bash
   journey agent <file.journey>
   ```

6. If implementation and journey disagree, preserve the journey as the source of truth unless the user explicitly asks to change the product intent.

## Current Contract

Today, `journey agent` does not spawn background agents or open Codex terminals by itself. It prepares the workspace for an agent by:

- parsing the `.journey`
- validating it strictly
- generating the FastAPI implementation
- writing `JOURNEY.md`
- writing `journey.agent.json`
- running generated pytest acceptance tests

The intended behavior for agents is to keep looping on those artifacts until the generated acceptance tests pass and no obvious drift remains.

For the handwritten natural-language journey direction, read `docs/handwritten-journey-format.md`.

## Repair Rules

- Prefer changing implementation to match the journey.
- Change the journey only when the product intent itself is wrong or incomplete.
- If the journey references `design.md`, preserve that design intent unless the user says otherwise.
- When tests fail, treat the failure as the next work item.
- Keep generated artifacts consistent with the source `.journey`.
- Do not remove acceptance coverage to make a journey pass.

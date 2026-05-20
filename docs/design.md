# Journey Design Notes

This file is an example design reference for `.journey` files.

The intended convention is simple:

```journey
design: ./design.md
```

When a journey cites a design file, agents should read it before implementing UI, docs, generated artifacts, or product-facing behavior.

## Product Feel

Journey should feel:

- precise
- calm
- agent-native
- infrastructure-grade
- readable by non-specialists

It should not feel like a low-level framework config file.

## Interface Principles

- Start with human intent.
- Show the path from story to working system.
- Keep acceptance criteria visible.
- Make drift and repair explicit.
- Prefer short sections, tables, and checklists over dense prose.

## Agent Experience

An agent entering a Journey repo should immediately know:

- which `.journey` files exist
- which one is the current source of truth
- what design file applies
- what command validates the journey
- what acceptance still fails
- what the next repair step is

## Page Spec Pattern

Each page in a handwritten journey should answer:

- What is this page for?
- Who uses it?
- What does the user see?
- What states can it be in?
- What rules must hold?
- What tests prove it works?
- What cleanup checks prevent drift?

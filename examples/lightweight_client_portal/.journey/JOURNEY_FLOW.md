# Lightweight Client Portal Journey Flow

A single read-through map of the project journey. Use this before clicking through the app or opening implementation files.

## Journey Graph

- `.journey/repo.journey` is the repository-level source of truth.
- Child journeys live under `.journey/pages/` and `.journey/apis/`.
- Run `journey sync .` after adding or moving routes.

## Route Map

| Type | Route | Journey | Source |
| --- | --- | --- | --- |
| api | `/api/leads` | `./apis/leads.journey` | `app/api/leads/route.ts` |
| page | `/dashboard` | `./pages/dashboard.journey` | `app/dashboard/page.tsx` |
| page | `/settings` | `./pages/settings.journey` | `app/settings/page.tsx` |

## Feature Flow

### Pages

1. **Dashboard** (`/dashboard`)
   - Journey: `./pages/dashboard.journey`
   - Captures visible states, primary actions, rules, and page-level acceptance.
2. **Settings** (`/settings`)
   - Journey: `./pages/settings.journey`
   - Captures visible states, primary actions, rules, and page-level acceptance.

### APIs

1. **Leads API** (`/api/leads`)
   - Journey: `./apis/leads.journey`
   - Captures caller intent, request shape, response shape, side effects, and API-level acceptance.
   - Methods: `POST`
   - Responses: returns JSON response

## End-to-End Walkthrough

1. Start with `.journey/repo.journey` to understand the product mission and linked child journeys.
2. Read page journeys in route order to understand what users see and do.
3. Read API journeys beside the pages that call them to understand data flow and side effects.
4. Update acceptance notes before changing code so agents can implement against product intent.

## Acceptance Outline

- every discovered page or API route has a linked child journey
- every child journey names its source file
- visible states, business rules, failures, and tests/QA notes are documented where relevant
- unresolved product questions are written in the journey instead of hidden in implementation

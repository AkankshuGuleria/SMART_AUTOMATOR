# AUTOMATA — Frontend Skill (SKILLS.md §3)

**Apply when building or modifying any UI screen.**

## Core rule
Frontend is a **thin presentation layer only**. No memory logic, no DB calls, no Bedrock calls.
All data comes from `http://127.0.0.1:8000` via `frontend/src/lib/api.ts`.

## Checklist
- [ ] Every async action has explicit **loading** and **error** states — a frozen screen reads as broken during a demo
- [ ] Restore Workspace UI shows **per-step progress** (git checkout → terminal → servers → editor/browser) — not a single spinner
- [ ] All interactive elements have unique `id` attributes for browser testing
- [ ] Accessible: readable contrast, keyboard-navigable primary actions

## Screens (in `frontend/src/screens/`)
| Screen | Route | Phase |
|---|---|---|
| `MorningBrief.tsx` | Tab: brief | Phase 2 |
| `RestoreWorkspace.tsx` | Tab: restore | Phase 3 |
| `QueryChat.tsx` | Tab: query | Phase 2 |

## Design system
Global CSS tokens in `frontend/src/styles/globals.css`. Use CSS custom properties:
- `--color-accent: #6366f1` (indigo)
- `--color-bg-base: #0d0f14` (dark)
- `--color-text-primary: #e8eaf0`
- Component classes: `automata-btn-primary`, `automata-loading`, `automata-error`, `automata-spinner`

## Tailwind
Configured via `@tailwindcss/vite` plugin — no `tailwind.config.js` needed.
Use Tailwind utilities OR the custom CSS classes above — don't mix ad-hoc inline styles.

## State management
TBD — not yet decided. Use React `useState`/`useEffect` for Phase 0-2. Decide before Phase 3.

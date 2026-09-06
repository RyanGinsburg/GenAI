# frontend

A minimal Vite + React app (Step 6 of [../BUILD_PROMPTS.md](../BUILD_PROMPTS.md)).

## Run it

```bash
npm install         # first time only
npm run dev
```

Opens on `http://localhost:3000` (fixed in `vite.config.js` to match
`backend/main.py`'s CORS allowlist). The backend must also be running:

```bash
# from the repo root
uvicorn backend.main:app --reload
```

## What's here

- `src/App.jsx` — top-level state: chat submission, per-club research
  results, calendar-event checkbox selections.
- `src/components/ChatForm.jsx` — the message box + optional resume upload.
- `src/components/ClubCard.jsx` — one matched club, its "Get info" button,
  and (once researched) the found fields as checkboxes plus a coffee-chat
  link.
- `src/components/CalendarBar.jsx` — the sticky confirmation bar and "Add
  to Google Calendar" button. **Stub for now** — Step 7 wires it to real
  Google OAuth; clicking it today just confirms what would be added.
- `src/api.js` — the two fetch calls to the backend.

**Getting a club's info is always an explicit action** (clicking "Get
info" on that specific card) — the chat/matching flow never triggers
research automatically, matching how `backend/main.py` keeps `/chat` and
`/research` decoupled.

# Cornell Club Matching Agent

## 👋 Directions for us (read this first)

We're taking turns, not working at the same time. Whoever's turn it is
follows this loop:

**Before you start working:**
```
git pull
```
Always do this first so you have the other person's latest changes.

**While you work:**
Open Claude Code in this folder. It reads `CLAUDE.md` automatically for
project context. Follow the prompts in `BUILD_PROMPTS.md`, in order —
don't skip ahead to a step that depends on one that isn't done yet.

**When you're done for the session:**
```
git add .
git commit -m "short description of what you did"
git push
```
Before committing, update the **"Current status"** line at the bottom of
`CLAUDE.md` so the other person knows exactly what's done. Then text/message
the other person: "pushed, your turn — [next step]."

**Whose turn is it right now:**
_(update this line each handoff)_
> Currently: **[name]** is working on **[step]**.

**Rules:**
- Only one of us commits to `main` at a time — that's the whole point of
  taking turns, it avoids merge conflicts.
- Never commit `.env` (it has API keys). It should already be in
  `.gitignore` — double check if unsure.
- If `git pull` or `git push` gives an error neither of us understands,
  stop and ask Claude before running more commands.

---

## What this project is

A chatbot that helps Cornell students find student organizations. The
student chats and/or uploads their resume. The system matches them to
relevant clubs from Cornell's real CampusGroups directory, researches each
matched club's website for deadlines/meetings/coffee chats, shows the
student what it found, and — only after the student approves — adds the
relevant events to their Google Calendar.

Built for the Generative AI @ Cornell developer application.

## Tech stack

- **Backend:** Python, FastAPI
- **LLM:** Anthropic Claude API
- **Embeddings:** lightweight model, cached locally (no hosted vector DB)
- **Frontend:** React
- **Calendar:** Google Calendar API (OAuth2)
- **Data:** scraped JSON files in `/data`

## Project structure

```
club-agent/
  scraper/              # scrapes CampusGroups directory -> data/clubs.json
  data/                 # clubs.json, embeddings.npy, cache files
  backend/
    routes/             # FastAPI route handlers
    services/
      matching.py        # embedding search + re-ranking
      resume_parser.py    # PDF -> structured profile
      research_agent.py   # fetch club site -> extract structured info
      calendar_sync.py    # Google Calendar OAuth + event creation
  frontend/              # React app
  .env.example
  CLAUDE.md              # project context for Claude Code
  BUILD_PROMPTS.md       # ordered prompts to build each piece
  README.md              # this file
```

## Setup

1. Clone the repo, `cd` into it.
2. Copy `.env.example` to `.env` and fill in your own API keys (never commit
   this file).
3. Backend: create a virtual environment and `pip install -r requirements.txt`.
4. Frontend: `cd frontend && npm install`.
5. See `BUILD_PROMPTS.md` for the build sequence if setting up from scratch.

## Key files for working with Claude Code

- **`CLAUDE.md`** — project context, tech stack decisions, and hard
  constraints. Claude Code reads this automatically at the start of every
  session. Keep the "Current status" section updated.
- **`BUILD_PROMPTS.md`** — the exact prompts to paste into Claude Code, in
  build order, from initial skeleton through calendar integration.

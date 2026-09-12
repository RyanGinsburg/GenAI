# Cornell Club Matching Agent

## 👋 Directions for us (read this first)

### Quick glossary (skip if you already know this)
- **This repo** = this folder. It's the shared project folder for the app.
- **`.md` files** (like this one, `CLAUDE.md`, `BUILD_PROMPTS.md`) = plain
  text files with some formatting. You don't need any special program —
  open them in any text editor, or view them on GitHub where they look
  nicely formatted automatically.
- **Claude Code** = a terminal app where you type instructions in plain
  English and it writes/edits code for you in this folder. You "open" it by
  typing `claude` in your terminal while inside this repo's folder.
- **`git pull` / `git push`** = downloading and uploading the latest version
  of the project so you and your teammate stay in sync. See the loop below.

### The workflow: we take turns, one person "has the ball" at a time

**Step-by-step, every time it's your turn:**

1. Open a terminal, navigate into the project folder, then run:
   ```
   git pull
   ```
   This downloads your teammate's latest work. Always do this first.

2. Start Claude Code by typing:
   ```
   claude
   ```
   It will automatically read `CLAUDE.md` in this folder for project context —
   you don't need to explain the project to it yourself.

3. Open `BUILD_PROMPTS.md` in this repo (in any text editor, or on GitHub).
   Find the step you're supposed to do (see "whose turn" below), and
   **copy-paste that exact prompt** into Claude Code. Hit enter and let it work.

4. Look at what it did. If something looks broken or you're not sure, come
   back to this Claude conversation (the one that gave you these files) and
   describe what happened — don't just keep guessing prompts at Claude Code.

5. When the step is working, tell it done for now, then in your terminal run:
   ```
   git add .
   git commit -m "short description of what you did"
   git push
   ```
   Replace the text in quotes with a real description, e.g.
   `"finished scraper, clubs.json has real data"`.

6. Open `CLAUDE.md`, find the **"Current status"** line near the bottom, and
   update it to reflect what's now done. Save, then run the `git add` /
   `commit` / `push` commands above again so that update gets shared too.

7. Text/message your teammate: **"pushed, your turn — do Step [X]."**

8. Your teammate now does steps 1-7 themselves, starting with `git pull`.

### Whose turn is it right now
_(update this line every handoff so it's never ambiguous)_
> Currently: a big post-Step-6 feature pass landed 2026-09-06 on top of the
> working app: real user accounts (SQLite, JWT login), the old single
> search box replaced by a multi-turn conversational profile-builder that
> can take a resume attachment mid-conversation, a real matching bug fixed
> (a multi-topic resume query was silently drowning out minority interests
> like robotics in favor of whatever topic dominated the phrase list),
> results now grouped into Professional/Social & Fun/Community Service, a
> "Browse Clubs" directory with search/filter, a "My Clubs" saved-clubs
> section, loading spinners/progress bars throughout, and a full visual
> redesign to a flatter "clean modern app" look (the earlier pinboard/tilt
> concept is retired). All driven end-to-end with a live backend + browser
> automation, not just eyeballed. See CLAUDE.md's "Current status" for the
> full breakdown.
> **Next step:** Step 7 (the last one) — Google Calendar OAuth
> (backend/services/calendar_sync.py + POST /calendar/add-events). Needs
> manual Google Cloud Console setup that can't be automated — see
> BUILD_PROMPTS.md's Step 7 prompt. To run the app locally: backend
> (`uvicorn backend.main:app --reload`, needs `JWT_SECRET_KEY` and
> `FIRECRAWL_API_KEY` set in `.env` — see `.env.example`) and frontend
> (`cd frontend && npm install && npm run dev`) both running at the same
> time.

### Rules
- **Only one of us works in the repo at a time.** If it's not your turn,
  don't run Claude Code prompts yet — wait for the "pushed, your turn" message.
- **Never commit `.env`** (it holds API keys). It should already be listed in
  a file called `.gitignore` so git skips it automatically — don't remove it
  from there.
- **Never paste your real API key into a message to Claude Code or into
  chat** — it goes in the `.env` file only.
- If `git pull` or `git push` gives an error you don't understand, **stop**
  and bring it back to this conversation before running more commands.

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

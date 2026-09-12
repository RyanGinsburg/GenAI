# Cornell Club Matching Agent

A chatbot that helps Cornell students find student organizations. The
student chats and/or uploads their resume; the app matches them to real
clubs from Cornell's CampusGroups directory, researches each matched
club's website for application deadlines, info sessions, and coffee chat
sign-ups, shows the student what it found, and — only after the student
approves — adds the relevant events to their Google Calendar.

Built for the Generative AI @ Cornell developer application.

## Tech stack

- **Backend:** Python, FastAPI
- **LLM:** Anthropic Claude API (resume parsing, club-site research
  extraction, conversational profile-building)
- **Embeddings:** `sentence-transformers` (local, no hosted vector DB),
  cached to `data/embeddings.npy`
- **Web crawling:** Firecrawl API (club-site research)
- **Frontend:** React (Vite)
- **Accounts:** SQLite (`data/app.db`) + stateless JWT login
- **Calendar:** Google Calendar API (OAuth2)

## Project structure

```
GenAI/
  scraper/              # scrapes CampusGroups -> data/clubs.json
  data/                  # clubs.json, clubs_filtered.json, embeddings,
                          # app.db, cache files (mostly gitignored/derived)
  backend/
    main.py                # FastAPI app, route wiring
    db.py                   # SQLite schema + raw CRUD
    routes/                 # one module per API concern (auth, chat,
                             # matching, research, calendar, browse, ...)
    services/                # matching, resume parsing, club research,
                              # chat profile-building, accounts, calendar
                              # sync, etc.
  frontend/               # React app (Chat / Browse Clubs / My Clubs)
  .env.example
  requirements.txt
```

## Setup

### 1. Configure environment variables

```
cp .env.example .env
```

Then fill in `.env` with real values. At minimum, to run the app locally:

| Variable | What it's for |
|---|---|
| `ANTHROPIC_API_KEY` | Resume parsing, club-site research extraction, chat |
| `FIRECRAWL_API_KEY` | Crawling club websites in `research_agent.py` |
| `JWT_SECRET_KEY` | Signs account login tokens — any random value works locally, e.g. `python -c "import secrets; print(secrets.token_hex(32))"` |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Google Sign-In and Calendar OAuth (see below) |
| `SMTP_*` | Sending password-reset emails |
| `FRONTEND_BASE_URL` / `BACKEND_BASE_URL` | Default to `localhost:3000` / `localhost:8000` — fine for local dev |

See the comments in [.env.example](.env.example) for exact details on each
variable, including the Google OAuth client requirements.

### 2. Backend

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn backend.main:app --reload
```

Runs at `http://localhost:8000`.

`data/clubs.json` and `data/clubs_filtered.json` are already committed, so
there's no need to re-scrape to get started. To refresh club data from
Cornell's live CampusGroups directory, run `scraper/scrape_campusgroups.py`
(optional).

### 3. Frontend

```
cd frontend
npm install
npm run dev
```

Runs at `http://localhost:3000` (fixed in `vite.config.js` to match the
backend's CORS allowlist).

Both the backend and frontend need to be running at the same time.

### 4. Google Calendar OAuth — one-time manual setup

Adding events to Google Calendar requires a one-time setup in Google Cloud
Console for the OAuth client referenced by `GOOGLE_CLIENT_ID`/
`GOOGLE_CLIENT_SECRET` (the same "Web application" client used for Google
Sign-In):

1. **APIs & Services → Library** — enable the **Google Calendar API**.
2. **APIs & Services → Credentials** — open the existing Web application
   OAuth client → **Authorized redirect URIs** → add
   `http://localhost:8000/calendar/oauth/callback` exactly (must match
   `BACKEND_BASE_URL` + `/calendar/oauth/callback`, no trailing slash).
3. **APIs & Services → OAuth consent screen → Scopes** — add
   `.../auth/calendar.events`.
4. If the consent screen is still in **Testing** status, add the Google
   accounts you'll test with under "Test users," or consent will fail with
   "access blocked" (an "unverified app" warning during consent is
   expected in Testing mode — click through it).

Everything else (accounts, chat, matching, browsing clubs, saving clubs,
researching a club's deadlines/info sessions) works without this step;
it's only needed for the final "Add to Google Calendar" action.

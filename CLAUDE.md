# Project: Cornell Club Matching Agent

## What this is
A chatbot that helps Cornell students find student organizations. The student
chats and/or uploads their resume. The system matches them to relevant clubs
from Cornell's real CampusGroups directory, researches each matched club's
website for deadlines/meetings/coffee chats, shows the student what it found,
and — only after the student approves — adds the relevant events to their
Google Calendar.

## Tech stack (decided, don't change without discussion)
- Backend: Python, FastAPI
- LLM: Anthropic Claude API (claude-sonnet for extraction/reasoning tasks)
- Embeddings: any lightweight embedding model or API is fine — keep it simple,
  store vectors in a local file (numpy array or Chroma), no hosted vector DB
- Frontend: React
- Calendar: Google Calendar API (OAuth2)
- Data: scraped JSON files in /data, not a full database (for MVP)

## Project structure
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
  README.md

## Hard constraints
- NEVER fabricate deadlines, meeting times, or links. If the research agent
  can't find something on a club's site, it must explicitly say so and return
  null/"not found" rather than guessing.
- Nothing gets added to the user's Google Calendar without an explicit
  confirmation step in the UI first.
- Keep API keys in .env, referenced via environment variables. Never hardcode
  or print keys.
- Prefer small, testable functions over large end-to-end scripts. After
  writing any pipeline stage, write or run a quick test against real sample
  data before moving to the next stage.

## Current status
Step 0 (skeleton) and Step 1 (scraper) done. scraper/scrape_campusgroups.py
scrapes Cornell's CampusGroups directory by iterating its ~11 group_type
buckets with view=all (the unfiltered listing silently truncates past ~1100
rows, so per-bucket fetching is what's reliable — see the module docstring).
data/clubs.json has all 1521 real clubs: name, category, description,
website_url. 100% have website_url, ~90% (1366) have a description. The
one-off "Cornell CG TEST" bucket is excluded on purpose.
Service files under backend/services/ are still docstring-only stubs.
frontend/ is a placeholder (Node not installed yet — `brew install node`
before Step 6).
Next: Step 2, embeddings + matching (backend/services/matching.py).

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

**Immediate next step (do this first if asked "what needs to be done"):**
research_agent.py's fetch mechanism was rewritten 2026-09-05 to use a
headless browser (Playwright) instead of plain `requests.get()`, and
qa/research_agent_review.md was just regenerated against it — see the
"2026-09-05: headless-browser fetch" section below for why and what
changed. Regenerating reset every "Verified?" checkbox in that file, so
Step 4 is NOT marked done yet: it needs a fresh manual pass — open each of
the 20 sites, confirm the newly-extracted fields — before Step 5 starts.
Two known, deliberately-not-fixed quirks are already documented below
(AppDev's multi-link coffee_chat_link, Cornell Business Analytics'
info_session count varying run to run) so the reviewer doesn't need to
re-flag those as new bugs.

**2026-09-05: headless-browser fetch, replacing the 2026-09-03 QA-round fixes' status.**
The 2026-09-03 manual review (below) found two real bugs and fixed both in
code, but that fix was only confirmed by re-processing saved HTML offline,
not against the live API. Re-running live surfaced a third, more
fundamental bug: Applied Public Policy Strategies at Cornell
(appscornell.org) has a real application deadline and two info-session
dates, but they only exist in the page because client-side JS
(`script.js`) injects them into the DOM via `appendChild`/`innerHTML` on
`DOMContentLoaded` — they're not in the HTML `requests.get()` receives at
all, so the old fetch was structurally blind to them, not merely
misreading them. Root-caused by reading `script.js` as plain text (without
executing it) and finding the real event data hardcoded in a
`RECRUITMENT_EVENTS` array. Fixed by rewriting `_fetch()` to render pages
with headless Chromium (Playwright) instead of a plain HTTP GET, and
bumping `MAX_PAGE_CHARS` 12000 → 25000 (JS-rendered pages run longer — this
one is ~13.8k chars fully rendered, and the old 12k cap was truncating the
deadline off the end of the page). `requirements.txt` now lists
`playwright`; after `pip install -r requirements.txt`, also run
`python -m playwright install chromium` once.

Re-running all 20 qa/research_agent_review.py sites against the live API
with this fix confirmed:
- Both 2026-09-03 bugs are genuinely fixed now, not just fixed-on-paper:
  Cornell Wall Street Club fully recovers (deadline + info session +
  coffee-chat link), and the coffee-chat link now shows up for Cornell
  Business Analytics Club, Cornell XR, 180 Degrees Consulting, Cornell
  FinTech Club, and Investment Banking Club.
- Two more clubs that were previously "just a title, no content" turned
  out to be JS-rendered too, and are now genuine hits for free: Cornell
  Alpha Fund Club (deadline + 2 info sessions + coffee-chat link) and
  Cornell Data Strategy Club (deadline + info session). Both spot-checked
  against the rendered page text to rule out hallucination.
- Two things did NOT get fixed, neither caused by this change, and per
  discussion (2026-09-05) both are being left as-is rather than chased
  further right now:
  1. AppDev at Cornell's coffee_chat_link is still null even though its
     page text contains all 5 real per-subteam Calendly links (confirmed
     present in the extracted text) — coffee_chat_link is a single-string
     field, and AppDev has 5 different links with no single unambiguous
     "the" coffee chat link, so the model appears to correctly decline to
     pick one arbitrarily rather than guess. A schema change (e.g. a list)
     would be needed to capture this case; not done.
  2. Cornell Business Analytics Club's info_session went from listing all
     3 real sessions (2026-09-03 run) to listing only 1 (2026-09-05 run)
     even though the page text still has all 3 — looks like ordinary LLM
     sampling variance (calls aren't pinned to temperature 0), not a
     regression from the fetch change.

Also done 2026-09-05, separately: created data/clubs_filtered.json (877 of
the 1521 clubs) via the new scraper/filter_clubs.py — see its module
docstring for the exact category rules and the two judgment calls made
(professional fraternities kept, competitive club sports kept). Bonus:
100% of the 877 have a description, vs. ~90% for the full 1521. Not yet
wired into matching.py/embeddings.npy — those still run against the full
data/clubs.json.

Step 0 (skeleton), Step 1 (scraper), and Step 2 (embeddings + matching) done.
scraper/scrape_campusgroups.py scrapes Cornell's CampusGroups directory by
iterating its ~11 group_type buckets with view=all (the unfiltered listing
silently truncates past ~1100 rows, so per-bucket fetching is what's
reliable — see the module docstring). data/clubs.json has all 1521 real
clubs: name, category, description, website_url. 100% have website_url,
~90% (1366) have a description. The one-off "Cornell CG TEST" bucket is
excluded on purpose.

backend/services/matching.py embeds each club (name + description +
category) with the local sentence-transformers model all-MiniLM-L6-v2 (no
API key needed) and caches vectors to data/embeddings.npy, with a
data/embeddings_meta.json sidecar (hash of source texts + model name) that
auto-invalidates the cache if clubs.json or the model changes. Both files
are gitignored/derived, regenerated on first run (~5s locally). match_clubs
(query, top_k=10) returns clubs ranked by cosine similarity. Sanity-checked
against "sustainability and climate policy clubs, low time commitment" —
top result was GreenClub, all top 5 genuinely on-topic.
Added sentence-transformers to requirements.txt.

backend/services/resume_parser.py extracts text from a resume PDF with
pypdf, then calls claude-sonnet-5 (per CLAUDE.md's "claude-sonnet for
extraction/reasoning tasks") to return strict JSON: major, graduation_year,
skills, interests, clubs_mentioned — all literal extractions, null/empty if
not stated, no fabrication — plus suggested_club_interests, a deliberately
separate field where the model reasons over the whole resume (major, skills,
experience) to suggest club/professional interest areas (e.g. "artificial
intelligence", "quantitative finance"), grounded in the resume's actual
content. Any failure (missing file, no extractable text/scanned PDF, bad API
response, truncated/invalid JSON) returns {"error": "..."} instead of
raising. Uploaded resumes go in data/resumes/ (gitignored — personal data).
Sanity-checked against a real resume; output looked accurate.

Note: this Anthropic account issues identity-linked API keys that require
an anthropic-workspace-id header per request — a plain workspace-scoped key
from the console worked fine, no code changes needed. If keys on this
account start requiring that header again, see the ANTHROPIC_WORKSPACE_ID /
default_headers approach discussed when this first came up.

backend/services/research_agent.py — Step 4, the research agent — is built,
tested, and committed, but not yet marked done (see "Immediate next step"
above — pending a manual review). research_club(website_url) fetches the
club's page with a headless browser (Playwright/Chromium, so client-side-
JS-injected content is visible — see the 2026-09-05 note above), follows
one secondary link if its nav text/href matches events/join/recruit/apply/
contact (max 2 pages), then calls claude-sonnet-5 with an explicit
no-guessing prompt to extract application_deadline, next_meeting,
info_session, coffee_chat_link — null for anything not concretely stated
(a recurring "we meet weekly" without an actual date doesn't count).
not_found: true when every field is null. Any failure (unreachable site,
navigation timeout, bad API response, truncated/invalid JSON) returns
not_found with an "error" key instead of raising.

Tested against the same 20 real club sites both before and after the
2026-09-05 fetch rewrite (qa/research_agent_review.py generates
qa/research_agent_review.md — a checklist a friend goes through to verify
field-by-field). Post-rewrite: 9/20 are genuine hits with real dates/
times/locations/links pulled verbatim (Cornell Business Analytics Club,
Cornell FinTech Club, AppDev at Cornell — partial, see the 2026-09-05
note's known-limitation #1 — Investment Banking Club, Cornell Wall Street
Club, Cornell XR, 180 Degrees Consulting, Cornell Alpha Fund Club, Cornell
Data Strategy Club); the other 11 correctly came back not_found (either
nothing concrete stated, or — Alpha Kappa Psi — a dead/unresolvable
domain). Most club sites genuinely don't post this info, so a mostly-null
result set across a broad sample is expected, not a sign of a bad
extractor.

Idea raised 2026-09-03, acted on 2026-09-05: data/clubs.json has 1521
clubs but many are inactive/low-signal for this use case (grad orgs,
academic departments, housing, social Greek life). scraper/filter_clubs.py
now produces data/clubs_filtered.json, 877 undergrad-facing clubs — see
its module docstring for the exact rules. Not yet wired into
matching.py/embeddings.npy.

Other service files under backend/services/ are still docstring-only stubs.
frontend/ is a placeholder (Node not installed yet — `brew install node`
before Step 6).

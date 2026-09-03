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
The manual review of research_agent.py (qa/research_agent_review.md) found
two real bugs on 2026-09-03; both are now fixed in code, but NOT yet
re-verified against the live Claude API, so Step 4 is still not marked
done. Before starting Step 5, run `qa/research_agent_review.py` again
(needs a working `.env` with ANTHROPIC_API_KEY) and confirm Cornell Wall
Street Club now returns real data and the previously-missed coffee chat
links now show up.

1. **Coffee chat links were missed systematically** (6 of 7 real ones
   missed: Cornell Business Analytics Club, Cornell XR, 180 Degrees
   Consulting, Cornell FinTech Club, AppDev at Cornell, Investment Banking
   Club). Root cause: `_page_text()` in research_agent.py used
   `soup.get_text()`, which strips all `<a href>` URLs and keeps only the
   visible link text (e.g. "Sign Up Now"), so Claude was never actually
   given the URL even when a coffee chat link was right there on the page.
   Fixed: `_page_text()` now appends each link's absolute URL in
   parentheses after its anchor text, and the prompt tells the model to use
   it. Confirmed (by re-processing the saved HTML directly, without an API
   call) that the target URLs now appear in the extracted text for Cornell
   Wall Street Club, AppDev, and Cornell Business Analytics.
2. **Cornell Wall Street Club (cornell-wsc.com/recruitment.html) came back
   entirely not_found when it should have been a real hit.** Turned out NOT
   to be JS rendering as originally suspected — the raw static HTML already
   has the real timeline/deadline/coffee-chat link well within the char
   limit. The actual cause: a stale "details will be announced soon" hero
   banner sits above the real, filled-in timeline on the same page, and the
   model appears to have let that vague banner suppress the concrete dates
   below it. Fixed by adding an explicit rule to SYSTEM_PROMPT that a vague
   placeholder elsewhere on the page must not override concrete data that's
   also present.

Also fixed: for Blockchain at Cornell, `_find_secondary_url` had followed
an off-domain LinkedIn profile URL instead of a real club page; it's now
restricted to same-domain links only.

Full detail (including the corrected root-cause writeup for Cornell Wall
Street Club) is in qa/research_agent_review.md. Once a live-API re-run
confirms the fixes actually change the model's output for these clubs,
Step 4 gets marked done here and Step 5 (backend/main.py — a FastAPI app
wiring matching.py, resume_parser.py, and research_agent.py together)
starts.

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
above — pending a manual review). research_club(website_url) fetches the club's page, follows one
secondary link if its nav text/href matches events/join/recruit/apply/
contact (max 2 pages), then calls claude-sonnet-5 with an explicit
no-guessing prompt to extract application_deadline, next_meeting,
info_session, coffee_chat_link — null for anything not concretely stated
(a recurring "we meet weekly" without an actual date doesn't count).
not_found: true when every field is null. Any failure (unreachable site,
bad API response, truncated/invalid JSON) returns not_found with an
"error" key instead of raising.

Tested against 20 real club sites (qa/research_agent_review.py generates
qa/research_agent_review.md — a checklist a friend is going through to
verify field-by-field). 4/20 were genuine hits with real dates/times/
locations pulled verbatim (Cornell Business Analytics Club, Cornell
FinTech Club, AppDev at Cornell, Investment Banking Club — all
application-cycle business/tech clubs); the other 16 correctly came back
not_found (either nothing concrete stated, or in one case — Alpha Kappa
Psi — a dead/unresolvable domain). Most club sites genuinely don't post
this info, so a mostly-null result set across a broad sample is expected,
not a sign of a bad extractor.

Idea raised, not yet acted on: data/clubs.json has 1521 clubs but many
are inactive/low-signal for this use case; a curated/filtered subset
might improve match relevance and cut down wasted research_agent calls
on dead or contentless sites. Decide later — don't filter clubs.json
without an explicit go-ahead.

Other service files under backend/services/ are still docstring-only stubs.
frontend/ is a placeholder (Node not installed yet — `brew install node`
before Step 6).

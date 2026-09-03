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

**Step 4 (backend/services/research_agent.py) is done.** The manual review
(qa/research_agent_review.md) found three real bugs on 2026-09-03, all
fixed in code and confirmed against the live Claude API the same day
(after swapping in a workspace-scoped API key — this account's
identity-linked keys 400 with "anthropic-workspace-id is required"; see the
note further down). The sample went from 7/20 real hits to 11/20: Cornell
Wall Street Club, Cornell Real Estate Club, Cornell Consulting Club,
Cornell Algo Trading Club, and Quant Fund at Cornell all flipped from
not_found to real data, and all 7 previously-missing coffee chat links
across the sample now come back populated with the right URLs.

**Immediate next step: Step 5 — build backend/main.py**, a FastAPI app
wiring together matching.py, resume_parser.py, and research_agent.py (see
BUILD_PROMPTS.md's Step 5 prompt for the exact routes/shape:
POST /chat and POST /research, no auth/database, simple per-club error
handling).

What the two bugs were and how they were fixed:

1. **Coffee chat links were missed systematically** (all 7 real ones
   missed: Cornell Business Analytics Club, Cornell XR, 180 Degrees
   Consulting, Cornell FinTech Club, AppDev at Cornell, Cornell Wall Street
   Club, Investment Banking Club). Root cause: `_page_text()` in
   research_agent.py used `soup.get_text()`, which strips all `<a href>`
   URLs and keeps only the visible link text (e.g. "Sign Up Now"), so
   Claude was never actually given the URL even when a coffee chat link was
   right there on the page. Fixed: `_page_text()` now appends each link's
   absolute URL in parentheses after its anchor text, and the prompt tells
   the model to use it. Confirmed against the live API on 2026-09-03 - all
   7 links now come back populated with the correct URL.
2. **Cornell Wall Street Club (cornell-wsc.com/recruitment.html) came back
   entirely not_found when it should have been a real hit.** Turned out NOT
   to be JS rendering as originally suspected — the raw static HTML already
   has the real timeline/deadline/coffee-chat link well within the char
   limit. The actual cause: a stale "details will be announced soon" hero
   banner sits above the real, filled-in timeline on the same page, and the
   model was letting that vague banner suppress the concrete dates below
   it. Fixed by adding an explicit rule to SYSTEM_PROMPT that a vague
   placeholder elsewhere on the page must not override concrete data that's
   also present. Confirmed against the live API on 2026-09-03 - the club
   now correctly comes back with its real deadline, info session, and
   coffee chat link.

3. **Applications reachable via a real on-site "Apply" page were being
   missed because `_find_secondary_url` followed the wrong link.** It
   returned the *first* nav link matching any keyword in document order,
   not the *best* one — so a page with both a generic "Contact"/"Events"
   link and the club's actual "Apply" page would often follow whichever
   appeared first in the HTML, missing the real recruiting page entirely.
   Confirmed on Cornell Real Estate Club, Cornell Consulting Club, Cornell
   Algo Trading Club, and Quant Fund at Cornell — all four have a real
   deadline/timeline/coffee-chat-link on an `/apply`-style page that was
   never fetched. Fixed by reordering `SECONDARY_LINK_KEYWORDS` by priority
   (apply/recruit/join before events/contact) and having
   `_find_secondary_url` scan every matching link and pick the
   highest-priority one instead of stopping at the first match. Confirmed
   against the live API on 2026-09-03 - all 4 clubs now return real data.

Also fixed: for Blockchain at Cornell, `_find_secondary_url` had followed
an off-domain LinkedIn profile URL instead of a real club page; it's now
restricted to same-domain links only (confirmed live: it no longer follows
that link). Blockchain at Cornell still comes back not_found even after
fix #3, though — its "Apply Now" button turned out not to be a real
`<a href>` at all (a client-side Framer component with a JS click handler,
no static destination), which would need actual browser/JS rendering to
resolve. Out of scope for the current requests/BeautifulSoup approach;
noted as a known limitation rather than fixed.

Full detail is in qa/research_agent_review.md.

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
an anthropic-workspace-id header per request, which a plain
Anthropic(...) client call rejects with a 400 ("anthropic-workspace-id is
required..."). This has come up twice now (Step 3, and again when
re-verifying Step 4 on 2026-09-03) and both times the fix was the same:
generate a plain workspace-scoped key from console.anthropic.com/settings/keys
(with a specific workspace selected, not "All workspaces"/personal
identity) and put that in .env instead — no code changes needed. If this
keeps recurring, it may be worth just adding ANTHROPIC_WORKSPACE_ID /
default_headers support in code instead of re-generating keys each time.

backend/services/research_agent.py — Step 4, the research agent — is done.
research_club(website_url) fetches the club's page, follows one
same-domain secondary link — prioritized apply/recruit/join over
events/contact, picking the best keyword match anywhere on the page rather
than the first one encountered (max 2 pages) — then calls claude-sonnet-5
with an explicit no-guessing prompt to extract application_deadline,
next_meeting, info_session, coffee_chat_link — null for anything not
concretely stated (a recurring "we meet weekly" without an actual date
doesn't count). Page text preserves link URLs next to their anchor text
(see the bug writeup above) so link-based fields like coffee_chat_link are
actually visible to the model. not_found: true when every field is null.
Any failure (unreachable site, bad API response, truncated/invalid JSON)
returns not_found with an "error" key instead of raising.

Tested against 20 real club sites (qa/research_agent_review.py generates
qa/research_agent_review.md, and a friend went through it verifying
field-by-field, which is what surfaced the three bugs fixed above). After
the fixes, 11/20 are genuine hits with real dates/times/locations and
coffee chat links pulled verbatim (Cornell Business Analytics Club,
Cornell Real Estate Club, Cornell XR, 180 Degrees Consulting, Cornell
Consulting Club, Cornell FinTech Club, AppDev at Cornell, Cornell Wall
Street Club, Investment Banking Club, Cornell Algo Trading Club, Quant
Fund at Cornell); the other 9 correctly come back not_found — two have a
dead/unresolvable domain (Alpha Kappa Psi, Black Ivy Pre-Law Society), one
(Blockchain at Cornell) has an apply button with no static href (see the
bug-3 writeup above), and the remaining 6 genuinely have no concrete
recruiting info anywhere on their site. This 11/20 hit rate skews heavily
toward business/finance/tech recruiting clubs that run formal application
cycles with published timelines — most other clubs (a cappella, outing
club, policy blogs, etc.) just don't operate that way, so this is the
correct output of a working extractor, not under-extraction.

Idea raised, not yet acted on: data/clubs.json has 1521 clubs but many
are inactive/low-signal for this use case; a curated/filtered subset
might improve match relevance and cut down wasted research_agent calls
on dead or contentless sites. Decide later — don't filter clubs.json
without an explicit go-ahead.

Other service files under backend/services/ are still docstring-only stubs.
frontend/ is a placeholder (Node not installed yet — `brew install node`
before Step 6).

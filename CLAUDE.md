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
Step 6 (frontend/) is done as of 2026-09-06 — see that section below. Next
up is Step 7: Google Calendar OAuth (backend/services/calendar_sync.py +
a POST /calendar/add-events route), the last step. Needs manual Google
Cloud Console setup (OAuth credentials) that can't be automated.

**Step 4 (backend/services/research_agent.py) is done as of 2026-09-05.**
Two people worked on it in parallel this week and both sets of fixes are
now merged together in code: Yair found and fixed three real bugs via a
2026-09-03 manual review (qa/research_agent_review.md), confirmed live the
same day; independently, a headless-browser rewrite on 2026-09-05 (below)
fixed a fourth, structurally different bug the 2026-09-03 round couldn't
have caught with a plain HTTP fetch. Re-running the full 20-site sample
against the *combined* code (both fixes together) got 13/20 genuine hits —
higher than either fix alone (11/20 for the priority-link fix by itself,
9/20 for the headless-browser fix by itself), confirming they catch
different, complementary classes of miss rather than overlapping.

qa/research_agent_review.md has been regenerated against the
combined code and its "Verified?" checkboxes are unchecked again (expected
— the underlying results changed) but this isn't blocking Step 5; a
review pass can happen alongside it.

**2026-09-03 bugs (Yair), confirmed against the live API that day:**

1. **Coffee chat links were missed systematically** (all 7 real ones
   missed: Cornell Business Analytics Club, Cornell XR, 180 Degrees
   Consulting, Cornell FinTech Club, AppDev at Cornell, Cornell Wall Street
   Club, Investment Banking Club). Root cause: `_page_text()` used
   `soup.get_text()`, which strips all `<a href>` URLs and keeps only the
   visible link text (e.g. "Sign Up Now"), so Claude never actually saw the
   URL even when a coffee chat link was right there on the page. Fixed:
   `_page_text()` now appends each link's absolute URL in parentheses
   after its anchor text, and the prompt tells the model to use it.
2. **Cornell Wall Street Club (cornell-wsc.com/recruitment.html) came back
   entirely not_found when it should have been a real hit.** Not JS
   rendering as originally suspected — the raw static HTML already has the
   real timeline/deadline/coffee-chat link well within the char limit. A
   stale "details will be announced soon" hero banner sits above the real,
   filled-in timeline on the same page, and the model was letting that
   vague banner suppress the concrete dates below it. Fixed by adding an
   explicit SYSTEM_PROMPT rule that a vague placeholder elsewhere on the
   page must not override concrete data that's also present.
3. **Applications reachable via a real on-site "Apply" page were being
   missed because `_find_secondary_url` followed the wrong link.** It
   returned the *first* nav link matching any keyword in document order,
   not the *best* one — so a page with both a generic "Contact"/"Events"
   link and the club's actual "Apply" page would often follow whichever
   appeared first in the HTML. Confirmed on Cornell Real Estate Club,
   Cornell Consulting Club, Cornell Algo Trading Club, and Quant Fund at
   Cornell — all four have a real deadline/timeline/coffee-chat-link on an
   `/apply`-style page that was never fetched. Fixed by reordering
   `SECONDARY_LINK_KEYWORDS` by priority (apply/recruit/join before
   events/contact) and having `_find_secondary_url` scan every matching
   link and pick the highest-priority one instead of stopping at the
   first match.

Also fixed (2026-09-03): for Blockchain at Cornell, `_find_secondary_url`
had followed an off-domain LinkedIn profile URL instead of a real club
page; it's now restricted to same-domain links only.

**2026-09-05: headless-browser fetch (independent 4th bug/fix).** The
2026-09-03 fixes above were only confirmed by re-processing saved HTML
offline at the time; re-running live that day surfaced a fourth, more
fundamental bug the static-HTML approach could never have caught: Applied
Public Policy Strategies at Cornell (appscornell.org) has a real
application deadline and two info-session dates, but they only exist in
the page because client-side JS (`script.js`) injects them into the DOM
via `appendChild`/`innerHTML` on `DOMContentLoaded` — they're not in the
HTML `requests.get()` receives at all, so the old fetch was structurally
blind to them, not merely misreading them. Root-caused by reading
`script.js` as plain text (without executing it) and finding the real
event data hardcoded in a `RECRUITMENT_EVENTS` array. Fixed by rewriting
`_fetch()` to render pages with headless Chromium (Playwright) instead of
a plain HTTP GET, and bumping `MAX_PAGE_CHARS` 12000 → 25000 (JS-rendered
pages run longer — this one is ~13.8k chars fully rendered, and the old
12k cap was truncating the deadline off the end of the page).
`requirements.txt` now lists `playwright`; after
`pip install -r requirements.txt`, also run
`python -m playwright install chromium` once.

This fix alone (before merging with Yair's) turned up two bonus hits that
were previously "just a title, no content": Cornell Alpha Fund Club
(deadline + 2 info sessions + coffee-chat link) and Cornell Data Strategy
Club (deadline + info session) — both spot-checked against the rendered
page text to rule out hallucination. It did NOT fix Blockchain at
Cornell's "Apply Now" button, confirmed still not_found even after full
JS rendering: the button is a client-side click handler with no static
`<a href>` at all (a Framer component that navigates via JS, not a real
link), so there's no URL in the rendered DOM to extract regardless of
whether JS runs. That's a genuine limitation of this fetch-and-read-the-
DOM approach, not something more rendering time would fix.

**Known, not-yet-fixed quirks in the merged code** (surfaced across
re-runs, neither caused by either fix above, not chased further for now):
1. AppDev at Cornell's page text contains all 5 real per-subteam Calendly
   coffee-chat links, but which (if any) comes back in `coffee_chat_link`
   varies by run — sometimes null, sometimes one arbitrary link — since
   the field is a single string and there's no single unambiguous "the"
   coffee chat link for the model to pick. A schema change (e.g. a list)
   would be needed to capture this properly; not done.
2. Cornell Business Analytics Club's `info_session` has varied between
   listing all 3 real sessions and listing just 1 across different runs,
   even though the page text always has all 3 — ordinary LLM sampling
   variance (calls aren't pinned to temperature 0).

Also done 2026-09-05, separately: created data/clubs_filtered.json (877 of
the 1521 clubs) via the new scraper/filter_clubs.py — see its module
docstring for the exact category rules and the two judgment calls made
(professional fraternities kept, competitive club sports kept). Bonus:
100% of the 877 have a description, vs. ~90% for the full 1521.
matching.py was switched over to it as part of Step 5 (below).

Sanity-checked research_agent.py further 2026-09-06 with a genuinely
random 50-club sample (data/clubs_filtered.json, not the curated 20):
15/50 (30%) genuine hits with real verbatim data, the other 35 correctly
not_found. Of those 35, 6 had an actual fetch problem rather than "site
has no info" — all investigated rather than left as an unexplained
error count: 2 clubs have a literal `https://www.idonothaveawebsite.com/`
placeholder in data/clubs.json itself (a scrape data-quality fact, not a
bug), 1 is a genuinely dead/unresolving domain (capsucornell.org), 1 is a
stale URL path that 404s (PulseGuard's Wix page), 1 is a real transient
flake (navy.cornell.edu failed in the batch run but fetched cleanly on a
manual retry seconds later), and 1 is a new, distinct limitation: 
scl.cornell.edu/convocation returns 403 to Playwright's headless Chromium
specifically (confirmed with our real User-Agent) - looks like WAF/bot
detection on Cornell's own site, not fixed or worked around. Also updates
the earlier campusgroups.com-hosted-sites-never-hit claim from the 20-site
sample (that was 0/7, too small a sample): this 50-club sample got 4/19
(~21%) hits on campusgroups.com URLs vs. 11/31 (~35%) on independently-
hosted ones - lower, but not zero.

Full detail on the 20-site curated sample is in qa/research_agent_review.md.

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
research_club(website_url) fetches the club's page with a headless browser
(Playwright/Chromium, so client-side-JS-injected content is visible — see
the 2026-09-05 note above), follows one same-domain secondary link —
prioritized apply/recruit/join over events/contact, picking the best
keyword match anywhere on the page rather than the first one encountered
(max 2 pages) — then calls claude-sonnet-5 with an explicit no-guessing
prompt to extract application_deadline, next_meeting, info_session,
coffee_chat_link — null for anything not concretely stated (a recurring
"we meet weekly" without an actual date doesn't count). Page text
preserves link URLs next to their anchor text so link-based fields like
coffee_chat_link are actually visible to the model. not_found: true when
every field is null. Any failure (unreachable site, navigation timeout,
bad API response, truncated/invalid JSON) returns not_found with an
"error" key instead of raising.

Tested against 20 real club sites (qa/research_agent_review.py generates
qa/research_agent_review.md, and a friend goes through it verifying
field-by-field, which is what surfaced the three 2026-09-03 bugs above).
With both the 2026-09-03 fixes and the 2026-09-05 headless-browser fix
merged together, 13/20 are genuine hits with real dates/times/locations
and coffee chat links pulled verbatim: Cornell Business Analytics Club,
Cornell Real Estate Club, Cornell Alpha Fund Club, Cornell XR, Cornell
Consulting Club, 180 Degrees Consulting, Cornell Data Strategy Club,
Cornell FinTech Club, AppDev at Cornell, Cornell Wall Street Club,
Investment Banking Club, Cornell Algo Trading Club, and Quant Fund at
Cornell. The other 7 correctly come back not_found: one has a
dead/unresolvable domain (Alpha Kappa Psi), one (Blockchain at Cornell)
has an apply button with no static href even after full JS rendering (see
the 2026-09-05 note above), and the remaining 5 (Johnson Consulting Club,
Absolute A Cappella, Black Ivy Pre-Law Society, Outing Club at Cornell,
Cornell Advancing Science and Policy Club) genuinely have no concrete
recruiting info anywhere on their site. This hit rate skews heavily toward
business/finance/tech recruiting clubs that run formal application cycles
with published timelines — most other clubs (a cappella, outing club,
policy blogs, etc.) just don't operate that way, so this is the correct
output of a working extractor, not under-extraction.

**Step 5 (backend/main.py) is done as of 2026-09-06.** A FastAPI app with
the two routes from BUILD_PROMPTS.md, both curl-tested against a live
server:
- **POST /chat** — takes `message` (form field) and an optional `resume`
  file upload. If a resume is given, parse_resume() runs and, when it
  succeeds, its `suggested_club_interests` get folded into the query text
  before matching (tested with a real resume: correctly biased matches
  toward finance/cybersecurity/fintech clubs matching that resume's actual
  skills). Returns matched clubs (name/category/description/website_url/
  score only) plus the parsed resume_profile (or its error).
  **Explicit design decision (requested 2026-09-06): /chat never calls
  research_agent.py.** Matching and researching are fully decoupled —
  getting a club's deadline/meeting/coffee-chat info is only ever a
  separate, explicit POST /research call, so nothing slow or
  Claude-API-costly happens just from browsing matches. The frontend
  (Step 6) should only hit /research when a student clicks something like
  a "get info" button on a specific club card.
- **POST /research** — takes `{"website_urls": [...]}`, runs
  research_club() on each. Each call is individually wrapped in try/except
  even though research_club() already never raises, per BUILD_PROMPTS'
  explicit ask that one club's failure can't take down the whole request.

New: backend/services/research_cache.py, a flat data/research_cache.json
keyed by website_url with a 24h TTL, sitting in front of research_club()
inside the /research route (not inside research_agent.py itself, which
stays a pure fetch-and-extract function with no caching concerns). Curl-
tested: an uncached 2-club /research call took ~11.7s; the identical
repeat call took ~0.015s. Deliberately does NOT cache a result that has an
"error" key, so a transient failure (like the navy.cornell.edu flake noted
above) gets retried on the next request instead of being stuck returning
"could not fetch" for the full TTL.

Also as part of Step 5: matching.py now loads data/clubs_filtered.json
(877 clubs) instead of the full data/clubs.json (1521) — re-verified the
sample query from Step 2 ("sustainability and climate policy clubs, low
time commitment") still returns GreenClub top-of-list with the smaller
set. requirements.txt gained `python-multipart` (FastAPI needs it for
Form(...)/UploadFile parsing in /chat). CORS is enabled for
localhost:3000/127.0.0.1:3000 only (dev default for the Step 6 frontend —
tighten before any real deployment).

**Step 6 (frontend/) is done as of 2026-09-06.** Node was installed
(`brew install node`, v26.8.1) and the app scaffolded with Vite + React.
Fixed the dev server to port 3000 in vite.config.js (Vite's default 5173
didn't match backend/main.py's CORS allowlist).

- `ChatForm` — message + optional resume upload, POSTs to /chat.
- `ClubCard` — one matched club; a "Get info" button that POSTs to
  /research **only when clicked** (explicit design decision from Step 5 —
  never automatic). Once researched: checkboxes for whichever of
  application_deadline/next_meeting/info_session were actually found (the
  calendar-eligible, dated fields), coffee_chat_link shown as a plain link
  (it's a booking link, not something with its own start/end time so it
  doesn't make sense as a checkbox), or a message distinguishing "nothing
  posted" from "couldn't check the site right now" (based on whether the
  research result carried an `error`).
- `CalendarBar` — sticky bottom bar, live count of checked events, "Add to
  Google Calendar" button. **Stub for now** (BUILD_PROMPTS.md's own
  instruction for this step) — clicking it never contacts Google, just
  confirms what would be added; Step 7 wires the real thing.

Driven end-to-end with Playwright against a live uvicorn + vite dev server
(not just eyeballed): submitted a real query, got real matched clubs,
clicked "Get info" and got real extracted deadline/info-session data
rendered with working checkboxes, confirmed the not_found message renders
correctly for a club with nothing posted, uploaded a real resume through
the actual file input (not just curl) and confirmed resume-informed
matches came back, and clicked through the checkbox → "Add to Google
Calendar" stub flow. Zero browser console errors across all of this.
Screenshots taken during this pass are in the session's scratchpad only,
not committed.

Other service files under backend/services/ (calendar_sync.py) are still
docstring-only stubs.

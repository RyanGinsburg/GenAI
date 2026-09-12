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
- Data: scraped JSON files in /data for club data. **Exception, discussed and
  approved 2026-09-06**: user accounts (name/email/password) and saved-club
  lists live in SQLite (data/app.db, stdlib sqlite3, no ORM) instead of JSON —
  passwords and concurrent per-user writes are exactly the case flat JSON
  files handle badly (no locking, easy to corrupt). Club data itself
  (clubs.json/clubs_filtered.json) stays JSON as before.
- Accounts: stateless JWT (`Authorization: Bearer <token>`, pyjwt), password
  hashing via stdlib hashlib.pbkdf2_hmac (not bcrypt/passlib — avoids a
  compiled-extension dependency). No server-side session table.

## Project structure
club-agent/
  scraper/              # scrapes CampusGroups directory -> data/clubs.json
  data/                 # clubs.json, clubs_filtered.json, embeddings.npy,
                         # app.db (accounts/saved clubs), cache files
  backend/
    paths.py            # shared DATA_DIR/RESUME_DIR/DB_PATH constants
    db.py                # SQLite: users, saved_clubs tables, raw CRUD
    routes/              # FastAPI route handlers, one module per concern:
      auth_routes.py       # /auth/register, /auth/login, /auth/me
      chat_routes.py        # /chat/message, /chat/resume
      matching_routes.py     # /matching/from-profile, /matching/refine
      research_routes.py      # /research
      saved_clubs_routes.py    # /clubs/saved (GET/POST/POST remove)
      browse_routes.py          # /clubs (search/filter/paginate)
    services/
      matching.py        # embedding search + category-aware diversification
      resume_parser.py    # PDF -> structured profile
      research_agent.py   # fetch club site -> extract structured info
      chat_profile.py      # multi-turn conversational profile-builder + refine
      categorize.py         # Professional/Cultural-Affinity/Social-Fun/
                             #   Community Service tagging
      profile_schema.py      # shared StudentProfile shape + merge/readiness
      auth.py                # password hashing, JWT issue/verify, get_current_user
      accounts.py             # register/login validation on top of db.py + auth.py
      saved_clubs.py           # "My Clubs" save/unsave/list
      calendar_sync.py          # Google Calendar OAuth + event creation (stub)
  frontend/              # React app - Chat / Browse Clubs / My Clubs sections
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
A pass on 2026-09-11 replaced research_agent.py's Playwright fetch with
Firecrawl - see the dated section below for full detail. The only step
from BUILD_PROMPTS.md still open is **Step 7: Google Calendar OAuth**
(backend/services/calendar_sync.py + a POST /calendar/add-events route).
Needs manual Google Cloud Console setup (OAuth credentials) that can't be
automated.

**2026-09-11: replaced Playwright with Firecrawl for research_agent.py's
page fetching, widened to a multi-page keyword-biased crawl, and
coffee_chat_link is now a list.** research_club() previously drove a
locally-launched headless Chromium via Playwright to fetch just the
primary page plus one hand-picked "secondary" link
(SECONDARY_LINK_KEYWORDS priority match, max 2 pages total). It now calls
the Firecrawl REST API directly (plain `requests.post`/`get` against
`api.firecrawl.dev/v2` - deliberately not the `firecrawl-py` SDK, whose
class/method names have moved across versions even in current docs,
`FirecrawlApp.crawl_url` -> `Firecrawl.crawl`) with `crawlEntireDomain:
true` and `limit: 8`, so it crawls up to 8 same-domain pages per site
(`POST /v2/crawl` to start, poll `GET .../crawl/{id}` every 3s up to a
120s wall-clock budget) instead of exactly 1-2. Firecrawl's own link
discovery has no notion of "this looks like a recruiting page," so an
`includePaths` keyword bias (`apply`/`recruit`/`join`/`event`/`contact` -
the same list `_find_secondary_url()` used to prioritize) was added to
stop team-bio/blog-heavy sites from crowding out the one page that
matters within the 8-page budget - see `_build_include_paths()`. Each
returned page's markdown is combined the same way as before
(`--- Page: {url} ---\n{text}` blocks joined by blank lines), now
truncated as one combined string at `MAX_COMBINED_CHARS = 60000` (renamed
from the old per-page `MAX_PAGE_CHARS = 25000`, which no longer made sense
once page count is variable) rather than truncating each page
individually - checked against real crawls: AppDev's real 8-page,
apply/interview-guide-heavy crawl came in at 50,068/60,000 chars (83%),
comfortably under the cap with real headroom to spare. Also changed
`coffee_chat_link` from a single string-or-null to an array of strings
(empty array, not null, when none is found) so clubs with multiple
legitimate per-subteam coffee chat links (the AppDev-style case) aren't
forced down to just one - `SYSTEM_PROMPT`, `not_found`'s all-fields-empty
check, `_empty_result()`'s default, `ClubCard.jsx`'s rendering (now maps
over the array, numbering "#1"/"#2" when there's more than one, and fixes
a pre-existing `![]` truthiness bug in the "no details found" condition
that silently never fired for an empty array even before this change),
`qa/research_agent_review.py`'s display column, and
`research_routes.py`'s exception-fallback dict were all updated to match.

**`temperature=0` was requested but is not implementable on
`claude-sonnet-5`.** Confirmed live (a bare `temperature=0` call raised
`TypeError: Messages.create() got an unexpected keyword argument
'temperature'`): Anthropic has removed `temperature`/`top_p`/`top_k`
entirely from the current model generation (Sonnet 5, Opus 5, and others)
- there is no sampling-determinism knob left to set for this model.
Dropped; the extraction call is unchanged from before (temperature was
never set either way).

**Firecrawl's API enforces a 3 requests/minute rate limit on this
account** (confirmed live via rapid-fire test calls; no `Retry-After`
header, only a `"...please retry after 22s..."` string inside the JSON
error body). `POST /research` loops over a list of `website_urls`
back-to-back with no delay between them, so without handling this, a
multi-club batch would fail almost entirely (confirmed: an initial
20-club test run got only 2/20 through before every remaining call came
back 429). Added bounded retry-with-backoff: `_firecrawl_start()` retries
up to `FIRECRAWL_MAX_START_RETRIES = 2` times on a 429, and
`_firecrawl_poll()` treats a 429 as "keep waiting" within its existing
poll deadline rather than failing outright - both parse the "retry after
Ns" hint out of the error body (`_retry_after_seconds()`), falling back to
`FIRECRAWL_DEFAULT_RETRY_SECONDS = 20` if it can't be parsed.

**Verification** (spot-check, not a full 20-club re-run, given the 3
req/min limit above - the specific known quirks plus a few general
checks):
- **AppDev at Cornell: genuinely fixed.** `coffee_chat_link` now returns
  all 5 real per-subteam Calendly links (previously the single-string
  field arbitrarily returned one, or none, run to run) - confirmed stable
  across repeated runs, crawling 8 pages (homepage + `/apply` +
  per-track interview guides).
- **Cornell Business Analytics Club: the info_session run-to-run variance
  is genuinely gone, but not because of temperature** (which couldn't be
  set - see above). The real cause of the *old* variance no longer
  applies: without `includePaths`, this club's crawl picked up several
  `/team/<uuid>` bio sub-pages, `/clients`, and `/contact`, and never
  reached its real `/recruitment` page at all (confirmed by fetching the
  homepage directly - `/recruitment` is linked right in its nav). With
  `includePaths` added, the crawl now reliably reaches exactly
  `/`, `/contact`, `/recruitment` (3 pages, not 8) and 3 consecutive live
  runs returned identical results: the same deadline, the same 2 real
  info sessions, and the same coffee chat link every time.
- **Blockchain at Cornell: can no longer be compared to the old quirk -
  the site is fully gone.** `cornellblockchain.org` no longer resolves at
  all (confirmed via `nslookup`: NXDOMAIN), so the 2026-09-05 "Apply Now
  button has no static href even after JS rendering" finding can't be
  re-tested; this is an unrelated, real-world domain-expiry fact, not a
  research_agent.py issue.
- **scl.cornell.edu/convocation: the 403/WAF block is gone.** The
  2026-09-06 finding (403 to Playwright's headless Chromium specifically)
  does not reproduce via Firecrawl, which crawls from its own
  infrastructure rather than this machine's IP - 8 pages fetched
  successfully with no error, genuinely `not_found` (this is a university
  event page, not a club, so "no recruiting info" is the correct answer,
  not a miss).
- **Cornell Real Estate Club: a new, confirmed trade-off from
  `includePaths`.** This club's real deadline/application/coffee-chat
  content now lives at `/general-4` - a generic Wix-style auto-numbered
  slug containing none of the `apply`/`recruit`/`join`/`event`/`contact`
  keywords - confirmed live by fetching that page directly (it has real
  "deadline"/"apply"/"application"/"coffee chat" text). Because its path
  matches none of the keywords, `includePaths` never lets Firecrawl crawl
  it, so this club now comes back `not_found`. Explicit product decision:
  keep `includePaths` anyway, since it fixes the more common team-bio-
  flooding failure mode (confirmed on Business Analytics Club) at the cost
  of occasionally missing a keyword-less URL slug (confirmed only on this
  one club of those checked) - there is no path-priority concept in
  Firecrawl's API to get both, only include/exclude.

**2026-09-07: richer chat profile, deterministic readiness/merge,
diversified matching, conversational refine.** Expanded on the
2026-09-06 conversational profile-builder per explicit new requirements:

1. **Profile schema expanded from 4 loosely-defined fields
   (`interests`/`mode`/`time_commitment`/`notes`) to 7 named fields**:
   `school_or_college`, `major`, `vibe` (`social`/`professional`/`both`,
   renamed from `mode`), `activity_level` (`low`/`medium`/`high`, renamed
   from `time_commitment`), `specific_interests_in_mind` (array),
   `hobbies` (array), `openness_to_cultural_affinity_groups`
   (`yes`/`open`/`not_sure`) - phrased in the system prompt as a warm,
   open invitation to see cultural/identity-based/affinity clubs,
   **never** asking the student to state their own race/ethnicity/other
   personal characteristics. New backend/services/profile_schema.py is
   the single source of truth for this shape (a Pydantic `StudentProfile`
   plus pure `merge_profile()`/`is_ready_for_matching()` functions),
   replacing four previously-duplicated, inconsistent versions of the
   profile shape (chat_profile.py's prompt text, matching.py's docstring,
   matching_routes.py's non-enum-constrained Pydantic model, and the
   frontend's implicit usage). `specific_interests_in_mind`/`hobbies` are
   the topic-bearing fields the LLM fills in as arrays of short phrases;
   there's no separate `interests` field anymore - matching.py's new
   `build_interest_phrases()` derives query phrases from them directly at
   match time, deliberately never blending them into one string (would
   reintroduce the exact 2026-09-06 diversity bug).
2. **Readiness and merging are now enforced in Python, not just prompt
   text.** `profile_schema.is_ready_for_matching()` sets an explicit low
   bar (vibe + at least one concrete topic + 3+ fields filled) and
   OR's with the model's own `ready_for_matching` judgment, plus a hard
   `MAX_TURNS = 3` backstop; `merge_profile()` deterministically merges
   each turn's `profile_delta` into the running profile so nothing
   previously established gets silently dropped. Verified live: the test
   case "I'm a sophomore in Engineering, want a mix of professional and
   fun clubs, not too intense time-wise" correctly does NOT clear the bar
   on turn 1 alone (school/vibe/activity_level but no major/interest/
   hobby yet), asks exactly one natural follow-up, then clears it on turn
   2 - two exchanges total, the intended normal case.
3. **Matching is now category-aware, via new
   `matching.match_clubs_diversified()`** (replaces
   `match_clubs_for_profile()`, which read now-nonexistent `interests`/
   `mode` keys). For a clearly single vibe ("professional"/"social") it
   delegates to the existing flat `match_clubs_multi_query()` - no forced
   diversification, respecting the student's stated preference. For
   `"both"`/unset vibe, it runs a **separate** `match_clubs_multi_query()`
   per target category (Professional, Social/Fun), filters each bucket's
   candidates through `categorize_club()` so embedding similarity alone
   can't leak an off-category club into a bucket, allocates an even quota
   per bucket, and interleaves - this is what actually fixes "a mix of
   professional and fun could come back all one type" (the old
   `match_clubs_for_profile()`/`match_clubs_multi_query()` pooling had no
   category awareness at all; diversification only ever existed as a
   post-hoc *display* grouping in categorize.py, fully decoupled from
   ranking). `activity_level` folds in as a soft embedding-text bias
   phrase per bucket (no time-commitment metadata exists on clubs, same
   soft-bias approach as the existing sustainability sanity check).
   Verified live end-to-end for the Engineering test case above: results
   correctly split across both Professional and Social/Fun (15/15 of a
   30-result set), not a lopsided single-category list.
4. **A `Cultural/Affinity` category was added to categorize.py**, keyed
   on CampusGroups' own `"International/Multicultural"` tag (111/877
   clubs) - checked against real data first: the previously-considered
   alternative of gating on the existing `Community Service` tag would
   have missed the great majority of actual cultural/affinity clubs (only
   8 of the 111 also carry a Community Service tag). It only gets an
   active, guaranteed quota slot in `match_clubs_diversified()` when
   `openness_to_cultural_affinity_groups == "yes"` specifically (a clear
   affirmative) - `"open"`/`"not_sure"` get no special treatment, per
   explicit product decision to treat that field as a genuine invitation
   rather than a default-on nudge. Since this category is global (not
   diversification-specific), `frontend/src/components/BrowseClubs.jsx`'s
   category filter buttons and `categorize.py`'s own sanity counts were
   updated too (Professional 235 / Cultural-Affinity 111 / Social-Fun 441
   / Community-Service 90 of 877, confirmed live).
5. **Conversational refine after results** - new
   `chat_profile.refine_profile()` (single-turn, no history) interprets a
   follow-up like "show me more social ones" or "something with less time
   commitment" into a `profile_delta`, and new `POST /matching/refine`
   bundles that plus a re-run of `match_clubs_diversified()` into one
   round trip. The frontend no longer unmounts the chat entirely once
   results appear (the old `ChatSection.jsx` behavior) - a new
   `RefineBar.jsx` stays alongside `MatchResults`, reusing the `busy`-
   gating pattern already established in `ChatAssistant.jsx`. Verified
   live: typing "show me more social ones" after initial results updated
   `vibe` to `"social"` and refreshed results in place, with the running
   profile/chat state intact (no restart).
6. **New `qa/verify_profile_and_matching.py`** scripts the full test case
   above against the real, non-mocked `continue_profile_chat`/
   `match_clubs_diversified` functions, printing the turn-by-turn
   conversation trace with profile snapshots and the final grouped/
   labeled club list, and asserts both Professional and Social/Fun come
   back non-empty (a regression check in the same spirit as matching.py's
   own diversity-bug assert). `resume_parser.py` also gained a literal-
   only `school_or_college` extraction field (same no-fabrication rule as
   `major`/`graduation_year`) so a resume can pre-fill it.

Verified end-to-end with a real Playwright pass against live `uvicorn
--reload` + `vite` dev servers (not just the qa script): the full 2-turn
chat interview, diversified results rendering correctly grouped, the
refine bar updating results in place without losing state, and Browse
Clubs' `Cultural/Affinity` filter button correctly filtering to 111
clubs - zero browser console errors throughout. The existing
`matching.py` diversity-bug regression assert (blended query still gets 0
Project Team hits, multi-query recovers more than 0) was re-run unchanged
and still passes.

**2026-09-06: accounts, conversational matching, a real matching bug fix,
and a visual redesign.** User testing after Step 6 surfaced three real
problems, all addressed together:

1. **Matching bug, root-caused and fixed.** A resume with 7 diverse
   `suggested_club_interests` (5 finance-flavored, 2 not) returned zero of
   the 36 "Project Team"-tagged clubs and a max score around 45-53%. Cause:
   the old `match_clubs()` joined all interests into one string and
   embedded it as a single blended vector, which drifts toward whichever
   topic dominates the phrase list and drowns out minority topics -
   confirmed a single-topic robotics query surfaces Project Team clubs
   fine (0.45-0.46), so this was specifically a multi-topic-blended-into-
   one-vector problem, not a broken embedding model (0.45-0.60 top scores
   are otherwise the normal ceiling here). Fixed by adding
   `match_clubs_multi_query()` in matching.py: embeds each interest
   separately and pools the top-k clubs **per interest** before merging,
   so a minority topic can't be out-voted by a blended average. Verified
   live end-to-end through the real UI: a chat profile of
   robotics + heavy finance interests now surfaces Combat Robotics at
   Cornell, AutoBoat at Cornell, Autonomous Sailboat Club, and CU Design
   Build Fly alongside the finance clubs. `matching.py`'s `__main__` block
   has a permanent regression assertion for this (0 hits via the old
   blended query, >0 via the new one).
2. **The single search textbox is gone, replaced by a real multi-turn
   conversational profile-builder** (backend/services/chat_profile.py,
   frontend ChatAssistant.jsx). Stateless (frontend resends full history
   each turn), same "return ONLY JSON" convention as resume_parser.py/
   research_agent.py, asks up to 5 short questions (interests, professional
   vs. social vs. both, time commitment), can take a resume attachment at
   any point (not just turn one) which feeds resume context into the
   conversation, and ends by producing a structured profile that
   `match_clubs_for_profile()` turns into results. Results are grouped into
   Professional / Social & Fun / Community Service via
   services/categorize.py - a **deterministic string match over the
   existing CampusGroups category tags already in clubs_filtered.json**
   (`PROF:`/`AFFILIATION: Project Team`/`AFFILIATION: Professional
   Fraternity` -> Professional; `Community Service` tag -> Community
   Service; else -> Social/Fun), not a new LLM call - sanity-checked
   against all 877 clubs: 235/544/98.
   **Bug found and fixed during Playwright testing**: while a resume was
   uploading (before its own chat turn even started), the text input
   wasn't disabled, so a manually-typed message could race the resume-
   triggered turn and corrupt conversation history via a stale `history`
   closure. Fixed by gating the text input, send button, and file input
   all on one combined `busy = sending || resumeUploading` flag.
3. **Accounts + "My Clubs" + "Browse Clubs".** New SQLite-backed accounts
   (see the tech-stack exception above) via backend/db.py,
   services/auth.py, services/accounts.py, routes/auth_routes.py.
   **Login only gates saving a club / viewing My Clubs** - chatting and
   browsing the full 877-club directory (routes/browse_routes.py, search +
   category filter + pagination, frontend BrowseClubs.jsx) work fully
   anonymously, so there's no wall before a student's even seen a club.
   Clicking "Save" while logged out opens the auth modal instead of a
   network call. services/saved_clubs.py stores only
   `(user_id, website_url)` in SQLite and resolves full club details from
   clubs_filtered.json at read time, so there's one source of truth for
   club data and My Clubs can't go stale relative to it.
4. **Visual redesign to a "clean modern app" look** (whitespace, refined
   type scale, subtle consistent elevation, quiet color use) - this
   **fully retires the "pinboard of tilted cards" concept** from the prior
   redesign pass (TILT_SEQUENCE and the rotate-on-hover CSS are gone
   entirely) in favor of flat, evenly-elevated cards. Cornell carnelian red
   stays the sole accent. Also removed every remaining em dash from
   user-facing copy (was 3: two in App.jsx, one in ClubCard.jsx) and wrote
   all new copy (chat messages, auth forms, section copy) without any -
   confirmed via a full-page text grep during the Playwright pass.

Loading feedback added throughout: a spinner for each chat turn ("Reading
your resume..." / "Thinking..."), an indeterminate progress bar for
"Finding your clubs..." after the interview ends, and spinners for
Browse Clubs' initial load and each "Get info" check.

Verified end-to-end with Playwright against live `uvicorn --reload` +
`vite` dev servers (not just eyeballed, and not just curl): a full chat
interview including a mid-conversation resume attach, transition to
grouped results, Save-while-logged-out correctly opening the auth modal
instead of hitting the network, registration + auto-login + a real save,
My Clubs showing the saved club with full resolved details, Browse Clubs
search/filter/pagination with no score badge shown, logout correctly
reverting My Clubs to the login prompt, the existing Get-info/checkbox/
calendar-stub flow still working unchanged, and zero browser console
errors and zero em dashes anywhere across the entire pass.

research_agent.py accuracy work was explicitly out of scope for this pass
(the user is handling that separately) - not touched.

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

**Step 5 (backend/main.py) is done as of 2026-09-06.** (Superseded later
the same day - see the "2026-09-06: accounts, conversational matching..."
section above. `POST /chat` described just below no longer exists; it was
replaced by `/chat/message` + `/chat/resume` + `/matching/from-profile`.
Keeping this section for the historical record of what Step 5 originally
shipped.) A FastAPI app with the two routes from BUILD_PROMPTS.md, both
curl-tested against a live server:
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

**Step 6 (frontend/) is done as of 2026-09-06.** (Also superseded later the
same day - `ChatForm` described just below was deleted and replaced by
`ChatAssistant`/`ChatSection`, and `NavBar`/`BrowseClubs`/`MyClubs`/
`AuthModal` were added; see the section above.) Node was installed
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

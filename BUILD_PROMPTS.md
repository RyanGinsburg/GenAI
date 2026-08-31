# Build sequence — paste these into Claude Code, one at a time

Do these in order. Don't move to the next prompt until the current one
actually works and you've looked at the output yourself.

---

## Step 0 — Setup (do this first, once)

1. Create a new folder, open it in Claude Code.
2. Save the CLAUDE.md file (from this conversation) into the root of that
   folder, named exactly `CLAUDE.md`.
3. Start Claude Code and paste this as your very first message:

```
Read CLAUDE.md in this repo for full project context before doing anything
else. Then set up the project skeleton: create the folder structure described
in CLAUDE.md, a Python virtual environment, a requirements.txt with fastapi,
uvicorn, requests, beautifulsoup4, anthropic, python-dotenv, pypdf, and
numpy, and a .env.example with placeholders for ANTHROPIC_API_KEY and
GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET. Don't write any feature code yet —
just the skeleton.
```

---

## Step 1 — Scraper

```
Build scraper/scrape_campusgroups.py. It should scrape Cornell's public
CampusGroups directory at https://cornell.campusgroups.com/club_signup
and its category pages, and for each club collect: name, category, a
description if available, and the club's own website URL if listed.
Output everything to data/clubs.json as a list of objects with keys:
name, category, description, website_url.

Add a small delay between requests to be polite to the server. Print
progress as it runs. After writing it, run it yourself on a limited
sample (e.g. one category, or the first 20 clubs) and show me the
output so we can check the data looks right before scraping everything.
```

Once you've eyeballed the sample and it looks right:

```
Looks good. Now run it on the full directory and confirm how many clubs
ended up in data/clubs.json, and show me 3 random examples from the file.
```

---

## Step 2 — Embeddings + matching

```
Build backend/services/matching.py. It should:
1. Load data/clubs.json
2. Generate an embedding for each club (combine name + description + category
   into one string before embedding)
3. Cache the embeddings to data/embeddings.npy so we don't regenerate them
   every run
4. Expose a function match_clubs(query: str, top_k: int = 10) that embeds
   the query and returns the top_k most similar clubs by cosine similarity

Use whatever embedding approach is simplest to get working — a local
sentence-transformers model is fine if internet access to pypi is
available, otherwise ask me which embedding API to use.

Write a small test at the bottom (under if __name__ == "__main__") that
runs a sample query like "sustainability and climate policy clubs, low
time commitment" and prints the top 5 results so I can sanity check it.
```

---

## Step 3 — Resume parsing

```
Build backend/services/resume_parser.py. It should take a PDF file path,
extract the text with pypdf, then call the Claude API with a prompt that
extracts: major, graduation year, skills, interests, and any clubs/orgs
already mentioned, returning strict JSON. Handle the case where the PDF
has no extractable text (e.g. scanned image) by returning an error message
instead of crashing.

Write a quick test that runs this against a sample resume PDF (I'll
provide one) and prints the extracted JSON.
```

(Have a real resume PDF ready to hand it, or ask Claude Code to generate a
fake sample resume text file to test against first.)

---

## Step 4 — Research agent (the hard part — go slow here)

```
Build backend/services/research_agent.py. Given a club's website_url, it
should:
1. Fetch the page (and if there's an obvious nav link containing words like
   "events", "join", "recruit", "apply", or "contact", fetch that page too —
   max 2 pages total)
2. Pass the combined page text to Claude with a prompt asking it to extract:
   application_deadline, next_meeting, info_session, coffee_chat_link —
   using null for anything not found. Be explicit in the prompt that it must
   NOT guess or infer dates that aren't actually stated on the page.
3. Return a structured result, and if nothing was found, return a
   clear "not_found": true flag along with the original website_url so the
   frontend can show "couldn't find details, here's their site" to the user.

Before wiring this into anything else, write a test that runs this
function against 3-4 real club website URLs from data/clubs.json (pick
ones that look like they have real content, e.g. business or tech clubs)
and prints what got extracted for each, so we can see how well it's
working on real messy websites.
```

Expect to iterate on the extraction prompt here — show Claude Code the
actual output on a few clubs and ask it to fix cases where it's missing
obvious info or including something it shouldn't.

---

## Step 5 — Wire it into a backend API

```
Build backend/main.py as a FastAPI app with these routes:
- POST /chat — takes a message and optional resume file, returns matched
  clubs using matching.py and resume_parser.py
- POST /research — takes a list of club website_urls, runs research_agent.py
  on each, returns results
- The routes should be simple for now — no auth, no database, just wiring
  the services together. Add basic error handling so a failure on one club's
  research doesn't crash the whole request.

Run the server and show me a working curl example for each route.
```

---

## Step 6 — Frontend

```
Build a minimal React frontend in frontend/ with:
- A chat interface where the student can type what they're looking for
  and optionally upload a resume PDF
- A results view showing matched clubs as cards
- A "research this club" button per card that calls /research and shows
  deadline/meeting/coffee chat info, or a "couldn't find details" message
  with a link to the club's site
- A confirmation step: checkboxes to select which found events to add to
  calendar, with an "Add to Google Calendar" button (can be a stub/fake
  button for now — we'll wire real calendar auth in the next step)

Keep the styling simple and clean, we'll polish it later. Focus on it
actually working end to end first.
```

---

## Step 7 — Google Calendar integration (last, since it needs OAuth setup)

```
Build backend/services/calendar_sync.py implementing Google Calendar OAuth2
(installed app flow) and a function create_event(summary, description,
start_time, end_time) that adds an event to the user's primary calendar.
Also add a route in main.py, POST /calendar/add-events, that takes a list
of confirmed events from the frontend and creates them.

Walk me through the Google Cloud Console setup steps I need to do manually
(creating OAuth credentials) since that part can't be automated.
```

---

## General tips while doing this

- If Claude Code's output for the research agent looks bad on real sites,
  paste the actual extracted (wrong) output back and ask it to fix the
  prompt — don't just re-run the same prompt hoping for a better result.
- Keep CLAUDE.md's "Current status" section updated as you finish each step,
  so future sessions (or your teammates) have context without re-explaining.
- Commit to git after each working step so you can roll back if a change
  breaks something.

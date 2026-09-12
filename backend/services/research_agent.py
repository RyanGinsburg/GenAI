"""Research a club's website for deadlines, meetings, and coffee chats.

Given a club's website_url:
1. Crawl the site with Firecrawl (api.firecrawl.dev), which renders pages
   with its own headless infrastructure and returns clean markdown per
   page — up to FIRECRAWL_CRAWL_LIMIT same-domain pages, not just a
   hand-picked primary + secondary link.
2. Ask Claude to extract: application_deadline, next_meeting, info_session,
   coffee_chat_link.
3. Return a structured result. If nothing was found, set not_found: true
   alongside the original website_url so the frontend can fall back to
   "couldn't find details, here's their site."

Per CLAUDE.md's "never fabricate" constraint: the model is explicitly told
not to guess or infer anything not actually stated on the page(s) — any
field it can't find comes back null (or an empty list, for
coffee_chat_link), not a plausible-looking guess.

Why Firecrawl instead of a local headless browser: this file previously
drove Playwright/Chromium itself, specifically because a plain
`requests.get()` can't see content a site injects into the DOM via
client-side JS after page load (confirmed 2026-09-05 on Applied Public
Policy Strategies at Cornell — its real deadline/info-session dates only
exist because script.js appends them to the page on DOMContentLoaded).
Firecrawl's hosted crawler renders JS the same way Playwright did, so that
problem is still solved, just by different infrastructure — and its
/crawl endpoint also does the "find more relevant pages on this site" job
that _find_secondary_url() used to do by hand (a single keyword-matched
link, max 2 pages total), now covering up to FIRECRAWL_CRAWL_LIMIT pages
per site via Firecrawl's own link discovery, biased toward the same
apply/recruit/join/event/contact keywords via includePaths (see
_build_include_paths) so a site with many unrelated pages (team bios, a
blog, a privacy policy) doesn't crowd out the one page that actually has
recruiting info within the page budget.
"""

from __future__ import annotations

import json
import os
import re
import time
from urllib.parse import urlparse

import anthropic
import requests
from dotenv import load_dotenv

load_dotenv()

FIRECRAWL_API_BASE = "https://api.firecrawl.dev/v2"
FIRECRAWL_CRAWL_LIMIT = 8  # replaces the old MAX_PAGES=2 primary+secondary cap
FIRECRAWL_REQUEST_TIMEOUT_SECONDS = 20  # per HTTP call (one POST or one GET poll)
FIRECRAWL_POLL_INTERVAL_SECONDS = 3
FIRECRAWL_POLL_TIMEOUT_SECONDS = 120  # wall-clock budget for the whole crawl to finish
# Raised from an initial 90s: a low-tier Firecrawl plan's 429 responses have
# been observed asking for a 20-60s backoff (see FIRECRAWL_DEFAULT_RETRY_SECONDS
# below), and this budget needs room for one such backoff cycle mid-poll on
# top of the crawl's own real run time.

FIRECRAWL_MAX_START_RETRIES = 2  # bounded retries for the initial POST /crawl
# request specifically, on 429 only. POST /research loops over multiple
# website_urls back-to-back with no delay between them, so a rate-limited
# Firecrawl plan (confirmed live: 3 requests/min, no Retry-After header, only
# a "retry after Ns" string in the JSON error body) would otherwise fail most
# of a multi-club batch outright instead of just running slower.
FIRECRAWL_DEFAULT_RETRY_SECONDS = 20  # fallback backoff when a 429 body's
# "retry after Ns" hint can't be parsed
_RETRY_AFTER_RE = re.compile(r"retry after (\d+)s", re.IGNORECASE)

FIRECRAWL_INCLUDE_PATH_KEYWORDS = ("apply", "recruit", "join", "event", "contact")
# Same keyword list the old _find_secondary_url() prioritized (apply/recruit/
# join over events/contact) - apply/recruit/join/event/contact paths are
# where clubs actually put deadlines and application info. Without this,
# Firecrawl's own link discovery has no notion of which pages matter and can
# fill the whole FIRECRAWL_CRAWL_LIMIT budget on low-value pages instead -
# confirmed live on Cornell Business Analytics Club, whose crawl picked up
# several /team/<uuid> bio sub-pages and never reached its real /recruitment
# page, which the site's own nav links directly from the homepage.

MAX_COMBINED_CHARS = 60000  # replaces the old per-page MAX_PAGE_CHARS=25000;
# applied to the final *combined* multi-page text now, since page count is
# variable (1-8, via FIRECRAWL_CRAWL_LIMIT) rather than a fixed 1-or-2. The
# most verbose real page seen so far (Applied Public Policy Strategies,
# ~13.8k chars fully rendered) plus headroom for an 8-page crawl averaging
# ~7-8k chars/page worst case (~56-64k total) both fit comfortably under
# this, while staying well inside claude-sonnet-5's 200k-token window and
# keeping the typical-case call cheap. Bump this if real testing finds a
# club site actually getting truncated at this boundary.

MODEL = "claude-sonnet-5"

RESULT_FIELDS = ("application_deadline", "next_meeting", "info_session", "coffee_chat_link")
# coffee_chat_link and info_session are list-valued (see SYSTEM_PROMPT) -
# info_session because a club can hold more than one session (e.g. two
# different dates), same reasoning as coffee_chat_link's per-subteam links.
# Every other field is a scalar string-or-null. _FIELD_DEFAULTS/
# _empty_result() and research_club()'s not_found check both need to treat
# a list field's "nothing found" value as [] rather than None.
_LIST_FIELDS = {"coffee_chat_link", "info_session"}
_FIELD_DEFAULTS = {f: ([] if f in _LIST_FIELDS else None) for f in RESULT_FIELDS}

SYSTEM_PROMPT = """You extract recruiting/event details from a student club's website text.

You will be given the markdown text of several pages crawled from the club's own
website. Return ONLY a single JSON object (no markdown fences, no commentary) with
exactly these keys:
- "application_deadline": string or null - a stated deadline to apply/join
- "next_meeting": string or null - a stated date/time for the next general meeting
- "info_session": array of strings - each string describing ONE info session with
  its own single date/time (e.g. "August 27, 5:30-7:00pm"). Use an empty array []
  if none are stated. Some clubs hold multiple info sessions - if that's the case,
  return each one as its own separate array entry rather than combining them into
  one string (do NOT return something like "Session 1: Aug 27 ...; Session 2:
  Sept 1 ..." as a single string - split it into two array entries instead).
- "coffee_chat_link": array of strings - URL(s)/contact(s) for booking a coffee chat.
  Use an empty array [] if none are stated. Some clubs have multiple sub-teams or
  committees, each with its own coffee chat sign-up link (e.g. a separate link for
  "Design" and one for "Engineering") - if that's the case, include ALL of them, not
  just one.

Rules:
- Only use information explicitly stated in the given page text. Do NOT guess, infer,
  estimate, or make up a date, time, or link that isn't actually written on the page.
- Recurring/vague statements ("we meet weekly") without an actual date or day are not
  a "next_meeting" - only extract it if a specific date, day-of-week + time, or
  similar concrete detail is given.
- Some pages contain a generic placeholder elsewhere on the page - e.g. a hero banner
  saying "details will be announced soon" or "TBD" - even when a specific, concrete
  date/time/link is also given further down (e.g. in a detailed timeline or list). If
  a concrete detail is stated anywhere on the page, extract it - a vague placeholder
  elsewhere on the same page does NOT override or suppress a specific date, time, or
  link that is actually present. Only use null when no concrete detail is given at all.
- Links appear in standard markdown syntax, e.g. '[Sign Up Now](https://forms.gle/abc123)'
  - collect the URL into coffee_chat_link whenever the surrounding link text/context
  indicates it's for booking a coffee chat. A page can legitimately have more than one
  such link (e.g. one per sub-team) - collect every one you find, not just the first.
- If application_deadline or next_meeting isn't present in the text, use null for that
  field. If no info session or coffee chat link is present anywhere, use an empty
  array [] for that field. It is normal and expected for most or all fields to come
  back empty - most club websites don't list this information.
- Output must be valid JSON and nothing else.
"""

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def _empty_result(website_url: str, error: str | None = None) -> dict:
    result = {"website_url": website_url, **_FIELD_DEFAULTS, "not_found": True}
    if error:
        result["error"] = error
    return result


def _retry_after_seconds(response_text: str) -> int:
    """Extract a "retry after Ns" hint from a Firecrawl 429 error body (no
    Retry-After header is sent), or fall back to a default backoff."""
    match = _RETRY_AFTER_RE.search(response_text)
    return int(match.group(1)) if match else FIRECRAWL_DEFAULT_RETRY_SECONDS


def _build_include_paths(url: str) -> list[str]:
    """includePaths patterns for one club's crawl. Firecrawl also checks the
    seed URL itself against these patterns (an all-keyword list with no
    exact-seed-path entry can return 0 pages), so the seed's own path is
    always included exactly, in addition to the keyword bias."""
    seed_path = urlparse(url).path or "/"
    return [f"^{re.escape(seed_path)}$"] + [
        f"(?i){kw}" for kw in FIRECRAWL_INCLUDE_PATH_KEYWORDS
    ]


def _firecrawl_start(url: str) -> tuple[str | None, str | None]:
    """POST /v2/crawl for url. Returns (status_url, None) on success, or
    (None, error_message) on any failure (missing key, network error,
    non-2xx response, malformed body) — never raises."""
    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        return None, "Missing FIRECRAWL_API_KEY."

    body = {
        "url": url,
        "limit": FIRECRAWL_CRAWL_LIMIT,
        "crawlEntireDomain": True,
        "allowSubdomains": False,
        "allowExternalLinks": False,
        "includePaths": _build_include_paths(url),
        "scrapeOptions": {"formats": ["markdown"], "onlyMainContent": False},
    }
    for attempt in range(FIRECRAWL_MAX_START_RETRIES + 1):
        try:
            resp = requests.post(
                f"{FIRECRAWL_API_BASE}/crawl",
                json=body,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=FIRECRAWL_REQUEST_TIMEOUT_SECONDS,
            )
        except requests.RequestException as e:
            return None, f"Network error starting Firecrawl crawl: {e}"

        if resp.status_code == 429 and attempt < FIRECRAWL_MAX_START_RETRIES:
            time.sleep(_retry_after_seconds(resp.text))
            continue
        break

    if not resp.ok:
        return None, f"Firecrawl crawl request failed ({resp.status_code}): {resp.text[:300]}"

    try:
        data = resp.json()
    except ValueError:
        return None, "Firecrawl crawl request did not return valid JSON."

    if not data.get("success") or not data.get("url"):
        return None, "Firecrawl crawl request did not return a job status URL."

    return data["url"], None


def _firecrawl_poll(status_url: str) -> tuple[list[dict] | None, str | None]:
    """Poll status_url until Firecrawl reports completed/failed, or
    FIRECRAWL_POLL_TIMEOUT_SECONDS elapses. Returns (pages, None) on
    success — pages is the raw list of Firecrawl page objects (each with
    "markdown"/"metadata") — or (None, error_message) on any failure.
    Never raises."""
    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        return None, "Missing FIRECRAWL_API_KEY."

    deadline = time.monotonic() + FIRECRAWL_POLL_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        try:
            resp = requests.get(
                status_url,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=FIRECRAWL_REQUEST_TIMEOUT_SECONDS,
            )
        except requests.RequestException as e:
            return None, f"Network error polling Firecrawl crawl: {e}"

        if resp.status_code == 429:
            # Wait out the rate limit within the existing deadline rather
            # than failing outright — see FIRECRAWL_MAX_START_RETRIES.
            wait = min(_retry_after_seconds(resp.text), max(0, deadline - time.monotonic()))
            time.sleep(wait)
            continue

        if not resp.ok:
            return None, f"Firecrawl status check failed ({resp.status_code}): {resp.text[:300]}"

        try:
            data = resp.json()
        except ValueError:
            return None, "Firecrawl status check did not return valid JSON."

        status = data.get("status")
        if status == "completed":
            return data.get("data") or [], None
        if status == "failed":
            return None, f"Firecrawl crawl failed: {data.get('error', 'no detail given')}"

        time.sleep(FIRECRAWL_POLL_INTERVAL_SECONDS)

    return None, f"Firecrawl crawl timed out after {FIRECRAWL_POLL_TIMEOUT_SECONDS}s."


def _crawl_site(url: str) -> tuple[list[dict], str | None]:
    """Start a Firecrawl crawl of url and wait for it to finish. Returns
    (pages, None) on success or ([], error_message) on any failure."""
    status_url, error = _firecrawl_start(url)
    if error:
        return [], error
    pages, error = _firecrawl_poll(status_url)
    if error:
        return [], error
    return pages, None


def _page_url(page: dict, fallback: str) -> str:
    """Best-effort source URL for one Firecrawl page object."""
    metadata = page.get("metadata") or {}
    return metadata.get("url") or metadata.get("sourceURL") or fallback


def _page_markdown(page: dict) -> str:
    """This page's markdown content, or '' if Firecrawl returned none."""
    return (page.get("markdown") or "").strip()


def research_club(website_url: str) -> dict:
    """Research one club's website. Returns a dict with website_url,
    application_deadline, next_meeting, info_session (a list, one entry per
    distinct session), coffee_chat_link (a list), and not_found (true iff
    every field above is empty). Never
    raises - any failure (unreachable site, crawl timeout, bad API
    response) comes back as not_found with an "error" key describing what
    went wrong.
    """
    pages, error = _crawl_site(website_url)
    if error or not pages:
        return _empty_result(website_url, error=error or f"No pages returned for {website_url}")

    pages_checked = [_page_url(p, website_url) for p in pages]
    texts = [_page_markdown(p) for p in pages]

    combined_text = "\n\n".join(
        f"--- Page: {url} ---\n{text}" for url, text in zip(pages_checked, texts)
    )[:MAX_COMBINED_CHARS]

    try:
        response = _get_client().messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": combined_text}],
        )
    except anthropic.AuthenticationError:
        return _empty_result(website_url, error="Invalid or missing ANTHROPIC_API_KEY.")
    except anthropic.PermissionDeniedError:
        return _empty_result(website_url, error="API key lacks permission for this request.")
    except anthropic.RateLimitError:
        return _empty_result(website_url, error="Rate limited by the Claude API. Try again shortly.")
    except anthropic.APIStatusError as e:
        return _empty_result(website_url, error=f"Claude API error ({e.status_code}): {e.message}")
    except anthropic.APIConnectionError:
        return _empty_result(website_url, error="Network error connecting to the Claude API.")

    response_text = next(
        (block.text for block in response.content if block.type == "text"), ""
    )

    if response.stop_reason == "max_tokens":
        return _empty_result(website_url, error="Model response was cut off (hit max_tokens).")

    match = re.match(r"^```(?:json)?\s*\n(.*)\n```$", response_text.strip(), re.DOTALL)
    cleaned = match.group(1).strip() if match else response_text.strip()

    try:
        extracted = json.loads(cleaned)
    except json.JSONDecodeError:
        return _empty_result(website_url, error=f"Model did not return valid JSON: {response_text[:300]!r}")

    fields = {f: extracted.get(f) for f in RESULT_FIELDS}
    for f in _LIST_FIELDS:
        if fields[f] is None:
            fields[f] = []
        elif isinstance(fields[f], str):
            # Defensive: tolerate the model returning a bare string despite
            # the schema instruction, rather than dropping a real value.
            fields[f] = [fields[f]]

    not_found = all(
        fields[f] == [] if f in _LIST_FIELDS else fields[f] is None
        for f in RESULT_FIELDS
    )

    return {
        "website_url": website_url,
        "pages_checked": pages_checked,
        "not_found": not_found,
        **fields,
    }


if __name__ == "__main__":
    import sys

    # A few real business/tech club sites from data/clubs.json, picked because
    # they're independently hosted (not campusgroups.com) and so more likely
    # to have real recruiting content to test extraction against.
    default_test_urls = [
        "https://www.johnsonconsultingclub.com/",
        "https://www.cornellbusinessanalytics.org/",
        "https://www.akpsicornell.com/",
        "https://www.cornellrealestateclub.com/",
    ]
    test_urls = sys.argv[1:] or default_test_urls

    for url in test_urls:
        print(f"\n=== {url} ===")
        result = research_club(url)
        print(json.dumps(result, indent=2))

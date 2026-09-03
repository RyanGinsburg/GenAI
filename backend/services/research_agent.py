"""Research a club's website for deadlines, meetings, and coffee chats.

Given a club's website_url:
1. Fetch the page, and if an obvious nav link looks like it points to
   events/join/recruit/apply/contact info, fetch that page too (max 2 pages
   total).
2. Ask Claude to extract: application_deadline, next_meeting, info_session,
   coffee_chat_link.
3. Return a structured result. If nothing was found, set not_found: true
   alongside the original website_url so the frontend can fall back to
   "couldn't find details, here's their site."

Per CLAUDE.md's "never fabricate" constraint: the model is explicitly told
not to guess or infer anything not actually stated on the page(s) — any
field it can't find comes back null, not a plausible-looking guess.
"""

from __future__ import annotations

import json
import re
from urllib.parse import urljoin, urlparse

import anthropic
import requests
from bs4 import BeautifulSoup, NavigableString
from dotenv import load_dotenv

load_dotenv()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; CornellClubAgent/0.1; "
        "student project, contact via github.com/RyanGinsburg/GenAI)"
    )
}
REQUEST_TIMEOUT_SECONDS = 15
MAX_PAGES = 2
MAX_PAGE_CHARS = 12000  # keep the prompt a reasonable size on very long pages

MODEL = "claude-sonnet-5"

SECONDARY_LINK_KEYWORDS = ("events", "join", "recruit", "apply", "contact")
RESULT_FIELDS = ("application_deadline", "next_meeting", "info_session", "coffee_chat_link")

SYSTEM_PROMPT = """You extract recruiting/event details from a student club's website text.

You will be given the text of 1-2 pages from the club's own website. Return ONLY a
single JSON object (no markdown fences, no commentary) with exactly these keys:
- "application_deadline": string or null - a stated deadline to apply/join
- "next_meeting": string or null - a stated date/time for the next general meeting
- "info_session": string or null - a stated date/time for an info session
- "coffee_chat_link": string or null - a stated URL/contact for booking a coffee chat

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
- Link destinations appear in parentheses right after their link text, e.g.
  'Sign Up Now (https://forms.gle/abc123)' - use that URL for coffee_chat_link when
  the surrounding link text/context indicates it's for booking a coffee chat.
- If a field isn't present in the text, use null for it. It is normal and expected
  for most or all fields to be null - most club websites don't list this information.
- Output must be valid JSON and nothing else.
"""

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def _empty_result(website_url: str, error: str | None = None) -> dict:
    result = {"website_url": website_url, **{f: None for f in RESULT_FIELDS}, "not_found": True}
    if error:
        result["error"] = error
    return result


def _fetch(url: str) -> BeautifulSoup | None:
    """Fetch and parse one page. Returns None on any request failure."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT_SECONDS)
        resp.raise_for_status()
    except requests.RequestException:
        return None
    return BeautifulSoup(resp.text, "html.parser")


def _page_text(soup: BeautifulSoup, base_url: str) -> str:
    """Visible text of a page, scripts/styles stripped, whitespace collapsed.

    Link destinations are preserved in parentheses right after their anchor
    text (e.g. "Sign Up Now (https://forms.gle/abc123)"). Plain
    soup.get_text() silently drops every <a href>, which meant a coffee chat
    link sitting right on the page was invisible to the model even though
    the button text ("Sign Up Now") survived - see qa/research_agent_review.md.
    """
    for tag in soup(["script", "style", "noscript"]):
        tag.extract()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        absolute = urljoin(base_url, href)
        a.append(NavigableString(f" ({absolute})"))
    text = soup.get_text(separator=" ", strip=True)
    return re.sub(r"\s+", " ", text)[:MAX_PAGE_CHARS]


def _find_secondary_url(soup: BeautifulSoup, base_url: str, already_fetched: str) -> str | None:
    """Look for a same-domain nav link whose text or href suggests events/
    join/recruit/apply/contact info, and return its absolute URL (or None).

    Restricted to the same domain as base_url so a stray keyword match (e.g.
    a "Contact" link that happens to point at someone's LinkedIn profile)
    can't send the second fetch off-site - see the Blockchain at Cornell
    case in qa/research_agent_review.md.
    """
    base_domain = urlparse(base_url).netloc
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        haystack = f"{a.get_text(strip=True)} {href}".lower()
        if not any(keyword in haystack for keyword in SECONDARY_LINK_KEYWORDS):
            continue
        absolute = urljoin(base_url, href)
        if urlparse(absolute).netloc != base_domain:
            continue
        if absolute != already_fetched:
            return absolute
    return None


def research_club(website_url: str) -> dict:
    """Research one club's website. Returns a dict with website_url,
    application_deadline, next_meeting, info_session, coffee_chat_link, and
    not_found (true iff every field above is null). Never raises - any
    failure (unreachable site, bad API response) comes back as not_found
    with an "error" key describing what went wrong.
    """
    soup = _fetch(website_url)
    if soup is None:
        return _empty_result(website_url, error=f"Could not fetch {website_url}")

    pages_checked = [website_url]
    texts = [_page_text(soup, website_url)]

    if MAX_PAGES > 1:
        secondary_url = _find_secondary_url(soup, website_url, website_url)
        if secondary_url:
            secondary_soup = _fetch(secondary_url)
            if secondary_soup is not None:
                pages_checked.append(secondary_url)
                texts.append(_page_text(secondary_soup, secondary_url))

    combined_text = "\n\n".join(
        f"--- Page: {url} ---\n{text}" for url, text in zip(pages_checked, texts)
    )

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
    not_found = all(v is None for v in fields.values())

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

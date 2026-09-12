"""Query expansion for Browse Clubs' "search by meaning" AI search box.

matching.match_clubs()'s local sentence-transformers embedding search is
good at genuinely semantic queries ("computer science clubs") but not at
bare abbreviations - "cs" alone token-overlaps with things like "Club
Sports" rather than embedding anywhere near "computer science".
Confirmed empirically: match_clubs("find my cs clubs") never surfaces
Association of Computer Science Undergraduates in its top 10, but
match_clubs() on an expanded phrase like "computer science clubs, coding
and software development organizations" puts it at the top (93%).

expand_search_query() is a single quick Claude call that rewrites a
short/abbreviated query into a clearer phrase before it's embedded -
same conventions as this codebase's other small Claude-calling services
(chat_profile.py, resume_parser.py): own client singleton, strict
system prompt, never raises. On any failure it falls back to the
original raw query, so a transient API problem degrades to today's
plain embedding search rather than breaking AI search entirely.
"""

from __future__ import annotations

import anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL = "claude-sonnet-5"

SYSTEM_PROMPT = """You are turning a short, possibly abbreviated club-search query from
a Cornell student into a clearer phrase for semantic search over a directory of
student club names and descriptions. Expand any abbreviations (e.g. "cs" -> "computer
science", "econ" -> "economics", "ee" -> "electrical engineering") and, if helpful,
add a couple of closely related terms - but stay faithful to the original intent, do
not invent unrelated topics or specific club names.

Return ONLY the rewritten search phrase as plain text, one line, no quotes, no
markdown, no explanation.
"""

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def expand_search_query(query: str) -> str:
    """Returns an expanded/clarified version of `query` for embedding, or
    `query` unchanged if the expansion call fails for any reason."""
    query = (query or "").strip()
    if not query:
        return query

    try:
        response = _get_client().messages.create(
            model=MODEL,
            max_tokens=100,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": query}],
        )
    except anthropic.APIError:
        return query

    if response.stop_reason == "max_tokens":
        return query

    expanded = next((block.text for block in response.content if block.type == "text"), "")
    expanded = expanded.strip()
    return expanded or query


if __name__ == "__main__":
    for sample in ["find my cs clubs", "econ clubs", "ee stuff", "clubs for people who like poli sci"]:
        print(f"{sample!r} -> {expand_search_query(sample)!r}")

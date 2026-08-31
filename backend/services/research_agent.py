"""Fetch a club's website and extract application deadlines, meetings, info
sessions, and coffee-chat links.

Hard constraint (CLAUDE.md): never guess or infer a date, time, or link that is
not actually stated on the page. Anything not found is null, and a result with
nothing found reports not_found alongside the original website_url.

TODO: BUILD_PROMPTS.md Step 4 — not implemented yet.
"""

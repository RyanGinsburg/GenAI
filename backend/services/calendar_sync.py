"""Google Calendar OAuth2 (installed-app flow) and event creation.

Hard constraint (CLAUDE.md): nothing reaches the user's calendar without an
explicit confirmation step in the UI first. This module creates events it is
handed; it does not decide what to add.

TODO: BUILD_PROMPTS.md Step 7 — not implemented yet.
"""

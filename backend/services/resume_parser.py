"""Parse a resume PDF into a structured student profile.

Extracts text with pypdf, then calls the Claude API (claude-sonnet-5, per
CLAUDE.md's "claude-sonnet for extraction/reasoning tasks") to pull out:
major, graduation year, skills, interests, and any clubs/orgs already
mentioned - as strict JSON.

Nothing here is guessed: the model is instructed to use null/empty rather
than infer, and any failure (unreadable PDF, no extractable text, a bad API
response) returns {"error": "..."} instead of raising, so callers can show
the student a clear message instead of crashing.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from pypdf import PdfReader

load_dotenv()

MODEL = "claude-sonnet-5"

_client = None  # lazy singleton, so importing this module doesn't require an API key


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
    return _client


SYSTEM_PROMPT = """You extract structured information from a college student's resume text.

Return ONLY a single JSON object (no markdown fences, no commentary) with exactly these keys:
- "major": string or null - the student's declared major(s)/field of study, if stated
- "graduation_year": integer or null - expected graduation year, if stated
- "skills": array of strings - technical or professional skills explicitly listed on the resume
- "interests": array of strings - interests/hobbies explicitly stated on the resume (do not infer these from skills, coursework, or work experience)
- "clubs_mentioned": array of strings - names of clubs, organizations, or student groups already mentioned on the resume
- "suggested_club_interests": array of 3-8 short phrases describing the kinds of clubs/professional communities this student would likely want to join - e.g. "artificial intelligence", "quantitative finance", "cybersecurity". This is the one field where you should reason over the whole resume (major, coursework, projects, skills, work/research experience) rather than only quoting explicit statements - but stay grounded in what's actually on the resume, don't speculate about areas with no supporting evidence.

Rules:
- Every field except "suggested_club_interests" must only contain what is explicitly stated in the text. Do not guess, infer, or fabricate those.
- If a field isn't present in the text, use null (for major/graduation_year) or an empty array (for the list fields).
- Output must be valid JSON and nothing else.
"""


def extract_text(pdf_path: str) -> str:
    """Extract all text from a PDF. Returns "" if nothing could be extracted
    (e.g. a scanned image with no text layer)."""
    reader = PdfReader(pdf_path)
    pages_text = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages_text).strip()


def _strip_code_fences(text: str) -> str:
    """Models occasionally wrap JSON in ```json ... ``` despite instructions
    not to; strip that before parsing."""
    text = text.strip()
    match = re.match(r"^```(?:json)?\s*\n(.*)\n```$", text, re.DOTALL)
    return match.group(1).strip() if match else text


def parse_resume(pdf_path: str) -> dict:
    """Parse a resume PDF into a structured profile: major, graduation_year,
    skills, interests, clubs_mentioned.

    On any failure, returns {"error": "<message>"} instead of raising -
    callers should check for the "error" key before using the rest of the
    result.
    """
    path = Path(pdf_path)
    if not path.exists():
        return {"error": f"File not found: {pdf_path}"}

    try:
        text = extract_text(pdf_path)
    except Exception as e:
        return {"error": f"Could not read PDF: {e}"}

    if not text:
        return {
            "error": "No extractable text found in this PDF. It may be a "
            "scanned image without an OCR text layer."
        }

    try:
        response = _get_client().messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": text}],
        )
    except anthropic.AuthenticationError:
        return {"error": "Invalid or missing ANTHROPIC_API_KEY."}
    except anthropic.PermissionDeniedError:
        return {"error": "API key lacks permission for this request."}
    except anthropic.RateLimitError:
        return {"error": "Rate limited by the Claude API. Try again shortly."}
    except anthropic.APIStatusError as e:
        return {"error": f"Claude API error ({e.status_code}): {e.message}"}
    except anthropic.APIConnectionError:
        return {"error": "Network error connecting to the Claude API."}

    response_text = next(
        (block.text for block in response.content if block.type == "text"), ""
    )

    if response.stop_reason == "max_tokens":
        return {"error": "Model response was cut off (hit max_tokens) before finishing the JSON."}

    try:
        profile = json.loads(_strip_code_fences(response_text))
    except json.JSONDecodeError:
        return {"error": f"Model did not return valid JSON: {response_text[:300]!r}"}

    return profile


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m backend.services.resume_parser <path_to_resume.pdf>")
        sys.exit(1)

    result = parse_resume(sys.argv[1])
    print(json.dumps(result, indent=2))

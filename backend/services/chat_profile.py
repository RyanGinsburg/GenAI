"""A short, multi-turn conversational interview that builds a student's
club-interest profile, replacing the old one-shot "type a query" search.

Stateless: the frontend resends the full conversation history every turn
(no server-side session). Same conventions as resume_parser.py and
research_agent.py - a strict "return ONLY JSON" system prompt, its own
Claude client/model constant, the same anthropic exception handling, and
the same code-fence-stripping regex - a small deliberate duplication
rather than a shared import, consistent with how research_agent.py
already keeps its own copy rather than reusing resume_parser.py's.

The assistant never names or recommends specific clubs itself - that's
matching.match_clubs_for_profile()'s job once this interview is done.
"""

from __future__ import annotations

import json
import re

import anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL = "claude-sonnet-5"
MAX_QUESTIONS = 5

SYSTEM_PROMPT = """You are conducting a short, friendly interview to help a Cornell
student figure out what clubs they might want to join. You are NOT recommending or
naming any specific clubs yourself - a separate matching step handles that after
this interview ends. Just get to know the student.

Ask about things like: what fields/topics they're interested in, whether they want
professional/career-focused clubs, purely social or fun clubs, or a mix of both, and
how much time they'd want to commit. Keep questions short, warm, and one at a time -
don't interrogate. If a resume summary is provided below, don't re-ask for things it
already answers; use it as context and ask about what it leaves open (e.g. professional
vs. social preference, since a resume doesn't usually say that).

Return ONLY a single JSON object (no markdown fences, no commentary) with exactly
these keys:
- "reply": string - your next message to the student (a question, or a short warm
  closing line once ready_for_matching is true).
- "ready_for_matching": boolean - true once you have enough to build a profile.
- "profile": null while ready_for_matching is false. Once true, an object with:
    - "interests": array of 3-8 short phrases (e.g. "quantitative finance", "robotics",
      "a cappella singing") grounded in what the student actually said (or their resume).
    - "mode": one of "professional", "social", "both" - which kinds of clubs they want.
    - "time_commitment": one of "low", "medium", "high", or null if not discussed.
    - "notes": a short string with anything else worth passing along, or null.

Rules:
- Never fabricate an interest, mode, or time commitment not actually expressed or
  reasonably grounded in what the student (or their resume) said.
- Do not use em dashes anywhere in "reply". Use periods or commas instead.
- Ask at most 5 questions total, then set ready_for_matching to true even if you'd
  like more detail - a rough profile beats an endless interview.
- Output must be valid JSON and nothing else.
"""

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    match = re.match(r"^```(?:json)?\s*\n(.*)\n```$", text, re.DOTALL)
    return match.group(1).strip() if match else text


def _resume_context(resume_profile: dict | None) -> str:
    if not resume_profile or "error" in resume_profile:
        return ""
    parts = []
    if resume_profile.get("major"):
        parts.append(f"Major: {resume_profile['major']}")
    if resume_profile.get("skills"):
        parts.append(f"Skills: {', '.join(resume_profile['skills'])}")
    if resume_profile.get("suggested_club_interests"):
        parts.append(f"Resume suggests interest in: {', '.join(resume_profile['suggested_club_interests'])}")
    if not parts:
        return ""
    return "\n\nThe student has attached a resume. Summary:\n" + "\n".join(parts)


def _safe_reply_error(message: str) -> dict:
    return {
        "reply": "Sorry, something went wrong on my end. Mind trying that again?",
        "ready_for_matching": False,
        "profile": None,
        "error": message,
    }


def continue_profile_chat(history: list[dict], resume_profile: dict | None = None) -> dict:
    """history: [{"role": "user"|"assistant", "content": str}, ...], must
    start with a user turn (the Claude API's requirement) and contain only
    real exchanged turns - a client-only greeting bubble shown before the
    student's first message should never be included here.

    Never raises. Returns {"reply": str, "ready_for_matching": bool,
    "profile": dict|None}, plus an "error" key (with a safe "reply") on
    any internal failure.
    """
    if not history:
        return _safe_reply_error("continue_profile_chat called with empty history")

    system = SYSTEM_PROMPT + _resume_context(resume_profile)

    try:
        response = _get_client().messages.create(
            model=MODEL,
            max_tokens=1024,
            system=system,
            messages=history,
        )
    except anthropic.AuthenticationError:
        return _safe_reply_error("Invalid or missing ANTHROPIC_API_KEY.")
    except anthropic.PermissionDeniedError:
        return _safe_reply_error("API key lacks permission for this request.")
    except anthropic.RateLimitError:
        return _safe_reply_error("Rate limited by the Claude API. Try again shortly.")
    except anthropic.APIStatusError as e:
        return _safe_reply_error(f"Claude API error ({e.status_code}): {e.message}")
    except anthropic.APIConnectionError:
        return _safe_reply_error("Network error connecting to the Claude API.")

    response_text = next((block.text for block in response.content if block.type == "text"), "")

    if response.stop_reason == "max_tokens":
        return _safe_reply_error("Model response was cut off (hit max_tokens).")

    try:
        parsed = json.loads(_strip_code_fences(response_text))
    except json.JSONDecodeError:
        return _safe_reply_error(f"Model did not return valid JSON: {response_text[:300]!r}")

    return {
        "reply": parsed.get("reply") or "",
        "ready_for_matching": bool(parsed.get("ready_for_matching")),
        "profile": parsed.get("profile"),
    }


if __name__ == "__main__":
    convo = [{"role": "user", "content": "hi, I want help finding a club"}]
    for _ in range(6):
        result = continue_profile_chat(convo)
        print("assistant:", result["reply"])
        if result.get("error"):
            print("ERROR:", result["error"])
            break
        if result["ready_for_matching"]:
            print("PROFILE:", json.dumps(result["profile"], indent=2))
            break
        convo.append({"role": "assistant", "content": result["reply"]})
        fake_user_reply = "I'm really into robotics and building things, and I'd like something professional, medium time commitment."
        print("user:", fake_user_reply)
        convo.append({"role": "user", "content": fake_user_reply})

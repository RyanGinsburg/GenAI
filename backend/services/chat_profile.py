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
matching.match_clubs_diversified()'s job once this interview is done.

The profile shape (school_or_college/major/vibe/activity_level/
specific_interests_in_mind/hobbies/openness_to_cultural_affinity_groups)
lives in profile_schema.py, the single source of truth shared with
matching.py and the routes. Readiness and merging are enforced in Python
(merge_profile/is_ready_for_matching) rather than left purely to the
model's own judgment, so "ask at most one question, two exchanges should
be the normal case" is an actual guarantee, not just a prompt hope.
"""

from __future__ import annotations

import json
import re

import anthropic
from dotenv import load_dotenv

from backend.services.profile_schema import is_ready_for_matching, merge_profile

load_dotenv()

MODEL = "claude-sonnet-5"
MAX_TURNS = 3  # hard backstop; two exchanges should be the NORMAL case

SYSTEM_PROMPT = """You are a warm, casual conversational assistant helping a Cornell
student figure out what clubs they might want to join. You are NOT recommending or
naming any specific clubs yourself - a separate matching step handles that once this
conversation has enough to go on. Just get to know the student, one natural question
at a time.

You are building a profile with these fields. Only ever report a field you can
confidently fill in or update based on the student's OWN words this turn (or their
resume, if a summary is given below) - never guess or fabricate a value.

- "school_or_college": string or null - e.g. "Engineering", "Arts and Sciences",
  "Dyson", "ILR".
- "major": string or null.
- "vibe": one of "social", "professional", "both", or null - purely fun/social
  clubs, career-focused/professional clubs, or a mix of both.
- "activity_level": one of "low", "medium", "high", or null - roughly how much time
  commitment they want (low = casual/occasional, high = active/intense).
- "specific_interests_in_mind": array of short phrases (e.g. "quantitative finance",
  "robotics", "a cappella") - specific club topics the student explicitly named.
- "hobbies": array of short phrases for things they enjoy doing, distinct from
  specific_interests_in_mind (broader personal interests like "hiking" or "cooking",
  not necessarily a club topic they named outright).
- "openness_to_cultural_affinity_groups": one of "yes", "open", "not_sure", or null.

About "openness_to_cultural_affinity_groups": at a natural point in the conversation,
offer this as a warm, low-pressure, OPEN INVITATION - something like asking whether
they'd like the results to include any cultural, identity-based, or affinity student
groups, so they have the option if it's relevant to them. NEVER ask the student to
state their own race, ethnicity, nationality, religion, gender, sexual orientation, or
any other personal characteristic - this is only ever about whether they're open to
SEEING that category of club, phrased so it's easy to say "not really my thing" or
skip past with no follow-up pressure. Ask about it at most once, briefly, and move on
regardless of their answer.

Return ONLY a single JSON object (no markdown fences, no commentary) with exactly
these keys:
- "reply": string - your next message. Ask AT MOST ONE question, phrased like a real
  conversation, never a list or a form. If you already have enough to move forward
  (see below), make this a short, warm line saying you'll go find some clubs instead.
- "ready_for_matching": boolean - your own judgment, with an explicitly LOW bar: as
  soon as you know their general vibe and at least one concrete thing to search on (a
  major, a named interest, or a hobby), that's enough - do not hold out for every
  field. Two total exchanges (one question, one answer) should be the NORMAL case,
  not three or more.
- "profile_delta": an object with ONLY the fields above that you can newly fill in or
  update this turn (plus anything the resume summary below answers, on the turn it
  first appears). Omit any key you have nothing new to say about - do not repeat
  values already established, and never null out a field previously set unless the
  student explicitly contradicts it. For "specific_interests_in_mind"/"hobbies", if
  you include the key at all, give the FULL updated list (previously known phrases
  plus any new ones), not just the newly mentioned ones.

Rules:
- Never fabricate a value not actually expressed or reasonably grounded in what the
  student (or their resume) said.
- Do not use em dashes anywhere in "reply". Use periods or commas instead.
- Output must be valid JSON and nothing else.
"""

SYSTEM_PROMPT_REFINE = """The student has already seen a set of matched clubs and is
sending a short follow-up asking to adjust results (e.g. "show me more social ones",
"something with less time commitment", "less finance-heavy"). You are NOT
recommending or naming clubs - a separate matching step re-runs after you update the
profile.

You'll be given the student's CURRENT profile as JSON, then their follow-up message.
Return ONLY a JSON object with exactly:
- "reply": a short, warm one-line acknowledgment (e.g. "Got it, more social ones
  coming up."). No em dashes.
- "profile_delta": an object with ONLY the fields that should change, using the same
  field names/values as before. Examples: "show me more social ones" ->
  {"vibe": "social"}; "something with less time commitment" ->
  {"activity_level": "low"}. For list fields, give the FULL updated list if you
  include the key. Never fabricate a value not grounded in the message. Omit
  untouched fields.
Output must be valid JSON and nothing else.
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
    if resume_profile.get("school_or_college"):
        parts.append(f"School/college: {resume_profile['school_or_college']}")
    if resume_profile.get("skills"):
        parts.append(f"Skills: {', '.join(resume_profile['skills'])}")
    if resume_profile.get("suggested_club_interests"):
        parts.append(f"Resume suggests interest in: {', '.join(resume_profile['suggested_club_interests'])}")
    if not parts:
        return ""
    return "\n\nThe student has attached a resume. Summary:\n" + "\n".join(parts)


def _profile_context(profile: dict | None) -> str:
    if not profile:
        return ""
    return (
        "\n\nProfile established so far (do not repeat or re-ask about these "
        "unless the student contradicts them):\n" + json.dumps(profile)
    )


def _safe_reply_error(message: str, profile: dict | None = None) -> dict:
    return {
        "reply": "Sorry, something went wrong on my end. Mind trying that again?",
        "ready_for_matching": False,
        "profile": profile or {},
        "error": message,
    }


def continue_profile_chat(
    history: list[dict], profile: dict | None = None, resume_profile: dict | None = None
) -> dict:
    """history: [{"role": "user"|"assistant", "content": str}, ...], must
    start with a user turn (the Claude API's requirement) and contain only
    real exchanged turns - a client-only greeting bubble shown before the
    student's first message should never be included here. profile is the
    running StudentProfile dict built up so far (empty/None on turn one).

    Never raises. Returns {"reply": str, "ready_for_matching": bool,
    "profile": dict} (the merged profile, always populated - not just at
    readiness), plus an "error" key (with a safe "reply") on any internal
    failure.
    """
    if not history:
        return _safe_reply_error("continue_profile_chat called with empty history", profile)

    system = SYSTEM_PROMPT + _resume_context(resume_profile) + _profile_context(profile)

    try:
        response = _get_client().messages.create(
            model=MODEL,
            max_tokens=1024,
            system=system,
            messages=history,
        )
    except anthropic.AuthenticationError:
        return _safe_reply_error("Invalid or missing ANTHROPIC_API_KEY.", profile)
    except anthropic.PermissionDeniedError:
        return _safe_reply_error("API key lacks permission for this request.", profile)
    except anthropic.RateLimitError:
        return _safe_reply_error("Rate limited by the Claude API. Try again shortly.", profile)
    except anthropic.APIStatusError as e:
        return _safe_reply_error(f"Claude API error ({e.status_code}): {e.message}", profile)
    except anthropic.APIConnectionError:
        return _safe_reply_error("Network error connecting to the Claude API.", profile)

    response_text = next((block.text for block in response.content if block.type == "text"), "")

    if response.stop_reason == "max_tokens":
        return _safe_reply_error("Model response was cut off (hit max_tokens).", profile)

    try:
        parsed = json.loads(_strip_code_fences(response_text))
    except json.JSONDecodeError:
        return _safe_reply_error(f"Model did not return valid JSON: {response_text[:300]!r}", profile)

    merged = merge_profile(profile, parsed.get("profile_delta") or {})
    user_turns = sum(1 for turn in history if turn.get("role") == "user")
    ready = bool(parsed.get("ready_for_matching")) or is_ready_for_matching(merged)
    if user_turns >= MAX_TURNS:
        ready = True

    reply = parsed.get("reply") or ""
    if ready and not parsed.get("ready_for_matching"):
        # The deterministic backstop forced readiness ahead of the model's
        # own call - swap in a short canned closing line so a question
        # doesn't get shown right before we jump to results.
        reply = "Great, that's plenty to go on. Let me find some clubs for you."

    return {"reply": reply, "ready_for_matching": ready, "profile": merged}


def refine_profile(profile: dict, message: str) -> dict:
    """Turns a post-results follow-up ("show me more social ones") into an
    updated profile. Single-turn (no history) - cheaper than a full
    continue_profile_chat round trip. Never raises; same error-handling
    pattern as continue_profile_chat, returning the profile unchanged on
    failure so the caller can keep showing the prior results."""
    system = SYSTEM_PROMPT_REFINE + "\n\nCurrent profile:\n" + json.dumps(profile or {})

    try:
        response = _get_client().messages.create(
            model=MODEL,
            max_tokens=512,
            system=system,
            messages=[{"role": "user", "content": message}],
        )
    except anthropic.AuthenticationError:
        return {"reply": "Sorry, something went wrong.", "profile": profile, "error": "Invalid or missing ANTHROPIC_API_KEY."}
    except anthropic.PermissionDeniedError:
        return {"reply": "Sorry, something went wrong.", "profile": profile, "error": "API key lacks permission for this request."}
    except anthropic.RateLimitError:
        return {"reply": "Sorry, something went wrong.", "profile": profile, "error": "Rate limited by the Claude API. Try again shortly."}
    except anthropic.APIStatusError as e:
        return {"reply": "Sorry, something went wrong.", "profile": profile, "error": f"Claude API error ({e.status_code}): {e.message}"}
    except anthropic.APIConnectionError:
        return {"reply": "Sorry, something went wrong.", "profile": profile, "error": "Network error connecting to the Claude API."}

    response_text = next((block.text for block in response.content if block.type == "text"), "")

    if response.stop_reason == "max_tokens":
        return {"reply": "Sorry, something went wrong.", "profile": profile, "error": "Model response was cut off (hit max_tokens)."}

    try:
        parsed = json.loads(_strip_code_fences(response_text))
    except json.JSONDecodeError:
        return {"reply": "Sorry, something went wrong.", "profile": profile, "error": f"Model did not return valid JSON: {response_text[:300]!r}"}

    merged = merge_profile(profile, parsed.get("profile_delta") or {})
    return {"reply": parsed.get("reply") or "", "profile": merged}


if __name__ == "__main__":
    convo = [{"role": "user", "content": "hi, I want help finding a club"}]
    running_profile: dict = {}
    for _ in range(6):
        result = continue_profile_chat(convo, profile=running_profile)
        print("assistant:", result["reply"])
        if result.get("error"):
            print("ERROR:", result["error"])
            break
        running_profile = result["profile"]
        if result["ready_for_matching"]:
            print("PROFILE:", json.dumps(running_profile, indent=2))
            break
        convo.append({"role": "assistant", "content": result["reply"]})
        fake_user_reply = "I'm really into robotics and building things, and I'd like something professional, medium time commitment."
        print("user:", fake_user_reply)
        convo.append({"role": "user", "content": fake_user_reply})

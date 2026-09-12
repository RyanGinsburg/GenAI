"""A short, multi-turn conversational interview that builds a student's
club-interest profile, replacing the old one-shot "type a query" search.

Stateless: the frontend resends the full conversation history every turn
(no server-side session). Same conventions as resume_parser.py/
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
matching.py and the routes.

Each turn is up to TWO sequential Claude calls, not one - a deliberate
split fixing a real bug: a single call that plays interviewer, extractor,
AND judge of its own readiness all at once is biased toward declaring
itself "ready" quickly (grading its own homework), which was cutting
real conversations off after as little as two exchanges.

- _judge_and_extract() (Call 1, always made): a strict evaluator, not a
  friendly voice. Extracts profile_delta from the student's latest
  message, then judges - after that delta is conceptually merged -
  whether the profile has genuine, SPECIFIC substance yet (not just
  technically-non-null fields), and if not, names one concrete gap for
  the next question to target.
- _ask_next_question() (Call 2, only made when not yet ready): the warm,
  casual voice, now with exactly one job - phrase ONE natural question
  targeting the judge's identified gap. It doesn't extract fields or
  judge readiness itself, so "ask at most one question" is enforced by
  construction (this call's JSON contract has nothing else in it), not
  just by prompt instruction.

Readiness = the deterministic profile_schema.is_ready_for_matching()
floor AND the judge's own "sufficient" verdict, OR'd with a MAX_TURNS
hard backstop - the floor stays a cheap sanity minimum (never ready
before it), the judge is the qualitative authority on top of it.
"""

from __future__ import annotations

import json
import re

import anthropic
from dotenv import load_dotenv

from backend.services.profile_schema import is_ready_for_matching, merge_profile

load_dotenv()

MODEL = "claude-sonnet-5"
MAX_TURNS = 7  # hard backstop; the judge decides when to stop well before this in the normal case

SYSTEM_PROMPT_JUDGE = """You are a strict, critical evaluator reviewing one turn of an
interview that builds a Cornell student's club-interest profile. You are NOT the
conversational voice the student sees - a separate step handles phrasing the next
question. Your only job is to (1) extract any new profile information from the
student's latest message, and (2) judge, harshly, whether the profile now has enough
SPECIFIC substance to produce genuinely good club matches.

The profile fields:
- "school_or_college": string or null - e.g. "Engineering", "Arts and Sciences",
  "Dyson", "ILR".
- "major": string or null.
- "vibe": one of "social", "professional", "both", or null.
- "activity_level": one of "low", "medium", "high", or null.
- "specific_interests_in_mind": array of short phrases - specific club topics the
  student explicitly named.
- "hobbies": array of short phrases for things they enjoy doing, distinct from
  specific_interests_in_mind (broader personal interests, not necessarily a club
  topic they named outright).
- "openness_to_cultural_affinity_groups": one of "yes", "open", "not_sure", or null.

You will be given the full conversation so far (and a resume summary, if one is
attached) plus the profile established before this turn. Extract "profile_delta":
ONLY fields you can newly fill in or update from the student's OWN words this turn
(or the resume, the first turn it's relevant) - never guess or fabricate. For list
fields, if you include the key at all, give the FULL updated list (previous items
plus any new ones), not just what's new this turn. Omit any key you have nothing new
to say about, and never null out a previously set field unless the student explicitly
contradicts it.

Then, judging the profile AFTER your delta is conceptually merged in, decide
"sufficient": true only if it has real, specific substance to match well on - not
just technically-filled fields. Be skeptical of single generic words ("music",
"sports", "business") with no elaboration; these are weak. Look for concrete
specifics: a named activity, a bit of a story, a specific club topic, a real level of
detail. A profile with a clear vibe, an activity level, and at least one genuinely
specific interest or hobby (described with enough detail that a real club could
actually be matched to it, not just a one-word category) is sufficient. A profile
that is only vague or generic on every topic mentioned is NOT sufficient even if every
field is technically non-null.

Exception: "openness_to_cultural_affinity_groups" is always optional context, never a
requirement - it being null or "not_sure" must NEVER by itself make "sufficient"
false. You may still name it as "next_focus" as a one-time nice-to-have once
everything else is already strong, but "sufficient" may be true even if it was never
brought up at all.

If not sufficient, set "next_focus" to ONE specific, concrete gap for the next
question to target - be precise and actionable, e.g. "hobbies only has the single
generic word 'music' - ask what kind of music or what they actually do with it (play
an instrument, go to shows, DJ, etc.)" or "vibe is 'both' but no professional-side
interest has been named at all yet". If sufficient, set "next_focus" to null.

Return ONLY a single JSON object (no markdown fences, no commentary) with exactly
these keys:
- "profile_delta": object, as described above.
- "sufficient": boolean.
- "next_focus": string or null.
- "reasoning": a one-sentence internal note on why (never shown to the student).

Rules:
- Never fabricate a value not actually expressed or reasonably grounded in what the
  student (or their resume) said.
- Output must be valid JSON and nothing else.
"""

SYSTEM_PROMPT_ASK = """You are a warm, casual conversational assistant helping a
Cornell student figure out what clubs they might want to join. You are NOT
recommending or naming any specific clubs yourself - a separate matching step handles
that once this conversation has enough to go on. You do not need to extract or track
profile fields, and you do not decide when the conversation is done - another step
already decided it should continue, and told you exactly what gap to close next.
Your only job is to turn that gap into ONE natural, warm question.

The gap to focus this question on is given below as the "next_focus" context. Ask
about it in a way that feels like a real conversation, not a form or checklist - use
the conversation history for tone and to build on what they already said, and don't
just repeat next_focus's wording verbatim back at them. Ask AT MOST ONE question,
never a list.

Special case: if next_focus is about inviting openness to cultural/affinity groups,
phrase it as a warm, low-pressure, OPEN INVITATION - something like asking whether
they'd like results to include any cultural, identity-based, or affinity student
groups, so they have the option if it's relevant to them. NEVER ask the student to
state their own race, ethnicity, nationality, religion, gender, sexual orientation, or
any other personal characteristic - this is only ever about whether they're open to
SEEING that category of club. You may optionally add that they're welcome to share a
bit about their background if they want more specific pointers, but make clear it's
totally fine to skip. Ask about this at most once, briefly, regardless of history.

Respond with ONLY your next message to the student - the question itself, and nothing
else. No JSON, no quotation marks around it, no preface like "Sure, here's a
question:", no commentary - just the message exactly as it should appear in the chat.

Rules:
- Never fabricate or assume anything about the student not already established.
- Do not use em dashes anywhere in your reply. Use periods or commas instead.
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


def _focus_context(next_focus: str | None) -> str:
    if not next_focus:
        return ""
    return "\n\nThe gap to focus this question on: " + next_focus


def _safe_reply_error(message: str, profile: dict | None = None) -> dict:
    return {
        "reply": "Sorry, something went wrong on my end. Mind trying that again?",
        "ready_for_matching": False,
        "profile": profile or {},
        "error": message,
    }


def _call_claude(system: str, messages: list[dict], max_tokens: int) -> tuple[str | None, str | None]:
    """Calls Claude and returns (response_text, None) on success, or
    (None, error_message) on any failure - never raises. The one shared
    exception-handling path for every Claude call in this module."""
    try:
        response = _get_client().messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        )
    except anthropic.AuthenticationError:
        return None, "Invalid or missing ANTHROPIC_API_KEY."
    except anthropic.PermissionDeniedError:
        return None, "API key lacks permission for this request."
    except anthropic.RateLimitError:
        return None, "Rate limited by the Claude API. Try again shortly."
    except anthropic.APIStatusError as e:
        return None, f"Claude API error ({e.status_code}): {e.message}"
    except anthropic.APIConnectionError:
        return None, "Network error connecting to the Claude API."

    if response.stop_reason == "max_tokens":
        return None, "Model response was cut off (hit max_tokens)."

    text = next((block.text for block in response.content if block.type == "text"), "")
    return text, None


def _call_claude_json(system: str, messages: list[dict], max_tokens: int) -> tuple[dict | None, str | None]:
    """Calls Claude with a "return ONLY JSON" system prompt and parses the
    result. Returns (parsed_dict, None) on success, or (None, error_message)
    on any failure. Shared by _judge_and_extract and refine_profile - both
    return several structured fields, so a JSON contract is worth the
    parsing risk. _ask_next_question deliberately does NOT use this - it
    only ever returns one free-text field, and empirically the model
    doesn't reliably wrap a single natural-language reply in JSON even
    when told to, so it uses _call_claude's raw text directly instead."""
    text, error = _call_claude(system, messages, max_tokens)
    if error:
        return None, error
    try:
        return json.loads(_strip_code_fences(text)), None
    except json.JSONDecodeError:
        return None, f"Model did not return valid JSON: {text[:300]!r}"


def _judge_and_extract(history: list[dict], profile: dict | None, resume_profile: dict | None) -> dict:
    """Call 1, always made. Returns {"profile_delta", "sufficient",
    "next_focus", "reasoning"} on success, or {"error": str} on failure."""
    system = SYSTEM_PROMPT_JUDGE + _resume_context(resume_profile) + _profile_context(profile)
    parsed, error = _call_claude_json(system, history, max_tokens=768)
    if error:
        return {"error": error}
    return parsed


def _ask_next_question(
    history: list[dict], profile: dict, next_focus: str | None, resume_profile: dict | None
) -> dict:
    """Call 2, only made when the judge says the profile isn't sufficient
    yet. Returns {"reply": str} on success, or {"error": str} on failure.
    Plain text, not JSON - see _call_claude_json's docstring for why."""
    system = (
        SYSTEM_PROMPT_ASK
        + _resume_context(resume_profile)
        + _profile_context(profile)
        + _focus_context(next_focus)
    )
    text, error = _call_claude(system, history, max_tokens=512)
    if error:
        return {"error": error}
    return {"reply": (text or "").strip()}


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

    judge = _judge_and_extract(history, profile, resume_profile)
    if judge.get("error"):
        return _safe_reply_error(judge["error"], profile)

    merged = merge_profile(profile, judge.get("profile_delta") or {})
    user_turns = sum(1 for turn in history if turn.get("role") == "user")
    ready = is_ready_for_matching(merged) and bool(judge.get("sufficient"))
    if user_turns >= MAX_TURNS:
        ready = True

    if ready:
        return {
            "reply": "Great, that's plenty to go on. Let me find some clubs for you.",
            "ready_for_matching": True,
            "profile": merged,
        }

    # Not ready - Call 2 phrases the actual question, targeting the
    # judge's identified gap. If it fails, still return the merged
    # profile (not the original) so this turn's extraction isn't lost.
    ask = _ask_next_question(history, merged, judge.get("next_focus"), resume_profile)
    if ask.get("error"):
        return _safe_reply_error(ask["error"], merged)

    return {"reply": ask.get("reply") or "", "ready_for_matching": False, "profile": merged}


def refine_profile(profile: dict, message: str) -> dict:
    """Turns a post-results follow-up ("show me more social ones") into an
    updated profile. Single-turn (no history) - cheaper than a full
    continue_profile_chat round trip. Never raises; returns the profile
    unchanged on failure so the caller can keep showing the prior
    results."""
    system = SYSTEM_PROMPT_REFINE + "\n\nCurrent profile:\n" + json.dumps(profile or {})
    parsed, error = _call_claude_json(system, [{"role": "user", "content": message}], max_tokens=512)
    if error:
        return {"reply": "Sorry, something went wrong.", "profile": profile, "error": error}

    merged = merge_profile(profile, parsed.get("profile_delta") or {})
    return {"reply": parsed.get("reply") or "", "profile": merged}


if __name__ == "__main__":
    convo = [{"role": "user", "content": "hi, I want help finding a club"}]
    running_profile: dict = {}
    for _ in range(9):
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

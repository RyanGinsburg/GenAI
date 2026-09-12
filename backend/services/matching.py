"""Match a student's profile to clubs: embedding search over
data/clubs_filtered.json, then re-ranking.

Embeddings are cached to data/embeddings.npy so they aren't regenerated per run.

Uses a local sentence-transformers model (all-MiniLM-L6-v2) — no API key
needed, runs on CPU, fast enough for ~1500 clubs. If we ever need a bigger
model or hosted embeddings, swap _embed_texts()/_get_model() only; the
caching and match_clubs() interface stay the same.

Uses the filtered 877-club set (scraper/filter_clubs.py), not the full
1521-club data/clubs.json — the excluded ~640 are grad orgs, academic
departments, housing, and social Greek life, none of which are what an
undergrad asking "what club should I join" wants matched. See
filter_clubs.py's module docstring for the exact rules. Regenerate
data/clubs_filtered.json (via `python scraper/filter_clubs.py`) after any
change to data/clubs.json; the embeddings cache below auto-invalidates
when the source text changes.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import numpy as np

from backend.services.categorize import categorize_club

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
CLUBS_PATH = DATA_DIR / "clubs_filtered.json"
EMBEDDINGS_PATH = DATA_DIR / "embeddings.npy"
EMBEDDINGS_META_PATH = DATA_DIR / "embeddings_meta.json"

MODEL_NAME = "all-MiniLM-L6-v2"

_model = None  # lazy-loaded singleton, so importing this module doesn't load a model


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(MODEL_NAME)
    return _model


def load_clubs() -> list[dict]:
    """Load the filtered, undergrad-facing club directory."""
    with open(CLUBS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _club_text(club: dict) -> str:
    """Combine a club's name, description, and category into one string to embed."""
    parts = [
        club.get("name") or "",
        club.get("description") or "",
        club.get("category") or "",
    ]
    return " | ".join(p.strip() for p in parts if p and p.strip())


def _texts_hash(texts: list[str]) -> str:
    """Fingerprint the club texts so a stale cache (clubs.json changed, model
    changed) is detected and rebuilt instead of silently reused."""
    h = hashlib.sha256()
    h.update(MODEL_NAME.encode("utf-8"))
    for t in texts:
        h.update(b"\x00")
        h.update(t.encode("utf-8"))
    return h.hexdigest()


_WORD_RE = re.compile(r"[a-z0-9]+")

KEYWORD_BONUS = 0.35
KEYWORD_BONUS_CAP = 1.3


def _normalize_words(text: str) -> set[str]:
    """Lowercased, punctuation-stripped token set with a light manual
    ing/s-stripping (no stemming library) so "skiing"/"ski" or
    "clubs"/"club" share a root. Deliberately simple/deterministic - the
    length guards avoid mangling short words (e.g. "gaming" -> "gam")."""
    words: set[str] = set()
    for w in _WORD_RE.findall((text or "").lower()):
        words.add(w)
        if w.endswith("ing") and len(w) > 5:
            words.add(w[:-3])
        elif w.endswith("s") and len(w) > 3:
            words.add(w[:-1])
    return words


def _keyword_bonus(interest: str, club_words: set[str]) -> float:
    """A direct lexical hit (e.g. hobby "skiing" against a club named "Ski
    and Snowboard Club") should count for more than pure embedding
    similarity gives it credit for - see match_clubs_multi_query()."""
    return KEYWORD_BONUS if _normalize_words(interest) & club_words else 0.0


def _score_to_match_percent(score: float) -> int:
    """Rescales the internal combined score (raw cosine ~0.3-0.6 for a
    genuinely strong match per this module's own history, up to
    KEYWORD_BONUS_CAP with a keyword-bonus hit) onto an intuitive 0-100
    display percentage. Purely cosmetic - ranking/quota logic always uses
    the raw combined score, never this rescaled value. Piecewise-linear
    between a noise floor and a "clearly great" ceiling; floor/ceiling are
    a starting point tuned against known-good query/club pairs (ski,
    spikeball), not derived from any ground truth beyond that."""
    floor, ceiling = 0.15, 0.65
    pct = (max(min(score, ceiling), floor) - floor) / (ceiling - floor)
    return int(round(10 + pct * 87))  # floor -> 10%, ceiling -> 97%


def _embed_texts(texts: list[str]) -> np.ndarray:
    model = _get_model()
    embeddings = model.encode(
        texts,
        batch_size=64,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,  # so cosine similarity == dot product
    )
    return embeddings.astype(np.float32)


def get_club_embeddings(clubs: list[dict]) -> np.ndarray:
    """Return embeddings for `clubs`, using the on-disk cache when it's still
    valid (same clubs, same model) and regenerating + saving it otherwise."""
    texts = [_club_text(c) for c in clubs]
    current_hash = _texts_hash(texts)

    if EMBEDDINGS_PATH.exists() and EMBEDDINGS_META_PATH.exists():
        with open(EMBEDDINGS_META_PATH, "r", encoding="utf-8") as f:
            meta = json.load(f)
        if meta.get("hash") == current_hash:
            embeddings = np.load(EMBEDDINGS_PATH)
            if embeddings.shape[0] == len(clubs):
                return embeddings
        # Cache is stale (clubs.json or model changed) — fall through and rebuild.

    print(f"Generating embeddings for {len(clubs)} clubs with {MODEL_NAME}...")
    embeddings = _embed_texts(texts)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    np.save(EMBEDDINGS_PATH, embeddings)
    with open(EMBEDDINGS_META_PATH, "w", encoding="utf-8") as f:
        json.dump({"hash": current_hash, "model": MODEL_NAME, "count": len(clubs)}, f)

    return embeddings


def match_clubs(query: str, top_k: int = 10) -> list[dict]:
    """Embed `query` and return the top_k most similar clubs by cosine
    similarity. Each result is the club dict plus a "score" field.

    Kept as-is for single-topic queries (e.g. browse/search). For a list of
    several distinct interests, use match_clubs_multi_query() instead - see
    its docstring for why a single blended query is the wrong tool there."""
    clubs = load_clubs()
    embeddings = get_club_embeddings(clubs)

    query_embedding = _embed_texts([query])[0]  # already normalized
    scores = embeddings @ query_embedding  # cosine similarity (both are unit vectors)

    top_k = min(top_k, len(clubs))
    top_indices = np.argsort(-scores)[:top_k]

    results = []
    for i in top_indices:
        club = dict(clubs[i])
        score = float(scores[i])
        club["score"] = score
        club["match_percent"] = _score_to_match_percent(score)
        results.append(club)
    return results


def match_clubs_multi_query(
    interests: list[str], top_k_total: int = 30, top_k_per_interest: int = 8
) -> list[dict]:
    """Fixes a real bug: joining several distinct interests into one string
    and embedding it as a single vector produces a blended embedding that
    drifts toward whichever topic dominates the phrase list, silently
    drowning out minority topics. Confirmed live: a resume-derived query of
    7 interests (5 finance-ish, 2 not) returned zero of the 36 "Project
    Team"-tagged clubs in data/clubs_filtered.json, even though a
    single-topic robotics query surfaces Project Team clubs fine
    (0.45-0.46 cosine similarity).

    Fix: embed each interest separately, and pool the top_k_per_interest
    clubs PER INTEREST (not per blended score) into one candidate set
    before final sorting - so a club that's the best match for one
    minority topic still makes it in, rather than needing to also beat
    every candidate from the majority topic on one shared, averaged score.

    Each result carries "matched_interest": the interest phrase that
    produced its best score (useful for showing "why this was suggested").

    Ranking also folds in a keyword-overlap bonus (see _keyword_bonus()):
    a direct lexical hit between an interest phrase and a club's own
    name/description/category (e.g. hobby "spikeball" against a club
    whose description says "Spikeball") is rewarded on top of embedding
    similarity, not just cosmetically at display time - this is what
    makes an explicit, direct hobby match actually outrank a merely
    topically-adjacent one, addressing "explicit stated interests aren't
    weighted heavily enough" (short 1-2 word interest phrases vs. long
    multi-sentence club descriptions structurally cap cosine similarity
    around 0.3-0.6 even for a genuinely great match).
    """
    clubs = load_clubs()
    if not interests:
        return []

    embeddings = get_club_embeddings(clubs)
    interest_embeddings = _embed_texts(interests)  # (n_interests, dim), already normalized

    scores_by_interest = embeddings @ interest_embeddings.T  # (n_clubs, n_interests)
    club_words = [_normalize_words(_club_text(c)) for c in clubs]

    best_score: dict[int, float] = {}
    best_interest: dict[int, str] = {}

    for interest_idx, interest in enumerate(interests):
        interest_scores = scores_by_interest[:, interest_idx]
        top_indices = np.argsort(-interest_scores)[:top_k_per_interest]
        for club_idx in top_indices:
            club_idx = int(club_idx)
            cosine = float(interest_scores[club_idx])
            combined = min(cosine + _keyword_bonus(interest, club_words[club_idx]), KEYWORD_BONUS_CAP)
            if combined > best_score.get(club_idx, -1.0):
                best_score[club_idx] = combined
                best_interest[club_idx] = interest

    ranked_indices = sorted(best_score, key=lambda i: -best_score[i])[:top_k_total]

    results = []
    for i in ranked_indices:
        club = dict(clubs[i])
        club["score"] = best_score[i]
        club["match_percent"] = _score_to_match_percent(best_score[i])
        club["matched_interest"] = best_interest[i]
        results.append(club)
    return results


_VIBE_BUCKET_PHRASES = {
    "Professional": "professional development and career-focused clubs",
    "Social/Fun": "social and fun clubs",
}
_ACTIVITY_LEVEL_PHRASES = {
    "low": "a casual, low time commitment club to join",
    "high": "an active, high time commitment club to join",
}
_CULTURAL_AFFINITY_PHRASE = "a cultural, identity-based, or affinity student group"
_CULTURAL_AFFINITY_QUOTA = 4


def build_interest_phrases(profile: dict) -> list[str]:
    """Deterministically turns major/specific_interests_in_mind/hobbies into
    separate short phrases for match_clubs_multi_query() - never blended
    into one string, which would reintroduce the exact bug that function
    exists to fix. school_or_college/vibe/activity_level are handled
    separately in match_clubs_diversified() as soft bucket-phrase biases,
    not raw topics."""
    phrases = []
    if profile.get("major"):
        phrases.append(str(profile["major"]))
    phrases += [p for p in (profile.get("specific_interests_in_mind") or []) if p]
    phrases += [p for p in (profile.get("hobbies") or []) if p]
    return phrases


def match_clubs_diversified(profile: dict, top_k_total: int = 30) -> list[dict]:
    """Profile -> matches, category-aware. profile is the StudentProfile
    shape from services/profile_schema.py.

    For a clearly single vibe ("professional"/"social"), delegates to a
    flat match_clubs_multi_query - respects the student's stated
    preference, no forced diversification. For "both" or unset/null vibe
    (treated as wanting variety), runs a SEPARATE match_clubs_multi_query
    per target category and filters each bucket's candidates through
    categorize_club() so embedding similarity alone can't leak an
    off-category club into a bucket, then interleaves quota'd results -
    this is what actually fixes the "mix of professional and fun could
    come back all one type" problem, since match_clubs_multi_query's own
    pooling has no category awareness at all.

    A Cultural/Affinity bucket only gets an active, guaranteed quota slot
    when openness_to_cultural_affinity_groups is exactly "yes" (a clear
    affirmative) - "open"/"not_sure" get no special treatment, consistent
    with treating that field as a genuine invitation rather than a
    default-on nudge.
    """
    vibe = profile.get("vibe")
    base_phrases = build_interest_phrases(profile)
    activity_phrase = _ACTIVITY_LEVEL_PHRASES.get(profile.get("activity_level") or "")
    want_cultural = profile.get("openness_to_cultural_affinity_groups") == "yes"

    if vibe in ("professional", "social"):
        bucket = "Professional" if vibe == "professional" else "Social/Fun"
        phrases = base_phrases + [_VIBE_BUCKET_PHRASES[bucket]]
        if activity_phrase:
            phrases.append(activity_phrase)
        if want_cultural:
            phrases.append(_CULTURAL_AFFINITY_PHRASE)
        return match_clubs_multi_query(phrases, top_k_total=top_k_total)

    # "both" / missing vibe: diversify across Professional + Social/Fun.
    target_buckets = ["Professional", "Social/Fun"]
    cultural_quota = _CULTURAL_AFFINITY_QUOTA if want_cultural else 0
    remaining = max(top_k_total - cultural_quota, 2)
    per_bucket = remaining // len(target_buckets)
    leftover = remaining - per_bucket * len(target_buckets)

    pooled: dict[str, list[dict]] = {}
    for i, bucket in enumerate(target_buckets):
        phrases = base_phrases + [_VIBE_BUCKET_PHRASES[bucket]]
        if activity_phrase:
            phrases.append(activity_phrase)
        quota = per_bucket + (1 if i < leftover else 0)
        candidates = match_clubs_multi_query(phrases, top_k_total=max(quota * 3, 10))
        pooled[bucket] = [c for c in candidates if categorize_club(c) == bucket][:quota]

    if want_cultural:
        phrases = base_phrases + [_CULTURAL_AFFINITY_PHRASE]
        if activity_phrase:
            phrases.append(activity_phrase)
        candidates = match_clubs_multi_query(phrases, top_k_total=cultural_quota * 3)
        pooled["Cultural/Affinity"] = [
            c for c in candidates if categorize_club(c) == "Cultural/Affinity"
        ][:cultural_quota]

    # Round-robin interleave (a presentation nicety - group_clubs_by_category()
    # re-buckets for display regardless; the quota step above is what
    # actually fixes the diversity bug).
    order = [b for b in ("Professional", "Social/Fun", "Cultural/Affinity") if b in pooled]
    interleaved: list[dict] = []
    seen: set[str] = set()
    idx = 0
    while len(interleaved) < top_k_total:
        progressed = False
        for bucket in order:
            items = pooled[bucket]
            if idx < len(items):
                club = items[idx]
                if club.get("website_url") not in seen:
                    interleaved.append(club)
                    seen.add(club.get("website_url"))
                progressed = True
        idx += 1
        if not progressed:
            break
    return interleaved


def debug_query(query: str, top_k: int = 10) -> None:
    """Diagnostic helper: print the raw embedding behavior for `query`
    through both matching paths, full scores + full (untruncated)
    description text, no re-ranking applied. For tracking down bad top
    matches (e.g. "law" surfacing Cornell Real Estate Club) - run via
    `python -m backend.services.matching <query>`."""
    print(f"=== debug_query({query!r}) ===\n")

    print(f"--- match_clubs() [single-vector path] top {top_k} ---\n")
    for rank, club in enumerate(match_clubs(query, top_k=top_k), start=1):
        print(f"{rank}. {club['name']}  (score={club['score']:.4f})")
        print(f"   category: {club['category']}")
        print(f"   description: {club.get('description') or '(no description)'}")
        print()

    print(f"--- match_clubs_multi_query([query]) [production path] top {top_k} ---\n")
    for rank, club in enumerate(
        match_clubs_multi_query([query], top_k_total=top_k), start=1
    ):
        print(f"{rank}. {club['name']}  (score={club['score']:.4f})")
        print(f"   category: {club['category']}")
        print(f"   description: {club.get('description') or '(no description)'}")
        print()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        debug_query(" ".join(sys.argv[1:]))
        raise SystemExit(0)

    sample_query = "sustainability and climate policy clubs, low time commitment"
    print(f"Query: {sample_query!r}\n")
    for rank, club in enumerate(match_clubs(sample_query, top_k=5), start=1):
        print(f"{rank}. {club['name']}  (score={club['score']:.3f})")
        print(f"   category: {club['category']}")
        desc = club.get("description") or "(no description)"
        print(f"   description: {desc[:150]}")
        print()

    # Permanent regression check for the diversity bug: a finance-heavy
    # interest list should still surface Project Team/robotics clubs once
    # "robotics" is one of the interests, via match_clubs_multi_query -
    # the old single-blended-query match_clubs() cannot do this.
    print("--- Diversity fix regression check ---")
    interests = [
        "robotics",
        "quantitative finance and trading",
        "fintech",
        "entrepreneurship and startups",
        "private equity",
        "investment banking",
        "consulting",
    ]
    blended = match_clubs(", ".join(interests), top_k=20)
    multi = match_clubs_multi_query(interests, top_k_total=20)
    blended_hits = sum(1 for c in blended if "Project Team" in (c["category"] or ""))
    multi_hits = sum(1 for c in multi if "Project Team" in (c["category"] or ""))
    print(f"Old blended query: {blended_hits} Project Team clubs in top 20")
    print(f"New multi-query:   {multi_hits} Project Team clubs in top 20")
    assert blended_hits == 0, "expected the old bug to still reproduce on this query"
    assert multi_hits > 0, "match_clubs_multi_query should recover Project Team clubs"
    print("PASS")

    # Keyword-bonus / match_percent regression check: a direct hobby match
    # should score with high confidence, not read as mediocre.
    print("\n--- Keyword-bonus / match_percent regression check ---")
    ski_matches = match_clubs_multi_query(["skiing"], top_k_total=10)
    ski_hit = next((c for c in ski_matches if "ski" in c["name"].lower()), None)
    assert ski_hit is not None, "expected a ski club in top 10 for hobby 'skiing'"
    assert ski_hit["match_percent"] >= 80, f"expected >=80% for {ski_hit['name']!r}, got {ski_hit['match_percent']}"
    print(f"PASS: {ski_hit['name']!r} -> {ski_hit['match_percent']}%")

    spikeball_matches = match_clubs_multi_query(["spikeball"], top_k_total=10)
    roundnet_hit = next((c for c in spikeball_matches if c["name"] == "Cornell Roundnet"), None)
    assert roundnet_hit is not None, "expected Cornell Roundnet in top 10 for hobby 'spikeball'"
    assert roundnet_hit["match_percent"] >= 80, f"expected >=80% for Cornell Roundnet, got {roundnet_hit['match_percent']}"
    print(f"PASS: Cornell Roundnet -> {roundnet_hit['match_percent']}%")

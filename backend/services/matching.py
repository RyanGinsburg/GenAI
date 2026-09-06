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
from pathlib import Path

import numpy as np

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
        club["score"] = float(scores[i])
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
    """
    clubs = load_clubs()
    if not interests:
        return []

    embeddings = get_club_embeddings(clubs)
    interest_embeddings = _embed_texts(interests)  # (n_interests, dim), already normalized

    scores_by_interest = embeddings @ interest_embeddings.T  # (n_clubs, n_interests)

    best_score: dict[int, float] = {}
    best_interest: dict[int, str] = {}

    for interest_idx, interest in enumerate(interests):
        interest_scores = scores_by_interest[:, interest_idx]
        top_indices = np.argsort(-interest_scores)[:top_k_per_interest]
        for club_idx in top_indices:
            score = float(interest_scores[club_idx])
            if score > best_score.get(club_idx, -1.0):
                best_score[club_idx] = score
                best_interest[club_idx] = interest

    ranked_indices = sorted(best_score, key=lambda i: -best_score[i])[:top_k_total]

    results = []
    for i in ranked_indices:
        club = dict(clubs[i])
        club["score"] = best_score[i]
        club["matched_interest"] = best_interest[i]
        results.append(club)
    return results


_MODE_PHRASES = {
    "professional": "professional development and career-focused clubs",
    "social": "social and fun clubs",
}


def match_clubs_for_profile(profile: dict, top_k_total: int = 30) -> list[dict]:
    """Turns a chat-built profile into match_clubs_multi_query() candidates.
    Pure function, no LLM call - matching stays deterministic. profile is
    the shape services/chat_profile.py produces: {"interests": [...],
    "mode": "professional"|"social"|"both", "time_commitment": ..., "notes": ...}."""
    interests = list(profile.get("interests") or [])
    mode_phrase = _MODE_PHRASES.get(profile.get("mode") or "")
    if mode_phrase:
        interests.append(mode_phrase)
    return match_clubs_multi_query(interests, top_k_total=top_k_total)


if __name__ == "__main__":
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

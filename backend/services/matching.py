"""Match a student's profile to clubs: embedding search over data/clubs.json,
then re-ranking.

Embeddings are cached to data/embeddings.npy so they aren't regenerated per run.

Uses a local sentence-transformers model (all-MiniLM-L6-v2) — no API key
needed, runs on CPU, fast enough for ~1500 clubs. If we ever need a bigger
model or hosted embeddings, swap _embed_texts()/_get_model() only; the
caching and match_clubs() interface stay the same.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
CLUBS_PATH = DATA_DIR / "clubs.json"
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
    """Load the scraped club directory from data/clubs.json."""
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
    similarity. Each result is the club dict plus a "score" field."""
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


if __name__ == "__main__":
    sample_query = "sustainability and climate policy clubs, low time commitment"
    print(f"Query: {sample_query!r}\n")
    for rank, club in enumerate(match_clubs(sample_query, top_k=5), start=1):
        print(f"{rank}. {club['name']}  (score={club['score']:.3f})")
        print(f"   category: {club['category']}")
        desc = club.get("description") or "(no description)"
        print(f"   description: {desc[:150]}")
        print()

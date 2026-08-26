"""
Semantic retrieval for the Q&A agent: a local embedding model (no API key, runs
offline — sentence-transformers/all-MiniLM-L6-v2) replaces hardcoded keyword
matching. Keyword matching isn't just a small-data shortcut — a merchant
question phrased outside the guessed keyword list gets zero context regardless
of dataset size. Embeddings degrade gracefully instead of returning nothing.

Embeddings are computed once per record (via `ensure_embeddings`) and persisted
in Postgres (see db.record_embeddings), not recomputed per question. Similarity
search is brute-force cosine in numpy, which is fine at this dataset's size —
see db.py's record_embeddings table docstring for the pgvector upgrade path
once volume actually warrants an ANN index.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from backend import db

_MODEL_NAME = "all-MiniLM-L6-v2"
_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(_MODEL_NAME)
    return _model


def record_to_text(record: dict[str, Any]) -> str:
    """A searchable natural-language rendering of one settlement record —
    what the embedding actually indexes."""
    parts = [
        f"Transaction {record['txn_id']} for order {record['order_id']}.",
        f"Amount ₹{record['txn_amount']} via {record['payment_method']}.",
        f"Reconciliation status: {record.get('reconciliation_status', 'unknown')}.",
    ]
    if record.get("reconciliation_tier"):
        parts.append(f"Matched via {record['reconciliation_tier']} tier.")
    if record.get("reconciliation_reasons"):
        for r in record["reconciliation_reasons"]:
            parts.append(f"Exception: {r['reason']} — {r['explanation']}.")
    if record.get("tax_category"):
        parts.append(f"Tax category: {record['tax_category']}.")
    if record.get("had_refund"):
        parts.append(f"Refunded amount: ₹{record.get('refund_amount')}.")
    if record.get("had_dispute_flag"):
        parts.append("This transaction had a dispute.")
    parts.append(f"Settled in {record.get('days_to_settle')} day(s), status {record.get('status')}.")
    return " ".join(parts)


def ensure_embeddings(records: list[dict[str, Any]]) -> None:
    """(Re)computes and persists embeddings only for records that don't already
    have one stored (by txn_id) — avoids re-embedding the whole dataset on
    every call once it's been indexed once."""
    existing = {e["txn_id"] for e in db.load_record_embeddings()}
    missing = [r for r in records if r["txn_id"] not in existing]
    if not missing:
        return

    model = _get_model()
    texts = [record_to_text(r) for r in missing]
    vectors = model.encode(texts, normalize_embeddings=True)

    rows = [
        {"txn_id": r["txn_id"], "text": text, "embedding": vector.tolist()}
        for r, text, vector in zip(missing, texts, vectors)
    ]
    engine = db.get_engine()
    with engine.begin() as conn:
        conn.execute(db.record_embeddings.insert(), rows)


def semantic_search(question: str, records: list[dict[str, Any]], top_k: int = 15) -> list[dict[str, Any]]:
    """Returns the top_k records most semantically similar to the question."""
    ensure_embeddings(records)

    stored = db.load_record_embeddings()
    if not stored:
        return []
    txn_ids = [s["txn_id"] for s in stored]
    matrix = np.array([s["embedding"] for s in stored], dtype=np.float32)

    model = _get_model()
    query_vector = model.encode([question], normalize_embeddings=True)[0]

    scores = matrix @ query_vector  # vectors are pre-normalized -> dot product == cosine similarity
    top_indices = np.argsort(-scores)[:top_k]
    top_txn_ids = {txn_ids[i] for i in top_indices}

    by_txn_id = {r["txn_id"]: r for r in records}
    return [by_txn_id[tid] for tid in top_txn_ids if tid in by_txn_id]

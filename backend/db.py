"""
Postgres-backed storage layer, replacing the flat JSON files each stage used to
read/write directly. Schema + indexes live here once; every stage module calls
these helpers instead of touching files, so query cost stays sublinear as data
grows (indexed lookups by order_id/txn_id/created_at) instead of loading an
entire dataset into memory on every read.

Each `save_*` function does a full-refresh (TRUNCATE + bulk INSERT) of its
table, matching the current pipeline's semantics: ingestion (re)generates a
complete synthetic dataset per run, and reconciliation/tax/forecaster each
recompute over the full current dataset. A real production system ingesting
a live, ever-growing transaction stream would append/upsert incrementally
instead — noted here rather than built, since it's a different ingestion model
than "regenerate the synthetic world," not just a bigger version of this one.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    delete,
    select,
    text,
)
from sqlalchemy.engine import Engine

from backend.config import require_database_url

metadata = MetaData()

base_transactions = Table(
    "base_transactions",
    metadata,
    Column("txn_id", String, primary_key=True),
    Column("source", String, index=True),
    Column("razorpay_payment_id", String, nullable=True),
    Column("order_id", String, index=True),
    Column("txn_amount", Float),
    Column("payment_method", String),
    Column("created_at", String, index=True),
    Column("day_of_week", Integer),
    Column("is_weekend_or_holiday", Boolean),
    Column("merchant_category", String),
    Column("had_dispute_flag", Boolean),
    Column("had_refund", Boolean),
    Column("refund_amount", Float),
    Column("gst_on_fee_flag", Boolean),
    Column("fee_amount", Float),
    Column("fee_amount_pending", Boolean),
    Column("tax_on_fee", Float),
    Column("fee_pct", Float),
    Column("days_to_settle", Integer),
    Column("deduction_pct", Float),
    Column("settled_at", String),
    Column("status", String),
    Column("true_tax_category", String),
)

ledger_rows = Table(
    "ledger_rows",
    metadata,
    Column("row_id", String, primary_key=True),
    Column("txn_id_hint", String, index=True),
    Column("order_id", String, index=True),
    Column("amount", Float),
    Column("timestamp", String),
    Column("payment_method", String, nullable=True),
    Column("status", String, nullable=True),
    Column("fee_amount", Float, nullable=True),
    Column("tax_on_fee", Float, nullable=True),
    Column("refund_amount", Float, nullable=True),
    Column("narration", String, nullable=True),
)

bank_rows = Table(
    "bank_rows",
    metadata,
    Column("row_id", String, primary_key=True),
    Column("txn_id_hint", String, index=True),
    Column("order_id", String, index=True),
    Column("amount", Float),
    Column("timestamp", String),
    Column("utr_reference", String, nullable=True),
    Column("type", String, nullable=True),
    Column("narration", String, nullable=True),
)

ground_truth = Table(
    "ground_truth",
    metadata,
    Column("txn_id", String, primary_key=True),
    Column("order_id", String, index=True),
    Column("ledger_row_ids", JSON),
    Column("bank_row_ids", JSON),
    Column("ledger_mismatch", String),
    Column("bank_mismatch", String),
    Column("should_fully_reconcile", Boolean),
    # "must_match" | "ambiguous" | "no_counterpart" — see
    # synthetic_data_generator._verdict. Kept alongside the boolean (rather
    # than replacing it) so validate.py can report the match-rate shortfall's
    # two distinct causes separately instead of conflating them.
    Column("reconcile_verdict", String, index=True),
)

reconciliation_matches = Table(
    "reconciliation_matches",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("ledger_row_id", String, index=True),
    Column("bank_row_id", String, index=True),
    Column("order_id", String, index=True),
    Column("tier", String),
    Column("amount_diff", Float),
    Column("timestamp_diff_hours", Float),
    Column("explanation", String, nullable=True),
)

reconciliation_exceptions = Table(
    "reconciliation_exceptions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("row_id", String, index=True),
    Column("side", String),
    Column("order_id", String, index=True),
    Column("reason", String),
    Column("explanation", String),
)

# Human-in-the-loop review decisions on reconciliation exceptions.
#
# Deliberately NOT part of any save_*/full-refresh cycle: every other derived
# table is TRUNCATE+reinserted per pipeline run, but a reviewer's decision is
# an audit record of something a person actually did — re-running ingestion
# must not erase it. Keyed by (row_id, side) rather than the exceptions
# table's surrogate `id`, because that id is reassigned on every refresh
# (save_reconciliation_exceptions strips and re-generates it), so a review
# pinned to it would silently attach to a different row after the next run.
reconciliation_reviews = Table(
    "reconciliation_reviews",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("row_id", String, index=True),
    Column("side", String),
    Column("order_id", String, index=True, nullable=True),
    # "approved_match" | "written_off" | "manually_paired"
    Column("decision", String, index=True),
    # Set only for manually_paired: the counterpart the reviewer chose.
    Column("paired_row_id", String, nullable=True),
    Column("note", String, nullable=True),
    Column("reviewer", String, nullable=True),
    Column("decided_at", String),
)

tax_classifications = Table(
    "tax_classifications",
    metadata,
    Column("txn_id", String, primary_key=True),
    Column("category", String, index=True),
    Column("method", String),
    Column("reasoning", String),
)

forecaster_metrics = Table(
    "forecaster_metrics",
    metadata,
    Column("label", String, primary_key=True),
    Column("report", JSON),
)

# Embeddings for the Q&A agent's semantic retrieval (see qa_agent/embeddings.py).
# Stored as a JSON float array and searched with brute-force cosine similarity
# in Python — fine at this dataset's size. The pgvector extension isn't
# installed on this Postgres instance; enabling it and switching this column
# to `vector` + an ivfflat/hnsw index is the natural next step for real scale,
# without changing anything about how records get embedded or searched.
record_embeddings = Table(
    "record_embeddings",
    metadata,
    Column("txn_id", String, primary_key=True),
    Column("text", String),
    Column("embedding", JSON),
)

_engine: Engine | None = None


def get_engine() -> Engine:
    """
    `pool_pre_ping`/`pool_recycle` matter now that the canonical database is
    hosted (Supabase) rather than a local socket: a managed Postgres reaps
    idle connections, so a pooled connection that sat unused across a quiet
    period is often already dead. Without the pre-ping the first request
    after an idle stretch fails with "server closed the connection
    unexpectedly" — a local Postgres never exhibits this, which is exactly
    why it's easy to miss until it happens in a deployed demo.

    `pool_size`/`max_overflow` are capped well below SQLAlchemy's own
    defaults (5 + 10 = 15) because Supabase's session-mode pooler enforces a
    hard ceiling of 15 total client connections on the smaller compute
    tiers — hitting that default exactly reproduced
    "FATAL: max clients reached in session mode" under a burst of concurrent
    dashboard polls. A small pool is also the right size for a
    single-worker, 0.1-CPU free-tier instance, which gets no real throughput
    benefit from holding more connections open anyway.
    """
    global _engine
    if _engine is None:
        _engine = create_engine(
            require_database_url(),
            pool_pre_ping=True,
            pool_recycle=300,
            pool_size=3,
            max_overflow=2,
        )
    return _engine


def init_db() -> None:
    metadata.create_all(get_engine())


def _replace_table(table: Table, rows: list[dict[str, Any]]) -> None:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(delete(table))
        if rows:
            conn.execute(table.insert(), rows)


def save_base_transactions(rows: list[dict[str, Any]]) -> None:
    _replace_table(base_transactions, rows)


def save_ledger_rows(rows: list[dict[str, Any]]) -> None:
    _replace_table(ledger_rows, rows)


def save_bank_rows(rows: list[dict[str, Any]]) -> None:
    _replace_table(bank_rows, rows)


def save_ground_truth(rows: list[dict[str, Any]]) -> None:
    _replace_table(ground_truth, rows)


def save_reconciliation_matches(rows: list[dict[str, Any]]) -> None:
    _replace_table(reconciliation_matches, [{k: v for k, v in r.items() if k != "id"} for r in rows])


def save_reconciliation_exceptions(rows: list[dict[str, Any]]) -> None:
    _replace_table(reconciliation_exceptions, [{k: v for k, v in r.items() if k != "id"} for r in rows])


def save_tax_classifications(rows: list[dict[str, Any]]) -> None:
    _replace_table(tax_classifications, rows)


def save_forecaster_metrics(label: str, report: dict[str, Any]) -> None:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(delete(forecaster_metrics).where(forecaster_metrics.c.label == label))
        conn.execute(forecaster_metrics.insert(), [{"label": label, "report": report}])


def save_record_embeddings(rows: list[dict[str, Any]]) -> None:
    _replace_table(record_embeddings, rows)


def load_record_embeddings() -> list[dict[str, Any]]:
    return _fetch_all(record_embeddings)


def _fetch_all(table: Table) -> list[dict[str, Any]]:
    """
    `dict(row._mapping)` looks like it produces plain str keys, but SQLAlchemy's
    RowMapping actually keys by its internal `quoted_name` (a str subclass) —
    that leaked into pandas DataFrames built from these dicts and silently
    broke a strict type-identity check deep in scikit-learn's feature-name
    validation (ColumnTransformer + FunctionTransformer). Casting to plain
    `str` here keeps that SQLAlchemy implementation detail from leaking past
    this module at all.
    """
    engine = get_engine()
    with engine.connect() as conn:
        return [
            {str(k): v for k, v in row._mapping.items()} for row in conn.execute(select(table))
        ]


def load_base_transactions() -> list[dict[str, Any]]:
    return _fetch_all(base_transactions)


def load_ledger_rows() -> list[dict[str, Any]]:
    return _fetch_all(ledger_rows)


def load_bank_rows() -> list[dict[str, Any]]:
    return _fetch_all(bank_rows)


def load_ground_truth() -> list[dict[str, Any]]:
    return _fetch_all(ground_truth)


def load_reconciliation_matches() -> list[dict[str, Any]]:
    return _fetch_all(reconciliation_matches)


def load_reconciliation_exceptions() -> list[dict[str, Any]]:
    return _fetch_all(reconciliation_exceptions)


def load_tax_classifications() -> list[dict[str, Any]]:
    return _fetch_all(tax_classifications)


def load_reconciliation_reviews() -> list[dict[str, Any]]:
    return _fetch_all(reconciliation_reviews)


def save_reconciliation_review(
    row_id: str,
    side: str,
    decision: str,
    order_id: str | None = None,
    paired_row_id: str | None = None,
    note: str | None = None,
    reviewer: str | None = None,
) -> dict[str, Any]:
    """
    Records one reviewer decision, replacing any previous decision for the
    same (row_id, side) so a reviewer can correct themselves without leaving
    two contradictory rows. Note this is a *replace*, not an append-only
    history — see the table docstring; a fuller audit trail would keep every
    revision, which is the natural next step if decisions ever need to be
    disputed rather than just recorded.
    """
    row = {
        "row_id": row_id,
        "side": side,
        "order_id": order_id,
        "decision": decision,
        "paired_row_id": paired_row_id,
        "note": note,
        "reviewer": reviewer,
        "decided_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            delete(reconciliation_reviews).where(
                reconciliation_reviews.c.row_id == row_id,
                reconciliation_reviews.c.side == side,
            )
        )
        conn.execute(reconciliation_reviews.insert(), [row])
    return row


def delete_reconciliation_review(row_id: str, side: str) -> None:
    """Reopens an exception by removing its decision — the undo path for a
    reviewer who resolved something in error."""
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            delete(reconciliation_reviews).where(
                reconciliation_reviews.c.row_id == row_id,
                reconciliation_reviews.c.side == side,
            )
        )


def load_forecaster_metrics(label: str) -> dict[str, Any] | None:
    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(
            select(forecaster_metrics).where(forecaster_metrics.c.label == label)
        ).first()
        return row.report if row else None


def find_transaction_by_order_id(order_id: str) -> dict[str, Any] | None:
    """Indexed point lookup — the query pattern that doesn't scale when it has
    to linear-scan a fully-loaded-into-memory JSON list."""
    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(
            select(base_transactions).where(base_transactions.c.order_id == order_id)
        ).first()
        return {str(k): v for k, v in row._mapping.items()} if row else None


def healthcheck() -> bool:
    with get_engine().connect() as conn:
        conn.execute(text("SELECT 1"))
    return True

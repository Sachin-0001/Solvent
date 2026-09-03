"""
Thin HTTP layer over the existing Python pipeline, for the Next.js frontend.
No business logic lives here — every endpoint just calls the same functions
the CLI entry points (run_reconciliation.py, run_tax_matcher.py, etc.) use, so
the dashboard and the CLI can never disagree about what "the numbers" are.

Run with: uvicorn backend.api:app --reload --port 8000
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend import db, track_b
from backend.config import CORS_ALLOWED_ORIGINS
from backend.ingestion.csv_adapter import CSVFormatError
from backend.qa_agent.agent import answer_question
from backend.qa_agent.retriever import load_settlement_records
from backend.reconciliation.validate import validate_reconciliation

app = FastAPI(title="Solvent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, bool]:
    return {"ok": db.healthcheck()}


@app.get("/api/reconciliation/summary")
def reconciliation_summary() -> dict[str, Any]:
    matches = db.load_reconciliation_matches()
    exceptions = db.load_reconciliation_exceptions()
    metrics = validate_reconciliation(matches, exceptions)
    return {
        **metrics,
        "tier_counts": metrics["tier_breakdown"],
    }


@app.get("/api/reconciliation/exceptions")
def reconciliation_exceptions() -> list[dict[str, Any]]:
    return db.load_reconciliation_exceptions()


# --- Human-in-the-loop review queue.
#
# Reconciliation deliberately leaves an honest exception list rather than
# force-matching. These endpoints are where a person resolves that residual:
# each exception is presented with the candidate rows that make the call
# possible, and the decision is persisted with an audit trail
# (db.reconciliation_reviews) that survives the pipeline's full-refresh.


def _review_candidates(exception: dict[str, Any], ledger_rows, bank_rows) -> list[dict[str, Any]]:
    """The opposite side's rows sharing this exception's order_id — what a
    reviewer needs to see to judge whether a pairing is right. Same-order_id
    only: without a shared join key there's nothing principled to suggest,
    and inventing cross-order candidates would invite exactly the false
    matches the engine refused to make."""
    if not exception.get("order_id"):
        return []
    opposite = bank_rows if exception["side"] == "ledger" else ledger_rows
    return [r for r in opposite if r.get("order_id") == exception["order_id"]]


@app.get("/api/reconciliation/review-queue")
def review_queue(status: str | None = None) -> dict[str, Any]:
    """`status` filters to "pending" or "resolved"; omitted returns both."""
    exceptions = db.load_reconciliation_exceptions()
    ledger_rows = db.load_ledger_rows()
    bank_rows = db.load_bank_rows()
    reviews_by_key = {(r["row_id"], r["side"]): r for r in db.load_reconciliation_reviews()}

    ledger_by_id = {r["row_id"]: r for r in ledger_rows}
    bank_by_id = {r["row_id"]: r for r in bank_rows}

    items = []
    for e in exceptions:
        review = reviews_by_key.get((e["row_id"], e["side"]))
        if status == "pending" and review is not None:
            continue
        if status == "resolved" and review is None:
            continue
        source = ledger_by_id.get(e["row_id"]) or bank_by_id.get(e["row_id"])
        items.append(
            {
                **e,
                "source_row": source,
                "candidates": _review_candidates(e, ledger_rows, bank_rows),
                "review": review,
            }
        )

    return {
        "total": len(exceptions),
        "pending": sum(1 for e in exceptions if (e["row_id"], e["side"]) not in reviews_by_key),
        "resolved": sum(1 for e in exceptions if (e["row_id"], e["side"]) in reviews_by_key),
        "items": items,
    }


VALID_DECISIONS = {"approved_match", "written_off", "manually_paired"}


class ReviewDecisionRequest(BaseModel):
    row_id: str
    side: str
    decision: str
    order_id: str | None = None
    paired_row_id: str | None = None
    note: str | None = None
    reviewer: str | None = None


@app.post("/api/reconciliation/review")
def submit_review(req: ReviewDecisionRequest) -> dict[str, Any]:
    if req.decision not in VALID_DECISIONS:
        raise HTTPException(
            status_code=400,
            detail=f"decision must be one of {sorted(VALID_DECISIONS)}",
        )
    if req.decision == "manually_paired" and not req.paired_row_id:
        raise HTTPException(
            status_code=400,
            detail="paired_row_id is required when decision is 'manually_paired'",
        )
    return db.save_reconciliation_review(
        row_id=req.row_id,
        side=req.side,
        decision=req.decision,
        order_id=req.order_id,
        paired_row_id=req.paired_row_id,
        note=req.note,
        reviewer=req.reviewer,
    )


@app.delete("/api/reconciliation/review")
def reopen_review(row_id: str, side: str) -> dict[str, bool]:
    db.delete_reconciliation_review(row_id, side)
    return {"reopened": True}


@app.get("/api/tax/summary")
def tax_summary() -> dict[str, Any]:
    classifications = db.load_tax_classifications()
    breakdown: dict[str, int] = {}
    for c in classifications:
        breakdown[c["category"]] = breakdown.get(c["category"], 0) + 1
    return {
        "total": len(classifications),
        "category_breakdown": breakdown,
        "resolved_by_rules": sum(1 for c in classifications if c["method"] == "rule"),
        "resolved_by_llm": sum(1 for c in classifications if c["method"] == "llm"),
    }


# The 250 synthetic transactions cluster in 2025-06..2025-08; the 7 real
# Razorpay test payments are from mid-2026. Defaulting to "day after the very
# latest transaction" (the pipeline's honest default for live use) lands the
# 7-day window almost entirely on the sparse real data and shows a near-empty
# chart. 2025-08-24 is a demo-window anchor picked because it's the densest
# 7-day stretch in the historical data — not a live "today". The API always
# returns the anchor it used so the frontend can label the chart honestly
# instead of implying this is a live forecast from today.
DEMO_FORECAST_ANCHOR = "2025-08-24"


@app.get("/api/forecast")
def forecast(reference_date: str | None = None) -> dict[str, Any]:
    from backend.forecaster.predict import forecast_daily_cashflow

    transactions = db.load_base_transactions()
    anchor = reference_date or DEMO_FORECAST_ANCHOR
    return {
        "reference_date": anchor,
        "days": forecast_daily_cashflow(transactions, reference_date=anchor),
    }


@app.get("/api/forecast/gmv")
def forecast_gmv() -> dict[str, Any]:
    from backend.forecaster.gmv import predict_next_day_gmv

    transactions = db.load_base_transactions()
    return predict_next_day_gmv(transactions)


@app.get("/api/cash-position")
def cash_position(current_cash: float = 1_000_000.0) -> dict[str, Any]:
    """Deterministic cash-position calculation — see
    backend/finance/cash_position.py. `current_cash` has no authoritative
    source in this synthetic dataset, so it's an explicit caller-supplied
    input (defaulted for a convenient demo call, never fabricated as if it
    came from real account data)."""
    from backend.finance.cash_position import compute_cash_position

    transactions = db.load_base_transactions()
    return compute_cash_position(transactions, current_cash)


class QARequest(BaseModel):
    question: str


@app.post("/api/qa")
def qa(req: QARequest) -> dict[str, Any]:
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question must not be empty")
    records = load_settlement_records()
    answer, trace = answer_question(req.question, records)
    return {"answer": answer, "trace": trace}


# --- Additive, read-only endpoints below. Each is a thin wrapper over the
# same db.load_*/validate_reconciliation calls the existing endpoints and CLI
# entry points use — no business logic here, nothing above this line changed.


@app.get("/api/pipeline/status")
def pipeline_status() -> dict[str, Any]:
    base_transactions = db.load_base_transactions()
    source_counts: dict[str, int] = {}
    for t in base_transactions:
        source_counts[t["source"]] = source_counts.get(t["source"], 0) + 1

    matches = db.load_reconciliation_matches()
    exceptions = db.load_reconciliation_exceptions()
    recon_metrics = validate_reconciliation(matches, exceptions)

    classifications = db.load_tax_classifications()
    category_counts: dict[str, int] = {}
    for c in classifications:
        category_counts[c["category"]] = category_counts.get(c["category"], 0) + 1

    model_a = db.load_forecaster_metrics("model_a")
    model_b_fee = db.load_forecaster_metrics("model_b_fee")
    model_b_refund = db.load_forecaster_metrics("model_b_refund")
    model_b_combined = db.load_forecaster_metrics("model_b_combined")

    embeddings = db.load_record_embeddings()

    return {
        "ingest": {
            "total_transactions": len(base_transactions),
            "source_counts": source_counts,
            "ledger_rows": len(db.load_ledger_rows()),
            "bank_rows": len(db.load_bank_rows()),
            "gate": "passed" if base_transactions else "pending",
        },
        "reconcile": {
            **recon_metrics,
            "gate": "passed" if matches or exceptions else "pending",
        },
        "classify": {
            "total": len(classifications),
            "category_counts": category_counts,
            "resolved_by_rules": sum(1 for c in classifications if c["method"] == "rule"),
            "resolved_by_llm": sum(1 for c in classifications if c["method"] == "llm"),
            "gate": "passed" if classifications else "pending",
        },
        "forecast": {
            "model_a": model_a,
            "model_b_fee": model_b_fee,
            "model_b_refund": model_b_refund,
            "model_b_combined": model_b_combined,
            "gate": "passed" if model_a and model_b_fee and model_b_refund else "pending",
        },
        "qa": {
            "indexed_records": len(embeddings),
            "gate": "passed" if embeddings else "pending",
        },
    }


# Tolerance bands used by each match tier, surfaced for the reconciliation UI
# (kept in sync by hand with exact_match.py / fuzzy_match.py — these are
# display-only constants, not re-imported to avoid coupling the API layer to
# matcher internals).
_TIER_TOLERANCES = {
    "exact": {"amount_abs": 5.0, "amount_pct": 0.015, "timestamp_hours": 6},
    "fuzzy": {"amount_abs": 30.0, "amount_pct": 0.08, "timestamp_hours": 96},
}


@app.get("/api/reconciliation/matches")
def reconciliation_matches(
    tier: str | None = None, sort: str | None = None, limit: int = 50
) -> dict[str, Any]:
    matches = db.load_reconciliation_matches()
    ledger_by_id = {r["row_id"]: r for r in db.load_ledger_rows()}
    bank_by_id = {r["row_id"]: r for r in db.load_bank_rows()}

    if tier:
        matches = [m for m in matches if m["tier"] == tier]
    if sort == "drift":
        matches = sorted(matches, key=lambda m: abs(m["amount_diff"]), reverse=True)

    total = len(matches)
    items = []
    for m in matches[:limit]:
        ledger = ledger_by_id.get(m["ledger_row_id"])
        bank = bank_by_id.get(m["bank_row_id"])
        items.append(
            {
                **m,
                "ledger": ledger,
                "bank": bank,
                "tolerance": _TIER_TOLERANCES.get(m["tier"]),
            }
        )

    return {"total": total, "items": items}


@app.get("/api/forecaster/metrics")
def forecaster_metrics() -> dict[str, Any]:
    return {
        "model_a": db.load_forecaster_metrics("model_a"),
        "model_b_fee": db.load_forecaster_metrics("model_b_fee"),
        "model_b_refund": db.load_forecaster_metrics("model_b_refund"),
        "model_b_combined": db.load_forecaster_metrics("model_b_combined"),
        "gmv": db.load_forecaster_metrics("gmv"),
    }


@app.get("/api/tax/classifications")
def tax_classifications_endpoint(category: str | None = None, limit: int = 50) -> dict[str, Any]:
    classifications = db.load_tax_classifications()
    if category:
        classifications = [c for c in classifications if c["category"] == category]
    return {"total": len(classifications), "items": classifications[:limit]}


# --- Track B: the live capability layer (CLAUDE.md sections 3-4). Same
# reconciliation/tax_matcher/forecaster/qa_agent functions Track A uses — see
# backend/track_b.py's module docstring for what's genuinely reused vs. why
# it's deliberately NOT persisted to Postgres the way Track A's data is.


class RazorpayConnectRequest(BaseModel):
    key_id: str
    key_secret: str


@app.post("/api/track-b/connect")
def track_b_connect(req: RazorpayConnectRequest) -> dict[str, Any]:
    # req.key_secret is used only inside run_from_razorpay and is never
    # logged, stored, or echoed back in this response.
    try:
        return track_b.run_from_razorpay(req.key_id, req.key_secret)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Couldn't connect to Razorpay with the provided credentials ({e.__class__.__name__}).",
        ) from None


@app.post("/api/track-b/upload")
async def track_b_upload(ledger_file: UploadFile = File(...), bank_file: UploadFile = File(...)) -> dict[str, Any]:
    ledger_csv = (await ledger_file.read()).decode("utf-8", errors="replace")
    bank_csv = (await bank_file.read()).decode("utf-8", errors="replace")
    try:
        return track_b.run_from_csv(ledger_csv, bank_csv)
    except CSVFormatError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


class TrackBQARequest(BaseModel):
    question: str
    records: list[dict[str, Any]]


@app.post("/api/track-b/qa")
def track_b_qa(req: TrackBQARequest) -> dict[str, Any]:
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question must not be empty")
    answer, trace = answer_question(req.question, req.records)
    return {"answer": answer, "trace": trace}

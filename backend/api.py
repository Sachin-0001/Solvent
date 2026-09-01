"""
Thin HTTP layer over the existing Python pipeline, for the Next.js frontend.
No business logic lives here — every endpoint just calls the same functions
the CLI entry points (run_reconciliation.py, run_tax_matcher.py, etc.) use, so
the dashboard and the CLI can never disagree about what "the numbers" are.

Run with: uvicorn backend.api:app --reload --port 8000
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend import db
from backend.config import CORS_ALLOWED_ORIGINS
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


class QARequest(BaseModel):
    question: str


@app.post("/api/qa")
def qa(req: QARequest) -> dict[str, str]:
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question must not be empty")
    records = load_settlement_records()
    return {"answer": answer_question(req.question, records)}


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
    model_b = db.load_forecaster_metrics("model_b")

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
            "model_b": model_b,
            "gate": "passed" if model_a and model_b else "pending",
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
        "model_b": db.load_forecaster_metrics("model_b"),
    }


@app.get("/api/tax/classifications")
def tax_classifications_endpoint(category: str | None = None, limit: int = 50) -> dict[str, Any]:
    classifications = db.load_tax_classifications()
    if category:
        classifications = [c for c in classifications if c["category"] == category]
    return {"total": len(classifications), "items": classifications[:limit]}

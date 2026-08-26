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
from backend.qa_agent.agent import answer_question
from backend.qa_agent.retriever import load_settlement_records
from backend.reconciliation.validate import validate_reconciliation

app = FastAPI(title="Solvent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
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

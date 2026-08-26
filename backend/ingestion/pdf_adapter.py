"""
STRETCH / NOT BUILT.

Documented slot for a future adapter that parses real bank-statement PDFs into
Transaction records (e.g. via pdfplumber + a layout-specific line parser, or an
LLM-assisted extraction pass through the shared Groq wrapper for statements whose
column layout isn't known ahead of time).

It is not implemented for the buildathon submission. It exists here so the
ingestion layer's pluggability claim ("swap in a PDF adapter without touching
downstream code") is concrete rather than aspirational: any real implementation
only needs to subclass IngestionAdapter and return `Transaction` objects with the
same normalized fields the other adapters produce.
"""

from __future__ import annotations

from typing import Any

from backend.ingestion.base import IngestionAdapter, Transaction


class PdfStatementAdapter(IngestionAdapter):
    name = "pdf_statement"

    def fetch(self, **kwargs: Any) -> list[Transaction]:
        raise NotImplementedError(
            "PdfStatementAdapter is a documented stretch goal, not implemented. "
            "See module docstring for the intended design."
        )

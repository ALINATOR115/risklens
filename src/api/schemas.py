"""
Pydantic request / response schemas for the risk scoring API.

These models define the public contract between the API and any client
(web frontend, CLI, integration tests). All field names use snake_case
to match the internal pandas column conventions.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------

class TransactionIn(BaseModel):
    """A single transaction submitted for scoring."""

    transaction_id: Optional[str] = Field(
        None,
        description="Client-provided transaction identifier. Auto-generated if omitted.",
    )
    user_id: str = Field(..., description="Unique identifier of the user/account.")
    amount: float = Field(..., gt=0, description="Transaction amount (positive).")
    transaction_time: datetime = Field(
        ...,
        description="Timestamp of the transaction (ISO-8601).",
    )
    transaction_type: Optional[str] = Field(
        None,
        description="Type of transaction, e.g. 'purchase', 'transfer'.",
    )
    merchant_id: Optional[str] = Field(
        None,
        description="Merchant / counterparty identifier.",
    )
    country: Optional[str] = Field(None, description="ISO country code.")


class BatchScoreRequest(BaseModel):
    """A batch of transactions to score in one call."""

    transactions: List[TransactionIn] = Field(
        ...,
        min_length=1,
        description="List of transactions to score.",
    )


# ---------------------------------------------------------------------------
# Response bodies
# ---------------------------------------------------------------------------

class ScoreBreakdown(BaseModel):
    """Decomposition of the final risk score into its three components."""

    rule_score: float = Field(..., ge=0, le=1)
    behavioral_risk_score: float = Field(..., ge=0, le=1)
    model_score: float = Field(..., ge=0, le=1)


class TransactionResult(BaseModel):
    """Scoring result for a single transaction."""

    transaction_id: str
    user_id: str
    amount: float
    transaction_time: datetime
    final_score: float = Field(..., ge=0, le=1)
    risk_class: str = Field(
        ...,
        description="One of: low_risk, medium_risk, high_risk.",
    )
    breakdown: ScoreBreakdown
    triggered_rules: List[str] = Field(
        default_factory=list,
        description="Names of rules that fired for this transaction.",
    )
    explanations: List[str] = Field(
        default_factory=list,
        description="Human-readable explanations of why this transaction is suspicious.",
    )


class BatchScoreResponse(BaseModel):
    """Response envelope for a batch scoring request."""

    total: int = Field(..., description="Number of transactions scored.")
    high_risk_count: int
    medium_risk_count: int
    low_risk_count: int
    results: List[TransactionResult]


class HealthResponse(BaseModel):
    """Health-check / readiness probe response."""

    status: str = "ok"
    model_loaded: bool
    model_name: Optional[str] = None
    version: str = "0.1.0"


class ErrorResponse(BaseModel):
    """Standard error envelope."""

    detail: str


class ColumnDetectResponse(BaseModel):
    """Response from /score/detect — column names, samples, and best-guess mapping."""

    columns: List[str] = Field(..., description="All column names found in the CSV.")
    sample: dict = Field(..., description="First non-null value per column.")
    guess: dict = Field(
        ...,
        description="Best-guess mapping: {user_id, amount, transaction_time} -> column name or null.",
    )
"""
API route definitions for the risk scoring service.

Endpoints
---------
GET  /health              Readiness probe + model info
POST /score/batch         Score a JSON array of transactions
POST /score/detect        Detect columns in an uploaded CSV (for mapping UI)
POST /score/upload        Score transactions from an uploaded CSV file (with column mapping)
POST /score/single        Score one transaction (convenience for demos)
"""

from __future__ import annotations

import io
import uuid
from typing import List, Optional

import pandas as pd
from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, File

from src.api.dependencies import AppState, get_state, score_dataframe
from src.api.schemas import (
    BatchScoreRequest,
    BatchScoreResponse,
    ColumnDetectResponse,
    ErrorResponse,
    HealthResponse,
    ScoreBreakdown,
    TransactionIn,
    TransactionResult,
)


router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _transactions_to_dataframe(transactions: List[TransactionIn]) -> pd.DataFrame:
    records = []
    for t in transactions:
        records.append({
            "transaction_id": t.transaction_id or str(uuid.uuid4())[:8],
            "user_id": t.user_id,
            "amount": t.amount,
            "transaction_time": t.transaction_time,
            "transaction_type": t.transaction_type or "unknown",
            "merchant_id": t.merchant_id or "unknown",
            "country": t.country or "unknown",
        })
    df = pd.DataFrame(records)
    df["transaction_time"] = pd.to_datetime(df["transaction_time"])
    return df


def _generate_explanations(row: pd.Series) -> list:
    """Generate human-readable explanations from behavioral features."""
    explanations = []

    # Amount vs previous transaction
    ratio_prev = row.get('amount_ratio_prev', None)
    if ratio_prev and ratio_prev == ratio_prev:  # NaN check
        if ratio_prev >= 10:
            explanations.append(
                f"Amount is {ratio_prev:.0f}× higher than the previous transaction for this user."
            )
        elif ratio_prev >= 3:
            explanations.append(
                f"Amount is {ratio_prev:.1f}× higher than the previous transaction for this user."
            )

    # Amount vs user average
    ratio_avg = row.get('amount_ratio_avg', None)
    if ratio_avg and ratio_avg == ratio_avg:
        if ratio_avg >= 10:
            explanations.append(
                f"Amount is {ratio_avg:.0f}× above this user average."
            )
        elif ratio_avg >= 3:
            explanations.append(
                f"Amount is {ratio_avg:.1f}× above this user average."
            )

    # Transaction frequency
    freq = row.get('transactions_last_24_h', None)
    if freq and freq == freq and freq >= 5:
        explanations.append(
            f"{int(freq)} transactions from this user in the last 24 hours — unusually high frequency."
        )

    # Share of total
    share = row.get('share_of_total', None)
    if share and share == share and share >= 0.5:
        explanations.append(
            f"This transaction is {share*100:.0f}% of the user total transaction volume."
        )

    # Increasing sequence
    increasing = row.get('is_increasing_3', None)
    if increasing and increasing == increasing and increasing == 1:
        explanations.append(
            "Three consecutive increasing transactions detected — possible structuring pattern."
        )

    # Model score
    model_score = row.get('model_score', 0)
    if model_score >= 0.9:
        explanations.append(
            f"ML model confidence: {model_score*100:.0f}% probability of fraud."
        )
    elif model_score >= 0.7:
        explanations.append(
            f"ML model flagged this transaction with {model_score*100:.0f}% fraud probability."
        )

    # Fallback if nothing triggered
    if not explanations:
        final = row.get('final_score', 0)
        if final >= 0.5:
            explanations.append("Combination of behavioral signals elevated the risk score.")

    return explanations


def _row_to_result(row: pd.Series) -> TransactionResult:
    triggered = row.get("triggered_rules", [])
    if isinstance(triggered, str):
        triggered = [r.strip() for r in triggered.split(",") if r.strip()]
    return TransactionResult(
        transaction_id=str(row["transaction_id"]),
        user_id=str(row["user_id"]),
        amount=float(row["amount"]),
        transaction_time=row["transaction_time"],
        final_score=round(float(row["final_score"]), 4),
        risk_class=str(row["risk_class"]),
        breakdown=ScoreBreakdown(
            rule_score=round(float(row.get("rule_score", 0)), 4),
            behavioral_risk_score=round(float(row.get("behavioral_risk_score", 0)), 4),
            model_score=round(float(row.get("model_score", 0)), 4),
        ),
        triggered_rules=triggered if isinstance(triggered, list) else [],
        explanations=_generate_explanations(row),
    )


def _build_batch_response(scored: pd.DataFrame) -> BatchScoreResponse:
    results = [_row_to_result(row) for _, row in scored.iterrows()]
    risk_counts = scored["risk_class"].value_counts()
    return BatchScoreResponse(
        total=len(results),
        high_risk_count=int(risk_counts.get("high_risk", 0)),
        medium_risk_count=int(risk_counts.get("medium_risk", 0)),
        low_risk_count=int(risk_counts.get("low_risk", 0)),
        results=results,
    )


def _ensure_ready(state: AppState) -> None:
    if not state.is_ready:
        raise HTTPException(
            status_code=503,
            detail="Model not loaded. The server is not ready to score.",
        )


def _parse_timestamp(series: pd.Series, col_name: str) -> pd.Series:
    """Smartly parse a timestamp column regardless of format.

    Handles three cases:
    - ISO strings: '2024-01-15 10:30:00' -> parsed directly
    - Unix seconds: 1705312200 (10-digit number) -> converted from epoch
    - Offset seconds: 86400 (small number, e.g. IEEE-CIS TransactionDT)
      -> treated as seconds offset from 2017-12-01 (IEEE-CIS reference date)
      -> for other datasets with small numbers, same approach gives readable dates
    """
    import numpy as np

    # Try standard datetime parsing first (handles ISO strings)
    try:
        parsed = pd.to_datetime(series, infer_datetime_format=True)
        # If parsed successfully and not all NaT, return
        if parsed.notna().any():
            return parsed
    except Exception:
        pass

    # Try numeric interpretation
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().all():
        max_val = numeric.max()

        if max_val > 1e12:
            # Milliseconds since epoch (13-digit)
            return pd.to_datetime(numeric, unit="ms", errors="coerce")
        elif max_val > 1e9:
            # Seconds since Unix epoch (10-digit)
            return pd.to_datetime(numeric, unit="s", errors="coerce")
        else:
            # Small offset (e.g. IEEE-CIS: seconds since 2017-12-01)
            # Use a sensible base date so times look realistic
            base = pd.Timestamp("2020-01-01")
            return base + pd.to_timedelta(numeric, unit="s")

    # Last resort: let pandas figure it out
    return pd.to_datetime(series, errors="coerce")


def _apply_mapping(
    df: pd.DataFrame, col_user: str, col_amount: str, col_time: str
) -> pd.DataFrame:
    """Rename client columns to the internal schema and validate types."""
    mapping = {col_user: "user_id", col_amount: "amount", col_time: "transaction_time"}
    missing = [c for c in mapping if c not in df.columns]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Mapped columns not found in CSV: {missing}",
        )
    df = df.rename(columns=mapping)
    try:
        df["amount"] = pd.to_numeric(df["amount"], errors="raise")
    except Exception:
        raise HTTPException(
            status_code=400,
            detail=f"Column '{col_amount}' cannot be parsed as a number.",
        )
    try:
        df["transaction_time"] = _parse_timestamp(df["transaction_time"], col_time)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=400,
            detail=f"Column '{col_time}' cannot be parsed as a datetime.",
        )
    df["user_id"] = df["user_id"].astype(str)
    if "transaction_id" not in df.columns:
        df["transaction_id"] = [str(uuid.uuid4())[:8] for _ in range(len(df))]
    return df


def _guess_mapping(columns: List[str]) -> dict:
    """Heuristically guess which column maps to each required field."""
    user_hints =   ["user_id", "userid", "user", "customer", "client", "card", "nameorig", "account", "card1"]
    amount_hints = ["amount", "amt", "sum", "value", "transactionamt", "price", "total"]
    time_hints =   ["transaction_time", "time", "date", "datetime", "timestamp", "created_at", "transactiondt", "step"]

    def best_match(hints, cols):
        cols_lower = {c.lower(): c for c in cols}
        for h in hints:
            if h.lower() in cols_lower:
                return cols_lower[h.lower()]
        return None

    return {
        "user_id": best_match(user_hints, columns),
        "amount": best_match(amount_hints, columns),
        "transaction_time": best_match(time_hints, columns),
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/health", response_model=HealthResponse, summary="Health / readiness check")
def health(state: AppState = Depends(get_state)) -> HealthResponse:
    return HealthResponse(
        status="ok" if state.is_ready else "warming_up",
        model_loaded=state.is_ready,
        model_name=state.model_name,
    )


@router.post(
    "/score/batch",
    response_model=BatchScoreResponse,
    responses={503: {"model": ErrorResponse}},
    summary="Score a batch of transactions (JSON)",
)
def score_batch(
    body: BatchScoreRequest, state: AppState = Depends(get_state)
) -> BatchScoreResponse:
    _ensure_ready(state)
    df = _transactions_to_dataframe(body.transactions)
    scored = score_dataframe(df, state)
    return _build_batch_response(scored)


@router.post(
    "/score/detect",
    response_model=ColumnDetectResponse,
    responses={400: {"model": ErrorResponse}},
    summary="Detect columns in an uploaded CSV for the mapping UI",
)
async def detect_columns(
    file: UploadFile = File(..., description="CSV file to inspect"),
) -> ColumnDetectResponse:
    """Returns column names, sample values, and a best-guess mapping.
    Used by the frontend to populate the column mapping dropdowns."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted.")
    contents = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(contents), nrows=5)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {exc}")

    columns = list(df.columns)
    sample = {
        col: str(df[col].dropna().iloc[0]) if not df[col].dropna().empty else ""
        for col in columns
    }
    guess = _guess_mapping(columns)
    return ColumnDetectResponse(columns=columns, sample=sample, guess=guess)


@router.post(
    "/score/upload",
    response_model=BatchScoreResponse,
    responses={400: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    summary="Score transactions from an uploaded CSV with column mapping",
)
async def score_upload(
    file: UploadFile = File(...),
    col_user: str = Form(..., description="Column name for user ID"),
    col_amount: str = Form(..., description="Column name for transaction amount"),
    col_time: str = Form(..., description="Column name for transaction timestamp"),
    state: AppState = Depends(get_state),
) -> BatchScoreResponse:
    _ensure_ready(state)
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted.")
    MAX_ROWS = 50_000
    TOP_N = 1_000

    contents = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(contents), nrows=MAX_ROWS)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {exc}")
    df.columns = df.columns.str.strip()
    df = _apply_mapping(df, col_user, col_amount, col_time)
    scored = score_dataframe(df, state)

    total_scored = len(scored)
    if total_scored > TOP_N:
        scored = scored.nlargest(TOP_N, "final_score")

    response = _build_batch_response(scored)
    response.total = total_scored
    return response


@router.get(
    "/users",
    summary="List all users with cached data",
)
def list_users(state: AppState = Depends(get_state)):
    return {"users": state.list_users(), "total": len(state.list_users())}


@router.get(
    "/users/{user_id}",
    summary="Get full transaction history for a user",
)
def get_user_profile(user_id: str, state: AppState = Depends(get_state)):
    txs = state.get_user(user_id)
    if not txs:
        raise HTTPException(status_code=404, detail=f"User '{user_id}' not found in cache.")

    # Compute summary stats
    scores = [t.get("final_score", 0) for t in txs]
    risk_counts = {"high_risk": 0, "medium_risk": 0, "low_risk": 0}
    for t in txs:
        rc = t.get("risk_class", "low_risk")
        if rc in risk_counts:
            risk_counts[rc] += 1

    # Serialize (convert non-JSON-safe types)
    serialized = []
    for t in txs:
        row = {}
        for k, v in t.items():
            try:
                import math
                if isinstance(v, float) and math.isnan(v):
                    row[k] = None
                else:
                    row[k] = v if not hasattr(v, 'isoformat') else v.isoformat()
            except Exception:
                row[k] = str(v)
        serialized.append(row)

    return {
        "user_id": user_id,
        "total_transactions": len(txs),
        "max_risk_score": round(max(scores), 4) if scores else 0,
        "avg_risk_score": round(sum(scores) / len(scores), 4) if scores else 0,
        "risk_counts": risk_counts,
        "transactions": serialized,
    }


@router.post(
    "/score/single",
    response_model=TransactionResult,
    responses={503: {"model": ErrorResponse}},
    summary="Score a single transaction",
)
def score_single(
    transaction: TransactionIn, state: AppState = Depends(get_state)
) -> TransactionResult:
    _ensure_ready(state)
    df = _transactions_to_dataframe([transaction])
    scored = score_dataframe(df, state)
    return _row_to_result(scored.iloc[0])

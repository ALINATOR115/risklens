"""
Behavioral feature engineering for transaction risk scoring.

Builds per-user temporal features from a raw transactions DataFrame.
All historical aggregates are computed using only the user's past
transactions (no leakage from future rows), with the deliberate
exception of ``share_of_total``, which by definition is normalized
against the user's full activity window present in the input.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Set

import pandas as pd

from src.config.settings import FeatureConfig


FEATURE_COLUMNS: List[str] = [
    "previous_amount",
    "diff_from_previous",
    "amount_ratio_prev",
    "avg_amount_before",
    "diff_from_avg",
    "amount_ratio_avg",
    "running_total",
    "transactions_last_24_h",
    "share_of_total",
    "is_increasing_3",
]

KEY_COLUMNS: List[str] = ["transaction_id", "user_id", "transaction_time", "amount"]

REQUIRED_INPUT_COLUMNS: Set[str] = {"user_id", "transaction_time", "amount"}


def get_feature_columns() -> List[str]:
    """Return the canonical, ordered list of engineered feature names."""
    return list(FEATURE_COLUMNS)


@dataclass
class FeatureBuilder:
    """Builds behavioral features from raw transactions.

    The builder is stateless in this first version: ``fit`` only validates
    the input schema. The interface is preserved so future versions can
    learn per-user baselines (mean amount, known countries, typical hours,
    etc.) without changing call sites.
    """

    config: FeatureConfig

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fit(self, transactions: pd.DataFrame) -> "FeatureBuilder":
        """Validate input schema. No state is learned in this version."""
        self._validate_input(transactions)
        return self

    def transform(self, transactions: pd.DataFrame) -> pd.DataFrame:
        """Compute features and return key columns plus engineered features.

        The output is sorted by ``(user_id, transaction_time)``. Rows where
        a feature cannot be computed (e.g. ``previous_amount`` for the
        user's first transaction) keep ``NaN`` for that feature, with the
        exception of explicit ratio features which are set to ``0`` per
        spec when the denominator is missing or zero.
        """
        self._validate_input(transactions)
        df = self._prepare(transactions)
        df = df.sort_values(
            ["user_id", "transaction_time"], kind="mergesort"
        ).reset_index(drop=True)

        grouped = df.groupby("user_id", sort=False)
        amount = df["amount"]

        # --- previous-transaction features ---
        df["previous_amount"] = grouped["amount"].shift(1)
        df["diff_from_previous"] = amount - df["previous_amount"]
        df["amount_ratio_prev"] = self._safe_ratio(amount, df["previous_amount"])

        # --- expanding mean of past transactions (excluding current) ---
        cum_sum = grouped["amount"].cumsum()
        n_before = grouped.cumcount()  # 0 for the user's first row
        sum_before = cum_sum - amount
        df["avg_amount_before"] = (
            sum_before / n_before.where(n_before > 0)
        ).astype(float)
        df["diff_from_avg"] = amount - df["avg_amount_before"]
        df["amount_ratio_avg"] = self._safe_ratio(amount, df["avg_amount_before"])

        # --- running total per user (includes current row) ---
        df["running_total"] = cum_sum

        # --- 24h velocity, time-based, right-closed, includes current ---
        df["transactions_last_24_h"] = self._rolling_count_24h(df)

        # --- share of the user's total amount in the dataset ---
        total_per_user = grouped["amount"].transform("sum")
        df["share_of_total"] = self._safe_ratio(amount, total_per_user)

        # --- monotonic 3-step increase indicator ---
        prev1 = df["previous_amount"]
        prev2 = grouped["amount"].shift(2)
        df["is_increasing_3"] = ((amount > prev1) & (prev1 > prev2)).astype(int)

        return df[KEY_COLUMNS + FEATURE_COLUMNS]

    def fit_transform(self, transactions: pd.DataFrame) -> pd.DataFrame:
        """Convenience method: fit on and transform the same data."""
        return self.fit(transactions).transform(transactions)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_input(df: pd.DataFrame) -> None:
        """Raise ``ValueError`` if required columns are missing."""
        missing = REQUIRED_INPUT_COLUMNS - set(df.columns)
        if missing:
            raise ValueError(
                f"Input transactions are missing required columns: {sorted(missing)}"
            )

    @staticmethod
    def _prepare(df: pd.DataFrame) -> pd.DataFrame:
        """Return a copy with normalized dtypes and a guaranteed transaction_id."""
        out = df.copy()
        out["transaction_time"] = pd.to_datetime(out["transaction_time"])
        if "transaction_id" not in out.columns:
            out["transaction_id"] = out.index.astype(str)
        else:
            out["transaction_id"] = out["transaction_id"].astype(str)
        return out

    @staticmethod
    def _safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
        """Element-wise division returning 0 where the denominator is NaN or 0."""
        safe_denominator = denominator.where(denominator.notna() & (denominator != 0))
        return (numerator / safe_denominator).fillna(0.0).astype(float)

    @staticmethod
    def _rolling_count_24h(df: pd.DataFrame) -> pd.Series:
        """Per-user count of transactions in the trailing 24h, including current.

        ``df`` is expected to be pre-sorted by ``(user_id, transaction_time)``.
        ``groupby(..., sort=False).rolling(on=...)`` returns a Series indexed
        by ``(user_id, transaction_time)`` rather than by df's integer index,
        so we read the values positionally — the order matches df because
        the input is already sorted in group/time order.
        """
        counts = (
            df.groupby("user_id", sort=False)
              .rolling("24h", on="transaction_time")["amount"]
              .count()
              .to_numpy()
        )
        return pd.Series(counts.astype(int), index=df.index, name="transactions_last_24_h")

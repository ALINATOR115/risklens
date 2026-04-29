"""
Final risk score composition.

This module turns three independent signals into a single risk verdict
per transaction:

* ``rule_score`` — discrete output of the rule engine (binary thresholds).
* ``behavioral_risk_score`` — a continuous integral risk index computed
  here from the behavioral features. Crucially, this is *not* a copy of
  the rule score: rules use hard thresholds and lose granularity (a
  transaction at ``ratio = 4.9`` triggers nothing, ``ratio = 5.0``
  triggers fully), whereas the behavioral index linearly interpolates
  each feature between a soft ``threshold`` and a hard ``cap``, giving a
  smooth, ranking-friendly signal.
* ``model_score`` — probability from the ML model (handled elsewhere).

The three signals are combined into ``final_score`` using configurable
weights, and the final score is mapped to a discrete risk class.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import pandas as pd

from src.config.settings import ScoringConfig


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class RiskAssessment:
    """The full risk verdict for a single transaction."""

    transaction_id: str
    rule_score: float
    behavioral_risk_score: float
    model_score: float
    final_score: float
    risk_class: str
    triggered_rules: List[str]


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------

class RiskScorer:
    """Combines rule-based, behavioral, and model-based signals."""

    OUTPUT_COLUMNS: List[str] = [
        "transaction_id",
        "rule_score",
        "behavioral_risk_score",
        "model_score",
        "final_score",
        "risk_class",
        "triggered_rules",
    ]

    def __init__(self, config: ScoringConfig) -> None:
        self.config = config

    # ------------------------------------------------------------------
    # Normalization primitives
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_ratio(value: float, threshold: float, cap: float) -> float:
        """Map a ratio-style value into [0, 1] via piecewise-linear scaling.

        - ``value <= threshold`` → 0
        - ``value >= cap``       → 1
        - in between             → linear interpolation
        - missing/NaN            → 0 (treated as "no signal")
        """
        if value is None or pd.isna(value):
            return 0.0
        v = float(value)
        if v <= threshold:
            return 0.0
        if v >= cap:
            return 1.0
        if cap <= threshold:  # degenerate config — fail safe to "high"
            return 1.0
        return (v - threshold) / (cap - threshold)

    @staticmethod
    def _normalize_count(value: float, threshold: float, cap: float) -> float:
        """Same shape as :meth:`_normalize_ratio`, kept separate for clarity.

        Having a distinct method lets the count normalizer evolve
        independently later (e.g. log-scale for heavy-tailed counts)
        without touching ratio normalization.
        """
        return RiskScorer._normalize_ratio(value, threshold, cap)

    # ------------------------------------------------------------------
    # Behavioral risk index
    # ------------------------------------------------------------------

    def compute_behavioral_risk_score(self, transaction: pd.Series) -> float:
        """Author's integral behavioral risk index in [0, 1].

        Built from four orthogonal behavioral signals — each normalized
        independently and then combined with configured weights. Uses
        only behavioral features; never reads ``rule_score`` or
        ``model_score``.
        """
        cfg = self.config

        spike_score = self._normalize_ratio(
            transaction.get("amount_ratio_prev"),
            cfg.spike_threshold,
            cfg.spike_cap,
        )
        deviation_score = self._normalize_ratio(
            transaction.get("amount_ratio_avg"),
            cfg.deviation_threshold,
            cfg.deviation_cap,
        )
        frequency_score = self._normalize_count(
            transaction.get("transactions_last_24_h"),
            cfg.frequency_threshold,
            cfg.frequency_cap,
        )
        share_score = self._normalize_ratio(
            transaction.get("share_of_total"),
            cfg.share_threshold,
            cfg.share_cap,
        )

        score = (
            cfg.spike_weight * spike_score
            + cfg.deviation_weight * deviation_score
            + cfg.frequency_weight * frequency_score
            + cfg.share_weight * share_score
        )
        return self._clip(score)

    # ------------------------------------------------------------------
    # Combination and classification
    # ------------------------------------------------------------------

    def combine(
        self,
        rule_score: float,
        behavioral_risk_score: float,
        model_score: float,
    ) -> float:
        """Weighted combination of the three signals into the final score."""
        cfg = self.config
        score = (
            cfg.final_rule_weight * self._clip(rule_score)
            + cfg.final_behavioral_weight * self._clip(behavioral_risk_score)
            + cfg.final_model_weight * self._clip(model_score)
        )
        return self._clip(score)

    def classify(self, final_score: float) -> str:
        """Map a final score to a discrete risk class."""
        cfg = self.config
        score = self._clip(final_score)
        if score >= cfg.high_risk_threshold:
            return "high_risk"
        if score >= cfg.medium_risk_threshold:
            return "medium_risk"
        return "low_risk"

    # ------------------------------------------------------------------
    # Per-transaction assessment
    # ------------------------------------------------------------------

    def assess(
        self,
        transaction: pd.Series,
        rule_score: float,
        model_score: float,
        triggered_rules: List[str],
    ) -> RiskAssessment:
        """Build a :class:`RiskAssessment` for a single feature row."""
        behavioral = self.compute_behavioral_risk_score(transaction)
        final = self.combine(rule_score, behavioral, model_score)
        return RiskAssessment(
            transaction_id=str(transaction.get("transaction_id", "")),
            rule_score=self._clip(rule_score),
            behavioral_risk_score=behavioral,
            model_score=self._clip(model_score),
            final_score=final,
            risk_class=self.classify(final),
            triggered_rules=list(triggered_rules),
        )

    # ------------------------------------------------------------------
    # Batch assessment
    # ------------------------------------------------------------------

    def assess_batch(
        self,
        features: pd.DataFrame,
        rule_results: pd.DataFrame,
        model_scores: pd.Series,
    ) -> pd.DataFrame:
        """Run assessment over a batch of feature rows.

        Inputs are aligned to ``features.index``. Missing rows in
        ``rule_results`` or ``model_scores`` are treated as zero (no
        signal) rather than dropped, so the output always has exactly
        one row per input feature row.
        """
        if features.empty:
            return pd.DataFrame(columns=self.OUTPUT_COLUMNS, index=features.index)

        cfg = self.config
        index = features.index

        # --- align inputs ---
        rule_score_aligned = (
            rule_results["rule_score"]
            .reindex(index)
            .fillna(0.0)
            .clip(0.0, 1.0)
        )
        triggered_aligned = (
            rule_results["triggered_rules"]
            .reindex(index)
            .apply(lambda x: x if isinstance(x, list) else [])
        )
        model_aligned = (
            model_scores.reindex(index).fillna(0.0).clip(0.0, 1.0)
        )

        # --- behavioral score (row-wise; vectorize later if needed) ---
        behavioral = features.apply(
            self.compute_behavioral_risk_score, axis=1
        ).astype(float)
        if behavioral.empty:
            behavioral = pd.Series(dtype=float, index=index)

        # --- final score: vectorized weighted sum ---
        final = (
            cfg.final_rule_weight * rule_score_aligned
            + cfg.final_behavioral_weight * behavioral
            + cfg.final_model_weight * model_aligned
        ).clip(0.0, 1.0)

        risk_class = final.apply(self.classify)

        # --- transaction_id: use column if present, else stringified index ---
        if "transaction_id" in features.columns:
            transaction_id = features["transaction_id"].astype(str)
        else:
            transaction_id = pd.Series(index.astype(str), index=index)

        return pd.DataFrame(
            {
                "transaction_id": transaction_id,
                "rule_score": rule_score_aligned.astype(float),
                "behavioral_risk_score": behavioral,
                "model_score": model_aligned.astype(float),
                "final_score": final.astype(float),
                "risk_class": risk_class,
                "triggered_rules": triggered_aligned,
            },
            index=index,
        )[self.OUTPUT_COLUMNS]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _clip(score: float) -> float:
        """Clamp a value into [0, 1], treating NaN as 0."""
        if score is None or pd.isna(score):
            return 0.0
        return float(max(0.0, min(1.0, float(score))))
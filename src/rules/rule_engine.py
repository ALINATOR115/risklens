"""
Rule-based risk component.

The rule engine evaluates a set of independent, human-readable rules
against a feature row produced by :class:`FeatureBuilder` and returns
a normalized rule-based risk score in the [0, 1] range plus the list
of rules that fired (used downstream for explainability).

Each rule is a small object pairing a name, a weight, and a predicate
on a feature row, so adding a new rule is a single entry in
:meth:`RuleEngine._build_rules`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, List

import pandas as pd

from src.config.settings import RuleConfig


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class RuleResult:
    """Outcome of evaluating the rule engine on a single transaction."""

    score: float
    triggered_rules: List[str]


@dataclass
class Rule:
    """A single named rule with a predicate and a contribution weight."""

    name: str
    weight: float
    predicate: Callable[[pd.Series], bool]

    def evaluate(self, transaction: pd.Series) -> bool:
        """Return ``True`` if this rule fires for the given transaction."""
        return bool(self.predicate(transaction))


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class RuleEngine:
    """Evaluates a configured set of rules against feature rows.

    The engine works on the schema produced by ``FeatureBuilder``: it
    expects engineered columns such as ``amount_ratio_prev``,
    ``amount_ratio_avg``, ``share_of_total``, ``transactions_last_24_h``
    and ``is_increasing_3`` to be present.
    """

    def __init__(self, config: RuleConfig) -> None:
        self.config = config
        self._rules: List[Rule] = self._build_rules()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def rules(self) -> List[Rule]:
        """Return a copy of the configured rules (for introspection/tests)."""
        return list(self._rules)

    def evaluate(self, transaction: pd.Series) -> RuleResult:
        """Evaluate all rules on a single transaction.

        The score is the sum of weights of fired rules, clipped to
        ``[0, 1]``. Order of triggered rule names follows their order
        of definition in :meth:`_build_rules`.
        """
        triggered: List[str] = []
        score = 0.0
        for rule in self._rules:
            if rule.evaluate(transaction):
                triggered.append(rule.name)
                score += rule.weight
        return RuleResult(
            score=self._clip_score(score),
            triggered_rules=triggered,
        )

    def evaluate_batch(self, transactions: pd.DataFrame) -> pd.DataFrame:
        """Evaluate rules across a DataFrame of feature rows.

        Returns a DataFrame aligned to the input index with two columns:

        * ``rule_score`` — float in ``[0, 1]``
        * ``triggered_rules`` — list of rule names that fired on that row
        """
        if transactions.empty:
            return pd.DataFrame(
                {"rule_score": pd.Series(dtype=float), "triggered_rules": []},
                index=transactions.index,
            )

        results = transactions.apply(self.evaluate, axis=1)
        return pd.DataFrame(
            {
                "rule_score": [r.score for r in results],
                "triggered_rules": [r.triggered_rules for r in results],
            },
            index=transactions.index,
        )

    # ------------------------------------------------------------------
    # Rule construction
    # ------------------------------------------------------------------

    def _build_rules(self) -> List[Rule]:
        """Instantiate the configured rules.

        Each rule is bound to one engineered feature column and one
        threshold from :class:`RuleConfig`. To add a new rule, append
        another :class:`Rule` here, declare its threshold and weight in
        ``RuleConfig``, and it will automatically be included in
        ``evaluate`` and ``evaluate_batch``.
        """
        cfg = self.config
        weights = cfg.rule_weights

        return [
            Rule(
                name="jump_from_previous",
                weight=weights["jump_from_previous"],
                predicate=self._ge("amount_ratio_prev", cfg.jump_from_previous_threshold),
            ),
            Rule(
                name="high_vs_average",
                weight=weights["high_vs_average"],
                predicate=self._ge("amount_ratio_avg", cfg.high_vs_average_threshold),
            ),
            Rule(
                name="high_share_of_total",
                weight=weights["high_share_of_total"],
                predicate=self._ge("share_of_total", cfg.high_share_of_total_threshold),
            ),
            Rule(
                name="high_transaction_frequency",
                weight=weights["high_transaction_frequency"],
                predicate=self._ge(
                    "transactions_last_24_h",
                    cfg.high_transaction_frequency_threshold,
                ),
            ),
            Rule(
                name="increasing_sequence",
                weight=weights["increasing_sequence"],
                predicate=self._eq("is_increasing_3", 1),
            ),
        ]

    # ------------------------------------------------------------------
    # Predicate factories
    # ------------------------------------------------------------------

    @staticmethod
    def _ge(column: str, threshold: float) -> Callable[[pd.Series], bool]:
        """Predicate: ``row[column] >= threshold``, with NaN treated as False."""
        def _predicate(tx: pd.Series) -> bool:
            value = tx.get(column)
            if value is None or pd.isna(value):
                return False
            return float(value) >= threshold
        return _predicate

    @staticmethod
    def _eq(column: str, target: Any) -> Callable[[pd.Series], bool]:
        """Predicate: ``row[column] == target``, with NaN treated as False."""
        def _predicate(tx: pd.Series) -> bool:
            value = tx.get(column)
            if value is None or pd.isna(value):
                return False
            return value == target
        return _predicate

    # ------------------------------------------------------------------
    # Scoring helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _clip_score(score: float) -> float:
        """Clamp a raw rule score into the [0, 1] range."""
        return float(max(0.0, min(1.0, score)))

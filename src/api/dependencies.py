"""
FastAPI dependency injection layer.

Manages the lifecycle of heavy objects (trained model, config, feature
builder) so they are loaded once at startup and shared across requests.
Also contains the core ``score_dataframe`` function that wires together
the existing pipeline modules — this is the single point where the API
layer touches the ML code.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pandas as pd

from src.config.settings import AppConfig, get_config
from src.features.feature_builder import FeatureBuilder
from src.models.predict import RiskPredictor
from src.rules.rule_engine import RuleEngine
from src.scoring.risk_score import RiskScorer


# ---------------------------------------------------------------------------
# Application state (singleton)
# ---------------------------------------------------------------------------

@dataclass
class AppState:
    """Holds all heavy objects shared across requests."""

    config: AppConfig = field(default_factory=get_config)
    predictor: Optional[RiskPredictor] = None
    model_name: Optional[str] = None
    # Cache: user_id -> list of scored transaction dicts
    user_cache: dict = field(default_factory=dict)

    def cache_results(self, scored: pd.DataFrame) -> None:
        """Store all scored transactions grouped by user_id."""
        for _, row in scored.iterrows():
            uid = str(row["user_id"])
            if uid not in self.user_cache:
                self.user_cache[uid] = []
            self.user_cache[uid].append(row.to_dict())

    def get_user(self, user_id: str) -> list:
        """Return all cached transactions for a user, sorted by time."""
        txs = self.user_cache.get(user_id, [])
        return sorted(txs, key=lambda x: x.get("transaction_time", ""))

    def list_users(self) -> list:
        """Return all user_ids that have cached data."""
        return sorted(self.user_cache.keys())

    # -- lazy-init helpers ------------------------------------------------

    def load_model(self, artifact_path: Path) -> None:
        """Load the ML model from a joblib bundle.

        Safe to call multiple times (idempotent).
        """
        self.predictor = RiskPredictor.load(artifact_path)
        self.model_name = artifact_path.stem

    @property
    def is_ready(self) -> bool:
        return self.predictor is not None


# Module-level singleton — initialised at import time with config only;
# the model is loaded explicitly via ``load_model`` at startup.
_state = AppState()


def get_state() -> AppState:
    """Return the shared application state (FastAPI Depends target)."""
    return _state


# ---------------------------------------------------------------------------
# Pipeline orchestration
# ---------------------------------------------------------------------------

def score_dataframe(
    transactions: pd.DataFrame,
    state: AppState,
) -> pd.DataFrame:
    """Run the full scoring pipeline on a transactions DataFrame.

    Mirrors ``demo_app.main`` exactly so that API results and CLI
    results are identical for the same input.

    Returns a DataFrame with columns:
        transaction_id, user_id, amount, transaction_time,
        rule_score, triggered_rules, behavioral_risk_score,
        model_score, final_score, risk_class
    """
    config = state.config

    if state.predictor is None:
        raise RuntimeError(
            "Model not loaded. Call state.load_model() before scoring."
        )

    # 1. Feature engineering
    builder = FeatureBuilder(config=config.features)
    features = builder.fit_transform(transactions)

    # 2. Rule engine
    engine = RuleEngine(config=config.rules)
    rule_results = engine.evaluate_batch(features)

    # 3. Behavioral risk score (must mirror training pipeline)
    scorer = RiskScorer(config=config.scoring)
    features["behavioral_risk_score"] = features.apply(
        scorer.compute_behavioral_risk_score, axis=1
    ).astype(float)

    # 4. ML model
    model_scores = state.predictor.predict_proba(features)

    # 5. Final scoring
    scored = scorer.assess_batch(features, rule_results, model_scores)

    # 6. Attach human-readable columns from the feature DataFrame
    #    (FeatureBuilder may reorder rows, so we take from features, not
    #    from the original transactions).
    for col in ("user_id", "amount", "transaction_time"):
        if col in features.columns:
            scored[col] = features[col].values

    # Ensure transaction_id exists
    if "transaction_id" not in scored.columns:
        if "transaction_id" in features.columns:
            scored["transaction_id"] = features["transaction_id"].values
        else:
            scored["transaction_id"] = [
                str(uuid.uuid4())[:8] for _ in range(len(scored))
            ]

    # 7. Attach behavioral features for explanation generation
    for col in ('amount_ratio_prev', 'amount_ratio_avg', 'transactions_last_24_h',
                'share_of_total', 'diff_from_avg', 'is_increasing_3'):
        if col in features.columns:
            scored[col] = features[col].values

    # 8. Cache all results by user_id
    state.cache_results(scored)

    return scored

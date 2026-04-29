"""
Inference module for the ML risk model.

Loads a model bundle previously saved by ``src.models.train.save_artifacts``
and produces risk probabilities for new feature rows. This module is
deliberately decoupled from feature engineering and rule evaluation:
it operates on a feature DataFrame that has already been built upstream
(by ``FeatureBuilder`` + ``RiskScorer``), so the same predictor can be
plugged into batch pipelines, online services, or notebooks without
dragging the rest of the stack along.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

import joblib
import pandas as pd
from sklearn.base import BaseEstimator


@dataclass
class RiskPredictor:
    """A trained ML risk model bundled with its expected feature schema."""

    model: BaseEstimator
    feature_columns: List[str]

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, artifacts_path: Path) -> "RiskPredictor":
        """Load a predictor from a joblib bundle written by ``save_artifacts``.

        The bundle is a dict containing at least ``model`` and
        ``feature_columns``. Any additional keys (metrics, model name,
        feature set name) are ignored here — they are useful metadata
        for reporting but not for inference.
        """
        path = Path(artifacts_path)
        if not path.exists():
            raise FileNotFoundError(f"Model artifact not found: {path}")

        bundle = joblib.load(path)

        if not isinstance(bundle, dict):
            raise ValueError(
                f"Unexpected artifact format at {path}: expected a dict bundle, "
                f"got {type(bundle).__name__}."
            )

        try:
            model = bundle["model"]
            feature_columns = list(bundle["feature_columns"])
        except KeyError as exc:
            raise ValueError(
                f"Artifact at {path} is missing required key: {exc.args[0]!r}"
            ) from exc

        return cls(model=model, feature_columns=feature_columns)

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def predict_proba(self, feature_df: pd.DataFrame) -> pd.Series:
        """Return the risk probability for each row of ``feature_df``.

        The input DataFrame must already contain the engineered feature
        columns expected by the trained model. Missing values in those
        columns are filled with 0.0 — matching the training-time
        convention used by ``split_features_and_target`` so that
        train and inference behave identically on first-transaction
        rows where some history features are NaN.
        """
        self._validate_columns(feature_df)

        X = feature_df[self.feature_columns].fillna(0.0).astype(float)
        proba = self.model.predict_proba(X)[:, 1]

        return pd.Series(proba, index=feature_df.index, name="model_score")

    def predict_class(
        self, feature_df: pd.DataFrame, threshold: float = 0.5
    ) -> pd.Series:
        """Return a binary 0/1 prediction per row using ``threshold``."""
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(
                f"threshold must be in [0, 1], got {threshold}"
            )

        proba = self.predict_proba(feature_df)
        return (proba >= threshold).astype(int).rename("model_class")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _validate_columns(self, feature_df: pd.DataFrame) -> None:
        """Raise ``ValueError`` if any expected feature column is missing."""
        missing = [c for c in self.feature_columns if c not in feature_df.columns]
        if missing:
            raise ValueError(
                f"Input feature DataFrame is missing required columns: {missing}. "
                f"Expected: {self.feature_columns}"
            )
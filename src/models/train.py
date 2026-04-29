"""
Training pipeline for the ML risk model.

Wires the feature engineering, rule engine, and behavioral scorer into
a single training-ready DataFrame, then trains and evaluates four
model variants:

* logistic_regression × {baseline features, extended features}
* random_forest × {baseline features, extended features}

The "baseline" set is the minimal raw signal a naive analyst would
reach for; the "extended" set adds all engineered behavioral features
plus the integral ``behavioral_risk_score``. Comparing the two
quantifies the value of the feature engineering work — which is the
core empirical question of the thesis.

The same stratified train/test split is used for all four runs so the
comparison is fair.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import joblib
import pandas as pd
from sklearn.base import BaseEstimator
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.config.settings import AppConfig, get_config
from src.features.feature_builder import FeatureBuilder
from src.rules.rule_engine import RuleEngine
from src.scoring.risk_score import RiskScorer


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SUPPORTED_MODELS: Tuple[str, ...] = ("logistic_regression", "random_forest")
TARGET_COLUMN: str = "is_anomaly"

BASELINE_FEATURE_COLUMNS: List[str] = [
    "amount",
    "running_total",
    "transactions_last_24_h",
    "share_of_total",
]

EXTENDED_FEATURE_COLUMNS: List[str] = [
    "amount",
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
    "behavioral_risk_score",
]


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class TrainingArtifacts:
    """Everything produced by training a single (model, feature set) variant."""

    model_name: str
    feature_set_name: str
    model: BaseEstimator
    feature_columns: List[str]
    metrics: Dict[str, float]

    @property
    def run_id(self) -> str:
        """Stable identifier of the variant for logging and filenames."""
        return f"{self.model_name}__{self.feature_set_name}"


# ---------------------------------------------------------------------------
# Model factory
# ---------------------------------------------------------------------------

def build_model(model_name: str, config: AppConfig) -> BaseEstimator:
    """Instantiate a fresh estimator by name.

    Logistic regression is wrapped in a ``Pipeline`` with a
    ``StandardScaler`` because the raw features span very different
    magnitudes (e.g. ``amount`` in the thousands vs. ``is_increasing_3``
    in {0, 1}); without scaling lbfgs fails to converge and the
    comparison between LR and RF becomes unfair.
    """
    cfg = config.model

    if model_name == "logistic_regression":
        return Pipeline(
            steps=[
                ("scaler", StandardScaler()),
                (
                    "classifier",
                    LogisticRegression(
                        max_iter=cfg.logistic_max_iter,
                        random_state=cfg.random_state,
                        class_weight="balanced",
                    ),
                ),
            ]
        )

    if model_name == "random_forest":
        return RandomForestClassifier(
            n_estimators=cfg.random_forest_n_estimators,
            max_depth=cfg.random_forest_max_depth,
            random_state=cfg.random_state,
            class_weight="balanced",
            n_jobs=-1,
        )

    raise ValueError(
        f"Unsupported model_name {model_name!r}. "
        f"Supported values: {SUPPORTED_MODELS}"
    )


# ---------------------------------------------------------------------------
# Dataset preparation
# ---------------------------------------------------------------------------

def prepare_training_dataset(
    transactions: pd.DataFrame, config: AppConfig
) -> pd.DataFrame:
    """Build a single training-ready DataFrame.

    Steps:

    1. Run :class:`FeatureBuilder` to produce engineered features.
    2. Run :class:`RuleEngine` to attach ``rule_score``.
    3. Compute ``behavioral_risk_score`` per row via :class:`RiskScorer`.
    4. Merge the original ``is_anomaly`` target back by ``transaction_id``.

    The output contains every column needed for both the baseline and
    the extended feature sets, plus the target column.
    """
    if TARGET_COLUMN not in transactions.columns:
        raise ValueError(
            f"Input transactions must contain '{TARGET_COLUMN}' column for training."
        )

    # 1. Feature engineering
    feature_builder = FeatureBuilder(config=config.features)
    features = feature_builder.fit_transform(transactions)

    # 2. Rule engine
    rule_engine = RuleEngine(config=config.rules)
    rule_results = rule_engine.evaluate_batch(features)

    # 3. Behavioral risk score (row-wise; aligned by index)
    scorer = RiskScorer(config=config.scoring)
    behavioral = features.apply(scorer.compute_behavioral_risk_score, axis=1)

    dataset = features.copy()
    dataset["rule_score"] = rule_results["rule_score"]
    dataset["behavioral_risk_score"] = behavioral.astype(float)

    # 4. Merge target back via transaction_id (FeatureBuilder casts it to str)
    target = transactions[["transaction_id", TARGET_COLUMN]].copy()
    target["transaction_id"] = target["transaction_id"].astype(str)
    dataset = dataset.merge(target, on="transaction_id", how="left")

    if dataset[TARGET_COLUMN].isna().any():
        n_missing = int(dataset[TARGET_COLUMN].isna().sum())
        raise ValueError(
            f"Target merge produced {n_missing} unmatched rows — "
            f"check transaction_id consistency between input and FeatureBuilder."
        )

    return dataset


def split_features_and_target(
    df: pd.DataFrame,
    feature_columns: List[str],
    target_column: str = TARGET_COLUMN,
) -> Tuple[pd.DataFrame, pd.Series]:
    """Extract ``(X, y)``, filling NaN feature values with 0.

    NaN values appear naturally in features such as ``previous_amount``
    or ``avg_amount_before`` for the first transaction of each user.
    Filling with 0 is a deliberate choice — it tells the model "no
    history" rather than dropping the rows.
    """
    missing = [c for c in feature_columns if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required feature columns: {missing}")

    X = df[feature_columns].fillna(0.0).astype(float)
    y = df[target_column].astype(int)
    return X, y


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def evaluate_model(
    y_true: pd.Series,
    y_pred: pd.Series,
    y_proba: pd.Series,
) -> Dict[str, float]:
    """Standard binary classification metrics for a fitted model."""
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, y_proba)),
    }


# ---------------------------------------------------------------------------
# Single-variant training
# ---------------------------------------------------------------------------

def train_one_model(
    dataset: pd.DataFrame,
    model_name: str,
    feature_columns: List[str],
    feature_set_name: str,
    config: AppConfig,
) -> TrainingArtifacts:
    """Fit one model on one feature set and return its artifacts."""
    X, y = split_features_and_target(dataset, feature_columns)

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=config.model.test_size,
        random_state=config.model.random_state,
        stratify=y,
    )

    model = build_model(model_name, config)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]
    metrics = evaluate_model(y_test, y_pred, y_proba)

    return TrainingArtifacts(
        model_name=model_name,
        feature_set_name=feature_set_name,
        model=model,
        feature_columns=list(feature_columns),
        metrics=metrics,
    )


# ---------------------------------------------------------------------------
# Full sweep
# ---------------------------------------------------------------------------

def train_all_models(
    transactions: pd.DataFrame,
    config: AppConfig | None = None,
) -> Dict[str, Any]:
    """Train all four (model × feature set) variants and pick the best.

    Returns a dict with:

    * ``runs`` — mapping ``run_id -> TrainingArtifacts``
    * ``best_run_id`` — id of the run with the highest ROC-AUC
    * ``best_artifacts`` — its :class:`TrainingArtifacts`
    * ``leaderboard`` — DataFrame with one row per run, sorted by ROC-AUC
    """
    config = config or get_config()
    dataset = prepare_training_dataset(transactions, config)

    plan: List[Tuple[str, List[str], str]] = [
        ("logistic_regression", BASELINE_FEATURE_COLUMNS, "baseline"),
        ("logistic_regression", EXTENDED_FEATURE_COLUMNS, "extended"),
        ("random_forest", BASELINE_FEATURE_COLUMNS, "baseline"),
        ("random_forest", EXTENDED_FEATURE_COLUMNS, "extended"),
    ]

    runs: Dict[str, TrainingArtifacts] = {}
    for model_name, columns, feature_set_name in plan:
        artifacts = train_one_model(
            dataset=dataset,
            model_name=model_name,
            feature_columns=columns,
            feature_set_name=feature_set_name,
            config=config,
        )
        runs[artifacts.run_id] = artifacts

    leaderboard = pd.DataFrame(
        [
            {
                "run_id": run_id,
                "model_name": art.model_name,
                "feature_set": art.feature_set_name,
                **art.metrics,
            }
            for run_id, art in runs.items()
        ]
    ).sort_values("roc_auc", ascending=False).reset_index(drop=True)

    best_run_id = leaderboard.iloc[0]["run_id"]

    return {
        "runs": runs,
        "best_run_id": best_run_id,
        "best_artifacts": runs[best_run_id],
        "leaderboard": leaderboard,
    }


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_artifacts(artifacts: TrainingArtifacts, output_dir: Path) -> Path:
    """Persist a fitted model bundle via joblib.

    Saves a single file containing the model, the exact feature
    columns used at training time (so inference can match the schema),
    and the test-set metrics for traceability.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    path = output_dir / f"{artifacts.run_id}.joblib"
    bundle = {
        "model": artifacts.model,
        "feature_columns": artifacts.feature_columns,
        "metrics": artifacts.metrics,
        "model_name": artifacts.model_name,
        "feature_set_name": artifacts.feature_set_name,
    }
    joblib.dump(bundle, path)
    return path

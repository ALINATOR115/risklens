"""
Feature importance and coefficient analysis for the trained risk models.

Runs the full training sweep, extracts:

* ``feature_importances_`` from the random forest (extended features)
* coefficients from the logistic regression classifier inside its
  ``Pipeline(StandardScaler + LogisticRegression)`` (extended features)

and saves both as CSVs for further analysis. Logistic regression
coefficients are read from the *scaled* feature space, which is what
makes them directly comparable in magnitude — unscaled coefficients
would just reflect the spread of each feature, not its importance.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from src.config.settings import get_config
from src.models.train import TrainingArtifacts, train_all_models


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

INPUT_CSV = PROJECT_ROOT / "data" / "raw" / "synthetic_transactions.csv"
RF_OUTPUT_CSV = PROJECT_ROOT / "outputs" / "rf_feature_importance.csv"
LR_OUTPUT_CSV = PROJECT_ROOT / "outputs" / "lr_feature_coefficients.csv"

# ---------------------------------------------------------------------------
# Extractors
# ---------------------------------------------------------------------------

def extract_rf_importance(artifacts: TrainingArtifacts) -> pd.DataFrame:
    """Build a sorted DataFrame of random-forest feature importances."""
    importances = artifacts.model.feature_importances_
    df = pd.DataFrame(
        {
            "feature": artifacts.feature_columns,
            "importance": importances,
        }
    )
    return df.sort_values("importance", ascending=False).reset_index(drop=True)


def extract_lr_coefficients(artifacts: TrainingArtifacts) -> pd.DataFrame:
    """Build a sorted DataFrame of logistic-regression coefficients.

    The model is a ``Pipeline(StandardScaler + LogisticRegression)``,
    so we need to drill into the named ``classifier`` step. Coefficients
    live in the scaled space, which is exactly what we want for
    cross-feature comparison: a coefficient of magnitude 0.5 means the
    same thing for ``amount`` (originally in the thousands) and for
    ``is_increasing_3`` (originally in {0, 1}).
    """
    model = artifacts.model
    if not isinstance(model, Pipeline):
        raise TypeError(
            f"Expected a sklearn Pipeline for logistic regression, got {type(model).__name__}"
        )

    classifier = model.named_steps.get("classifier")
    if not isinstance(classifier, LogisticRegression):
        raise TypeError(
            f"Expected a LogisticRegression in the 'classifier' step, "
            f"got {type(classifier).__name__}"
        )

    coefficients = classifier.coef_[0]
    df = pd.DataFrame(
        {
            "feature": artifacts.feature_columns,
            "coefficient": coefficients,
            "abs_coefficient": pd.Series(coefficients).abs(),
        }
    )
    return df.sort_values("abs_coefficient", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    config = get_config()

    print("Loading transactions and training all model variants...")
    transactions = pd.read_csv(INPUT_CSV, parse_dates=["transaction_time"])
    results = train_all_models(transactions, config)

    print()
    print("=== leaderboard ===")
    print(results["leaderboard"].to_string(index=False))

    rf_artifacts = results["runs"]["random_forest__extended"]
    lr_artifacts = results["runs"]["logistic_regression__extended"]

    rf_importance = extract_rf_importance(rf_artifacts)
    lr_coefficients = extract_lr_coefficients(lr_artifacts)

    print()
    print("=== random_forest__extended — feature importance ===")
    print(rf_importance.to_string(index=False))

    print()
    print("=== logistic_regression__extended — coefficients (scaled features) ===")
    print(lr_coefficients.to_string(index=False))

    RF_OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    rf_importance.to_csv(RF_OUTPUT_CSV, index=False)
    lr_coefficients.to_csv(LR_OUTPUT_CSV, index=False)

    print()
    print(f"Saved RF importance to: {RF_OUTPUT_CSV.resolve()}")
    print(f"Saved LR coefficients to: {LR_OUTPUT_CSV.resolve()}")


if __name__ == "__main__":
    main()
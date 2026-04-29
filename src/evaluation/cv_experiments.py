"""
Cross-validation and ablation experiments.

Runs stratified 5-fold CV on all model × feature-set variants,
including an ablation variant that removes ``behavioral_risk_score``
from the extended set to isolate its contribution.

Usage::

    python -m src.evaluation.cv_experiments          # synthetic data
    python -m src.evaluation.cv_experiments --paysim  # PaySim data
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
from sklearn.metrics import (
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold

from src.config.settings import AppConfig, get_config
from src.models.train import (
    BASELINE_FEATURE_COLUMNS,
    EXTENDED_FEATURE_COLUMNS,
    TARGET_COLUMN,
    build_model,
    prepare_training_dataset,
    split_features_and_target,
)


# ---------------------------------------------------------------------------
# Feature sets (including ablation)
# ---------------------------------------------------------------------------

EXTENDED_WITHOUT_BRS_COLUMNS: List[str] = [
    c for c in EXTENDED_FEATURE_COLUMNS if c != "behavioral_risk_score"
]

FEATURE_SETS: Dict[str, List[str]] = {
    "baseline": BASELINE_FEATURE_COLUMNS,
    "extended": EXTENDED_FEATURE_COLUMNS,
    "extended_no_brs": EXTENDED_WITHOUT_BRS_COLUMNS,
}

MODEL_NAMES: Tuple[str, ...] = ("logistic_regression", "random_forest")

N_FOLDS: int = 5


# ---------------------------------------------------------------------------
# Single-fold evaluation
# ---------------------------------------------------------------------------

def evaluate_fold(
    model_name: str,
    feature_columns: List[str],
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    config: AppConfig,
) -> Dict[str, float]:
    """Fit a model on one fold and return test-set metrics."""
    model = build_model(model_name, config)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    return {
        "roc_auc": float(roc_auc_score(y_test, y_proba)),
        "f1": float(f1_score(y_test, y_pred, zero_division=0)),
        "precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "recall": float(recall_score(y_test, y_pred, zero_division=0)),
    }


# ---------------------------------------------------------------------------
# Full cross-validation sweep
# ---------------------------------------------------------------------------

def run_cv(
    transactions: pd.DataFrame,
    config: AppConfig | None = None,
    n_folds: int = N_FOLDS,
) -> pd.DataFrame:
    """Run stratified k-fold CV over all (model × feature set) variants.

    Returns a DataFrame with one row per variant: mean and std for each
    metric, plus fold count.
    """
    config = config or get_config()
    dataset = prepare_training_dataset(transactions, config)

    skf = StratifiedKFold(
        n_splits=n_folds,
        shuffle=True,
        random_state=config.model.random_state,
    )

    all_results: List[dict] = []

    for model_name in MODEL_NAMES:
        for fs_name, fs_columns in FEATURE_SETS.items():
            X, y = split_features_and_target(dataset, fs_columns)
            fold_metrics: List[Dict[str, float]] = []

            for train_idx, test_idx in skf.split(X, y):
                X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
                y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

                metrics = evaluate_fold(
                    model_name, fs_columns,
                    X_train, y_train, X_test, y_test, config,
                )
                fold_metrics.append(metrics)

            metrics_df = pd.DataFrame(fold_metrics)
            row = {
                "model": model_name,
                "features": fs_name,
                "n_folds": n_folds,
            }
            for col in metrics_df.columns:
                row[f"{col}_mean"] = metrics_df[col].mean()
                row[f"{col}_std"] = metrics_df[col].std()
            all_results.append(row)

    results = pd.DataFrame(all_results)
    results = results.sort_values("roc_auc_mean", ascending=False).reset_index(drop=True)
    return results


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def print_results(results: pd.DataFrame) -> None:
    """Pretty-print the leaderboard."""
    print(f"=== {results.iloc[0]['n_folds']}-fold cross-validation ===")
    print()

    display_cols = ["model", "features"]
    for metric in ["roc_auc", "f1", "precision", "recall"]:
        results[metric] = results.apply(
            lambda r: f"{r[f'{metric}_mean']:.4f} ± {r[f'{metric}_std']:.4f}",
            axis=1,
        )
        display_cols.append(metric)

    print(results[display_cols].to_string(index=False))
    print()

    # Ablation comparison
    for model_name in MODEL_NAMES:
        ext = results[
            (results["model"] == model_name) & (results["features"] == "extended")
        ]
        no_brs = results[
            (results["model"] == model_name) & (results["features"] == "extended_no_brs")
        ]
        if ext.empty or no_brs.empty:
            continue
        delta = ext.iloc[0]["roc_auc_mean"] - no_brs.iloc[0]["roc_auc_mean"]
        print(
            f"Ablation [{model_name}]: "
            f"extended={ext.iloc[0]['roc_auc_mean']:.4f}, "
            f"extended_no_brs={no_brs.iloc[0]['roc_auc_mean']:.4f}, "
            f"delta={delta:+.4f}"
        )
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="CV + ablation experiments")
    parser.add_argument(
        "--paysim", action="store_true",
        help="Use PaySim instead of synthetic data",
    )
    parser.add_argument(
        "--ieee", action="store_true",
        help="Use IEEE-CIS instead of synthetic data",
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Save results CSV to this path",
    )
    args = parser.parse_args()

    if args.ieee:
        csv_path = Path("data/processed/ieee_cis_prepared.csv")
    elif args.paysim:
        csv_path = Path("data/processed/paysim_prepared.csv")
    else:
        csv_path = Path("data/raw/synthetic_transactions.csv")

    if not csv_path.exists():
        raise FileNotFoundError(f"Dataset not found: {csv_path.resolve()}")

    config = get_config()
    transactions = pd.read_csv(csv_path, parse_dates=["transaction_time"])
    print(f"Loaded {len(transactions)} transactions from {csv_path}")
    print(f"Anomaly share: {transactions['is_anomaly'].mean():.2%}")
    print()

    results = run_cv(transactions, config)
    print_results(results)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        results.to_csv(out_path, index=False)
        print(f"Saved to: {out_path.resolve()}")


if __name__ == "__main__":
    main()

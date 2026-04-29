"""
Paired t-tests on IEEE-CIS fold-level data.

Run after cv_experiments.py has completed.
Usage: python -m src.evaluation.statistical_tests --ieee
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold

from src.config.settings import get_config
from src.models.train import (
    BASELINE_FEATURE_COLUMNS,
    EXTENDED_FEATURE_COLUMNS,
    build_model,
    prepare_training_dataset,
    split_features_and_target,
)


EXTENDED_NO_BRS = [c for c in EXTENDED_FEATURE_COLUMNS if c != "behavioral_risk_score"]


def collect_fold_aucs(
    dataset: pd.DataFrame, config, n_folds: int = 5
) -> dict[str, np.ndarray]:
    """Return per-fold ROC-AUC for every variant."""
    variants = {
        "rf_base": ("random_forest", BASELINE_FEATURE_COLUMNS),
        "rf_ext": ("random_forest", EXTENDED_FEATURE_COLUMNS),
        "rf_ext_no_brs": ("random_forest", EXTENDED_NO_BRS),
        "lr_base": ("logistic_regression", BASELINE_FEATURE_COLUMNS),
        "lr_ext": ("logistic_regression", EXTENDED_FEATURE_COLUMNS),
        "lr_ext_no_brs": ("logistic_regression", EXTENDED_NO_BRS),
    }

    skf = StratifiedKFold(
        n_splits=n_folds, shuffle=True, random_state=config.model.random_state
    )
    fold_aucs: dict[str, list[float]] = {k: [] for k in variants}

    for name, (model_name, cols) in variants.items():
        X, y = split_features_and_target(dataset, cols)
        for train_idx, test_idx in skf.split(X, y):
            model = build_model(model_name, config)
            model.fit(X.iloc[train_idx], y.iloc[train_idx])
            proba = model.predict_proba(X.iloc[test_idx])[:, 1]
            fold_aucs[name].append(roc_auc_score(y.iloc[test_idx], proba))
        print(f"  {name}: done")

    return {k: np.array(v) for k, v in fold_aucs.items()}


def run_tests(fold_aucs: dict[str, np.ndarray]) -> None:
    print("\n=== Per-fold ROC-AUC ===")
    for k, v in fold_aucs.items():
        print(f"  {k:20s}: {v.round(4)}  mean={v.mean():.4f}")

    print("\n=== PAIRED T-TESTS: baseline -> extended ===\n")
    for prefix, label in [("rf", "Random Forest"), ("lr", "Logistic Regression")]:
        base = fold_aucs[f"{prefix}_base"]
        ext = fold_aucs[f"{prefix}_ext"]
        diff = ext - base
        t, p = stats.ttest_rel(ext, base)
        print(f"{label}: baseline -> extended")
        print(f"  deltas: {diff.round(4)}")
        print(f"  mean delta: {diff.mean():+.4f}")
        print(f"  t={t:.3f}, p={p:.6f}")
        print(f"  all folds positive: {(diff > 0).all()}")
        print()

    print("=== PAIRED T-TEST: LR extended vs RF baseline ===\n")
    diff = fold_aucs["lr_ext"] - fold_aucs["rf_base"]
    t, p = stats.ttest_rel(fold_aucs["lr_ext"], fold_aucs["rf_base"])
    print(f"  deltas: {diff.round(4)}")
    print(f"  mean delta: {diff.mean():+.4f}")
    print(f"  t={t:.3f}, p={p:.6f}")
    print()

    print("=== ABLATION: extended vs extended_no_brs ===\n")
    for prefix, label in [("rf", "Random Forest"), ("lr", "Logistic Regression")]:
        ext = fold_aucs[f"{prefix}_ext"]
        no_brs = fold_aucs[f"{prefix}_ext_no_brs"]
        diff = ext - no_brs
        t, p = stats.ttest_rel(ext, no_brs)
        print(f"{label}: extended vs no_brs")
        print(f"  deltas: {diff.round(4)}")
        print(f"  mean delta: {diff.mean():+.4f}")
        print(f"  t={t:.3f}, p={p:.6f}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ieee", action="store_true")
    parser.add_argument("--paysim", action="store_true")
    args = parser.parse_args()

    if args.ieee:
        csv_path = Path("data/processed/ieee_cis_prepared.csv")
    elif args.paysim:
        csv_path = Path("data/processed/paysim_prepared.csv")
    else:
        csv_path = Path("data/raw/synthetic_transactions.csv")

    config = get_config()
    transactions = pd.read_csv(csv_path, parse_dates=["transaction_time"])
    print(f"Loaded {len(transactions)} transactions from {csv_path}")

    print("Preparing dataset...")
    dataset = prepare_training_dataset(transactions, config)

    print("Running 5-fold CV for all variants...")
    fold_aucs = collect_fold_aucs(dataset, config)
    run_tests(fold_aucs)


if __name__ == "__main__":
    main()

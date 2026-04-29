"""
History depth analysis on IEEE-CIS.

Splits users into buckets by transaction count and measures the
ROC-AUC improvement from extended features in each bucket.

This quantifies the central thesis: the deeper the user history,
the larger the benefit of behavioral feature engineering.

Usage: python -m src.evaluation.history_depth_analysis
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

import pandas as pd
import numpy as np
from sklearn.metrics import roc_auc_score

from src.config.settings import get_config
from src.models.train import (
    BASELINE_FEATURE_COLUMNS,
    EXTENDED_FEATURE_COLUMNS,
    build_model,
    prepare_training_dataset,
    split_features_and_target,
)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

IEEE_PATH = Path("data/processed/ieee_cis_prepared.csv")
OUTPUT_PATH = Path("outputs/history_depth_analysis.csv")

# Bucket boundaries: [5, 10), [10, 25), [25, 50), [50, 100), [100, +∞)
BUCKET_EDGES: List[int] = [5, 10, 25, 50, 100]


# ---------------------------------------------------------------------------
# Logic
# ---------------------------------------------------------------------------

def make_buckets(
    dataset: pd.DataFrame, edges: List[int]
) -> List[Tuple[str, pd.Index]]:
    """Assign each row to a bucket based on user's total transaction count."""
    user_counts = dataset.groupby("user_id")["transaction_id"].transform("count")
    buckets: List[Tuple[str, pd.Index]] = []

    for i, lo in enumerate(edges):
        hi = edges[i + 1] if i + 1 < len(edges) else None
        if hi is not None:
            label = f"{lo}–{hi - 1}"
            mask = (user_counts >= lo) & (user_counts < hi)
        else:
            label = f"{lo}+"
            mask = user_counts >= lo
        idx = dataset.index[mask]
        if len(idx) > 0:
            buckets.append((label, idx))

    return buckets


def evaluate_bucket(
    dataset: pd.DataFrame,
    train_idx: pd.Index,
    test_idx: pd.Index,
    model_name: str,
    feature_columns: List[str],
    config,
) -> float:
    """Train on train_idx, evaluate ROC-AUC on test_idx."""
    X, y = split_features_and_target(dataset, feature_columns)
    model = build_model(model_name, config)
    model.fit(X.loc[train_idx], y.loc[train_idx])
    proba = model.predict_proba(X.loc[test_idx])[:, 1]
    y_test = y.loc[test_idx]
    if y_test.nunique() < 2:
        return float("nan")
    return float(roc_auc_score(y_test, proba))


def run_analysis(dataset: pd.DataFrame, config) -> pd.DataFrame:
    """For each bucket, train on everything else, test on bucket rows."""
    buckets = make_buckets(dataset, BUCKET_EDGES)
    all_idx = dataset.index
    rows = []

    for label, bucket_idx in buckets:
        train_idx = all_idx.difference(bucket_idx)
        n_rows = len(bucket_idx)
        n_fraud = int(dataset.loc[bucket_idx, "is_anomaly"].sum())
        n_users = dataset.loc[bucket_idx, "user_id"].nunique()
        median_txn = int(
            dataset.loc[bucket_idx]
            .groupby("user_id")["transaction_id"]
            .count()
            .median()
        )

        print(f"  bucket {label}: {n_rows} rows, {n_fraud} fraud, "
              f"{n_users} users, median {median_txn} txn/user")

        for model_name in ["random_forest"]:
            auc_base = evaluate_bucket(
                dataset, train_idx, bucket_idx,
                model_name, BASELINE_FEATURE_COLUMNS, config,
            )
            auc_ext = evaluate_bucket(
                dataset, train_idx, bucket_idx,
                model_name, EXTENDED_FEATURE_COLUMNS, config,
            )
            delta = auc_ext - auc_base if not (
                np.isnan(auc_base) or np.isnan(auc_ext)
            ) else float("nan")

            rows.append({
                "bucket": label,
                "n_transactions": n_rows,
                "n_fraud": n_fraud,
                "n_users": n_users,
                "median_txn_per_user": median_txn,
                "model": model_name,
                "roc_auc_baseline": round(auc_base, 4),
                "roc_auc_extended": round(auc_ext, 4),
                "delta": round(delta, 4),
            })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not IEEE_PATH.exists():
        raise FileNotFoundError(f"Dataset not found: {IEEE_PATH.resolve()}")

    config = get_config()
    transactions = pd.read_csv(IEEE_PATH, parse_dates=["transaction_time"])
    print(f"Loaded {len(transactions)} transactions")

    print("Preparing dataset...")
    dataset = prepare_training_dataset(transactions, config)

    print("Running history depth analysis...")
    results = run_analysis(dataset, config)

    print()
    print("=== RESULTS ===")
    print(results.to_string(index=False))

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(OUTPUT_PATH, index=False)
    print(f"\nSaved to: {OUTPUT_PATH.resolve()}")


if __name__ == "__main__":
    main()

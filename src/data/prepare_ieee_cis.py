"""
Prepare the IEEE-CIS Fraud Detection dataset for the risk scoring pipeline.

The IEEE-CIS dataset originates from Vesta Corporation and contains
real-world e-commerce transaction data. This script maps it onto the
columns expected by ``FeatureBuilder``.

Key mapping decisions:

* ``card1`` → ``user_id``.  card1 is a payment-card identifier with
  ~13 000 unique values across ~590 000 transactions, yielding an
  average of ~45 transactions per "user" — sufficient history for
  behavioral features.
* ``TransactionDT`` → ``transaction_time``.  TransactionDT is seconds
  from an undisclosed reference point; we anchor it to an arbitrary
  start date and convert to datetime.
* ``TransactionAmt`` → ``amount``.
* ``isFraud`` → ``is_anomaly``.

Download the data from:
    https://www.kaggle.com/c/ieee-fraud-detection/data
Place ``train_transaction.csv`` at ``data/raw/ieee_cis_train.csv``.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

RAW_PATH = Path("data/raw/ieee_cis_train.csv")
OUTPUT_PATH = Path("data/processed/ieee_cis_prepared.csv")
START_DATE = pd.Timestamp("2024-01-01")

# Users with fewer transactions than this threshold are dropped —
# behavioral features need history to be meaningful.
MIN_TRANSACTIONS_PER_USER: int = 5

# Optional: limit total rows for faster iteration (None = keep all).
MAX_ROWS: int | None = None

RANDOM_SEED: int = 42


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def load_raw(path: Path, max_rows: int | None = None) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"IEEE-CIS file not found: {path.resolve()}. "
            f"Download train_transaction.csv from "
            f"https://www.kaggle.com/c/ieee-fraud-detection/data "
            f"and place it at {path}."
        )
    cols = [
        "TransactionID", "TransactionDT", "TransactionAmt",
        "isFraud", "card1", "card2", "card4", "card6",
        "ProductCD", "addr1", "P_emaildomain",
    ]
    return pd.read_csv(path, usecols=cols, nrows=max_rows)


def map_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Map IEEE-CIS schema onto the pipeline's expected columns."""
    out = pd.DataFrame()
    out["transaction_id"] = "txn_" + df["TransactionID"].astype(str)
    out["user_id"] = "card_" + df["card1"].astype(int).astype(str)
    out["transaction_time"] = START_DATE + pd.to_timedelta(
        df["TransactionDT"], unit="s"
    )
    out["amount"] = df["TransactionAmt"].astype(float)
    out["is_anomaly"] = df["isFraud"].astype(int)

    # Preserve extra columns for potential future use.
    for col in ["ProductCD", "card2", "card4", "card6", "addr1", "P_emaildomain"]:
        if col in df.columns:
            out[col] = df[col].values

    return out


def filter_users(df: pd.DataFrame, min_txn: int) -> pd.DataFrame:
    """Keep only users with at least ``min_txn`` transactions.

    This ensures behavioral features (previous_amount, avg_amount_before,
    etc.) are computed from meaningful history rather than being NaN
    for almost every row.
    """
    counts = df.groupby("user_id")["transaction_id"].transform("count")
    filtered = df[counts >= min_txn].copy()
    return filtered.sort_values("transaction_time").reset_index(drop=True)


def prepare_ieee_cis(
    raw_path: Path = RAW_PATH,
    output_path: Path = OUTPUT_PATH,
    min_txn: int = MIN_TRANSACTIONS_PER_USER,
    max_rows: int | None = MAX_ROWS,
) -> pd.DataFrame:
    """End-to-end: load, map, filter, save."""
    raw = load_raw(raw_path, max_rows=max_rows)
    mapped = map_columns(raw)
    filtered = filter_users(mapped, min_txn=min_txn)

    # Reassign transaction_id to be contiguous after filtering.
    filtered["transaction_id"] = [f"txn_{i:07d}" for i in range(len(filtered))]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    filtered.to_csv(output_path, index=False)
    return filtered


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    df = prepare_ieee_cis()
    n_users = df["user_id"].nunique()
    txn_per_user = df.groupby("user_id").size()

    print(f"Saved to: {OUTPUT_PATH.resolve()}")
    print(f"Shape: {df.shape}")
    print(f"Unique users: {n_users}")
    print(f"Anomaly share: {df['is_anomaly'].mean():.2%}")
    print(f"Transactions per user: "
          f"median={txn_per_user.median():.0f}, "
          f"mean={txn_per_user.mean():.1f}, "
          f"p95={txn_per_user.quantile(0.95):.0f}")
    print()
    print("is_anomaly value_counts:")
    print(df["is_anomaly"].value_counts())
    if "ProductCD" in df.columns:
        print()
        print("ProductCD distribution:")
        print(df["ProductCD"].value_counts())


if __name__ == "__main__":
    main()

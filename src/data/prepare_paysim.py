"""
Prepare the PaySim dataset for the risk scoring pipeline.

PaySim (Lopez-Rojas et al., 2016) is a synthetic mobile-money
transaction simulator. This script maps its schema onto the columns
expected by ``FeatureBuilder`` and downstream modules.

Key transformations:

* ``step`` (integer hour) → ``transaction_time`` (datetime)
* ``nameOrig`` → ``user_id``
* ``isFraud`` → ``is_anomaly``

An optional downsampling step keeps all fraud rows and a configurable
fraction of normal rows, which makes experimentation on the full
6.3M-row file tractable without a cluster.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.evaluation.feature_importance_analysis import PROJECT_ROOT

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_PATH = PROJECT_ROOT/ "data" / "raw" / "paysim.csv"
OUTPUT_PATH = PROJECT_ROOT/ "data" / "processed" / "paysim_prepared.csv"
START_DATE = pd.Timestamp("2024-01-01")

# Keep all fraud rows; sample this fraction of normal rows.
# Set to 1.0 to keep everything (slow on 6.3M rows).
NORMAL_SAMPLE_FRACTION: float = 0.05
RANDOM_SEED: int = 42


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def load_raw(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"PaySim file not found: {path.resolve()}. "
            f"Download it from https://www.kaggle.com/datasets/ealaxi/paysim1 "
            f"and place the CSV at {path}."
        )
    return pd.read_csv(path)


def map_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Map PaySim schema onto the pipeline's expected columns."""
    out = pd.DataFrame()
    out["transaction_id"] = [f"txn_{i:07d}" for i in range(len(df))]
    out["user_id"] = df["nameOrig"].values
    out["transaction_time"] = START_DATE + pd.to_timedelta(df["step"].values, unit="h")
    out["amount"] = df["amount"].values
    out["is_anomaly"] = df["isFraud"].astype(int).values

    # Preserve useful PaySim-specific columns for future use.
    for col in ["type", "oldbalanceOrg", "newbalanceOrig", "nameDest",
                "oldbalanceDest", "newbalanceDest"]:
        if col in df.columns:
            out[col] = df[col].values

    return out


def downsample(df: pd.DataFrame, frac: float, seed: int) -> pd.DataFrame:
    """Keep all anomaly rows; sample ``frac`` of normal rows."""
    if frac >= 1.0:
        return df
    anomalies = df[df["is_anomaly"] == 1]
    normals = df[df["is_anomaly"] == 0].sample(frac=frac, random_state=seed)
    combined = pd.concat([anomalies, normals], ignore_index=True)
    return combined.sort_values("transaction_time", kind="mergesort").reset_index(drop=True)


def prepare_paysim(
    raw_path: Path = RAW_PATH,
    output_path: Path = OUTPUT_PATH,
    normal_frac: float = NORMAL_SAMPLE_FRACTION,
    seed: int = RANDOM_SEED,
) -> pd.DataFrame:
    """End-to-end: load, map, downsample, save."""
    raw = load_raw(raw_path)
    mapped = map_columns(raw)
    sampled = downsample(mapped, frac=normal_frac, seed=seed)

    # Re-assign transaction_id after sampling so IDs are contiguous.
    sampled["transaction_id"] = [f"txn_{i:07d}" for i in range(len(sampled))]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    sampled.to_csv(output_path, index=False)
    return sampled


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    df = prepare_paysim()
    print(f"Saved to: {OUTPUT_PATH.resolve()}")
    print(f"Shape: {df.shape}")
    print(f"Anomaly share: {df['is_anomaly'].mean():.4%}")
    print(f"Unique users: {df['user_id'].nunique()}")
    print()
    print("is_anomaly value_counts:")
    print(df["is_anomaly"].value_counts())
    print()
    print("type distribution:")
    if "type" in df.columns:
        print(df["type"].value_counts())


if __name__ == "__main__":
    main()

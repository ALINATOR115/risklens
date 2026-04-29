from pathlib import Path
from typing import Any

import pandas as pd


def read_transactions(path: Path) -> pd.DataFrame:
    """Load a transactions file (CSV or Parquet) into a DataFrame."""
    path = Path(path)

    if path.suffix.lower() == ".parquet":
        df = pd.read_parquet(path)
    elif path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    else:
        raise ValueError(f"Unsupported transactions file format: {path.suffix}")

    if "transaction_time" in df.columns:
        df["transaction_time"] = pd.to_datetime(df["transaction_time"])
    elif "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])

    return df


def write_dataframe(df: pd.DataFrame, path: Path) -> None:
    """Persist a DataFrame to CSV or Parquet based on file extension."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.suffix.lower() == ".parquet":
        df.to_parquet(path, index=False)
    elif path.suffix.lower() == ".csv":
        df.to_csv(path, index=False)
    else:
        raise ValueError(f"Unsupported output file format: {path.suffix}")


def save_artifact(obj: Any, path: Path) -> None:
    """Serialize a Python object with joblib."""
    import joblib

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(obj, path)


def load_artifact(path: Path) -> Any:
    """Deserialize a joblib artifact."""
    import joblib

    return joblib.load(Path(path))
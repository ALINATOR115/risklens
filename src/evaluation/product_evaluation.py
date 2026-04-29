"""
End-to-end product evaluation.

Evaluates the full risk scoring pipeline as a black box: it takes the
ground-truth transactions and the scored output produced by
``demo_app.py`` and reports how well the system separates anomalies
from normal activity.

Two binary decision modes are reported:

* **strict** — only ``high_risk`` is treated as a positive prediction.
  Optimizes precision; the operating point an analyst would use when
  alert volume must be tightly controlled.
* **lenient** — both ``medium_risk`` and ``high_risk`` are positive.
  Optimizes recall; the operating point for "review queue" workflows.

Top-K precision is also reported because in a real fraud-review setting
analysts work down a ranked queue, and "how clean is the top of the
list" is often a more honest quality metric than threshold-based F1.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_TRANSACTIONS_PATH = PROJECT_ROOT / "data" / "raw" / "synthetic_transactions.csv"
SCORED_OUTPUT_PATH = PROJECT_ROOT / "outputs" / "final_risk_scores.csv"
MERGED_OUTPUT_PATH = PROJECT_ROOT / "outputs" / "product_evaluation_merged.csv"
TOP_K_VALUES: List[int] = [20, 50, 100]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class BinaryMetrics:
    """Standard binary classification metrics for one decision mode."""

    mode: str
    accuracy: float
    precision: float
    recall: float
    f1: float
    confusion: pd.DataFrame  # 2x2 with row=true, col=pred
    n_positive_pred: int
    n_positive_true: int


# ---------------------------------------------------------------------------
# IO
# ---------------------------------------------------------------------------

def load_inputs(
    raw_path: Path = RAW_TRANSACTIONS_PATH,
    scored_path: Path = SCORED_OUTPUT_PATH,
) -> pd.DataFrame:
    """Load raw transactions and scored output and merge by transaction_id."""
    if not raw_path.exists():
        raise FileNotFoundError(
            f"Raw transactions file not found: {raw_path.resolve()}"
        )
    if not scored_path.exists():
        raise FileNotFoundError(
            f"Scored output file not found: {scored_path.resolve()}. "
            f"Run demo_app.py first."
        )

    raw = pd.read_csv(raw_path)
    scored = pd.read_csv(scored_path)

    if "transaction_id" not in raw.columns or "transaction_id" not in scored.columns:
        raise ValueError("Both files must contain a 'transaction_id' column.")

    merged = scored.merge(
        raw[["transaction_id", "is_anomaly"]],
        on="transaction_id",
        how="left",
        validate="one_to_one",
    )

    if merged["is_anomaly"].isna().any():
        n_missing = int(merged["is_anomaly"].isna().sum())
        raise ValueError(
            f"Merge produced {n_missing} unmatched rows — check that the scored "
            f"output corresponds to the same transactions file."
        )

    merged["is_anomaly"] = merged["is_anomaly"].astype(int)
    return merged


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def compute_binary_metrics(
    merged: pd.DataFrame, mode: str, positive_classes: List[str]
) -> BinaryMetrics:
    """Build binary predictions from risk_class and compute metrics."""
    y_true = merged["is_anomaly"].astype(int)
    y_pred = merged["risk_class"].isin(positive_classes).astype(int)

    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    cm_df = pd.DataFrame(
        cm,
        index=["true_normal", "true_anomaly"],
        columns=["pred_normal", "pred_positive"],
    )

    return BinaryMetrics(
        mode=mode,
        accuracy=float(accuracy_score(y_true, y_pred)),
        precision=float(precision_score(y_true, y_pred, zero_division=0)),
        recall=float(recall_score(y_true, y_pred, zero_division=0)),
        f1=float(f1_score(y_true, y_pred, zero_division=0)),
        confusion=cm_df,
        n_positive_pred=int(y_pred.sum()),
        n_positive_true=int(y_true.sum()),
    )


def compute_top_k_precision(
    merged: pd.DataFrame, k_values: List[int]
) -> pd.DataFrame:
    """Precision in the top-K rows ranked by ``final_score`` (descending)."""
    ranked = merged.sort_values("final_score", ascending=False)
    rows = []
    for k in k_values:
        if k > len(ranked):
            continue
        head = ranked.head(k)
        hits = int(head["is_anomaly"].sum())
        rows.append(
            {
                "k": k,
                "hits": hits,
                "precision_at_k": hits / k,
            }
        )
    return pd.DataFrame(rows)


def compute_crosstab(merged: pd.DataFrame) -> pd.DataFrame:
    """Cross-tab of true label vs predicted risk class."""
    return pd.crosstab(
        merged["is_anomaly"],
        merged["risk_class"],
        rownames=["is_anomaly"],
        colnames=["risk_class"],
    )


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_binary_metrics(metrics: BinaryMetrics) -> None:
    print(f"--- mode: {metrics.mode} ---")
    print(
        f"  positives: predicted={metrics.n_positive_pred}, "
        f"true={metrics.n_positive_true}"
    )
    print(f"  accuracy : {metrics.accuracy:.4f}")
    print(f"  precision: {metrics.precision:.4f}")
    print(f"  recall   : {metrics.recall:.4f}")
    print(f"  f1       : {metrics.f1:.4f}")
    print("  confusion matrix:")
    print(metrics.confusion.to_string())
    print()


def print_report(
    merged: pd.DataFrame,
    crosstab: pd.DataFrame,
    binary: Dict[str, BinaryMetrics],
    top_k: pd.DataFrame,
) -> None:
    print(f"Merged evaluation rows: {len(merged)}")
    print(f"Anomaly base rate: {merged['is_anomaly'].mean():.2%}")
    print()

    print("=== crosstab(is_anomaly, risk_class) ===")
    print(crosstab.to_string())
    print()

    print("=== binary metrics ===")
    for metrics in binary.values():
        print_binary_metrics(metrics)

    print("=== top-K precision (ranked by final_score) ===")
    print(top_k.to_string(index=False))
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    merged = load_inputs()

    crosstab = compute_crosstab(merged)
    binary = {
        "strict_high_only": compute_binary_metrics(
            merged, mode="strict_high_only", positive_classes=["high_risk"]
        ),
        "lenient_medium_or_high": compute_binary_metrics(
            merged,
            mode="lenient_medium_or_high",
            positive_classes=["medium_risk", "high_risk"],
        ),
    }
    top_k = compute_top_k_precision(merged, TOP_K_VALUES)

    print_report(merged, crosstab, binary, top_k)

    MERGED_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(MERGED_OUTPUT_PATH, index=False)
    print(f"Saved merged evaluation table to: {MERGED_OUTPUT_PATH.resolve()}")


if __name__ == "__main__":
    main()
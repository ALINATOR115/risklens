"""
Synthetic transaction dataset generator for the risk scoring thesis project.

Produces a realistic-shaped CSV with:

* ~200 users, each with their own behavioral profile (mean amount,
  spending volatility, daily activity rate, home country/device,
  preferred merchants).
* ~4000 transactions over a 60-day window.
* ~9% anomalies, deliberately injected as four distinct scenarios so
  they actually activate the engineered features used by the risk
  scoring pipeline (``amount_ratio_prev``, ``amount_ratio_avg``,
  ``transactions_last_24_h``, ``share_of_total``, ``is_increasing_3``).

Run as a script — the file is saved to ``data/raw/synthetic_transactions.csv``
relative to the current working directory.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

RANDOM_SEED: int = 42

N_USERS: int = 200
PERIOD_DAYS: int = 60
START_DATE: pd.Timestamp = pd.Timestamp("2024-01-01")

# Calibrated to land on ~4000 normal transactions:
# 200 users * 60 days * mean(daily_rate ~ 0.33) ≈ 4000
DAILY_RATE_RANGE: tuple[float, float] = (0.10, 0.60)
MIN_TRANSACTIONS_PER_USER: int = 5

# Anomaly plan: each entry assigns one anomaly type to N distinct users.
# Total injected anomalous transactions ≈ 80 + 25*4 + 15*8 + 50 ≈ 350,
# which against ~4000 normal transactions gives ~9% anomaly share.
ANOMALY_PLAN: List[tuple[str, int]] = [
    ("spike", 100),
    ("increasing_sequence", 30),
    ("burst", 15),
    ("dominant", 60),
]


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH: Path = PROJECT_ROOT / "data" / "raw" / "synthetic_transactions.csv"


# ---------------------------------------------------------------------------
# Categorical pools
# ---------------------------------------------------------------------------

COUNTRIES: List[str] = [
    "US", "GB", "DE", "FR", "ES", "IT", "NL", "PL",
    "RU", "BR", "CN", "JP", "IN", "MX", "CA",
]
COUNTRY_WEIGHTS = np.array(
    [0.22, 0.12, 0.10, 0.08, 0.07, 0.07, 0.05, 0.05,
     0.04, 0.04, 0.04, 0.04, 0.03, 0.03, 0.02]
)
COUNTRY_WEIGHTS = COUNTRY_WEIGHTS / COUNTRY_WEIGHTS.sum()

TRANSACTION_TYPES: List[str] = ["purchase", "withdrawal", "transfer", "payment"]
TYPE_WEIGHTS: List[float] = [0.60, 0.15, 0.10, 0.15]


# ---------------------------------------------------------------------------
# User profile
# ---------------------------------------------------------------------------

@dataclass
class UserProfile:
    """Behavioral baseline for a single synthetic user."""

    user_id: str
    mean_amount: float
    amount_std: float
    daily_txn_rate: float
    home_country: str
    home_device: str
    preferred_merchants: List[str]


def make_user_profiles(n_users: int, rng: np.random.Generator) -> List[UserProfile]:
    """Sample heterogeneous user profiles."""
    profiles: List[UserProfile] = []
    for i in range(n_users):
        # Heavy-tailed amount distribution to mimic real spending.
        mean_amount = float(np.clip(rng.lognormal(mean=4.0, sigma=0.7), 20.0, 1500.0))
        amount_std = mean_amount * float(rng.uniform(0.10, 0.35))
        daily_rate = float(rng.uniform(*DAILY_RATE_RANGE))
        home_country = str(rng.choice(COUNTRIES, p=COUNTRY_WEIGHTS))
        home_device = f"dev_{int(rng.integers(100_000, 999_999))}"
        n_merchants = int(rng.integers(3, 9))
        merchants = [
            f"mrc_{int(rng.integers(1000, 9999))}" for _ in range(n_merchants)
        ]
        profiles.append(
            UserProfile(
                user_id=f"user_{i:04d}",
                mean_amount=mean_amount,
                amount_std=amount_std,
                daily_txn_rate=daily_rate,
                home_country=home_country,
                home_device=home_device,
                preferred_merchants=merchants,
            )
        )
    return profiles


# ---------------------------------------------------------------------------
# Normal transaction generation
# ---------------------------------------------------------------------------

def _make_normal_row(profile: UserProfile, seconds: float, rng: np.random.Generator) -> dict:
    """Build a single normal-behavior transaction row."""
    amount = max(1.0, float(rng.normal(profile.mean_amount, profile.amount_std)))
    return {
        "user_id": profile.user_id,
        "transaction_time": START_DATE + pd.Timedelta(seconds=float(seconds)),
        "amount": round(amount, 2),
        "transaction_type": str(rng.choice(TRANSACTION_TYPES, p=TYPE_WEIGHTS)),
        "merchant_id": str(rng.choice(profile.preferred_merchants)),
        "country": profile.home_country,
        "device_id": profile.home_device,
        "is_anomaly": 0,
    }


def generate_normal_transactions(
    profile: UserProfile, rng: np.random.Generator
) -> List[dict]:
    """Generate this user's normal transactions over the period."""
    expected = profile.daily_txn_rate * PERIOD_DAYS
    n_txns = max(int(rng.poisson(expected)), MIN_TRANSACTIONS_PER_USER)

    seconds = rng.uniform(0, PERIOD_DAYS * 86_400, size=n_txns)
    seconds.sort()

    return [_make_normal_row(profile, s, rng) for s in seconds]


# ---------------------------------------------------------------------------
# Anomaly injection
# ---------------------------------------------------------------------------

def _pick_foreign_country(home_country: str, rng: np.random.Generator) -> str:
    candidates = [c for c in COUNTRIES if c != home_country]
    return str(rng.choice(candidates))


def _new_device_id(rng: np.random.Generator) -> str:
    return f"dev_{int(rng.integers(100_000, 999_999))}"


def inject_spike(
    rows: List[dict], profile: UserProfile, rng: np.random.Generator
) -> List[dict]:
    """Replace one transaction with a sudden 8–15× spike.

    Targets: ``amount_ratio_prev``, ``amount_ratio_avg``.
    """
    if len(rows) < 3:
        return rows
    idx = int(rng.integers(2, len(rows)))
    multiplier = float(rng.uniform(8.0, 15.0))
    rows[idx]["amount"] = round(profile.mean_amount * multiplier, 2)
    rows[idx]["is_anomaly"] = 1
    if rng.random() < 0.4:
        rows[idx]["country"] = _pick_foreign_country(profile.home_country, rng)
    if rng.random() < 0.4:
        rows[idx]["device_id"] = _new_device_id(rng)
    return rows


def inject_increasing_sequence(
    rows: List[dict], profile: UserProfile, rng: np.random.Generator
) -> List[dict]:
    """Replace 4 consecutive transactions with strictly increasing amounts.

    Targets: ``is_increasing_3`` (and indirectly the ratio features).
    """
    if len(rows) < 7:
        return rows
    start = int(rng.integers(2, len(rows) - 4))
    base = profile.mean_amount * float(rng.uniform(1.2, 2.0))
    multipliers = [1.0, 1.4, 1.9, 2.5]
    for offset, mult in enumerate(multipliers):
        rows[start + offset]["amount"] = round(base * mult, 2)
        rows[start + offset]["is_anomaly"] = 1
    return rows


def inject_burst(
    rows: List[dict], profile: UserProfile, rng: np.random.Generator
) -> List[dict]:
    """Append 6–10 new transactions clustered within a 0.5–2 hour window.

    Targets: ``transactions_last_24_h``.
    """
    n_burst = int(rng.integers(6, 11))
    center_seconds = float(rng.uniform(86_400, (PERIOD_DAYS - 1) * 86_400))
    window_seconds = float(rng.uniform(1_800, 7_200))

    burst_seconds = rng.uniform(
        center_seconds - window_seconds / 2,
        center_seconds + window_seconds / 2,
        size=n_burst,
    )
    burst_seconds.sort()

    new_device = _new_device_id(rng) if rng.random() < 0.3 else profile.home_device
    new_country = (
        _pick_foreign_country(profile.home_country, rng)
        if rng.random() < 0.3
        else profile.home_country
    )

    new_rows: List[dict] = []
    for s in burst_seconds:
        amount = max(1.0, float(rng.normal(profile.mean_amount, profile.amount_std)))
        new_rows.append(
            {
                "user_id": profile.user_id,
                "transaction_time": START_DATE + pd.Timedelta(seconds=float(s)),
                "amount": round(amount, 2),
                "transaction_type": str(rng.choice(TRANSACTION_TYPES, p=TYPE_WEIGHTS)),
                "merchant_id": str(rng.choice(profile.preferred_merchants)),
                "country": new_country,
                "device_id": new_device,
                "is_anomaly": 1,
            }
        )
    return rows + new_rows


def inject_dominant(
    rows: List[dict], profile: UserProfile, rng: np.random.Generator
) -> List[dict]:
    """Replace one transaction with a single huge amount that dominates the user's volume.

    Targets: ``share_of_total``.
    """
    if len(rows) < 3:
        return rows
    idx = int(rng.integers(2, len(rows)))
    other_total = sum(r["amount"] for i, r in enumerate(rows) if i != idx)
    rows[idx]["amount"] = round(other_total * float(rng.uniform(2.5, 5.0)), 2)
    rows[idx]["is_anomaly"] = 1
    if rng.random() < 0.5:
        rows[idx]["country"] = _pick_foreign_country(profile.home_country, rng)
    return rows


ANOMALY_INJECTORS = {
    "spike": inject_spike,
    "increasing_sequence": inject_increasing_sequence,
    "burst": inject_burst,
    "dominant": inject_dominant,
}


def inject_anomalies(
    user_rows: Dict[str, List[dict]],
    profiles: List[UserProfile],
    rng: np.random.Generator,
) -> Dict[str, List[dict]]:
    """Distribute anomaly scenarios across distinct users.

    Each affected user receives at most one anomaly type so that the
    resulting dataset is unambiguous: a flagged transaction belongs to a
    well-defined scenario, which makes downstream evaluation honest.
    """
    profile_by_id = {p.user_id: p for p in profiles}
    shuffled_user_ids = list(rng.permutation(list(user_rows.keys())))

    cursor = 0
    for anomaly_type, count in ANOMALY_PLAN:
        injector = ANOMALY_INJECTORS[anomaly_type]
        for _ in range(count):
            if cursor >= len(shuffled_user_ids):
                break
            uid = shuffled_user_ids[cursor]
            cursor += 1
            user_rows[uid] = injector(user_rows[uid], profile_by_id[uid], rng)

    return user_rows


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

def assemble_dataframe(user_rows: Dict[str, List[dict]]) -> pd.DataFrame:
    """Flatten the per-user dicts into a sorted, ID'd DataFrame."""
    all_rows: List[dict] = []
    for rows in user_rows.values():
        all_rows.extend(rows)

    df = pd.DataFrame(all_rows)
    df = df.sort_values("transaction_time", kind="mergesort").reset_index(drop=True)
    df.insert(0, "transaction_id", [f"txn_{i:06d}" for i in range(len(df))])

    column_order = [
        "transaction_id",
        "user_id",
        "transaction_time",
        "amount",
        "transaction_type",
        "merchant_id",
        "country",
        "device_id",
        "is_anomaly",
    ]
    return df[column_order]


def generate_dataset(seed: int = RANDOM_SEED) -> pd.DataFrame:
    """End-to-end dataset construction."""
    rng = np.random.default_rng(seed)
    profiles = make_user_profiles(N_USERS, rng)
    user_rows = {p.user_id: generate_normal_transactions(p, rng) for p in profiles}
    user_rows = inject_anomalies(user_rows, profiles, rng)
    return assemble_dataframe(user_rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    df = generate_dataset()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)

    print(f"Saved synthetic dataset to: {OUTPUT_PATH.resolve()}")
    print(f"Shape: {df.shape}")
    print()
    print("is_anomaly value_counts:")
    print(df["is_anomaly"].value_counts())
    print()
    print("Anomaly share: {:.2%}".format(df["is_anomaly"].mean()))
    print()
    print("Head:")
    print(df.head())


if __name__ == "__main__":
    main()
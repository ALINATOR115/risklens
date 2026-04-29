"""
Centralized configuration for the transaction risk scoring system.

All tunable parameters (paths, thresholds, model hyperparameters, rule weights)
are declared here as dataclasses so the rest of the codebase depends on typed
configuration objects rather than scattered magic numbers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class PathsConfig:
    """Filesystem layout used across the project."""

    project_root: Path = PROJECT_ROOT
    data_dir: Path = PROJECT_ROOT / "data"
    raw_data_dir: Path = PROJECT_ROOT / "data" / "raw"
    processed_data_dir: Path = PROJECT_ROOT / "data" / "processed"
    models_dir: Path = PROJECT_ROOT / "artifacts" / "models"
    reports_dir: Path = PROJECT_ROOT / "artifacts" / "reports"


# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FeatureConfig:
    """Parameters controlling behavioral feature construction."""

    rolling_windows_days: tuple[int, ...] = (1, 7, 30)
    amount_zscore_window: int = 30
    night_hours: tuple[int, int] = (0, 6)


# ---------------------------------------------------------------------------
# Rule engine
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RuleConfig:
    """Thresholds and weights for the rule-based component.

    Each engineered feature has a matching threshold and weight. Weights
    are intentionally chosen to sum to ~1.0 so that the raw rule score
    naturally lands in [0, 1] without aggressive clipping, while still
    allowing the engine to clip defensively if a future rule pushes it
    above 1.
    """

    # --- thresholds ---
    jump_from_previous_threshold: float = 5.0
    high_vs_average_threshold: float = 4.0
    high_share_of_total_threshold: float = 0.5
    high_transaction_frequency_threshold: int = 10

    # --- weights ---
    rule_weights: Dict[str, float] = field(
        default_factory=lambda: {
            "jump_from_previous": 0.25,
            "high_vs_average": 0.25,
            "high_share_of_total": 0.20,
            "high_transaction_frequency": 0.20,
            "increasing_sequence": 0.10,
        }
    )


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ScoringConfig:
    """How rule-based, behavioral, and ML signals are combined.

    Three groups of parameters:

    1. Behavioral component weights and normalization parameters —
       used by ``RiskScorer.compute_behavioral_risk_score`` to turn
       raw feature values into a continuous integral risk index.
    2. Final combination weights — used by ``RiskScorer.combine`` to
       merge rule, behavioral, and model signals into ``final_score``.
    3. Risk-class thresholds — used by ``RiskScorer.classify``.
    """

    # --- behavioral component weights (sum ≈ 1.0) ---
    spike_weight: float = 0.30
    deviation_weight: float = 0.30
    frequency_weight: float = 0.20
    share_weight: float = 0.20

    # --- behavioral normalization parameters ---
    # Each is a (threshold, cap) pair: below threshold -> 0,
    # above cap -> 1, linear in between.
    spike_threshold: float = 2.0
    spike_cap: float = 10.0

    deviation_threshold: float = 2.0
    deviation_cap: float = 8.0

    frequency_threshold: float = 5.0
    frequency_cap: float = 20.0

    share_threshold: float = 0.20
    share_cap: float = 0.70

    # --- final combination weights (sum ≈ 1.0) ---
    final_rule_weight: float = 0.35
    final_behavioral_weight: float = 0.25
    final_model_weight: float = 0.40

    # --- risk class thresholds (applied to final_score) ---
    medium_risk_threshold: float = 0.40
    high_risk_threshold: float = 0.70


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ModelConfig:
    """Hyperparameters for the ML risk models.

    Holds parameters for both supported estimators in a single config
    so that ``build_model`` can construct either by name without
    additional plumbing.
    """

    random_state: int = 42
    test_size: float = 0.2

    # Logistic regression
    logistic_max_iter: int = 1000

    # Random forest
    random_forest_n_estimators: int = 200
    random_forest_max_depth: int = 8

# ---------------------------------------------------------------------------
# Top-level container
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AppConfig:
    """Aggregate configuration object passed through the pipeline."""

    paths: PathsConfig = field(default_factory=PathsConfig)
    features: FeatureConfig = field(default_factory=FeatureConfig)
    rules: RuleConfig = field(default_factory=RuleConfig)
    scoring: ScoringConfig = field(default_factory=ScoringConfig)
    model: ModelConfig = field(default_factory=ModelConfig)


def get_config() -> AppConfig:
    """Return the default application configuration.

    A function indirection is used so the rest of the codebase can later
    swap in environment-driven or file-driven config loading without
    changing call sites.
    """
    return AppConfig()
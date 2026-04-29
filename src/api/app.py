"""
FastAPI application factory for the transaction risk scoring API.

Creates the app, registers routes, and wires the startup lifecycle
(model loading). The factory pattern lets tests create a fresh app
with a test config / mock model without touching module-level state.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.dependencies import get_state
from src.api.routes import router


def create_app(
    model_path: Optional[Path] = None,
    title: str = "Transaction Risk Scoring API",
) -> FastAPI:
    """Build and return a configured FastAPI application.

    Parameters
    ----------
    model_path:
        Path to the joblib model bundle. If provided, the model is
        loaded eagerly at startup. If ``None``, the ``/health``
        endpoint will report ``model_loaded: false`` and scoring
        endpoints will return 503 until a model is loaded manually.
    title:
        OpenAPI title shown in the Swagger UI.
    """
    app = FastAPI(
        title=title,
        version="0.1.0",
        description=(
            "Configurable transaction risk anomaly detection system. "
            "Combines behavioral feature engineering, a rule engine, "
            "and ML models to produce explainable risk scores."
        ),
    )

    # -- CORS (permissive for local dev / demo) --
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # -- Routes --
    app.include_router(router, prefix="/api/v1", tags=["scoring"])

    # -- Startup hook --
    @app.on_event("startup")
    def _load_model() -> None:
        if model_path is not None:
            state = get_state()
            state.load_model(model_path)

    return app

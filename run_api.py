"""
Entry point for the risk scoring API server.

Usage:
    python run_api.py
    python run_api.py --model artifacts/models/random_forest__extended.joblib
    python run_api.py --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn

from src.api.app import create_app


DEFAULT_MODEL_PATH = Path("artifacts/models/random_forest__extended.joblib")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Start the Transaction Risk Scoring API server.",
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=DEFAULT_MODEL_PATH,
        help=f"Path to the joblib model bundle (default: {DEFAULT_MODEL_PATH}).",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Bind address (default: 127.0.0.1).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port number (default: 8000).",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    model_path: Path | None = args.model
    if model_path and not model_path.exists():
        print(f"WARNING: model file not found at {model_path.resolve()}")
        print("         The server will start but scoring endpoints will return 503.")
        print("         Train a model first: python -m src.models.train")
        model_path = None

    app = create_app(model_path=model_path)

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()

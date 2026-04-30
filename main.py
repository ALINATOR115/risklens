from pathlib import Path
from src.api.app import create_app

model_path = Path("artifacts/models/random_forest__extended.joblib")
app = create_app(model_path=model_path)


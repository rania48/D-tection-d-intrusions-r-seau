import json
from pathlib import Path

BASE_DIR = Path(__file__).parent
models_dir = BASE_DIR / "models"

metadata_path = models_dir / "metadata.json"
xgb_features_path = models_dir / "xgb_features.json"

with open(metadata_path, "r", encoding="utf-8") as f:
    metadata = json.load(f)

features = metadata["feature_names"]

with open(xgb_features_path, "w", encoding="utf-8") as f:
    json.dump(features, f, ensure_ascii=False, indent=4)

print("xgb_features.json créé avec succès")
print("Nombre de features :", len(features))
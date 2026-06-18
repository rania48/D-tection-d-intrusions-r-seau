import pandas as pd
import json
from pathlib import Path

BASE_DIR = Path(__file__).parent

x_train_path = BASE_DIR / "data" / "X_train.csv"
models_dir = BASE_DIR / "models"
models_dir.mkdir(exist_ok=True)

X_train = pd.read_csv(x_train_path, low_memory=False)

# Nettoyage simple des noms de colonnes
X_train.columns = X_train.columns.str.strip()

# Supprimer colonnes inutiles si elles existent
for col in ["Unnamed: 0", "index"]:
    if col in X_train.columns:
        X_train = X_train.drop(columns=[col])

features = list(X_train.columns)

with open(models_dir / "rf_features.json", "w", encoding="utf-8") as f:
    json.dump(features, f, ensure_ascii=False, indent=4)

print("rf_features.json créé avec succès")
print("Nombre de features :", len(features))
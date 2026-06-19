
import json
import joblib
import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.metrics import classification_report, accuracy_score, f1_score

X_TEST_PATH = "data/X_test.csv"
Y_TEST_PATH = "data/y_test.csv"

XGB_MODEL_PATH = "models/xgboost_multiclass_final.ubj"
XGB_ENCODER_PATH = "models/label_encoder_xgb.joblib"
XGB_FEATURES_PATH = "models/xgb_features.json"


print("Chargement X_test/y_test utilisés par le producer...")

X = pd.read_csv(X_TEST_PATH, low_memory=False)
y = pd.read_csv(Y_TEST_PATH, low_memory=False).squeeze()

print("X shape :", X.shape)
print("y shape :", y.shape)

# XGBoost attaque ne connaît pas BENIGN, donc on garde seulement les attaques
mask_attack = y.astype(str).str.strip() != "0"

X_attack = X.loc[mask_attack].copy()
y_attack = y.loc[mask_attack].astype(int).reset_index(drop=True)

print("Nombre de lignes attaque :", len(X_attack))

with open(XGB_FEATURES_PATH, "r", encoding="utf-8") as f:
    xgb_features = json.load(f)

X_attack.columns = X_attack.columns.str.strip()

for feature in xgb_features:
    if feature not in X_attack.columns:
        X_attack[feature] = 0

X_attack = X_attack[xgb_features]
X_attack = X_attack.replace([np.inf, -np.inf], np.nan)
X_attack = X_attack.apply(pd.to_numeric, errors="coerce").fillna(0)

model = xgb.Booster()
model.load_model(XGB_MODEL_PATH)

encoder = joblib.load(XGB_ENCODER_PATH)

dmatrix = xgb.DMatrix(X_attack, feature_names=xgb_features)
probs = model.predict(dmatrix)

if len(probs.shape) == 1:
    probs = probs.reshape(len(X_attack), -1)

pred_indices = np.argmax(probs, axis=1)

# Le nouveau encoder retourne directement les vrais labels globaux : 1..14
pred_global = encoder.inverse_transform(pred_indices).astype(int)

print("\n=== Résultats XGBoost sur le X_test actuel du producer ===")
print("Accuracy :", accuracy_score(y_attack, pred_global))
print("F1 macro :", f1_score(y_attack, pred_global, average="macro", zero_division=0))
print("F1 weighted :", f1_score(y_attack, pred_global, average="weighted", zero_division=0))

print("\n=== Rapport détaillé ===")
print(classification_report(y_attack, pred_global, zero_division=0))

print("\n=== Exemples des 30 premières attaques ===")
result = pd.DataFrame({
    "true_label": y_attack.head(30),
    "xgb_prediction": pred_global[:30],
    "correct": y_attack.head(30).values == pred_global[:30]
})

print(result.to_string(index=False))


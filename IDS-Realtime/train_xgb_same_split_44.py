
import json
import shutil
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier


# =========================================================
# Objectif :
# Réentraîner XGBoost sur le même split que Random Forest
# - même X_train / X_test
# - même preprocessing déjà fait
# - mêmes 44 colonnes
# - même mapping global des labels
# - mais en retirant seulement BENIGN / 0
# =========================================================

DATA_DIR = Path("data")
MODELS_DIR = Path("models")
RESULTS_DIR = Path("results_xgb_same_split_44")

MODELS_DIR.mkdir(exist_ok=True)
RESULTS_DIR.mkdir(exist_ok=True)

X_TRAIN_PATH = DATA_DIR / "X_train.csv"
X_TEST_PATH = DATA_DIR / "X_test.csv"
Y_TRAIN_PATH = DATA_DIR / "y_train.csv"
Y_TEST_PATH = DATA_DIR / "y_test.csv"

XGB_MODEL_PATH = MODELS_DIR / "xgboost_multiclass_final.ubj"
XGB_ENCODER_PATH = MODELS_DIR / "label_encoder_xgb.joblib"
XGB_FEATURES_PATH = MODELS_DIR / "xgb_features.json"

RANDOM_STATE = 42


# =========================================================
# Backup des anciens fichiers XGBoost
# =========================================================

for path in [XGB_MODEL_PATH, XGB_ENCODER_PATH, XGB_FEATURES_PATH]:
    if path.exists():
        backup_path = path.with_suffix(path.suffix + ".old_before_same_split")
        shutil.copy2(path, backup_path)
        print(f"Backup créé : {backup_path}")


# =========================================================
# Chargement des données déjà préprocessées
# =========================================================

print("\nChargement des fichiers Random Forest...")
X_train = pd.read_csv(X_TRAIN_PATH, low_memory=False)
X_test = pd.read_csv(X_TEST_PATH, low_memory=False)
y_train = pd.read_csv(Y_TRAIN_PATH, low_memory=False).squeeze()
y_test = pd.read_csv(Y_TEST_PATH, low_memory=False).squeeze()

print("Avant nettoyage :")
print("X_train :", X_train.shape)
print("X_test  :", X_test.shape)
print("y_train :", y_train.shape)
print("y_test  :", y_test.shape)


# =========================================================
# Même nettoyage de base que Random Forest
# =========================================================

X_train.columns = X_train.columns.str.strip()
X_test.columns = X_test.columns.str.strip()

for col in ["Unnamed: 0", "index"]:
    if col in X_train.columns:
        X_train = X_train.drop(columns=[col])
    if col in X_test.columns:
        X_test = X_test.drop(columns=[col])

# Sécuriser les types
X_train = X_train.replace([np.inf, -np.inf], np.nan)
X_test = X_test.replace([np.inf, -np.inf], np.nan)

X_train = X_train.apply(pd.to_numeric, errors="coerce")
X_test = X_test.apply(pd.to_numeric, errors="coerce")

# Utiliser les médianes du train complet, comme logique de preprocessing stable
medians = X_train.median(numeric_only=True)

X_train = X_train.fillna(medians).fillna(0)
X_test = X_test.fillna(medians).fillna(0)

# Même ordre de colonnes train/test
X_test = X_test[X_train.columns]

FEATURES = X_train.columns.tolist()

print("\nAprès nettoyage :")
print("X_train :", X_train.shape)
print("X_test  :", X_test.shape)
print("Nombre de features :", len(FEATURES))


# =========================================================
# Filtrer seulement BENIGN / 0
# =========================================================

def is_benign_label(value):
    value_str = str(value).strip().lower()
    return value_str == "0" or value_str == "benign" or value_str == "normal"


mask_train_attack = ~y_train.apply(is_benign_label)
mask_test_attack = ~y_test.apply(is_benign_label)

X_train_attack = X_train.loc[mask_train_attack].copy()
X_test_attack = X_test.loc[mask_test_attack].copy()

y_train_attack_raw = y_train.loc[mask_train_attack].copy()
y_test_attack_raw = y_test.loc[mask_test_attack].copy()

print("\nAprès suppression BENIGN :")
print("X_train_attack :", X_train_attack.shape)
print("X_test_attack  :", X_test_attack.shape)
print("y_train_attack :", y_train_attack_raw.shape)
print("y_test_attack  :", y_test_attack_raw.shape)

print("\nDistribution y_train_attack :")
print(y_train_attack_raw.value_counts().sort_index())


# =========================================================
# LabelEncoder aligné sur les labels globaux 1..14
# XGBoost travaille en interne avec 0..13,
# mais l'encoder permet de revenir aux vrais labels 1..14.
# =========================================================

label_encoder_xgb = LabelEncoder()
y_train_attack = label_encoder_xgb.fit_transform(y_train_attack_raw.astype(str))
y_test_attack = label_encoder_xgb.transform(y_test_attack_raw.astype(str))

print("\nMapping XGBoost interne -> label global :")
for idx, cls in enumerate(label_encoder_xgb.classes_):
    print(f"{idx} -> {cls}")

n_classes = len(label_encoder_xgb.classes_)


# =========================================================
# Split validation extrait uniquement du train
# =========================================================

try:
    X_tr, X_val, y_tr, y_val = train_test_split(
        X_train_attack,
        y_train_attack,
        test_size=0.15,
        random_state=RANDOM_STATE,
        stratify=y_train_attack
    )
except Exception:
    print("Stratify impossible, split validation sans stratify.")
    X_tr, X_val, y_tr, y_val = train_test_split(
        X_train_attack,
        y_train_attack,
        test_size=0.15,
        random_state=RANDOM_STATE
    )

sample_weight = compute_sample_weight(class_weight="balanced", y=y_tr)


# =========================================================
# Entraînement XGBoost
# =========================================================

print("\nEntraînement XGBoost sur le même split que RF, avec 44 features...")

xgb_model = XGBClassifier(
    objective="multi:softprob",
    num_class=n_classes,
    n_estimators=300,
    max_depth=8,
    learning_rate=0.05,
    subsample=0.9,
    colsample_bytree=0.9,
    min_child_weight=1,
    reg_lambda=1.0,
    reg_alpha=0.0,
    eval_metric="mlogloss",
    tree_method="hist",
    random_state=RANDOM_STATE,
    n_jobs=-1
)

xgb_model.fit(
    X_tr,
    y_tr,
    sample_weight=sample_weight,
    eval_set=[(X_val, y_val)],
    verbose=50
)

print("\nEntraînement terminé.")


# =========================================================
# Évaluation sur le vrai X_test attack du même split RF
# =========================================================

print("\nÉvaluation sur X_test_attack...")

y_pred = xgb_model.predict(X_test_attack)

accuracy = accuracy_score(y_test_attack, y_pred)
f1_macro = f1_score(y_test_attack, y_pred, average="macro", zero_division=0)
f1_weighted = f1_score(y_test_attack, y_pred, average="weighted", zero_division=0)

print("\n=== Résultats XGBoost same split 44 features ===")
print("Accuracy    :", accuracy)
print("F1 macro    :", f1_macro)
print("F1 weighted :", f1_weighted)

target_names = [str(c) for c in label_encoder_xgb.classes_]

report_text = classification_report(
    y_test_attack,
    y_pred,
    target_names=target_names,
    zero_division=0
)

print("\n=== Rapport détaillé ===")
print(report_text)

report_dict = classification_report(
    y_test_attack,
    y_pred,
    target_names=target_names,
    output_dict=True,
    zero_division=0
)

report_df = pd.DataFrame(report_dict).transpose()
report_df.to_csv(RESULTS_DIR / "classification_report_xgb_same_split_44.csv")

cm = confusion_matrix(y_test_attack, y_pred)
cm_df = pd.DataFrame(
    cm,
    index=target_names,
    columns=target_names
)
cm_df.to_csv(RESULTS_DIR / "confusion_matrix_xgb_same_split_44.csv")


# =========================================================
# Sauvegarde pour le pipeline Spark
# On remplace les anciens fichiers utilisés par Spark.
# =========================================================

print("\nSauvegarde des fichiers XGBoost pour Spark...")

xgb_model.save_model(XGB_MODEL_PATH)
joblib.dump(label_encoder_xgb, XGB_ENCODER_PATH)

with open(XGB_FEATURES_PATH, "w", encoding="utf-8") as f:
    json.dump(FEATURES, f, indent=4, ensure_ascii=False)

metadata = {
    "model": "XGBoost attack-only",
    "source_split": "same as Random Forest data/X_train.csv and data/X_test.csv",
    "benign_removed": True,
    "features_count": len(FEATURES),
    "classes_global_labels": list(map(str, label_encoder_xgb.classes_)),
    "accuracy": float(accuracy),
    "f1_macro": float(f1_macro),
    "f1_weighted": float(f1_weighted)
}

with open(RESULTS_DIR / "metadata_xgb_same_split_44.json", "w", encoding="utf-8") as f:
    json.dump(metadata, f, indent=4, ensure_ascii=False)

print("\nFichiers sauvegardés :")
print("-", XGB_MODEL_PATH)
print("-", XGB_ENCODER_PATH)
print("-", XGB_FEATURES_PATH)
print("-", RESULTS_DIR / "classification_report_xgb_same_split_44.csv")
print("-", RESULTS_DIR / "confusion_matrix_xgb_same_split_44.csv")
print("-", RESULTS_DIR / "metadata_xgb_same_split_44.json")

print("\nTerminé. XGBoost est maintenant réentraîné sur le même split que Random Forest avec 44 features.")

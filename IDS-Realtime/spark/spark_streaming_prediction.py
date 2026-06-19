
import json
import joblib
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from pymongo import MongoClient
import xgboost as xgb

from pyspark.sql import SparkSession


KAFKA_BOOTSTRAP = "localhost:9092"
TOPIC = "network-flows"

MONGO_URI = "mongodb://localhost:27017/"
MONGO_DB = "ids_db"
MONGO_COLLECTION = "predictions"

RF_MODEL_PATH = "models/random_forest_multiclass_model.joblib"
XGB_MODEL_PATH = "models/xgboost_multiclass_final.ubj"

RF_ENCODER_PATH = "models/label_encoder_rf.joblib"
XGB_ENCODER_PATH = "models/label_encoder_xgb.joblib"

RF_FEATURES_PATH = "models/rf_features.json"
XGB_FEATURES_PATH = "models/xgb_features.json"


# =========================
# Chargement des modèles
# =========================

print("Chargement du modèle Random Forest...")
rf_model = joblib.load(RF_MODEL_PATH)
rf_encoder = joblib.load(RF_ENCODER_PATH)

print("Chargement du modèle XGBoost...")
xgb_model = xgb.Booster()
xgb_model.load_model(XGB_MODEL_PATH)

print("Chargement du label encoder XGBoost...")
xgb_encoder = joblib.load(XGB_ENCODER_PATH)


# =========================
# Chargement des features
# =========================

with open(RF_FEATURES_PATH, "r", encoding="utf-8") as f:
    rf_features = json.load(f)

with open(XGB_FEATURES_PATH, "r", encoding="utf-8") as f:
    xgb_features = json.load(f)

print(f"Nombre de features RF  : {len(rf_features)}")
print(f"Nombre de features XGB : {len(xgb_features)}")


# =========================
# Fonctions utilitaires
# =========================

def decode_rf_prediction(pred):
    """
    Random Forest prédit les codes globaux 0..14.
    """
    try:
        decoded = rf_encoder.inverse_transform([int(pred)])[0]
        return str(decoded).strip()
    except Exception:
        return str(pred).strip()


def decode_xgb_prediction(pred_index):
    """
    XGBoost prédit un index interne.
    Le label_encoder_xgb sauvegardé après réentraînement convertit directement :
    index interne XGB -> vrai label global 1..14.
    """
    try:
        decoded = xgb_encoder.inverse_transform([int(pred_index)])[0]
        return str(decoded).strip()
    except Exception as e:
        print("Erreur décodage XGBoost :", e)
        return str(pred_index).strip()


def is_benign_label(label):
    label_str = str(label).strip().lower()

    if label_str == "0":
        return True

    if "benign" in label_str:
        return True

    if "normal" in label_str:
        return True

    return False


def prepare_features(pdf, features):
    """
    Prépare les colonnes exactement dans l'ordre utilisé par le modèle.
    """
    X = pdf.copy()

    for col_name in ["flow_id", "true_label", "event_time", "timestamp"]:
        if col_name in X.columns:
            X = X.drop(columns=[col_name])

    X.columns = X.columns.str.strip()

    for feature in features:
        if feature not in X.columns:
            X[feature] = 0

    X = X[features]

    X = X.replace([np.inf, -np.inf], np.nan)
    X = X.apply(pd.to_numeric, errors="coerce").fillna(0)

    return X


# =========================
# Fonction appelée par Spark à chaque batch
# =========================

def predict_batch(batch_df, batch_id):
    if batch_df.count() == 0:
        return

    rows = batch_df.select("value").toPandas()

    records = []

    for value in rows["value"]:
        try:
            records.append(json.loads(value))
        except Exception as e:
            print("Erreur JSON :", e)

    if not records:
        return

    pdf = pd.DataFrame(records)

    flow_ids = pdf.get("flow_id", pd.Series(range(len(pdf))))
    true_labels = pdf.get("true_label", pd.Series(["unknown"] * len(pdf)))

    # =========================
    # Préparation Random Forest
    # =========================

    X_rf = prepare_features(pdf, rf_features)

    # =========================
    # Prédiction Random Forest
    # =========================

    rf_preds = rf_model.predict(X_rf)

    final_results = []

    for idx, rf_pred in enumerate(rf_preds):
        rf_label = decode_rf_prediction(rf_pred)

        result = {
            "flow_id": int(flow_ids.iloc[idx]),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "true_label": str(true_labels.iloc[idx]).strip(),
            "rf_prediction": rf_label,
            "status": None,
            "attack_type": None,
            "model_used": None
        }

        # =========================
        # Si Random Forest prédit BENIGN / NORMAL
        # =========================

        if is_benign_label(rf_label):
            result["status"] = "NORMAL"
            result["attack_type"] = "None"
            result["model_used"] = "Random Forest"

        # =========================
        # Si Random Forest prédit ATTACK
        # XGBoost confirme le type d'attaque
        # =========================

        else:
            result["status"] = "ATTACK"

            X_xgb = pdf.iloc[[idx]].copy()
            X_xgb = prepare_features(X_xgb, xgb_features)

            dmatrix = xgb.DMatrix(X_xgb, feature_names=xgb_features)

            xgb_probs = xgb_model.predict(dmatrix)

            # Cas normal : multi:softprob -> probabilités par classe
            if len(xgb_probs.shape) == 1:
                xgb_pred_index = int(np.argmax(xgb_probs))
            else:
                xgb_pred_index = int(np.argmax(xgb_probs[0]))

            xgb_label = decode_xgb_prediction(xgb_pred_index)

            result["attack_type"] = xgb_label
            result["model_used"] = "Random Forest + XGBoost"

        final_results.append(result)

    # =========================
    # Sauvegarde MongoDB
    # =========================

    client = MongoClient(MONGO_URI)
    collection = client[MONGO_DB][MONGO_COLLECTION]

    if final_results:
        collection.insert_many(final_results)
        print(f"Batch {batch_id} : {len(final_results)} prédictions insérées dans MongoDB.")


# =========================
# Spark Streaming
# =========================

spark = SparkSession.builder \
    .appName("IDS-Realtime-Prediction") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")

kafka_df = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP) \
    .option("subscribe", TOPIC) \
    .option("startingOffsets", "latest") \
    .load()

messages = kafka_df.selectExpr("CAST(value AS STRING) as value")

query = messages.writeStream \
    .foreachBatch(predict_batch) \
    .outputMode("append") \
    .option("checkpointLocation", "checkpoints/ids_stream") \
    .start()

print("Spark Streaming démarré. En attente des messages Kafka...")

query.awaitTermination()



import json
import os
import joblib
import pandas as pd
from datetime import datetime, timezone
from pymongo import MongoClient
from xgboost import XGBClassifier

from pyspark.sql import SparkSession


# =========================
# Configuration Kafka
# =========================

KAFKA_BOOTSTRAP = "localhost:9092"
TOPIC = "network-flows"


# =========================
# Configuration MongoDB
# =========================

MONGO_URI = "mongodb://localhost:27017/"
MONGO_DB = "ids_db"
MONGO_COLLECTION = "predictions"


# =========================
# Chemins des modèles
# =========================

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
xgb_model = XGBClassifier()
xgb_model.load_model(XGB_MODEL_PATH)

if os.path.exists(XGB_ENCODER_PATH):
    print("Chargement du label encoder XGBoost...")
    xgb_encoder = joblib.load(XGB_ENCODER_PATH)
else:
    print("Aucun label_encoder_xgb.joblib trouvé. Les prédictions XGBoost seront affichées en numérique.")
    xgb_encoder = None


# =========================
# Chargement des features
# =========================

with open(RF_FEATURES_PATH, "r", encoding="utf-8") as f:
    rf_features = json.load(f)

with open(XGB_FEATURES_PATH, "r", encoding="utf-8") as f:
    xgb_features = json.load(f)


# =========================
# Fonctions utilitaires
# =========================

def decode_prediction(pred, encoder=None):
    """
    Convertit une prédiction numérique en label lisible si un encoder existe.
    Sinon retourne la valeur numérique sous forme de string.
    """
    if encoder is not None:
        try:
            return str(encoder.inverse_transform([int(pred)])[0])
        except Exception:
            pass

    try:
        return str(int(pred))
    except Exception:
        return str(pred)


def is_benign_label(label):
    """
    Détermine si la classe prédite correspond à un trafic normal.
    Compatible avec plusieurs formats :
    - "0"
    - "BENIGN"
    - "Normal"
    - "Normal (Benign) (0)"
    """
    label_str = str(label).strip().lower()

    if label_str == "0":
        return True

    if "benign" in label_str:
        return True

    if "normal" in label_str:
        return True

    return False


# =========================
# Fonction appelée par Spark à chaque micro-batch
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
    # Préparation des données pour Random Forest
    # =========================

    X_rf = pdf.copy()

    for col_name in ["flow_id", "true_label"]:
        if col_name in X_rf.columns:
            X_rf = X_rf.drop(columns=[col_name])

    X_rf.columns = X_rf.columns.str.strip()

    for feature in rf_features:
        if feature not in X_rf.columns:
            X_rf[feature] = 0

    X_rf = X_rf[rf_features]
    X_rf = X_rf.apply(pd.to_numeric, errors="coerce").fillna(0)

    # =========================
    # Prédiction Random Forest
    # =========================

    rf_preds = rf_model.predict(X_rf)

    final_results = []

    for idx, rf_pred in enumerate(rf_preds):
        rf_label = decode_prediction(rf_pred, rf_encoder)

        result = {
            "flow_id": int(flow_ids.iloc[idx]),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "true_label": str(true_labels.iloc[idx]),
            "rf_prediction": rf_label,
            "status": None,
            "attack_type": None,
            "model_used": None
        }

        # =========================
        # Décision NORMAL / ATTACK
        # =========================

        if is_benign_label(rf_label):
            result["status"] = "NORMAL"
            result["attack_type"] = "None"
            result["model_used"] = "Random Forest"

        else:
            result["status"] = "ATTACK"

            # =========================
            # Préparation des données pour XGBoost
            # =========================

            X_xgb = pdf.iloc[[idx]].copy()

            for col_name in ["flow_id", "true_label"]:
                if col_name in X_xgb.columns:
                    X_xgb = X_xgb.drop(columns=[col_name])

            X_xgb.columns = X_xgb.columns.str.strip()

            for feature in xgb_features:
                if feature not in X_xgb.columns:
                    X_xgb[feature] = 0

            X_xgb = X_xgb[xgb_features]
            X_xgb = X_xgb.apply(pd.to_numeric, errors="coerce").fillna(0)

            # =========================
            # Prédiction XGBoost du type d'attaque
            # =========================

            xgb_pred = xgb_model.predict(X_xgb)[0]
            xgb_label = decode_prediction(xgb_pred, xgb_encoder)

            result["attack_type"] = xgb_label
            result["model_used"] = "Random Forest + XGBoost"

        final_results.append(result)

    # =========================
    # Sauvegarde dans MongoDB
    # =========================

    client = MongoClient(MONGO_URI)
    collection = client[MONGO_DB][MONGO_COLLECTION]

    if final_results:
        collection.insert_many(final_results)
        print(f"Batch {batch_id} : {len(final_results)} prédictions insérées dans MongoDB.")


# =========================
# Spark Structured Streaming
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


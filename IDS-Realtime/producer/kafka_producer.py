import json
import time
import argparse
import pandas as pd
from kafka import KafkaProducer


def clean_dataframe(df):
    df.columns = df.columns.str.strip()

    for col in ["Unnamed: 0", "index"]:
        if col in df.columns:
            df = df.drop(columns=[col])

    return df


def json_serializer(data):
    return json.dumps(data).encode("utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--x_path", default="data/X_test.csv")
    parser.add_argument("--y_path", default="data/y_test.csv")
    parser.add_argument("--topic", default="network-flows")
    parser.add_argument("--bootstrap", default="localhost:9092")
    parser.add_argument("--sleep", type=float, default=0.1)
    parser.add_argument("--limit", type=int, default=1000)
    args = parser.parse_args()

    X = pd.read_csv(args.x_path, low_memory=False)
    y = pd.read_csv(args.y_path, low_memory=False)

    X = clean_dataframe(X)
    y = clean_dataframe(y).squeeze()

    producer = KafkaProducer(
        bootstrap_servers=args.bootstrap,
        value_serializer=json_serializer
    )

    print("Producer démarré.")
    print("Nombre de lignes disponibles :", len(X))

    for i, row in X.head(args.limit).iterrows():
        message = row.to_dict()

        message["flow_id"] = int(i)
        message["true_label"] = str(y.iloc[i])

        producer.send(args.topic, value=message)

        print(f"Envoyé flow_id={i}, true_label={message['true_label']}")
        time.sleep(args.sleep)

    producer.flush()
    producer.close()

    print("Envoi terminé.")


if __name__ == "__main__":
    main()
"""Purchase-time delivery-risk model with chronological evaluation."""

import json
import pickle
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import average_precision_score
from sklearn.pipeline import make_pipeline

FEATURES = ("item_count", "seller_count", "item_value", "freight_value", "lead_days",
            "purchase_month", "purchase_weekday")
FEATURE_COLUMNS = """o.order_id, o.purchased_at, o.item_count, o.seller_count,
o.item_value, o.freight_value,
date_diff('day', o.purchased_at, o.estimated_at) AS lead_days,
month(o.purchased_at) AS purchase_month,
dayofweek(o.purchased_at) AS purchase_weekday"""
FEATURE_SQL = ("SELECT " + FEATURE_COLUMNS + ", o.delivered_at > o.estimated_at AS late "
                             "FROM fact_orders o WHERE o.order_status = 'delivered' "
                             "AND o.purchased_at IS NOT NULL AND o.delivered_at IS NOT NULL "
                             "AND o.estimated_at IS NOT NULL")


def split_chronologically(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    ordered = frame.sort_values(["purchased_at", "order_id"]).reset_index(drop=True)
    boundary = int(len(ordered) * 0.8)
    if boundary < 2 or boundary >= len(ordered):
        raise ValueError("Need at least 3 labelled orders for chronological split")
    train, test = ordered.iloc[:boundary], ordered.iloc[boundary:]
    if train["purchased_at"].max() > test["purchased_at"].min():
        raise ValueError("Train/test timestamps overlap at the split boundary")
    if train["late"].nunique() != 2 or test["late"].nunique() != 2:
        raise ValueError("Both chronological partitions must contain positive and negative labels")
    return train, test


def population_stability_index(reference: pd.Series, current: pd.Series) -> float:
    reference = np.asarray(reference.dropna(), dtype=float)
    current = np.asarray(current.dropna(), dtype=float)
    if len(reference) == 0 or len(current) == 0:
        raise ValueError("PSI needs nonempty numeric distributions")
    edges = np.unique(np.quantile(reference, np.linspace(0, 1, 11)))
    edges[0], edges[-1] = -np.inf, np.inf
    if len(edges) < 2:
        edges = np.array([-np.inf, np.inf])
    expected = np.histogram(reference, bins=edges)[0] / len(reference)
    observed = np.histogram(current, bins=edges)[0] / len(current)
    expected, observed = np.maximum(expected, 1e-6), np.maximum(observed, 1e-6)
    return float(np.sum((observed - expected) * np.log(observed / expected)))


def train(database: Path, output_dir: Path, track_mlflow: bool = False) -> dict:
    with duckdb.connect(str(database), read_only=True) as con:
        frame = con.execute(FEATURE_SQL).df()
    train_set, test_set = split_chronologically(frame)
    model = make_pipeline(SimpleImputer(strategy="median"),
                          HistGradientBoostingClassifier(random_state=42))
    model.fit(train_set[list(FEATURES)], train_set["late"].astype(int))
    baseline = DummyClassifier(strategy="prior")
    baseline.fit(train_set[list(FEATURES)], train_set["late"].astype(int))
    truth = test_set["late"].astype(int)
    report = {
        "train_rows": len(train_set), "test_rows": len(test_set),
        "train_end": str(train_set["purchased_at"].max()),
        "test_start": str(test_set["purchased_at"].min()),
        "positive_rate_test": float(truth.mean()),
        "pr_auc": float(average_precision_score(truth, model.predict_proba(test_set[list(FEATURES)])[:, 1])),
        "baseline_pr_auc": float(average_precision_score(truth, baseline.predict_proba(test_set[list(FEATURES)])[:, 1])),
        "item_value_psi": population_stability_index(train_set["item_value"], test_set["item_value"]),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "model.pkl").open("wb") as stream:
        pickle.dump(model, stream)
    (output_dir / "model_report.json").write_text(json.dumps(report, indent=2))
    if track_mlflow:
        import mlflow

        mlflow.set_tracking_uri(f"sqlite:///{(output_dir / 'mlflow.db').resolve().as_posix()}")
        mlflow.set_experiment("olist-late-delivery")
        with mlflow.start_run():
            mlflow.log_params({"split": "chronological-80-20", "model": "HistGradientBoosting",
                               "features": ",".join(FEATURES)})
            mlflow.log_metrics({key: value for key, value in report.items()
                                if key in {"pr_auc", "baseline_pr_auc", "item_value_psi"}})
    return report


def predict(database: Path, model_path: Path, order_id: str) -> dict:
    with duckdb.connect(str(database), read_only=True) as con:
        frame = con.execute("SELECT " + FEATURE_COLUMNS + " FROM fact_orders o WHERE o.order_id = ?",
                            [order_id]).df()
    if frame.empty:
        raise ValueError("Order not found")
    with model_path.open("rb") as stream:
        model = pickle.load(stream)
    return {"order_id": order_id, "late_probability": float(model.predict_proba(frame[list(FEATURES)])[0, 1])}
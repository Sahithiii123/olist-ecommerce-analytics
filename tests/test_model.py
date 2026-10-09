import duckdb
import pandas as pd
import pytest

from olist_agent.model import (
    FEATURES,
    population_stability_index,
    predict,
    split_chronologically,
    train,
)


def test_features_exclude_outcomes_and_split_is_temporal():
    assert not any("delivered" in name or "approved" in name or "carrier" in name for name in FEATURES)
    frame = pd.DataFrame({"order_id": [str(n) for n in range(10)],
                          "purchased_at": pd.date_range("2018-01-01", periods=10),
                          "late": [False, True] * 5})
    training, testing = split_chronologically(frame.sample(frac=1, random_state=1))
    assert len(training) == 8 and len(testing) == 2
    assert training.purchased_at.max() < testing.purchased_at.min()


def test_psi_identical_distribution_is_zero():
    sample = pd.Series(range(100))
    assert population_stability_index(sample, sample) == pytest.approx(0)


def test_train_and_predict_on_synthetic_orders(tmp_path):
        database = tmp_path / "synthetic.duckdb"
        with duckdb.connect(str(database)) as con:
                con.execute("""
                        CREATE TABLE fact_orders AS SELECT 'order' || n AS order_id,
                            'delivered' AS order_status,
                            TIMESTAMP '2018-01-01' + n * INTERVAL '1 day' AS purchased_at,
                            TIMESTAMP '2018-01-06' + n * INTERVAL '1 day' AS estimated_at,
                            TIMESTAMP '2018-01-04' + n * INTERVAL '1 day' +
                                CASE WHEN n % 2 = 0 THEN INTERVAL '5 days' ELSE INTERVAL '0 days' END
                                AS delivered_at,
                            1 AS item_count, 1 AS seller_count, n + 10 AS item_value,
                            2 AS freight_value
                        FROM range(20) AS t(n)
                """)
        report = train(database, tmp_path)
        assert report["test_rows"] == 4
        assert 0 <= predict(database, tmp_path / "model.pkl", "order0")["late_probability"] <= 1
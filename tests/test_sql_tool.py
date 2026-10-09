import duckdb
import pytest

from olist_agent.sql_tool import query_database, validate_sql


@pytest.mark.parametrize("query", [
    "DELETE FROM fact_orders", "SELECT * FROM raw_orders",
    "SELECT * FROM read_csv_auto('secrets.csv')", "SELECT 1; DROP TABLE fact_orders",
    "COPY fact_orders TO 'leak.csv'", "SELECT * FROM main.fact_orders",
])
def test_rejects_unsafe_sql(query):
    with pytest.raises(ValueError):
        validate_sql(query)


def test_cte_and_bounded_query(tmp_path):
    path = tmp_path / "data.duckdb"
    with duckdb.connect(str(path)) as con:
        con.execute("CREATE TABLE fact_orders AS SELECT range AS order_id FROM range(200)")
    rows = query_database(path, "WITH orders AS (SELECT * FROM fact_orders) SELECT * FROM orders")
    assert len(rows) == 100
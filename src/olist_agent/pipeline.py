"""Local Olist ELT, data-quality checks and reproducible timing reports."""

import json
import statistics
import time
from pathlib import Path

import duckdb

TABLES = (
    "customers", "geolocation", "order_items", "order_payments", "order_reviews",
    "orders", "products", "sellers", "product_category_name_translation",
)


def csv_path(data_dir: Path, name: str) -> Path:
    filename = ("product_category_name_translation.csv" if name == "product_category_name_translation"
                else f"olist_{name}_dataset.csv")
    return data_dir / filename

MODEL_SQL = """
CREATE OR REPLACE TABLE dim_date AS
WITH date_values AS (
    SELECT CAST(order_purchase_timestamp AS DATE) AS date_value FROM raw_orders
    UNION ALL
    SELECT CAST(order_delivered_customer_date AS DATE) FROM raw_orders
), bounds AS (
    SELECT MIN(date_value) AS min_date, MAX(date_value) AS max_date FROM date_values
)
SELECT CAST(calendar_date AS DATE) AS date_day,
       CAST(STRFTIME(calendar_date, '%Y%m%d') AS INTEGER) AS date_key,
       YEAR(calendar_date) AS year,
       QUARTER(calendar_date) AS quarter,
       MONTH(calendar_date) AS month,
       STRFTIME(calendar_date, '%B') AS month_name,
       DAY(calendar_date) AS day_of_month,
       DAYOFWEEK(calendar_date) AS day_of_week
FROM bounds, GENERATE_SERIES(min_date, max_date, INTERVAL 1 DAY) AS calendar(calendar_date);
CREATE OR REPLACE TABLE dim_customers AS
SELECT customer_id, customer_unique_id, customer_zip_code_prefix, customer_city, customer_state
FROM raw_customers;
CREATE OR REPLACE TABLE dim_products AS
SELECT p.product_id, p.product_category_name,
       t.product_category_name_english, p.product_weight_g
FROM raw_products p LEFT JOIN raw_product_category_name_translation t
ON p.product_category_name = t.product_category_name;
CREATE OR REPLACE TABLE dim_sellers AS
SELECT seller_id, seller_zip_code_prefix, seller_city, seller_state FROM raw_sellers;
CREATE OR REPLACE TABLE fact_orders AS
WITH items AS (
    SELECT order_id, COUNT(*) AS item_count, COUNT(DISTINCT seller_id) AS seller_count,
           SUM(CAST(price AS DOUBLE)) AS item_value,
           SUM(CAST(freight_value AS DOUBLE)) AS freight_value
    FROM raw_order_items GROUP BY order_id
), payments AS (
    SELECT order_id, SUM(CAST(payment_value AS DOUBLE)) AS payment_value
    FROM raw_order_payments GROUP BY order_id
)
SELECT o.order_id, o.customer_id, o.order_status,
       TRY_CAST(o.order_purchase_timestamp AS TIMESTAMP) AS purchased_at,
       TRY_CAST(o.order_approved_at AS TIMESTAMP) AS approved_at,
       TRY_CAST(o.order_delivered_carrier_date AS TIMESTAMP) AS carrier_at,
       TRY_CAST(o.order_delivered_customer_date AS TIMESTAMP) AS delivered_at,
       TRY_CAST(o.order_estimated_delivery_date AS TIMESTAMP) AS estimated_at,
    CASE WHEN TRY_CAST(o.order_delivered_customer_date AS TIMESTAMP) IS NOT NULL
            AND TRY_CAST(o.order_estimated_delivery_date AS TIMESTAMP) IS NOT NULL
          THEN TRY_CAST(o.order_delivered_customer_date AS TIMESTAMP)
              > TRY_CAST(o.order_estimated_delivery_date AS TIMESTAMP)
          ELSE NULL END AS is_late,
    CASE WHEN TRY_CAST(o.order_delivered_customer_date AS TIMESTAMP) IS NOT NULL
            AND TRY_CAST(o.order_estimated_delivery_date AS TIMESTAMP) IS NOT NULL
          THEN CASE
              WHEN TRY_CAST(o.order_delivered_customer_date AS TIMESTAMP)
                  > TRY_CAST(o.order_estimated_delivery_date AS TIMESTAMP)
              THEN GREATEST(DATE_DIFF('day',
                  CAST(o.order_estimated_delivery_date AS DATE),
                  CAST(o.order_delivered_customer_date AS DATE)), 1)
              ELSE 0 END
          ELSE NULL END AS days_late,
       i.item_count, i.seller_count, i.item_value, i.freight_value, p.payment_value
FROM raw_orders o LEFT JOIN items i USING (order_id) LEFT JOIN payments p USING (order_id);
CREATE OR REPLACE TABLE fact_order_items AS
SELECT i.order_id, CAST(i.order_item_id AS INTEGER) AS order_item_id,
       i.product_id, i.seller_id, CAST(i.price AS DOUBLE) AS price,
       CAST(i.freight_value AS DOUBLE) AS freight_value
FROM raw_order_items i;
CREATE OR REPLACE TABLE fact_reviews AS
SELECT review_id, order_id, CAST(review_score AS INTEGER) AS review_score,
       review_comment_title, review_comment_message
FROM raw_order_reviews;
"""


def quality_summary(checks: list[dict]) -> str:
    core = [check for check in checks if not check["name"].startswith("dim_date_")]
    date_coverage = [check for check in checks if check["name"].startswith("dim_date_")]
    passed_core = sum(check["passed"] for check in core)
    passed_dates = sum(check["passed"] for check in date_coverage)
    return (
        f"{passed_core + passed_dates}/{len(checks)} data-quality checks "
        f"({passed_core} core + {passed_dates} date coverage)"
    )


def build(data_dir: Path, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    missing = [csv_path(data_dir, name).name for name in TABLES
               if not csv_path(data_dir, name).is_file()]
    if missing:
        raise FileNotFoundError(f"Missing Olist CSVs in {data_dir}: {', '.join(missing)}")
    database = output_dir / "olist.duckdb"
    con = duckdb.connect(str(database))
    try:
        for name in TABLES:
            source = csv_path(data_dir, name)
            con.execute(f"CREATE OR REPLACE TABLE raw_{name} AS SELECT * FROM read_csv_auto(?)",
                        [str(source)])
        con.execute(MODEL_SQL)
        checks = quality_checks(con)
        report = {"raw_tables": len(TABLES), "checks": checks,
              "quality_summary": quality_summary(checks),
                  "passed": all(check["passed"] for check in checks)}
        (output_dir / "quality.json").write_text(json.dumps(report, indent=2))
        if not report["passed"]:
            raise ValueError("Data-quality checks failed; inspect quality.json")
        parquet_dir = output_dir / "parquet"
        parquet_dir.mkdir(exist_ok=True)
        for table in ("dim_date", "dim_customers", "dim_products", "dim_sellers", "fact_orders",
                      "fact_order_items", "fact_reviews"):
            con.execute(f"COPY {table} TO ? (FORMAT PARQUET)",
                        [str(parquet_dir / f"{table}.parquet")])
        return report
    finally:
        con.close()


def quality_checks(con: duckdb.DuckDBPyConnection) -> list[dict]:
    rules = {
        "orders_present": "SELECT COUNT(*) > 0 FROM fact_orders",
        "unique_orders": "SELECT COUNT(*) = COUNT(DISTINCT order_id) FROM fact_orders",
        "unique_customers": "SELECT COUNT(*) = COUNT(DISTINCT customer_id) FROM dim_customers",
        "unique_products": "SELECT COUNT(*) = COUNT(DISTINCT product_id) FROM dim_products",
        "unique_sellers": "SELECT COUNT(*) = COUNT(DISTINCT seller_id) FROM dim_sellers",
        "item_keys": "SELECT COUNT(*) = COUNT(DISTINCT (order_id, order_item_id)) FROM fact_order_items",
        "valid_item_prices": "SELECT COUNT(*) = 0 FROM fact_order_items WHERE price < 0 OR freight_value < 0",
        "item_order_fk": "SELECT COUNT(*) = 0 FROM fact_order_items i LEFT JOIN fact_orders o USING(order_id) WHERE o.order_id IS NULL",
        "customer_fk": "SELECT COUNT(*) = 0 FROM fact_orders o LEFT JOIN dim_customers c USING(customer_id) WHERE c.customer_id IS NULL",
        "item_product_fk": "SELECT COUNT(*) = 0 FROM fact_order_items i LEFT JOIN dim_products p USING(product_id) WHERE p.product_id IS NULL",
        "item_seller_fk": "SELECT COUNT(*) = 0 FROM fact_order_items i LEFT JOIN dim_sellers s USING(seller_id) WHERE s.seller_id IS NULL",
        "valid_delivery_dates": "SELECT COUNT(*) = 0 FROM fact_orders WHERE delivered_at < purchased_at",
        "dim_date_purchase_coverage": "SELECT COUNT(*) = 0 FROM fact_orders o LEFT JOIN dim_date d ON CAST(o.purchased_at AS DATE) = d.date_day WHERE o.purchased_at IS NOT NULL AND d.date_day IS NULL",
        "dim_date_delivery_coverage": "SELECT COUNT(*) = 0 FROM fact_orders o LEFT JOIN dim_date d ON CAST(o.delivered_at AS DATE) = d.date_day WHERE o.delivered_at IS NOT NULL AND d.date_day IS NULL",
    }
    return [{"name": name, "passed": bool(con.execute(query).fetchone()[0])}
            for name, query in rules.items()]


def benchmark(data_dir: Path, output_dir: Path, repeats: int = 5) -> dict:
    if repeats < 1:
        raise ValueError("repeats must be positive")
    csv_file = data_dir / "olist_order_items_dataset.csv"
    parquet_file = output_dir / "parquet" / "fact_order_items.parquet"
    if not csv_file.is_file() or not parquet_file.is_file():
        raise FileNotFoundError("Build the project before benchmarking")
    con = duckdb.connect()
    try:
        timings = {}
        results = {}
        for fmt, path, source in (("csv", csv_file, "read_csv_auto(?)"),
                                  ("parquet", parquet_file, "read_parquet(?)")):
            query = ("SELECT COUNT(*), SUM(CAST(price AS DECIMAL(18,2))), "
                     f"SUM(CAST(freight_value AS DECIMAL(18,2))) FROM {source}")
            samples = []
            for _ in range(repeats):
                start = time.perf_counter()
                result = con.execute(query, [str(path)]).fetchone()
                samples.append(time.perf_counter() - start)
            timings[fmt] = samples
            results[fmt] = result
        if results["csv"] != results["parquet"]:
            raise ValueError("CSV and Parquet aggregates differ")
        report = {"repeats": repeats, "csv_seconds": statistics.median(timings["csv"]),
                  "parquet_seconds": statistics.median(timings["parquet"]),
                  "aggregate": [results["csv"][0], str(results["csv"][1]),
                                str(results["csv"][2])]}
        (output_dir / "benchmark.json").write_text(json.dumps(report, indent=2))
        return report
    finally:
        con.close()


def prefect_flow(data_dir: Path, output_dir: Path) -> dict:
    from prefect import flow, task

    @task
    def run_build() -> dict:
        return build(data_dir, output_dir)

    @flow(name="olist-elt")
    def run_flow() -> dict:
        return run_build()

    return run_flow()
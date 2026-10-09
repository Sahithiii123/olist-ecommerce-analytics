import csv

import duckdb

from olist_agent.data_dictionary import missing_column_descriptions, write_data_dictionary
from olist_agent.delivery import analyze_delivery
from olist_agent.pipeline import MODEL_SQL, benchmark, build, csv_path, quality_checks


def test_translation_csv_has_distinct_filename(tmp_path):
    assert csv_path(tmp_path, "product_category_name_translation").name == "product_category_name_translation.csv"


def fixture_rows():
    return {
        "customers": ("customer_id,customer_unique_id,customer_zip_code_prefix,customer_city,customer_state", [("c", "u", 1, "x", "SP")]),
        "products": ("product_id,product_category_name,product_weight_g", [("p", "cat", 10)]),
        "product_category_name_translation": ("product_category_name,product_category_name_english", [("cat", "category")]),
        "sellers": ("seller_id,seller_zip_code_prefix,seller_city,seller_state", [("s", 1, "x", "SP")]),
        "orders": ("order_id,customer_id,order_status,order_purchase_timestamp,order_approved_at,order_delivered_carrier_date,order_delivered_customer_date,order_estimated_delivery_date", [("o", "c", "delivered", "2018-01-01", "2018-01-02", "2018-01-03", "2018-01-05", "2018-01-04")]),
        "order_items": ("order_id,order_item_id,product_id,seller_id,price,freight_value", [("o", 1, "p", "s", 10, 2), ("o", 2, "p", "s", 20, 3)]),
        "order_payments": ("order_id,payment_value", [("o", 15), ("o", 20)]),
        "order_reviews": ("review_id,order_id,review_score,review_comment_title,review_comment_message", [("r", "o", 4, "ok", "fine")]),
    }
def test_order_grain_survives_multiple_items_and_payments():
    con = duckdb.connect()
    for name, (header, rows) in fixture_rows().items():
        con.execute(f"CREATE TABLE raw_{name} AS SELECT * FROM (VALUES {','.join(str(tuple(row)) for row in rows)}) AS v({header})")
    con.execute(MODEL_SQL)
    assert con.execute("SELECT item_count, payment_value FROM fact_orders").fetchone() == (2, 35.0)
    assert all(check["passed"] for check in quality_checks(con))


def test_build_and_benchmark_tiny_csvs(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    for name, (header, rows) in {**fixture_rows(), "geolocation":
                                ("geolocation_zip_code_prefix,geolocation_city", [(1, "x")])}.items():
        with csv_path(raw, name).open("w", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(header.split(","))
            writer.writerows(rows)
    output = tmp_path / "artifacts"
    assert build(raw, output)["passed"]
    assert benchmark(raw, output, repeats=1)["aggregate"][0] == 2


def test_analyze_delivery_deduplicates_reviews_per_order(tmp_path):
    database = tmp_path / "olist.duckdb"
    con = duckdb.connect(str(database))
    for name, (header, rows) in fixture_rows().items():
        values = ",".join(str(tuple(row)) for row in rows)
        columns = header.replace(",", ", ")
        con.execute(f"CREATE TABLE raw_{name} AS SELECT * FROM (VALUES {values}) AS v({columns})")
    con.execute("INSERT INTO raw_order_reviews VALUES ('r2', 'o', 2, NULL, NULL)")
    con.execute(MODEL_SQL)
    con.close()

    tableau = tmp_path / "tableau"
    result = analyze_delivery(database, tableau)
    assert result["rows"]["seller_metrics.csv"] == 1
    assert result["rows"]["kpi_summary.csv"] == 1
    assert result["rows"]["state_metrics.csv"] == 2
    assert result["rows"]["review_by_lateness.csv"] == 1
    assert result["rows"]["fact_orders_flat.csv"] == 1
    assert result["data_quality"] == "14/14 data-quality checks (12 core + 2 date coverage)"
    expected_headers = {
        "kpi_summary.csv": ["orders", "on_time_delivery_pct", "late_order_pct",
                            "avg_review_score", "avg_score_on_time", "avg_score_late"],
        "review_by_lateness.csv": ["lateness_bucket", "bucket_order", "order_count",
                                   "pct_of_orders", "avg_review_score"],
        "state_metrics.csv": ["state_code", "state_name", "country", "state_role",
                              "order_count", "on_time_delivery_pct", "late_order_pct",
                              "avg_review_score"],
        "seller_metrics.csv": ["seller_id", "seller_state", "state_name", "country",
                               "order_count", "on_time_delivery_pct", "late_order_pct",
                               "avg_review_score", "meets_min_orders"],
        "fact_orders_flat.csv": ["order_id", "customer_id", "customer_state", "purchased_at",
                                 "delivered_at", "estimated_at", "is_late", "days_late",
                                 "review_score"],
    }
    for filename, headers in expected_headers.items():
        with (tableau / filename).open(newline="", encoding="utf-8") as stream:
            assert next(csv.reader(stream)) == headers

    with (tableau / "kpi_summary.csv").open(newline="", encoding="utf-8") as stream:
        kpi = next(csv.DictReader(stream))
    assert kpi["orders"] == "1"
    assert kpi["late_order_pct"] == "100.0"
    assert kpi["avg_score_late"] == "3.0"

    with (tableau / "seller_metrics.csv").open(newline="") as stream:
        seller = next(csv.DictReader(stream))
    assert seller["state_name"] == "Sao Paulo"
    assert seller["country"] == "Brazil"
    assert seller["meets_min_orders"] == "false"
    assert seller["avg_review_score"] == "3.0"
    assert seller["order_count"] == "1"

    with (tableau / "state_metrics.csv").open(newline="", encoding="utf-8") as stream:
        state_rows = list(csv.DictReader(stream))
    assert {(row["state_role"], row["state_name"]) for row in state_rows} == {
        ("seller", "Sao Paulo"), ("customer", "Sao Paulo")
    }

    with (tableau / "review_by_lateness.csv").open(newline="") as stream:
        lateness = list(csv.DictReader(stream))
    assert lateness[0]["lateness_bucket"] == "1-3 days"
    assert lateness[0]["bucket_order"] == "2"
    assert lateness[0]["pct_of_orders"] == "100.0"

    with duckdb.connect(str(database)) as dictionary_con:
        assert missing_column_descriptions(dictionary_con, tableau) == []
    dictionary_path = tmp_path / "DATA_DICTIONARY.md"
    assert write_data_dictionary(database, dictionary_path, tableau) > 36
    assert "## `tableau_kpi_summary`" in dictionary_path.read_text(encoding="utf-8")

    kpi_path = tableau / "kpi_summary.csv"
    with kpi_path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.reader(stream))
    rows[0].append("undocumented_metric")
    for row in rows[1:]:
        row.append("")
    with kpi_path.open("w", newline="", encoding="utf-8") as stream:
        csv.writer(stream).writerows(rows)
    with duckdb.connect(str(database)) as dictionary_con:
        assert missing_column_descriptions(dictionary_con, tableau) == [
            "tableau_kpi_summary.undocumented_metric"
        ]


def test_data_dictionary_requires_descriptions_for_schema_columns(tmp_path):
    con = duckdb.connect()
    for name, (header, rows) in fixture_rows().items():
        values = ",".join(str(tuple(row)) for row in rows)
        columns = header.replace(",", ", ")
        con.execute(f"CREATE TABLE raw_{name} AS SELECT * FROM (VALUES {values}) AS v({columns})")
    con.execute(MODEL_SQL)
    assert missing_column_descriptions(con) == []
    con.execute("CREATE TABLE raw_unmapped (unmapped_column VARCHAR)")
    assert missing_column_descriptions(con) == ["raw_unmapped.unmapped_column"]
    con.close()
"""Delivery and review analysis exports."""

from pathlib import Path

import duckdb

from olist_agent.pipeline import quality_checks, quality_summary

MIN_SELLER_ORDERS = 30

EXPORTS = {
    "delivery_kpi_summary": "kpi_summary.csv",
    "delivery_review_by_lateness": "review_by_lateness.csv",
    "delivery_state_metrics": "state_metrics.csv",
    "delivery_seller_metrics": "seller_metrics.csv",
    "delivery_fact_orders_flat": "fact_orders_flat.csv",
}

# Stable row order so repeated exports are byte-identical.
EXPORT_ORDER = {
    "delivery_kpi_summary": "1",
    "delivery_review_by_lateness": "bucket_order",
    "delivery_state_metrics": "state_role, state_code",
    "delivery_seller_metrics": "late_order_pct DESC, order_count DESC, seller_id",
    "delivery_fact_orders_flat": "order_id",
}


def analyze_delivery(database: Path, output_dir: Path, sql_path: Path | None = None) -> dict:
    """Run the delivery analysis SQL and export Tableau-ready CSV files."""
    if not database.is_file():
        raise FileNotFoundError(f"DuckDB database not found: {database}")
    if sql_path is None:
        sql_path = Path(__file__).resolve().parents[2] / "sql" / "delivery_vs_reviews.sql"
    if not sql_path.is_file():
        raise FileNotFoundError(f"Delivery analysis SQL not found: {sql_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(database))
    try:
        sql = sql_path.read_text(encoding="utf-8").replace(
            "__MIN_SELLER_ORDERS__", str(MIN_SELLER_ORDERS)
        )
        con.execute(sql)
        missing_state_names = con.execute(
            """SELECT COUNT(*) FROM delivery_state_metrics WHERE state_name IS NULL
               UNION ALL
               SELECT COUNT(*) FROM delivery_seller_metrics WHERE state_name IS NULL"""
        ).fetchall()
        if any(count for (count,) in missing_state_names):
            raise ValueError("A Brazilian state code has no ASCII state-name mapping")

        exported = {}
        for view, filename in EXPORTS.items():
            destination = output_dir / filename
            con.execute(
                f"COPY (SELECT * FROM {view} ORDER BY {EXPORT_ORDER[view]}) "
                "TO ? (HEADER, DELIMITER ',')",
                        [str(destination)])
            exported[filename] = con.execute(f"SELECT COUNT(*) FROM {view}").fetchone()[0]
        checks = quality_checks(con)
        return {"output_dir": str(output_dir), "rows": exported,
                "data_quality": quality_summary(checks)}
    finally:
        con.close()
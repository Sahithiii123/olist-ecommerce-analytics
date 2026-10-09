"""Information-schema-backed data dictionary generation."""

from pathlib import Path

import duckdb

COLUMN_DESCRIPTIONS = {
    "customer_id": "Unique identifier for a customer record/order customer.",
    "customer_unique_id": "Stable identifier linking customer records belonging to the same person.",
    "customer_zip_code_prefix": "Customer's five-digit postal-code prefix.",
    "customer_city": "Customer city as supplied in the source data.",
    "customer_state": "Two-letter Brazilian state code for the customer.",
    "geolocation_zip_code_prefix": "Postal-code prefix associated with this geolocation observation.",
    "geolocation_lat": "Latitude associated with the postal-code prefix.",
    "geolocation_lng": "Longitude associated with the postal-code prefix.",
    "geolocation_city": "City label associated with the postal-code prefix.",
    "geolocation_state": "State code associated with the postal-code prefix.",
    "order_id": "Unique identifier for an order.",
    "order_item_id": "One-based item sequence number within an order.",
    "product_id": "Unique identifier for a product.",
    "seller_id": "Unique identifier for a seller.",
    "shipping_limit_date": "Latest date/time by which the seller should hand the item to the carrier.",
    "price": "Item selling price in R$ (BRL), excluding freight.",
    "freight_value": "Freight charge in R$ (BRL) for the item/order.",
    "payment_sequential": "Sequence number for a payment method applied to an order.",
    "payment_type": "Payment method reported for the payment record.",
    "payment_installments": "Number of installments used for the payment record.",
    "payment_value": "Amount in R$ (BRL) for the payment record.",
    "review_id": "Identifier for an individual review row; an order can have multiple rows.",
    "review_score": "Integer customer review score, usually on a one-to-five scale.",
    "review_comment_title": "Optional customer-authored review title.",
    "review_comment_message": "Optional customer-authored review text.",
    "review_creation_date": "Timestamp when the review was created.",
    "review_answer_timestamp": "Timestamp when the review was answered.",
    "order_status": "Lifecycle status reported for the order.",
    "order_purchase_timestamp": "Source purchase timestamp for the order.",
    "order_approved_at": "Source timestamp when payment approval was recorded.",
    "order_delivered_carrier_date": "Source timestamp when the order was handed to the carrier.",
    "order_delivered_customer_date": "Source timestamp when the order was delivered to the customer.",
    "order_estimated_delivery_date": "Source promised/estimated customer delivery timestamp.",
    "product_category_name": "Portuguese product category label from the source catalog.",
    "product_category_name_english": "English translation of the product category, where available.",
    "product_name_lenght": "Source product-name character count; spelling retained from source column.",
    "product_description_lenght": "Source product-description character count; spelling retained from source column.",
    "product_photos_qty": "Number of product photos reported in the catalog.",
    "product_weight_g": "Product weight in grams.",
    "product_length_cm": "Product length in centimeters.",
    "product_height_cm": "Product height in centimeters.",
    "product_width_cm": "Product width in centimeters.",
    "seller_zip_code_prefix": "Seller's five-digit postal-code prefix.",
    "seller_city": "Seller city as supplied in the source data.",
    "seller_state": "Two-letter Brazilian state code for the seller.",
    "date_day": "Calendar date in the generated date dimension.",
    "date_key": "Integer date key formatted as YYYYMMDD.",
    "year": "Calendar year for the date dimension row.",
    "quarter": "Calendar quarter number, 1 through 4.",
    "month": "Calendar month number, 1 through 12.",
    "month_name": "English calendar month name.",
    "day_of_month": "Calendar day number within the month.",
    "day_of_week": "DuckDB day-of-week number for the calendar date.",
    "purchased_at": "Purchase timestamp cast from the raw order timestamp.",
    "approved_at": "Payment approval timestamp cast from the raw order timestamp.",
    "carrier_at": "Carrier handoff timestamp cast from the raw order timestamp.",
    "delivered_at": "Customer delivery timestamp cast from the raw order timestamp.",
    "estimated_at": "Estimated delivery timestamp cast from the raw order timestamp.",
    "is_late": "TRUE when a delivered timestamp is later than the estimated timestamp; NULL when either is missing.",
    "days_late": "Calendar days beyond the estimate for delivered orders; zero on time and NULL when dates are missing.",
    "item_count": "Number of order-item rows associated with the order.",
    "seller_count": "Number of distinct sellers represented by the order's items.",
    "item_value": "Sum of item prices in R$ (BRL) for the order, excluding freight.",
    "orders": "Number of delivered orders with at least one review.",
    "on_time_delivery_pct": "On-time percentage from 0 to 100 among orders with known lateness status.",
    "late_order_pct": "Late-order percentage from 0 to 100 among orders with known lateness status.",
    "avg_review_score": "Arithmetic mean of one mean review score per order.",
    "avg_score_on_time": "Average per-order review score for on-time orders.",
    "avg_score_late": "Average per-order review score for late orders.",
    "lateness_bucket": "Delivery lateness group: On time, 1-3 days, 4-7 days, or 8+ days.",
    "bucket_order": "Sort order for the lateness bucket, from 1 (On time) through 4 (8+ days).",
    "order_count": "Number of orders at the grain of this exported seller, state, or lateness group.",
    "pct_of_orders": "Share from 0 to 100 of known-lateness delivered reviewed orders in this bucket.",
    "state_code": "Two-letter Brazilian state abbreviation used for Tableau geographic matching.",
    "state_name": "Plain ASCII English name for the Brazilian state code.",
    "country": "Country label; always Brazil for these exports.",
    "state_role": "Whether state_code describes the seller or the customer.",
    "meets_min_orders": "TRUE when the seller has at least MIN_SELLER_ORDERS distinct reviewed delivered orders.",
}

TABLE_SOURCES = {
    "raw_customers": "olist_customers_dataset.csv (raw)",
    "raw_geolocation": "olist_geolocation_dataset.csv (raw)",
    "raw_order_items": "olist_order_items_dataset.csv (raw)",
    "raw_order_payments": "olist_order_payments_dataset.csv (raw)",
    "raw_order_reviews": "olist_order_reviews_dataset.csv (raw)",
    "raw_orders": "olist_orders_dataset.csv (raw)",
    "raw_products": "olist_products_dataset.csv (raw)",
    "raw_sellers": "olist_sellers_dataset.csv (raw)",
    "raw_product_category_name_translation": "product_category_name_translation.csv (raw)",
    "dim_customers": "raw_customers",
    "dim_date": "Generated from purchase and customer-delivery timestamps in raw_orders",
    "dim_products": "raw_products LEFT JOIN raw_product_category_name_translation",
    "dim_sellers": "raw_sellers",
    "fact_order_items": "raw_order_items",
    "fact_orders": "raw_orders with item and payment aggregates",
    "fact_reviews": "raw_order_reviews",
    "tableau_kpi_summary": "tableau/kpi_summary.csv exported from reviewed delivered orders",
    "tableau_review_by_lateness": "tableau/review_by_lateness.csv exported from reviewed delivered orders",
    "tableau_state_metrics": "tableau/state_metrics.csv exported from reviewed delivered orders and dimensions",
    "tableau_seller_metrics": "tableau/seller_metrics.csv exported from reviewed delivered orders and dimensions",
    "tableau_fact_orders_flat": "tableau/fact_orders_flat.csv exported at one row per reviewed delivered order",
}

TABLE_GRAINS = {
    "raw_customers": "One source customer record",
    "raw_geolocation": "One source postal-code geolocation observation",
    "raw_order_items": "One order line item",
    "raw_order_payments": "One payment method/sequence per order",
    "raw_order_reviews": "One source review row",
    "raw_orders": "One source order",
    "raw_products": "One source product",
    "raw_sellers": "One source seller",
    "raw_product_category_name_translation": "One Portuguese-to-English category mapping",
    "dim_customers": "One customer ID",
    "dim_date": "One calendar date",
    "dim_products": "One product ID",
    "dim_sellers": "One seller ID",
    "fact_order_items": "One order ID and order item ID",
    "fact_orders": "One order ID",
    "fact_reviews": "One source review ID; multiple rows per order are retained",
    "tableau_kpi_summary": "One overall summary row",
    "tableau_review_by_lateness": "One row per observed lateness bucket",
    "tableau_state_metrics": "One state and role (seller/customer)",
    "tableau_seller_metrics": "One seller ID",
    "tableau_fact_orders_flat": "One delivered reviewed order",
}

KPI_COLUMNS = {
    ("fact_orders", "order_id"): "order count; delivery percentages",
    ("fact_orders", "delivered_at"): "delivered-order filter; delivery percentages",
    ("fact_orders", "estimated_at"): "on-time and late delivery classification",
    ("fact_orders", "is_late"): "on-time delivery %; late-order %",
    ("fact_orders", "days_late"): "review score by lateness bucket",
    ("fact_orders", "customer_id"): "customer-state grouping",
    ("fact_reviews", "order_id"): "review-to-order join and duplicate-review handling",
    ("fact_reviews", "review_score"): "average review score",
    ("fact_order_items", "order_id"): "seller/order attribution",
    ("fact_order_items", "seller_id"): "seller-level and seller-state grouping",
    ("dim_sellers", "seller_id"): "seller-level join",
    ("dim_sellers", "seller_state"): "seller-state grouping",
    ("dim_customers", "customer_id"): "customer-level join",
    ("dim_customers", "customer_state"): "customer-state grouping",
    ("dim_date", "date_day"): "purchase/delivery calendar coverage",
    ("fact_order_items", "price"): "item sales value (not a delivery/review KPI)",
    ("tableau_kpi_summary", "orders"): "overall reviewed delivered order count",
    ("tableau_kpi_summary", "on_time_delivery_pct"): "overall on-time delivery percentage",
    ("tableau_kpi_summary", "late_order_pct"): "overall late-order percentage",
    ("tableau_kpi_summary", "avg_review_score"): "overall average review score",
    ("tableau_kpi_summary", "avg_score_on_time"): "on-time average review score",
    ("tableau_kpi_summary", "avg_score_late"): "late-order average review score",
    ("tableau_review_by_lateness", "lateness_bucket"): "lateness chart category",
    ("tableau_review_by_lateness", "bucket_order"): "lateness chart sorting",
    ("tableau_review_by_lateness", "order_count"): "lateness bucket sample size",
    ("tableau_review_by_lateness", "pct_of_orders"): "share of classified orders in each lateness bucket",
    ("tableau_review_by_lateness", "avg_review_score"): "average score by lateness bucket",
    ("tableau_state_metrics", "state_code"): "state geographic key",
    ("tableau_state_metrics", "state_name"): "state map label",
    ("tableau_state_metrics", "state_role"): "seller-state/customer-state distinction",
    ("tableau_seller_metrics", "seller_id"): "seller comparison key",
    ("tableau_seller_metrics", "meets_min_orders"): "30-order seller volume flag",
    ("tableau_fact_orders_flat", "order_id"): "one-row-per-order KPI grain",
}


TABLEAU_CSVS = (
    "kpi_summary.csv", "review_by_lateness.csv", "state_metrics.csv",
    "seller_metrics.csv", "fact_orders_flat.csv",
)


def schema_columns(
    con: duckdb.DuckDBPyConnection, tableau_dir: Path | None = None
) -> list[tuple[str, str, str]]:
    columns = con.execute(
        """SELECT table_name, column_name, data_type
           FROM information_schema.columns
           WHERE (table_schema = 'main'
                  AND (table_name LIKE 'raw_%' OR table_name LIKE 'dim_%' OR table_name LIKE 'fact_%'))
           ORDER BY table_name, ordinal_position"""
    ).fetchall()
    if tableau_dir is not None:
        for filename in TABLEAU_CSVS:
            path = tableau_dir / filename
            if not path.is_file():
                raise FileNotFoundError(f"Missing Tableau CSV for dictionary: {path}")
            csv_path = path.resolve().as_posix().replace("'", "''")
            output_table = f"tableau_{path.stem}"
            csv_columns = con.execute(
                f"DESCRIBE SELECT * FROM read_csv_auto('{csv_path}')"
            ).fetchall()
            columns.extend((output_table, column[0], column[1]) for column in csv_columns)
    return columns


def missing_column_descriptions(
    con: duckdb.DuckDBPyConnection, tableau_dir: Path | None = None
) -> list[str]:
    return [f"{table}.{column}" for table, column, _ in schema_columns(con, tableau_dir)
            if column not in COLUMN_DESCRIPTIONS]


def write_data_dictionary(
    database: Path, output_path: Path, tableau_dir: Path | None = None
) -> int:
    """Generate the Markdown dictionary from DuckDB schema and handwritten descriptions."""
    if tableau_dir is None:
        tableau_dir = Path("tableau")
    con = duckdb.connect(str(database), read_only=True)
    try:
        columns = schema_columns(con, tableau_dir)
        missing = [f"{table}.{column}" for table, column, _ in columns
                   if column not in COLUMN_DESCRIPTIONS]
        if missing:
            raise ValueError(f"Missing data dictionary descriptions: {', '.join(missing)}")
        lines = [
            "# Data Dictionary",
            "",
            "Generated from DuckDB `information_schema.columns` and DuckDB-inferred Tableau CSV schemas; descriptions and KPI uses are maintained in code.",
            "",
        ]
        current_table = None
        for table, column, data_type in columns:
            if table != current_table:
                current_table = table
                lines.extend([f"## `{table}`", "",
                              f"**Grain:** {TABLE_GRAINS[table]}.  ",
                              f"**Source:** {TABLE_SOURCES[table]}", "",
                              "| Column | DuckDB type | Description | KPI use |",
                              "|---|---|---|---|"])
            kpi_use = KPI_COLUMNS.get((table, column), "None; reference/context field")
            lines.append(f"| `{column}` | `{data_type}` | {COLUMN_DESCRIPTIONS[column]} | {kpi_use} |")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return len(columns)
    finally:
        con.close()
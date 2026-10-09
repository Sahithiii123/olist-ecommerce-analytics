# Delivery and Review Analytics Requirements

## Business Questions

- Do late deliveries lower review scores, and where is the relationship most pronounced?
- What are the on-time delivery and late-order percentages by seller, seller state, and customer state?
- How does average review score vary between on-time and late orders, and across lateness buckets?
- Which sellers or states merit operational follow-up after considering their order counts?

These are descriptive questions. The analysis measures association, not the causal effect of lateness on customer satisfaction.

## Stakeholders

- Analysts define and interpret delivery and review KPIs and build the Tableau workbook.
- Data engineers own reproducible ingestion, the star-schema model, metric SQL, and data-quality checks.
- Delivery operations and seller-management teams use seller and geographic breakdowns to prioritize investigation.
- Business leadership uses the aggregate view to monitor delivery experience without treating correlation as causation.

## Data Assets and Grain

The ELT ingests the nine Olist source CSVs as `raw_*` tables. It models `dim_customers`, `dim_date`, `dim_products`, and `dim_sellers`, plus `fact_orders`, `fact_order_items`, and `fact_reviews`.

- `fact_orders`: one row per order. `is_late` and `days_late` are NULL when either actual or estimated delivery time is unavailable.
- `fact_order_items`: one row per `(order_id, order_item_id)`.
- `fact_reviews`: one row per source review ID; multiple reviews for an order are retained.
- `dim_date`: one row per calendar day from the earliest purchase/delivery date through the latest, inclusive.
- `tableau/fact_orders_flat.csv`: one row per delivered reviewed order, independent of seller count, so overall KPI averages do not overweight multi-seller orders.
- Seller metrics count each distinct order once per seller. Seller-state metrics count each distinct order once per seller state. Customer-state metrics count each order once per customer state.

## KPI Definitions

All delivery/review analysis includes orders with a non-null customer delivery timestamp and at least one review row. Before joining, review rows are reduced to one record per order: `review_score` is the arithmetic mean of that order's non-null source review scores. This prevents multiple reviews from multiplying the order's weight. `order_count` counts the resulting analysis-grain rows, not raw item lines or review rows.

- **On-time delivery %** = 100 × count of included orders with `is_late = FALSE` / count of included orders with known `is_late` status.
- **Late-order %** = 100 × count of included orders with `is_late = TRUE` / count of included orders with known `is_late` status.
- **Average review score** = arithmetic mean of the per-order mean review score over the included analysis-grain rows. Seller and seller-state summaries therefore weight each order once for each seller attribution; customer-state summaries weight each order once.
- **Late status** = `delivered_at > estimated_at`, comparing timestamps. A missing timestamp yields unknown status and is not in the on-time/late percentage denominator.
- **Days late** = calendar-day difference between estimated and actual delivery dates, floored at zero for on-time deliveries and at one for any timestamp-late delivery. The date-based bucket labels are `on time`, `1-3 days`, `4-7 days`, and `8+ days`.
- **Sales context** = sum of order-item `price` in Brazilian reais, excluding freight and payment totals; it is not a delivery KPI.
- All monetary fields are labeled R$ (BRL). The item-sales sum uses `price` only, excluding freight.

## Filters

The delivered-review dataset excludes undelivered orders and delivered orders without a review row. Delivery percentage denominators additionally exclude orders with unknown lateness status. The lateness comparison and lateness-bucket outputs include only known lateness status. No date range or state is excluded by default. Tableau users may filter the purchase date, seller ID/state, customer state, and lateness group; filtering must not change the KPI formulas above.

## Tableau CSV Contract

The five UTF-8 CSV exports use numeric percentage values on a 0-100 scale. `kpi_summary.csv` contains one row with `orders`, `on_time_delivery_pct`, `late_order_pct`, `avg_review_score`, `avg_score_on_time`, and `avg_score_late`. `review_by_lateness.csv` contains `lateness_bucket`, `bucket_order` (1-4), `order_count`, `pct_of_orders`, and `avg_review_score`. Bucket percentages are each bucket's share of orders with known lateness status. `state_metrics.csv` uses one row per `state_code` and `state_role`, with `state_name`, `country`, `order_count`, both delivery percentages, and average score. Roles are `seller` and `customer`; state names use plain ASCII English. `seller_metrics.csv` contains seller-level counts and KPIs, Brazilian state code and name, `country`, and `meets_min_orders`. That flag uses the named `MIN_SELLER_ORDERS = 30` constant in `olist_agent.delivery`. `fact_orders_flat.csv` has one row per delivered reviewed order.

## Acceptance Criteria

- ELT loads all nine raw tables and produces the seven modeled tables with an order-grain `fact_orders` and purchase/delivery date coverage in `dim_date`.
- 14/14 data-quality checks (12 core + 2 date coverage) pass; purchase-date and delivery-date coverage are checked separately.
- `sql/delivery_vs_reviews.sql` produces seller metrics, seller/customer state metrics, on-time-versus-late review scores, and day-late buckets using fact/dimension joins.
- Duplicate reviews are explicitly handled as one mean score per order before aggregation.
- `olist analyze-delivery` writes the five CSVs specified in the Tableau CSV Contract under `tableau/` and reports `14/14 data-quality checks (12 core + 2 date coverage)` when all checks pass.
- A tiny fixture verifies export shape and review deduplication. A schema-driven dictionary test fails if a DuckDB column lacks a handwritten description.
- Tableau worksheets and filters follow `tableau/BUILD_GUIDE.md`; the repository does not claim a completed Tableau workbook until one is built and reviewed.
- Reported dataset totals and findings are obtained from the checked-in local raw CSVs and DuckDB queries; no sample-derived or hardcoded outcome figures are presented as measured results.

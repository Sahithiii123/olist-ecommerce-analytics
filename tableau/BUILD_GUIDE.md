# Tableau Public Build Guide

## 1. Generate the CSVs

From the repository root, run:

```powershell
python -m olist_agent.cli build
python -m olist_agent.cli analyze-delivery
```

This produces five UTF-8 CSVs in `tableau/` (`fact_orders_flat.csv` is git-ignored and only exists after you run the command). Percentages are numeric values from 0 to 100, not fractions. Brazilian state names are plain ASCII. Use separate Tableau data sources for the files; their grains differ, so do not physically join the aggregate extracts to `fact_orders_flat.csv`.

| File | Grain | Fields, in order |
|---|---|---|
| `kpi_summary.csv` | One summary row | `orders`, `on_time_delivery_pct`, `late_order_pct`, `avg_review_score`, `avg_score_on_time`, `avg_score_late` |
| `review_by_lateness.csv` | One row per observed lateness bucket | `lateness_bucket`, `bucket_order`, `order_count`, `pct_of_orders`, `avg_review_score` |
| `state_metrics.csv` | One state and role | `state_code`, `state_name`, `country`, `state_role`, `order_count`, `on_time_delivery_pct`, `late_order_pct`, `avg_review_score` |
| `seller_metrics.csv` | One seller | `seller_id`, `seller_state`, `state_name`, `country`, `order_count`, `on_time_delivery_pct`, `late_order_pct`, `avg_review_score`, `meets_min_orders` |
| `fact_orders_flat.csv` | One delivered reviewed order | `order_id`, `customer_id`, `customer_state`, `purchased_at`, `delivered_at`, `estimated_at`, `is_late`, `days_late`, `review_score` |

`review_score` is the per-order mean when the source has multiple reviews for that order. The bucket percentage denominator is all included orders with known lateness status. Delivery rates also exclude unknown lateness status. The seller flag uses `olist_agent.delivery.MIN_SELLER_ORDERS`, currently 30 orders.

## 2. Build the worksheets

### KPI tiles

Connect to `kpi_summary.csv`. Make six text tiles from the single row: `orders`, `on_time_delivery_pct`, `late_order_pct`, `avg_review_score`, `avg_score_on_time`, and `avg_score_late`. Rename the visible captions for readability without changing the underlying fields.

Format review scores to two decimals. Format the percentage fields as Number (Custom) with two decimal places and a literal percent sign, for example `0.00\%`; do not apply Tableau's Percentage format because that would multiply the already-scaled 0-100 values by 100. Confirm the chosen custom format displays the literal percent suffix in your Tableau version.

### State map

Connect to `state_metrics.csv`. Use `state_name` as the State/Province geographic field and include `country` on Detail to scope the location to Brazil. Color by `late_order_pct`; put `order_count`, `on_time_delivery_pct`, and `avg_review_score` in Tooltip. Add a filter on `state_role` with `seller` and `customer` choices, and show the selected role in the title. State names are ASCII spellings such as `Sao Paulo` and `Espirito Santo`. If Tableau does not geocode a spelling, add a workbook geographic alias for that same Brazilian state; do not edit the CSV values.

### Seller table

Connect to `seller_metrics.csv`. Display `seller_id`, `seller_state`, `state_name`, `order_count`, `on_time_delivery_pct`, `late_order_pct`, `avg_review_score`, and `meets_min_orders`. Sort by `late_order_pct` descending. Offer `meets_min_orders` as a filter, defaulting to true only if the filter state is clearly shown; the flag is true at 30 or more orders. Keep `order_count` visible so sample size is not hidden.

### Review score by lateness

Connect to `review_by_lateness.csv`. Put `lateness_bucket` on Columns and `avg_review_score` on Rows; show `order_count` and `pct_of_orders` in Tooltip. Sort the bucket by `bucket_order` ascending (1 through 4) so the display order is On time, 1-3 days, 4-7 days, 8+ days. Use a bar chart and a zero-based score axis.

### Order detail

Optionally connect to `fact_orders_flat.csv` for a detail sheet or a purchase-date trend. It contains exactly one row per delivered reviewed order, independent of seller count. Do not use it to reconstruct seller metrics; use `seller_metrics.csv` for seller-level rows.

## 3. Assemble the dashboard

Use a 16:9 layout with six compact KPI tiles across the top, the state map beside the seller table, and the lateness bar chart across the lower area. Keep sample counts visible with rates and averages. Add a short footnote that these are descriptive results for delivered orders with reviews, not a causal estimate.

Filters are source-specific: `state_role` belongs to the map; `meets_min_orders` and seller state belong to the seller table; purchase date belongs to the order-detail source; lateness bucket is inherent in the lateness chart. These files do not support one universal cross-source filter. Scope filters to their own worksheets unless you build and validate a Tableau relationship.

## 4. Validate before publishing

- Confirm all five source headers match the contract above and all CSVs use UTF-8.
- Confirm percentages display on the 0-100 scale without Tableau percentage-format multiplication.
- Confirm the state map is scoped to Brazil and `state_role` is explicit.
- Confirm the seller threshold is the documented 30-order flag and low-volume sellers are not silently hidden.
- Confirm lateness bucket order and displayed counts; reconcile summary values with `docs/FINDINGS.md`.
- Review the dashboard in Tableau Public, save a dashboard screenshot as `tableau/dashboard.png`, and keep the published Tableau Public URL in the README.

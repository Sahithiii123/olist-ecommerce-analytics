# Delivery and Review Findings

Computed from the nine files in `data/raw/` by the DuckDB build and `sql/delivery_vs_reviews.sql` on 2026-10-08. Values below describe this Olist extract and are descriptive, not causal.

## Data and Quality

- Raw tables ingested: 9.
- Order items: 112,650 rows.
- Item prices summed from `fact_order_items.price`: R$ (BRL) 13,591,643.70. This is R$13.6M in item sales, excluding freight, rounded to one decimal place.
- Orders: 99,441; delivered orders with at least one review: 95,830.
- Source reviews: 99,224 rows. There are 547 orders with multiple review rows (1,098 rows across those orders); each order contributes one mean review score to the analysis.
- 14/14 data-quality checks (12 core + 2 date coverage) pass.
- `dim_date` contains 774 consecutive calendar days, 2016-09-04 through 2018-10-17, covering all 634 distinct purchase dates and 645 distinct non-null delivery dates.

## Delivery and Review Relationship

For delivered orders with reviews and known lateness status, there are 95,830 observations: 88,168 on time (92.00%) and 7,662 late (8.00%). The overall per-order average review score is 4.156; it is 4.294 on time and 2.567 late, a difference of -1.728 points for late orders.

| Lateness bucket | Orders | Share of classified orders | Average review score |
|---|---:|---:|---:|
| On time | 88,168 | 92.00% | 4.294 |
| 1-3 days | 3,132 | 3.27% | 3.595 |
| 4-7 days | 1,748 | 1.82% | 2.106 |
| 8+ days | 2,782 | 2.90% | 1.698 |

The score declines across these observed lateness buckets. This is a strong descriptive relationship in the observed delivered/reviewed cohort, not proof that lateness alone caused lower scores. Selection into delivered orders and reviewed orders, as well as other order/customer factors, may affect the comparison.

## Geographic and Seller Context

Customer states with at least 100 delivered reviewed orders, ranked by late-order percentage: Alagoas 23.35% (394 orders), Maranhao 19.24% (712), Piaui 15.92% (471), Ceara 15.24% (1,273), and Sergipe 14.97% (334). These are customer-state results; the state export also contains seller-state results, which use distinct order/seller-state pairs.

Among sellers meeting the exported `MIN_SELLER_ORDERS = 30` threshold, the highest observed late-order percentage is seller `ede0c03645598cdfc63ca8237acbe73d` at 33.33% across 42 orders (average review score 3.571). The threshold is a display aid, not a significance test; the export includes every seller and the dashboard should keep sample size visible.

## Reproduction

From the repository root, run `python -m olist_agent.cli build`, then `python -m olist_agent.cli analyze-delivery`. The first command writes `artifacts/olist.duckdb`; the second writes five Tableau CSVs, including the one-row `kpi_summary.csv`. These values were queried from the built database and generated exports, not embedded in the analysis SQL.

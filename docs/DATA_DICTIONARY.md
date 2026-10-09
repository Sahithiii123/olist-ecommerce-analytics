# Data Dictionary

Generated from DuckDB `information_schema.columns` and DuckDB-inferred Tableau CSV schemas; descriptions and KPI uses are maintained in code.

## `dim_customers`

**Grain:** One customer ID.  
**Source:** raw_customers

| Column | DuckDB type | Description | KPI use |
|---|---|---|---|
| `customer_id` | `VARCHAR` | Unique identifier for a customer record/order customer. | customer-level join |
| `customer_unique_id` | `VARCHAR` | Stable identifier linking customer records belonging to the same person. | None; reference/context field |
| `customer_zip_code_prefix` | `VARCHAR` | Customer's five-digit postal-code prefix. | None; reference/context field |
| `customer_city` | `VARCHAR` | Customer city as supplied in the source data. | None; reference/context field |
| `customer_state` | `VARCHAR` | Two-letter Brazilian state code for the customer. | customer-state grouping |
## `dim_date`

**Grain:** One calendar date.  
**Source:** Generated from purchase and customer-delivery timestamps in raw_orders

| Column | DuckDB type | Description | KPI use |
|---|---|---|---|
| `date_day` | `DATE` | Calendar date in the generated date dimension. | purchase/delivery calendar coverage |
| `date_key` | `INTEGER` | Integer date key formatted as YYYYMMDD. | None; reference/context field |
| `year` | `BIGINT` | Calendar year for the date dimension row. | None; reference/context field |
| `quarter` | `BIGINT` | Calendar quarter number, 1 through 4. | None; reference/context field |
| `month` | `BIGINT` | Calendar month number, 1 through 12. | None; reference/context field |
| `month_name` | `VARCHAR` | English calendar month name. | None; reference/context field |
| `day_of_month` | `BIGINT` | Calendar day number within the month. | None; reference/context field |
| `day_of_week` | `BIGINT` | DuckDB day-of-week number for the calendar date. | None; reference/context field |
## `dim_products`

**Grain:** One product ID.  
**Source:** raw_products LEFT JOIN raw_product_category_name_translation

| Column | DuckDB type | Description | KPI use |
|---|---|---|---|
| `product_id` | `VARCHAR` | Unique identifier for a product. | None; reference/context field |
| `product_category_name` | `VARCHAR` | Portuguese product category label from the source catalog. | None; reference/context field |
| `product_category_name_english` | `VARCHAR` | English translation of the product category, where available. | None; reference/context field |
| `product_weight_g` | `BIGINT` | Product weight in grams. | None; reference/context field |
## `dim_sellers`

**Grain:** One seller ID.  
**Source:** raw_sellers

| Column | DuckDB type | Description | KPI use |
|---|---|---|---|
| `seller_id` | `VARCHAR` | Unique identifier for a seller. | seller-level join |
| `seller_zip_code_prefix` | `VARCHAR` | Seller's five-digit postal-code prefix. | None; reference/context field |
| `seller_city` | `VARCHAR` | Seller city as supplied in the source data. | None; reference/context field |
| `seller_state` | `VARCHAR` | Two-letter Brazilian state code for the seller. | seller-state grouping |
## `fact_order_items`

**Grain:** One order ID and order item ID.  
**Source:** raw_order_items

| Column | DuckDB type | Description | KPI use |
|---|---|---|---|
| `order_id` | `VARCHAR` | Unique identifier for an order. | seller/order attribution |
| `order_item_id` | `INTEGER` | One-based item sequence number within an order. | None; reference/context field |
| `product_id` | `VARCHAR` | Unique identifier for a product. | None; reference/context field |
| `seller_id` | `VARCHAR` | Unique identifier for a seller. | seller-level and seller-state grouping |
| `price` | `DOUBLE` | Item selling price in R$ (BRL), excluding freight. | item sales value (not a delivery/review KPI) |
| `freight_value` | `DOUBLE` | Freight charge in R$ (BRL) for the item/order. | None; reference/context field |
## `fact_orders`

**Grain:** One order ID.  
**Source:** raw_orders with item and payment aggregates

| Column | DuckDB type | Description | KPI use |
|---|---|---|---|
| `order_id` | `VARCHAR` | Unique identifier for an order. | order count; delivery percentages |
| `customer_id` | `VARCHAR` | Unique identifier for a customer record/order customer. | customer-state grouping |
| `order_status` | `VARCHAR` | Lifecycle status reported for the order. | None; reference/context field |
| `purchased_at` | `TIMESTAMP` | Purchase timestamp cast from the raw order timestamp. | None; reference/context field |
| `approved_at` | `TIMESTAMP` | Payment approval timestamp cast from the raw order timestamp. | None; reference/context field |
| `carrier_at` | `TIMESTAMP` | Carrier handoff timestamp cast from the raw order timestamp. | None; reference/context field |
| `delivered_at` | `TIMESTAMP` | Customer delivery timestamp cast from the raw order timestamp. | delivered-order filter; delivery percentages |
| `estimated_at` | `TIMESTAMP` | Estimated delivery timestamp cast from the raw order timestamp. | on-time and late delivery classification |
| `is_late` | `BOOLEAN` | TRUE when a delivered timestamp is later than the estimated timestamp; NULL when either is missing. | on-time delivery %; late-order % |
| `days_late` | `BIGINT` | Calendar days beyond the estimate for delivered orders; zero on time and NULL when dates are missing. | review score by lateness bucket |
| `item_count` | `BIGINT` | Number of order-item rows associated with the order. | None; reference/context field |
| `seller_count` | `BIGINT` | Number of distinct sellers represented by the order's items. | None; reference/context field |
| `item_value` | `DOUBLE` | Sum of item prices in R$ (BRL) for the order, excluding freight. | None; reference/context field |
| `freight_value` | `DOUBLE` | Freight charge in R$ (BRL) for the item/order. | None; reference/context field |
| `payment_value` | `DOUBLE` | Amount in R$ (BRL) for the payment record. | None; reference/context field |
## `fact_reviews`

**Grain:** One source review ID; multiple rows per order are retained.  
**Source:** raw_order_reviews

| Column | DuckDB type | Description | KPI use |
|---|---|---|---|
| `review_id` | `VARCHAR` | Identifier for an individual review row; an order can have multiple rows. | None; reference/context field |
| `order_id` | `VARCHAR` | Unique identifier for an order. | review-to-order join and duplicate-review handling |
| `review_score` | `INTEGER` | Integer customer review score, usually on a one-to-five scale. | average review score |
| `review_comment_title` | `VARCHAR` | Optional customer-authored review title. | None; reference/context field |
| `review_comment_message` | `VARCHAR` | Optional customer-authored review text. | None; reference/context field |
## `raw_customers`

**Grain:** One source customer record.  
**Source:** olist_customers_dataset.csv (raw)

| Column | DuckDB type | Description | KPI use |
|---|---|---|---|
| `customer_id` | `VARCHAR` | Unique identifier for a customer record/order customer. | None; reference/context field |
| `customer_unique_id` | `VARCHAR` | Stable identifier linking customer records belonging to the same person. | None; reference/context field |
| `customer_zip_code_prefix` | `VARCHAR` | Customer's five-digit postal-code prefix. | None; reference/context field |
| `customer_city` | `VARCHAR` | Customer city as supplied in the source data. | None; reference/context field |
| `customer_state` | `VARCHAR` | Two-letter Brazilian state code for the customer. | None; reference/context field |
## `raw_geolocation`

**Grain:** One source postal-code geolocation observation.  
**Source:** olist_geolocation_dataset.csv (raw)

| Column | DuckDB type | Description | KPI use |
|---|---|---|---|
| `geolocation_zip_code_prefix` | `VARCHAR` | Postal-code prefix associated with this geolocation observation. | None; reference/context field |
| `geolocation_lat` | `DOUBLE` | Latitude associated with the postal-code prefix. | None; reference/context field |
| `geolocation_lng` | `DOUBLE` | Longitude associated with the postal-code prefix. | None; reference/context field |
| `geolocation_city` | `VARCHAR` | City label associated with the postal-code prefix. | None; reference/context field |
| `geolocation_state` | `VARCHAR` | State code associated with the postal-code prefix. | None; reference/context field |
## `raw_order_items`

**Grain:** One order line item.  
**Source:** olist_order_items_dataset.csv (raw)

| Column | DuckDB type | Description | KPI use |
|---|---|---|---|
| `order_id` | `VARCHAR` | Unique identifier for an order. | None; reference/context field |
| `order_item_id` | `BIGINT` | One-based item sequence number within an order. | None; reference/context field |
| `product_id` | `VARCHAR` | Unique identifier for a product. | None; reference/context field |
| `seller_id` | `VARCHAR` | Unique identifier for a seller. | None; reference/context field |
| `shipping_limit_date` | `TIMESTAMP` | Latest date/time by which the seller should hand the item to the carrier. | None; reference/context field |
| `price` | `DOUBLE` | Item selling price in R$ (BRL), excluding freight. | None; reference/context field |
| `freight_value` | `DOUBLE` | Freight charge in R$ (BRL) for the item/order. | None; reference/context field |
## `raw_order_payments`

**Grain:** One payment method/sequence per order.  
**Source:** olist_order_payments_dataset.csv (raw)

| Column | DuckDB type | Description | KPI use |
|---|---|---|---|
| `order_id` | `VARCHAR` | Unique identifier for an order. | None; reference/context field |
| `payment_sequential` | `BIGINT` | Sequence number for a payment method applied to an order. | None; reference/context field |
| `payment_type` | `VARCHAR` | Payment method reported for the payment record. | None; reference/context field |
| `payment_installments` | `BIGINT` | Number of installments used for the payment record. | None; reference/context field |
| `payment_value` | `DOUBLE` | Amount in R$ (BRL) for the payment record. | None; reference/context field |
## `raw_order_reviews`

**Grain:** One source review row.  
**Source:** olist_order_reviews_dataset.csv (raw)

| Column | DuckDB type | Description | KPI use |
|---|---|---|---|
| `review_id` | `VARCHAR` | Identifier for an individual review row; an order can have multiple rows. | None; reference/context field |
| `order_id` | `VARCHAR` | Unique identifier for an order. | None; reference/context field |
| `review_score` | `BIGINT` | Integer customer review score, usually on a one-to-five scale. | None; reference/context field |
| `review_comment_title` | `VARCHAR` | Optional customer-authored review title. | None; reference/context field |
| `review_comment_message` | `VARCHAR` | Optional customer-authored review text. | None; reference/context field |
| `review_creation_date` | `TIMESTAMP` | Timestamp when the review was created. | None; reference/context field |
| `review_answer_timestamp` | `TIMESTAMP` | Timestamp when the review was answered. | None; reference/context field |
## `raw_orders`

**Grain:** One source order.  
**Source:** olist_orders_dataset.csv (raw)

| Column | DuckDB type | Description | KPI use |
|---|---|---|---|
| `order_id` | `VARCHAR` | Unique identifier for an order. | None; reference/context field |
| `customer_id` | `VARCHAR` | Unique identifier for a customer record/order customer. | None; reference/context field |
| `order_status` | `VARCHAR` | Lifecycle status reported for the order. | None; reference/context field |
| `order_purchase_timestamp` | `TIMESTAMP` | Source purchase timestamp for the order. | None; reference/context field |
| `order_approved_at` | `TIMESTAMP` | Source timestamp when payment approval was recorded. | None; reference/context field |
| `order_delivered_carrier_date` | `TIMESTAMP` | Source timestamp when the order was handed to the carrier. | None; reference/context field |
| `order_delivered_customer_date` | `TIMESTAMP` | Source timestamp when the order was delivered to the customer. | None; reference/context field |
| `order_estimated_delivery_date` | `TIMESTAMP` | Source promised/estimated customer delivery timestamp. | None; reference/context field |
## `raw_product_category_name_translation`

**Grain:** One Portuguese-to-English category mapping.  
**Source:** product_category_name_translation.csv (raw)

| Column | DuckDB type | Description | KPI use |
|---|---|---|---|
| `product_category_name` | `VARCHAR` | Portuguese product category label from the source catalog. | None; reference/context field |
| `product_category_name_english` | `VARCHAR` | English translation of the product category, where available. | None; reference/context field |
## `raw_products`

**Grain:** One source product.  
**Source:** olist_products_dataset.csv (raw)

| Column | DuckDB type | Description | KPI use |
|---|---|---|---|
| `product_id` | `VARCHAR` | Unique identifier for a product. | None; reference/context field |
| `product_category_name` | `VARCHAR` | Portuguese product category label from the source catalog. | None; reference/context field |
| `product_name_lenght` | `BIGINT` | Source product-name character count; spelling retained from source column. | None; reference/context field |
| `product_description_lenght` | `BIGINT` | Source product-description character count; spelling retained from source column. | None; reference/context field |
| `product_photos_qty` | `BIGINT` | Number of product photos reported in the catalog. | None; reference/context field |
| `product_weight_g` | `BIGINT` | Product weight in grams. | None; reference/context field |
| `product_length_cm` | `BIGINT` | Product length in centimeters. | None; reference/context field |
| `product_height_cm` | `BIGINT` | Product height in centimeters. | None; reference/context field |
| `product_width_cm` | `BIGINT` | Product width in centimeters. | None; reference/context field |
## `raw_sellers`

**Grain:** One source seller.  
**Source:** olist_sellers_dataset.csv (raw)

| Column | DuckDB type | Description | KPI use |
|---|---|---|---|
| `seller_id` | `VARCHAR` | Unique identifier for a seller. | None; reference/context field |
| `seller_zip_code_prefix` | `VARCHAR` | Seller's five-digit postal-code prefix. | None; reference/context field |
| `seller_city` | `VARCHAR` | Seller city as supplied in the source data. | None; reference/context field |
| `seller_state` | `VARCHAR` | Two-letter Brazilian state code for the seller. | None; reference/context field |
## `tableau_kpi_summary`

**Grain:** One overall summary row.  
**Source:** tableau/kpi_summary.csv exported from reviewed delivered orders

| Column | DuckDB type | Description | KPI use |
|---|---|---|---|
| `orders` | `BIGINT` | Number of delivered orders with at least one review. | overall reviewed delivered order count |
| `on_time_delivery_pct` | `DOUBLE` | On-time percentage from 0 to 100 among orders with known lateness status. | overall on-time delivery percentage |
| `late_order_pct` | `DOUBLE` | Late-order percentage from 0 to 100 among orders with known lateness status. | overall late-order percentage |
| `avg_review_score` | `DOUBLE` | Arithmetic mean of one mean review score per order. | overall average review score |
| `avg_score_on_time` | `DOUBLE` | Average per-order review score for on-time orders. | on-time average review score |
| `avg_score_late` | `DOUBLE` | Average per-order review score for late orders. | late-order average review score |
## `tableau_review_by_lateness`

**Grain:** One row per observed lateness bucket.  
**Source:** tableau/review_by_lateness.csv exported from reviewed delivered orders

| Column | DuckDB type | Description | KPI use |
|---|---|---|---|
| `lateness_bucket` | `VARCHAR` | Delivery lateness group: On time, 1-3 days, 4-7 days, or 8+ days. | lateness chart category |
| `bucket_order` | `BIGINT` | Sort order for the lateness bucket, from 1 (On time) through 4 (8+ days). | lateness chart sorting |
| `order_count` | `BIGINT` | Number of orders at the grain of this exported seller, state, or lateness group. | lateness bucket sample size |
| `pct_of_orders` | `DOUBLE` | Share from 0 to 100 of known-lateness delivered reviewed orders in this bucket. | share of classified orders in each lateness bucket |
| `avg_review_score` | `DOUBLE` | Arithmetic mean of one mean review score per order. | average score by lateness bucket |
## `tableau_state_metrics`

**Grain:** One state and role (seller/customer).  
**Source:** tableau/state_metrics.csv exported from reviewed delivered orders and dimensions

| Column | DuckDB type | Description | KPI use |
|---|---|---|---|
| `state_code` | `VARCHAR` | Two-letter Brazilian state abbreviation used for Tableau geographic matching. | state geographic key |
| `state_name` | `VARCHAR` | Plain ASCII English name for the Brazilian state code. | state map label |
| `country` | `VARCHAR` | Country label; always Brazil for these exports. | None; reference/context field |
| `state_role` | `VARCHAR` | Whether state_code describes the seller or the customer. | seller-state/customer-state distinction |
| `order_count` | `BIGINT` | Number of orders at the grain of this exported seller, state, or lateness group. | None; reference/context field |
| `on_time_delivery_pct` | `DOUBLE` | On-time percentage from 0 to 100 among orders with known lateness status. | None; reference/context field |
| `late_order_pct` | `DOUBLE` | Late-order percentage from 0 to 100 among orders with known lateness status. | None; reference/context field |
| `avg_review_score` | `DOUBLE` | Arithmetic mean of one mean review score per order. | None; reference/context field |
## `tableau_seller_metrics`

**Grain:** One seller ID.  
**Source:** tableau/seller_metrics.csv exported from reviewed delivered orders and dimensions

| Column | DuckDB type | Description | KPI use |
|---|---|---|---|
| `seller_id` | `VARCHAR` | Unique identifier for a seller. | seller comparison key |
| `seller_state` | `VARCHAR` | Two-letter Brazilian state code for the seller. | None; reference/context field |
| `state_name` | `VARCHAR` | Plain ASCII English name for the Brazilian state code. | None; reference/context field |
| `country` | `VARCHAR` | Country label; always Brazil for these exports. | None; reference/context field |
| `order_count` | `BIGINT` | Number of orders at the grain of this exported seller, state, or lateness group. | None; reference/context field |
| `on_time_delivery_pct` | `DOUBLE` | On-time percentage from 0 to 100 among orders with known lateness status. | None; reference/context field |
| `late_order_pct` | `DOUBLE` | Late-order percentage from 0 to 100 among orders with known lateness status. | None; reference/context field |
| `avg_review_score` | `DOUBLE` | Arithmetic mean of one mean review score per order. | None; reference/context field |
| `meets_min_orders` | `BOOLEAN` | TRUE when the seller has at least MIN_SELLER_ORDERS distinct reviewed delivered orders. | 30-order seller volume flag |
## `tableau_fact_orders_flat`

**Grain:** One delivered reviewed order.  
**Source:** tableau/fact_orders_flat.csv exported at one row per reviewed delivered order

| Column | DuckDB type | Description | KPI use |
|---|---|---|---|
| `order_id` | `VARCHAR` | Unique identifier for an order. | one-row-per-order KPI grain |
| `customer_id` | `VARCHAR` | Unique identifier for a customer record/order customer. | None; reference/context field |
| `customer_state` | `VARCHAR` | Two-letter Brazilian state code for the customer. | None; reference/context field |
| `purchased_at` | `TIMESTAMP` | Purchase timestamp cast from the raw order timestamp. | None; reference/context field |
| `delivered_at` | `TIMESTAMP` | Customer delivery timestamp cast from the raw order timestamp. | None; reference/context field |
| `estimated_at` | `TIMESTAMP` | Estimated delivery timestamp cast from the raw order timestamp. | None; reference/context field |
| `is_late` | `BOOLEAN` | TRUE when a delivered timestamp is later than the estimated timestamp; NULL when either is missing. | None; reference/context field |
| `days_late` | `BIGINT` | Calendar days beyond the estimate for delivered orders; zero on time and NULL when dates are missing. | None; reference/context field |
| `review_score` | `DOUBLE` | Integer customer review score, usually on a one-to-five scale. | None; reference/context field |

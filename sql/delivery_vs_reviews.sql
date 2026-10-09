CREATE OR REPLACE TEMP VIEW br_states AS
SELECT * FROM (VALUES
    ('AC', 'Acre'), ('AL', 'Alagoas'), ('AP', 'Amapa'), ('AM', 'Amazonas'),
    ('BA', 'Bahia'), ('CE', 'Ceara'), ('DF', 'Distrito Federal'), ('ES', 'Espirito Santo'),
    ('GO', 'Goias'), ('MA', 'Maranhao'), ('MT', 'Mato Grosso'),
    ('MS', 'Mato Grosso do Sul'), ('MG', 'Minas Gerais'), ('PA', 'Para'),
    ('PB', 'Paraiba'), ('PR', 'Parana'), ('PE', 'Pernambuco'), ('PI', 'Piaui'),
    ('RJ', 'Rio de Janeiro'), ('RN', 'Rio Grande do Norte'), ('RS', 'Rio Grande do Sul'),
    ('RO', 'Rondonia'), ('RR', 'Roraima'), ('SC', 'Santa Catarina'),
    ('SP', 'Sao Paulo'), ('SE', 'Sergipe'), ('TO', 'Tocantins')
) AS states(state_code, state_name);

CREATE OR REPLACE TEMP VIEW review_per_order AS
SELECT order_id,
       AVG(CAST(review_score AS DOUBLE)) AS review_score,
       COUNT(*) AS review_count
FROM fact_reviews
GROUP BY order_id;

CREATE OR REPLACE TEMP VIEW reviewed_delivered_orders AS
SELECT o.order_id, o.customer_id, o.purchased_at, o.delivered_at, o.estimated_at,
       o.is_late, o.days_late, r.review_score, r.review_count, c.customer_state
FROM fact_orders o
JOIN review_per_order r USING (order_id)
JOIN dim_customers c USING (customer_id)
WHERE o.delivered_at IS NOT NULL;

CREATE OR REPLACE TEMP VIEW delivery_order_sellers AS
SELECT DISTINCT o.order_id, i.seller_id, s.seller_state
FROM reviewed_delivered_orders o
JOIN fact_order_items i USING (order_id)
JOIN dim_sellers s USING (seller_id);

CREATE OR REPLACE TEMP VIEW delivery_kpi_summary AS
SELECT COUNT(*) AS orders,
       100.0 * COUNT(*) FILTER (WHERE is_late = FALSE)
           / NULLIF(COUNT(*) FILTER (WHERE is_late IS NOT NULL), 0) AS on_time_delivery_pct,
       100.0 * COUNT(*) FILTER (WHERE is_late = TRUE)
           / NULLIF(COUNT(*) FILTER (WHERE is_late IS NOT NULL), 0) AS late_order_pct,
       AVG(review_score) AS avg_review_score,
       AVG(review_score) FILTER (WHERE is_late = FALSE) AS avg_score_on_time,
       AVG(review_score) FILTER (WHERE is_late = TRUE) AS avg_score_late
FROM reviewed_delivered_orders;

CREATE OR REPLACE TEMP VIEW delivery_seller_metrics AS
SELECT s.seller_id,
       s.seller_state,
       d.state_name,
       'Brazil' AS country,
       COUNT(*) AS order_count,
       100.0 * COUNT(*) FILTER (WHERE o.is_late = FALSE)
           / NULLIF(COUNT(*) FILTER (WHERE o.is_late IS NOT NULL), 0) AS on_time_delivery_pct,
       100.0 * COUNT(*) FILTER (WHERE o.is_late = TRUE)
           / NULLIF(COUNT(*) FILTER (WHERE o.is_late IS NOT NULL), 0) AS late_order_pct,
       AVG(o.review_score) AS avg_review_score,
       COUNT(*) >= CAST('__MIN_SELLER_ORDERS__' AS INTEGER) AS meets_min_orders
FROM delivery_order_sellers s
JOIN reviewed_delivered_orders o USING (order_id)
LEFT JOIN br_states d ON s.seller_state = d.state_code
GROUP BY s.seller_id, s.seller_state, d.state_name;

CREATE OR REPLACE TEMP VIEW delivery_state_metrics AS
WITH seller_states AS (
    SELECT DISTINCT order_id, seller_state AS state_code FROM delivery_order_sellers
), seller_metrics AS (
    SELECT s.state_code, d.state_name, 'Brazil' AS country, 'seller' AS state_role,
           COUNT(*) AS order_count,
           100.0 * COUNT(*) FILTER (WHERE o.is_late = FALSE)
               / NULLIF(COUNT(*) FILTER (WHERE o.is_late IS NOT NULL), 0) AS on_time_delivery_pct,
           100.0 * COUNT(*) FILTER (WHERE o.is_late = TRUE)
               / NULLIF(COUNT(*) FILTER (WHERE o.is_late IS NOT NULL), 0) AS late_order_pct,
           AVG(o.review_score) AS avg_review_score
    FROM seller_states s
    JOIN reviewed_delivered_orders o USING (order_id)
    LEFT JOIN br_states d ON s.state_code = d.state_code
    GROUP BY s.state_code, d.state_name
), customer_metrics AS (
    SELECT o.customer_state AS state_code, d.state_name, 'Brazil' AS country,
           'customer' AS state_role, COUNT(*) AS order_count,
           100.0 * COUNT(*) FILTER (WHERE o.is_late = FALSE)
               / NULLIF(COUNT(*) FILTER (WHERE o.is_late IS NOT NULL), 0) AS on_time_delivery_pct,
           100.0 * COUNT(*) FILTER (WHERE o.is_late = TRUE)
               / NULLIF(COUNT(*) FILTER (WHERE o.is_late IS NOT NULL), 0) AS late_order_pct,
           AVG(o.review_score) AS avg_review_score
    FROM reviewed_delivered_orders o
    LEFT JOIN br_states d ON o.customer_state = d.state_code
    GROUP BY o.customer_state, d.state_name
)
SELECT * FROM seller_metrics
UNION ALL
SELECT * FROM customer_metrics;

CREATE OR REPLACE TEMP VIEW delivery_review_by_lateness AS
WITH bucketed AS (
    SELECT CASE WHEN days_late = 0 THEN 'On time'
                WHEN days_late BETWEEN 1 AND 3 THEN '1-3 days'
                WHEN days_late BETWEEN 4 AND 7 THEN '4-7 days'
                ELSE '8+ days' END AS lateness_bucket,
           CASE WHEN days_late = 0 THEN 1
                WHEN days_late BETWEEN 1 AND 3 THEN 2
                WHEN days_late BETWEEN 4 AND 7 THEN 3 ELSE 4 END AS bucket_order,
           review_score
    FROM reviewed_delivered_orders
    WHERE days_late IS NOT NULL
), grouped AS (
    SELECT lateness_bucket, bucket_order, COUNT(*) AS order_count,
           AVG(review_score) AS avg_review_score
    FROM bucketed
    GROUP BY lateness_bucket, bucket_order
)
SELECT lateness_bucket, bucket_order, order_count,
       100.0 * order_count / NULLIF(SUM(order_count) OVER (), 0) AS pct_of_orders,
       avg_review_score
FROM grouped;

CREATE OR REPLACE TEMP VIEW delivery_fact_orders_flat AS
SELECT order_id, customer_id, customer_state, purchased_at, delivered_at,
       estimated_at, is_late, days_late, review_score
FROM reviewed_delivered_orders;

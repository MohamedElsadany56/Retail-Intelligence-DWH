CREATE INDEX IF NOT EXISTS idx_stg_transactions_basket_id
    ON retail_dw.stg_transactions (basket_id);

CREATE INDEX IF NOT EXISTS idx_stg_transactions_household_id
    ON retail_dw.stg_transactions (household_id);

CREATE INDEX IF NOT EXISTS idx_stg_transactions_product_id
    ON retail_dw.stg_transactions (product_id);

CREATE INDEX IF NOT EXISTS idx_stg_transactions_store_id
    ON retail_dw.stg_transactions (store_id);

CREATE INDEX IF NOT EXISTS idx_stg_transactions_transaction_date
    ON retail_dw.stg_transactions (transaction_date);

CREATE INDEX IF NOT EXISTS idx_stg_transactions_week
    ON retail_dw.stg_transactions (week);

CREATE INDEX IF NOT EXISTS idx_stg_promotions_product_store_week
    ON retail_dw.stg_promotions (product_id, store_id, week);

CREATE INDEX IF NOT EXISTS idx_fact_transaction_item_basket_id
    ON retail_dw.fact_transaction_item (basket_id);

CREATE INDEX IF NOT EXISTS idx_fact_transaction_item_product_key
    ON retail_dw.fact_transaction_item (product_key);

CREATE INDEX IF NOT EXISTS idx_fact_transaction_item_household_key
    ON retail_dw.fact_transaction_item (household_key);

CREATE INDEX IF NOT EXISTS idx_fact_transaction_item_date_key
    ON retail_dw.fact_transaction_item (date_key);

CREATE MATERIALIZED VIEW IF NOT EXISTS retail_dw.mv_basket_items AS
SELECT
    f.basket_id,
    f.household_id,
    f.product_id,
    p.department,
    p.commodity_desc,
    p.sub_commodity_desc,
    f.transaction_date,
    f.quantity,
    f.quantity_capped,
    f.sales_value,
    f.sales_value_capped
FROM retail_dw.fact_transaction_item f
LEFT JOIN retail_dw.dim_product p
    ON p.product_key = f.product_key
WHERE f.basket_id IS NOT NULL
    AND f.product_id IS NOT NULL;

CREATE MATERIALIZED VIEW IF NOT EXISTS retail_dw.mv_customer_rfm AS
SELECT
    f.household_key,
    f.household_id,
    MAX(f.transaction_date) AS last_purchase_date,
    CURRENT_DATE - MAX(f.transaction_date) AS recency_days,
    COUNT(DISTINCT f.basket_id) AS frequency_baskets,
    SUM(COALESCE(f.sales_value_capped, f.sales_value, 0)) AS monetary_value
FROM retail_dw.fact_transaction_item f
WHERE f.household_key <> 0
GROUP BY f.household_key, f.household_id;

CREATE MATERIALIZED VIEW IF NOT EXISTS retail_dw.mv_transaction_analytics AS
SELECT
    f.date_key,
    d.full_date,
    d.week_of_year,
    d.month_number,
    d.year_number,
    f.store_key,
    f.store_id,
    COUNT(*) AS item_rows,
    COUNT(DISTINCT f.basket_id) AS basket_count,
    COUNT(DISTINCT f.household_key) AS household_count,
    SUM(COALESCE(f.quantity_capped, f.quantity, 0)) AS total_quantity,
    SUM(COALESCE(f.sales_value_capped, f.sales_value, 0)) AS total_sales_value,
    SUM(COALESCE(f.retail_disc_capped, f.retail_disc, 0)) AS total_retail_discount,
    SUM(COALESCE(f.coupon_disc_capped, f.coupon_disc, 0)) AS total_coupon_discount
FROM retail_dw.fact_transaction_item f
LEFT JOIN retail_dw.dim_date d
    ON d.date_key = f.date_key
GROUP BY
    f.date_key,
    d.full_date,
    d.week_of_year,
    d.month_number,
    d.year_number,
    f.store_key,
    f.store_id;

CREATE MATERIALIZED VIEW IF NOT EXISTS retail_dw.mv_coupon_redemption_analysis AS
SELECT
    c.coupon_key,
    c.coupon_upc,
    c.product_id,
    c.campaign_id,
    cmp.campaign_type,
    COUNT(*) AS redemption_count,
    COUNT(DISTINCT r.household_key) AS redeeming_households,
    MIN(r.redemption_date) AS first_redemption_date,
    MAX(r.redemption_date) AS last_redemption_date
FROM retail_dw.fact_coupon_redemption r
LEFT JOIN retail_dw.dim_coupon c
    ON c.coupon_key = r.coupon_key
LEFT JOIN retail_dw.dim_campaign cmp
    ON cmp.campaign_key = r.campaign_key
GROUP BY
    c.coupon_key,
    c.coupon_upc,
    c.product_id,
    c.campaign_id,
    cmp.campaign_type;

CREATE MATERIALIZED VIEW IF NOT EXISTS retail_dw.mv_campaign_performance AS
SELECT
    cp.campaign_key,
    cp.campaign_id,
    cp.campaign_type,
    COUNT(DISTINCT cp.household_key) AS targeted_households,
    COUNT(DISTINCT cr.household_key) AS redeeming_households,
    COUNT(cr.coupon_redemption_key) AS redemption_count
FROM retail_dw.fact_campaign_participation cp
LEFT JOIN retail_dw.fact_coupon_redemption cr
    ON cr.campaign_key = cp.campaign_key
    AND cr.household_key = cp.household_key
GROUP BY
    cp.campaign_key,
    cp.campaign_id,
    cp.campaign_type;

REFRESH MATERIALIZED VIEW retail_dw.mv_basket_items;

REFRESH MATERIALIZED VIEW retail_dw.mv_customer_rfm;

REFRESH MATERIALIZED VIEW retail_dw.mv_transaction_analytics;

REFRESH MATERIALIZED VIEW retail_dw.mv_coupon_redemption_analysis;

REFRESH MATERIALIZED VIEW retail_dw.mv_campaign_performance;

CREATE OR REPLACE VIEW retail_dw.vw_table_row_counts AS
SELECT 'stg_transactions' AS table_name, COUNT(*) AS row_count FROM retail_dw.stg_transactions
UNION ALL
SELECT 'stg_products', COUNT(*) FROM retail_dw.stg_products
UNION ALL
SELECT 'stg_demographics', COUNT(*) FROM retail_dw.stg_demographics
UNION ALL
SELECT 'stg_campaigns', COUNT(*) FROM retail_dw.stg_campaigns
UNION ALL
SELECT 'stg_campaign_descriptions', COUNT(*) FROM retail_dw.stg_campaign_descriptions
UNION ALL
SELECT 'stg_coupons', COUNT(*) FROM retail_dw.stg_coupons
UNION ALL
SELECT 'stg_coupon_redemptions', COUNT(*) FROM retail_dw.stg_coupon_redemptions
UNION ALL
SELECT 'stg_promotions', COUNT(*) FROM retail_dw.stg_promotions
UNION ALL
SELECT 'stg_basket_items_for_mba', COUNT(*) FROM retail_dw.stg_basket_items_for_mba
UNION ALL
SELECT 'dim_household', COUNT(*) FROM retail_dw.dim_household
UNION ALL
SELECT 'dim_product', COUNT(*) FROM retail_dw.dim_product
UNION ALL
SELECT 'dim_store', COUNT(*) FROM retail_dw.dim_store
UNION ALL
SELECT 'dim_date', COUNT(*) FROM retail_dw.dim_date
UNION ALL
SELECT 'dim_campaign', COUNT(*) FROM retail_dw.dim_campaign
UNION ALL
SELECT 'dim_coupon', COUNT(*) FROM retail_dw.dim_coupon
UNION ALL
SELECT 'dim_holiday', COUNT(*) FROM retail_dw.dim_holiday
UNION ALL
SELECT 'fact_transaction_item', COUNT(*) FROM retail_dw.fact_transaction_item
UNION ALL
SELECT 'fact_coupon_redemption', COUNT(*) FROM retail_dw.fact_coupon_redemption
UNION ALL
SELECT 'fact_campaign_participation', COUNT(*) FROM retail_dw.fact_campaign_participation
UNION ALL
SELECT 'fact_product_promotion', COUNT(*) FROM retail_dw.fact_product_promotion;

CREATE OR REPLACE VIEW retail_dw.vw_data_quality_summary AS
SELECT
    'fact_transaction_item.product_key_unknown' AS check_name,
    COUNT(*) AS issue_count
FROM retail_dw.fact_transaction_item
WHERE product_key = 0
UNION ALL
SELECT
    'fact_transaction_item.household_key_unknown',
    COUNT(*)
FROM retail_dw.fact_transaction_item
WHERE household_key = 0
UNION ALL
SELECT
    'fact_transaction_item.store_key_unknown',
    COUNT(*)
FROM retail_dw.fact_transaction_item
WHERE store_key = 0
UNION ALL
SELECT
    'fact_transaction_item.null_surrogate_keys',
    COUNT(*)
FROM retail_dw.fact_transaction_item
WHERE household_key IS NULL
    OR product_key IS NULL
    OR store_key IS NULL
    OR date_key IS NULL
UNION ALL
SELECT
    'fact_transaction_item.invalid_quantity',
    COUNT(*)
FROM retail_dw.fact_transaction_item
WHERE quantity_is_invalid IS TRUE
UNION ALL
SELECT
    'fact_transaction_item.sales_value_outliers',
    COUNT(*)
FROM retail_dw.fact_transaction_item
WHERE sales_value_is_possible_outlier IS TRUE
UNION ALL
SELECT
    'fact_transaction_item.quantity_outliers',
    COUNT(*)
FROM retail_dw.fact_transaction_item
WHERE quantity_is_possible_outlier IS TRUE
UNION ALL
SELECT
    'fact_transaction_item.retail_discount_outliers',
    COUNT(*)
FROM retail_dw.fact_transaction_item
WHERE retail_disc_is_possible_outlier IS TRUE
UNION ALL
SELECT
    'fact_transaction_item.coupon_discount_outliers',
    COUNT(*)
FROM retail_dw.fact_transaction_item
WHERE coupon_disc_is_possible_outlier IS TRUE;

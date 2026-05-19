-- validation: staging_row_counts
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
SELECT 'stg_basket_items_for_mba', COUNT(*) FROM retail_dw.stg_basket_items_for_mba;

-- validation: dimension_row_counts
SELECT 'dim_household' AS table_name, COUNT(*) AS row_count FROM retail_dw.dim_household
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
SELECT 'dim_holiday', COUNT(*) FROM retail_dw.dim_holiday;

-- validation: fact_row_counts
SELECT 'fact_transaction_item' AS table_name, COUNT(*) AS row_count FROM retail_dw.fact_transaction_item
UNION ALL
SELECT 'fact_coupon_redemption', COUNT(*) FROM retail_dw.fact_coupon_redemption
UNION ALL
SELECT 'fact_campaign_participation', COUNT(*) FROM retail_dw.fact_campaign_participation
UNION ALL
SELECT 'fact_product_promotion', COUNT(*) FROM retail_dw.fact_product_promotion;

-- validation: missing_product_references
SELECT
    COUNT(*) AS transaction_rows_with_unknown_product
FROM retail_dw.fact_transaction_item
WHERE product_key = 0;

-- validation: missing_household_references
SELECT
    COUNT(*) AS transaction_rows_with_unknown_household
FROM retail_dw.fact_transaction_item
WHERE household_key = 0;

-- validation: missing_store_references
SELECT
    COUNT(*) AS transaction_rows_with_unknown_store
FROM retail_dw.fact_transaction_item
WHERE store_key = 0;

-- validation: null_surrogate_keys_in_fact_transaction_item
SELECT
    COUNT(*) AS rows_with_null_surrogate_keys
FROM retail_dw.fact_transaction_item
WHERE household_key IS NULL
    OR product_key IS NULL
    OR store_key IS NULL
    OR date_key IS NULL;

-- validation: duplicate_basket_product_rows
SELECT
    basket_id,
    product_id,
    COUNT(*) AS duplicate_count
FROM retail_dw.fact_transaction_item
WHERE basket_id IS NOT NULL
    AND product_id IS NOT NULL
GROUP BY basket_id, product_id
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC, basket_id, product_id
LIMIT 100;

-- validation: invalid_quantity_count
SELECT
    COUNT(*) AS invalid_quantity_count
FROM retail_dw.fact_transaction_item
WHERE quantity_is_invalid IS TRUE;

-- validation: coupon_usage_count
SELECT
    coupon_was_used,
    COUNT(*) AS row_count,
    SUM(COALESCE(coupon_disc_capped, coupon_disc, 0)) AS total_coupon_discount
FROM retail_dw.fact_transaction_item
GROUP BY coupon_was_used
ORDER BY coupon_was_used;

-- validation: outlier_flag_counts
SELECT 'sales_value_is_possible_outlier' AS flag_name, COUNT(*) AS flagged_rows
FROM retail_dw.fact_transaction_item
WHERE sales_value_is_possible_outlier IS TRUE
UNION ALL
SELECT 'quantity_is_possible_outlier', COUNT(*)
FROM retail_dw.fact_transaction_item
WHERE quantity_is_possible_outlier IS TRUE
UNION ALL
SELECT 'retail_disc_is_possible_outlier', COUNT(*)
FROM retail_dw.fact_transaction_item
WHERE retail_disc_is_possible_outlier IS TRUE
UNION ALL
SELECT 'coupon_disc_is_possible_outlier', COUNT(*)
FROM retail_dw.fact_transaction_item
WHERE coupon_disc_is_possible_outlier IS TRUE;

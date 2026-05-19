CREATE SCHEMA IF NOT EXISTS retail_dw;

CREATE TABLE IF NOT EXISTS retail_dw.stg_transactions (
    household_id BIGINT,
    store_id BIGINT,
    basket_id BIGINT,
    product_id BIGINT,
    quantity NUMERIC,
    sales_value NUMERIC,
    retail_disc NUMERIC,
    coupon_disc NUMERIC,
    coupon_match_disc NUMERIC,
    week INTEGER,
    transaction_timestamp TIMESTAMP,
    transaction_datetime TIMESTAMP,
    transaction_date DATE,
    sales_value_is_possible_outlier BOOLEAN,
    sales_value_capped NUMERIC,
    quantity_is_possible_outlier BOOLEAN,
    quantity_capped NUMERIC,
    retail_disc_is_possible_outlier BOOLEAN,
    retail_disc_capped NUMERIC,
    coupon_disc_is_possible_outlier BOOLEAN,
    coupon_disc_capped NUMERIC,
    quantity_is_invalid BOOLEAN,
    coupon_was_used BOOLEAN,
    retail_discount_was_applied BOOLEAN
);

CREATE TABLE IF NOT EXISTS retail_dw.stg_products (
    product_id BIGINT,
    manufacturer TEXT,
    department TEXT,
    brand TEXT,
    commodity_desc TEXT,
    sub_commodity_desc TEXT,
    curr_size_of_product TEXT
);

CREATE TABLE IF NOT EXISTS retail_dw.stg_demographics (
    household_id BIGINT,
    age_desc TEXT,
    marital_status_code TEXT,
    income_desc TEXT,
    homeowner_desc TEXT,
    hh_comp_desc TEXT,
    household_size_desc TEXT,
    kid_category_desc TEXT
);

CREATE TABLE IF NOT EXISTS retail_dw.stg_campaigns (
    campaign_id BIGINT,
    household_id BIGINT,
    campaign_type TEXT,
    start_day INTEGER,
    end_day INTEGER
);

CREATE TABLE IF NOT EXISTS retail_dw.stg_campaign_descriptions (
    campaign_id BIGINT,
    campaign_type TEXT,
    start_day INTEGER,
    end_day INTEGER,
    start_date DATE,
    end_date DATE,
    duration_days INTEGER
);

CREATE TABLE IF NOT EXISTS retail_dw.stg_coupons (
    coupon_upc BIGINT,
    product_id BIGINT,
    campaign_id BIGINT
);

CREATE TABLE IF NOT EXISTS retail_dw.stg_coupon_redemptions (
    household_id BIGINT,
    coupon_upc BIGINT,
    campaign_id BIGINT,
    redemption_date DATE
);

CREATE TABLE IF NOT EXISTS retail_dw.stg_promotions (
    product_id BIGINT,
    store_id BIGINT,
    week INTEGER,
    display_location TEXT,
    mailer_location TEXT
);

CREATE TABLE IF NOT EXISTS retail_dw.stg_basket_items_for_mba (
    basket_id BIGINT,
    product_id BIGINT,
    household_id BIGINT,
    transaction_date DATE,
    product_name TEXT,
    department TEXT,
    commodity_desc TEXT,
    quantity NUMERIC,
    sales_value NUMERIC
);

-- Placeholder only. Holiday loading will be implemented after the exact source filename is confirmed.
CREATE TABLE IF NOT EXISTS retail_dw.stg_holidays (
    holiday_date DATE,
    holiday_name TEXT,
    holiday_type TEXT
);

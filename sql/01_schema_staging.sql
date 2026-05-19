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
    manufacturer_id BIGINT,
    department TEXT,
    brand TEXT,
    product_category TEXT,
    product_type TEXT,
    package_size TEXT
);

CREATE TABLE IF NOT EXISTS retail_dw.stg_demographics (
    household_id BIGINT,
    age TEXT,
    income TEXT,
    home_ownership TEXT,
    marital_status TEXT,
    household_size TEXT,
    household_comp TEXT,
    kids_count TEXT
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
    department TEXT,
    product_category TEXT,
    product_type TEXT
);

-- Placeholder only. Holiday loading will be implemented after the exact source filename is confirmed.
CREATE TABLE IF NOT EXISTS retail_dw.stg_holidays (
    holiday_date DATE,
    holiday_name TEXT,
    holiday_type TEXT
);

ALTER TABLE IF EXISTS retail_dw.stg_products ADD COLUMN IF NOT EXISTS manufacturer_id BIGINT;
ALTER TABLE IF EXISTS retail_dw.stg_products ADD COLUMN IF NOT EXISTS product_category TEXT;
ALTER TABLE IF EXISTS retail_dw.stg_products ADD COLUMN IF NOT EXISTS product_type TEXT;
ALTER TABLE IF EXISTS retail_dw.stg_products ADD COLUMN IF NOT EXISTS package_size TEXT;

ALTER TABLE IF EXISTS retail_dw.stg_demographics ADD COLUMN IF NOT EXISTS age TEXT;
ALTER TABLE IF EXISTS retail_dw.stg_demographics ADD COLUMN IF NOT EXISTS income TEXT;
ALTER TABLE IF EXISTS retail_dw.stg_demographics ADD COLUMN IF NOT EXISTS home_ownership TEXT;
ALTER TABLE IF EXISTS retail_dw.stg_demographics ADD COLUMN IF NOT EXISTS marital_status TEXT;
ALTER TABLE IF EXISTS retail_dw.stg_demographics ADD COLUMN IF NOT EXISTS household_size TEXT;
ALTER TABLE IF EXISTS retail_dw.stg_demographics ADD COLUMN IF NOT EXISTS household_comp TEXT;
ALTER TABLE IF EXISTS retail_dw.stg_demographics ADD COLUMN IF NOT EXISTS kids_count TEXT;

ALTER TABLE IF EXISTS retail_dw.stg_basket_items_for_mba ADD COLUMN IF NOT EXISTS product_category TEXT;
ALTER TABLE IF EXISTS retail_dw.stg_basket_items_for_mba ADD COLUMN IF NOT EXISTS product_type TEXT;

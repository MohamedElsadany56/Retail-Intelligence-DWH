CREATE SCHEMA IF NOT EXISTS retail_dw;

CREATE TABLE IF NOT EXISTS retail_dw.dim_household (
    household_key BIGSERIAL PRIMARY KEY,
    household_id BIGINT UNIQUE,
    age TEXT,
    income TEXT,
    home_ownership TEXT,
    marital_status TEXT,
    household_size TEXT,
    household_comp TEXT,
    kids_count TEXT
);

CREATE TABLE IF NOT EXISTS retail_dw.dim_product (
    product_key BIGSERIAL PRIMARY KEY,
    product_id BIGINT UNIQUE,
    manufacturer_id BIGINT,
    department TEXT,
    brand TEXT,
    product_category TEXT,
    product_type TEXT,
    package_size TEXT
);

CREATE TABLE IF NOT EXISTS retail_dw.dim_store (
    store_key BIGSERIAL PRIMARY KEY,
    store_id BIGINT UNIQUE
);

CREATE TABLE IF NOT EXISTS retail_dw.dim_date (
    date_key INTEGER PRIMARY KEY,
    full_date DATE UNIQUE,
    day_of_week INTEGER,
    day_name TEXT,
    day_of_month INTEGER,
    week_of_year INTEGER,
    month_number INTEGER,
    month_name TEXT,
    quarter_number INTEGER,
    year_number INTEGER
);

CREATE TABLE IF NOT EXISTS retail_dw.dim_campaign (
    campaign_key BIGSERIAL PRIMARY KEY,
    campaign_id BIGINT UNIQUE,
    campaign_type TEXT,
    start_day INTEGER,
    end_day INTEGER,
    start_date DATE,
    end_date DATE,
    duration_days INTEGER
);

CREATE TABLE IF NOT EXISTS retail_dw.dim_coupon (
    coupon_key BIGSERIAL PRIMARY KEY,
    coupon_upc BIGINT UNIQUE,
    product_id BIGINT,
    campaign_id BIGINT
);

CREATE TABLE IF NOT EXISTS retail_dw.dim_holiday (
    holiday_key BIGSERIAL PRIMARY KEY,
    holiday_date DATE UNIQUE,
    date_text TEXT,
    date_definition TEXT,
    official_name TEXT,
    details TEXT,
    holiday_name TEXT,
    holiday_type TEXT
);

CREATE TABLE IF NOT EXISTS retail_dw.fact_transaction_item (
    transaction_item_key BIGSERIAL PRIMARY KEY,
    basket_id BIGINT,
    household_key BIGINT NOT NULL REFERENCES retail_dw.dim_household(household_key),
    product_key BIGINT NOT NULL REFERENCES retail_dw.dim_product(product_key),
    store_key BIGINT NOT NULL REFERENCES retail_dw.dim_store(store_key),
    date_key INTEGER NOT NULL REFERENCES retail_dw.dim_date(date_key),
    household_id BIGINT,
    product_id BIGINT,
    store_id BIGINT,
    week INTEGER,
    transaction_timestamp TIMESTAMP,
    transaction_datetime TIMESTAMP,
    transaction_date DATE,
    quantity NUMERIC,
    quantity_capped NUMERIC,
    sales_value NUMERIC,
    sales_value_capped NUMERIC,
    retail_disc NUMERIC,
    retail_disc_capped NUMERIC,
    coupon_disc NUMERIC,
    coupon_disc_capped NUMERIC,
    coupon_match_disc NUMERIC,
    quantity_is_invalid BOOLEAN,
    coupon_was_used BOOLEAN,
    retail_discount_was_applied BOOLEAN,
    sales_value_is_possible_outlier BOOLEAN,
    quantity_is_possible_outlier BOOLEAN,
    retail_disc_is_possible_outlier BOOLEAN,
    coupon_disc_is_possible_outlier BOOLEAN
);

CREATE TABLE IF NOT EXISTS retail_dw.fact_coupon_redemption (
    coupon_redemption_key BIGSERIAL PRIMARY KEY,
    household_key BIGINT NOT NULL REFERENCES retail_dw.dim_household(household_key),
    coupon_key BIGINT NOT NULL REFERENCES retail_dw.dim_coupon(coupon_key),
    campaign_key BIGINT NOT NULL REFERENCES retail_dw.dim_campaign(campaign_key),
    redemption_date_key INTEGER NOT NULL REFERENCES retail_dw.dim_date(date_key),
    household_id BIGINT,
    coupon_upc BIGINT,
    campaign_id BIGINT,
    redemption_date DATE
);

CREATE TABLE IF NOT EXISTS retail_dw.fact_campaign_participation (
    campaign_participation_key BIGSERIAL PRIMARY KEY,
    campaign_key BIGINT NOT NULL REFERENCES retail_dw.dim_campaign(campaign_key),
    household_key BIGINT NOT NULL REFERENCES retail_dw.dim_household(household_key),
    campaign_id BIGINT,
    household_id BIGINT,
    campaign_type TEXT,
    start_day INTEGER,
    end_day INTEGER
);

CREATE TABLE IF NOT EXISTS retail_dw.fact_product_promotion (
    product_promotion_key BIGSERIAL PRIMARY KEY,
    product_key BIGINT NOT NULL REFERENCES retail_dw.dim_product(product_key),
    store_key BIGINT NOT NULL REFERENCES retail_dw.dim_store(store_key),
    product_id BIGINT,
    store_id BIGINT,
    week INTEGER,
    display_location TEXT,
    mailer_location TEXT
);

ALTER TABLE IF EXISTS retail_dw.dim_household ADD COLUMN IF NOT EXISTS age TEXT;
ALTER TABLE IF EXISTS retail_dw.dim_household ADD COLUMN IF NOT EXISTS income TEXT;
ALTER TABLE IF EXISTS retail_dw.dim_household ADD COLUMN IF NOT EXISTS home_ownership TEXT;
ALTER TABLE IF EXISTS retail_dw.dim_household ADD COLUMN IF NOT EXISTS marital_status TEXT;
ALTER TABLE IF EXISTS retail_dw.dim_household ADD COLUMN IF NOT EXISTS household_size TEXT;
ALTER TABLE IF EXISTS retail_dw.dim_household ADD COLUMN IF NOT EXISTS household_comp TEXT;
ALTER TABLE IF EXISTS retail_dw.dim_household ADD COLUMN IF NOT EXISTS kids_count TEXT;

ALTER TABLE IF EXISTS retail_dw.dim_product ADD COLUMN IF NOT EXISTS manufacturer_id BIGINT;
ALTER TABLE IF EXISTS retail_dw.dim_product ADD COLUMN IF NOT EXISTS product_category TEXT;
ALTER TABLE IF EXISTS retail_dw.dim_product ADD COLUMN IF NOT EXISTS product_type TEXT;
ALTER TABLE IF EXISTS retail_dw.dim_product ADD COLUMN IF NOT EXISTS package_size TEXT;

ALTER TABLE IF EXISTS retail_dw.dim_holiday ADD COLUMN IF NOT EXISTS date_text TEXT;
ALTER TABLE IF EXISTS retail_dw.dim_holiday ADD COLUMN IF NOT EXISTS date_definition TEXT;
ALTER TABLE IF EXISTS retail_dw.dim_holiday ADD COLUMN IF NOT EXISTS official_name TEXT;
ALTER TABLE IF EXISTS retail_dw.dim_holiday ADD COLUMN IF NOT EXISTS details TEXT;

INSERT INTO retail_dw.dim_household (
    household_key,
    household_id,
    age,
    income,
    home_ownership,
    marital_status,
    household_size,
    household_comp,
    kids_count
)
VALUES (0, NULL, 'Unknown', 'Unknown', 'Unknown', 'Unknown', 'Unknown', 'Unknown', 'Unknown')
ON CONFLICT (household_key) DO NOTHING;

INSERT INTO retail_dw.dim_product (
    product_key,
    product_id,
    manufacturer_id,
    department,
    brand,
    product_category,
    product_type,
    package_size
)
VALUES (0, NULL, NULL, 'Unknown', 'Unknown', 'Unknown', 'Unknown', 'Unknown')
ON CONFLICT (product_key) DO NOTHING;

INSERT INTO retail_dw.dim_store (store_key, store_id)
VALUES (0, NULL)
ON CONFLICT (store_key) DO NOTHING;

INSERT INTO retail_dw.dim_date (
    date_key,
    full_date,
    day_of_week,
    day_name,
    day_of_month,
    week_of_year,
    month_number,
    month_name,
    quarter_number,
    year_number
)
VALUES (0, NULL, NULL, 'Unknown', NULL, NULL, NULL, 'Unknown', NULL, NULL)
ON CONFLICT (date_key) DO NOTHING;

INSERT INTO retail_dw.dim_campaign (
    campaign_key,
    campaign_id,
    campaign_type,
    start_day,
    end_day,
    start_date,
    end_date,
    duration_days
)
VALUES (0, NULL, 'Unknown', NULL, NULL, NULL, NULL, NULL)
ON CONFLICT (campaign_key) DO NOTHING;

INSERT INTO retail_dw.dim_coupon (
    coupon_key,
    coupon_upc,
    product_id,
    campaign_id
)
VALUES (0, NULL, NULL, NULL)
ON CONFLICT (coupon_key) DO NOTHING;

INSERT INTO retail_dw.dim_holiday (
    holiday_key,
    holiday_date,
    date_text,
    date_definition,
    official_name,
    details,
    holiday_name,
    holiday_type
)
VALUES (0, NULL, 'Unknown', 'Unknown', 'Unknown', 'Unknown', 'Unknown', 'Unknown')
ON CONFLICT (holiday_key) DO NOTHING;

INSERT INTO retail_dw.dim_household (
    household_id,
    age,
    income,
    home_ownership,
    marital_status,
    household_size,
    household_comp,
    kids_count
)
SELECT
    d.household_id,
    d.age,
    d.income,
    d.home_ownership,
    d.marital_status,
    d.household_size,
    d.household_comp,
    d.kids_count
FROM (
    SELECT
        stg.*,
        ROW_NUMBER() OVER (
            PARTITION BY stg.household_id
            ORDER BY
                stg.age,
                stg.income,
                stg.home_ownership,
                stg.marital_status,
                stg.household_size,
                stg.household_comp,
                stg.kids_count
        ) AS row_number
    FROM retail_dw.stg_demographics stg
    WHERE stg.household_id IS NOT NULL
) d
WHERE d.row_number = 1
ON CONFLICT (household_id) DO UPDATE SET
    age = EXCLUDED.age,
    income = EXCLUDED.income,
    home_ownership = EXCLUDED.home_ownership,
    marital_status = EXCLUDED.marital_status,
    household_size = EXCLUDED.household_size,
    household_comp = EXCLUDED.household_comp,
    kids_count = EXCLUDED.kids_count;

INSERT INTO retail_dw.dim_household (household_id)
SELECT DISTINCT t.household_id
FROM retail_dw.stg_transactions t
WHERE t.household_id IS NOT NULL
ON CONFLICT (household_id) DO NOTHING;

INSERT INTO retail_dw.dim_product (
    product_id,
    manufacturer_id,
    department,
    brand,
    product_category,
    product_type,
    package_size
)
SELECT
    p.product_id,
    p.manufacturer_id,
    p.department,
    p.brand,
    p.product_category,
    p.product_type,
    p.package_size
FROM (
    SELECT
        stg.*,
        ROW_NUMBER() OVER (
            PARTITION BY stg.product_id
            ORDER BY
                stg.manufacturer_id,
                stg.department,
                stg.brand,
                stg.product_category,
                stg.product_type,
                stg.package_size
        ) AS row_number
    FROM retail_dw.stg_products stg
    WHERE stg.product_id IS NOT NULL
) p
WHERE p.row_number = 1
ON CONFLICT (product_id) DO UPDATE SET
    manufacturer_id = EXCLUDED.manufacturer_id,
    department = EXCLUDED.department,
    brand = EXCLUDED.brand,
    product_category = EXCLUDED.product_category,
    product_type = EXCLUDED.product_type,
    package_size = EXCLUDED.package_size;

INSERT INTO retail_dw.dim_product (product_id)
SELECT DISTINCT t.product_id
FROM retail_dw.stg_transactions t
WHERE t.product_id IS NOT NULL
ON CONFLICT (product_id) DO NOTHING;

INSERT INTO retail_dw.dim_store (store_id)
SELECT DISTINCT store_id
FROM retail_dw.stg_transactions
WHERE store_id IS NOT NULL
ON CONFLICT (store_id) DO NOTHING;

INSERT INTO retail_dw.dim_store (store_id)
SELECT DISTINCT store_id
FROM retail_dw.stg_promotions
WHERE store_id IS NOT NULL
ON CONFLICT (store_id) DO NOTHING;

INSERT INTO retail_dw.dim_date (
    date_key,
    full_date,
    day_of_week,
    day_name,
    day_of_month,
    week_of_year,
    month_number,
    month_name,
    quarter_number,
    year_number
)
SELECT DISTINCT
    TO_CHAR(transaction_date, 'YYYYMMDD')::INTEGER AS date_key,
    transaction_date AS full_date,
    EXTRACT(ISODOW FROM transaction_date)::INTEGER AS day_of_week,
    TO_CHAR(transaction_date, 'Day') AS day_name,
    EXTRACT(DAY FROM transaction_date)::INTEGER AS day_of_month,
    EXTRACT(WEEK FROM transaction_date)::INTEGER AS week_of_year,
    EXTRACT(MONTH FROM transaction_date)::INTEGER AS month_number,
    TO_CHAR(transaction_date, 'Month') AS month_name,
    EXTRACT(QUARTER FROM transaction_date)::INTEGER AS quarter_number,
    EXTRACT(YEAR FROM transaction_date)::INTEGER AS year_number
FROM retail_dw.stg_transactions
WHERE transaction_date IS NOT NULL
ON CONFLICT (date_key) DO NOTHING;

INSERT INTO retail_dw.dim_date (
    date_key,
    full_date,
    day_of_week,
    day_name,
    day_of_month,
    week_of_year,
    month_number,
    month_name,
    quarter_number,
    year_number
)
SELECT DISTINCT
    TO_CHAR(redemption_date, 'YYYYMMDD')::INTEGER AS date_key,
    redemption_date AS full_date,
    EXTRACT(ISODOW FROM redemption_date)::INTEGER AS day_of_week,
    TO_CHAR(redemption_date, 'Day') AS day_name,
    EXTRACT(DAY FROM redemption_date)::INTEGER AS day_of_month,
    EXTRACT(WEEK FROM redemption_date)::INTEGER AS week_of_year,
    EXTRACT(MONTH FROM redemption_date)::INTEGER AS month_number,
    TO_CHAR(redemption_date, 'Month') AS month_name,
    EXTRACT(QUARTER FROM redemption_date)::INTEGER AS quarter_number,
    EXTRACT(YEAR FROM redemption_date)::INTEGER AS year_number
FROM retail_dw.stg_coupon_redemptions
WHERE redemption_date IS NOT NULL
ON CONFLICT (date_key) DO NOTHING;

INSERT INTO retail_dw.dim_campaign (
    campaign_id,
    campaign_type,
    start_day,
    end_day,
    start_date,
    end_date,
    duration_days
)
SELECT
    cd.campaign_id,
    cd.campaign_type,
    cd.start_day,
    cd.end_day,
    cd.start_date,
    cd.end_date,
    cd.duration_days
FROM (
    SELECT
        stg.*,
        ROW_NUMBER() OVER (
            PARTITION BY stg.campaign_id
            ORDER BY
                stg.start_date,
                stg.end_date,
                stg.campaign_type
        ) AS row_number
    FROM retail_dw.stg_campaign_descriptions stg
    WHERE stg.campaign_id IS NOT NULL
) cd
WHERE cd.row_number = 1
ON CONFLICT (campaign_id) DO UPDATE SET
    campaign_type = EXCLUDED.campaign_type,
    start_day = EXCLUDED.start_day,
    end_day = EXCLUDED.end_day,
    start_date = EXCLUDED.start_date,
    end_date = EXCLUDED.end_date,
    duration_days = EXCLUDED.duration_days;

INSERT INTO retail_dw.dim_campaign (
    campaign_id,
    campaign_type,
    start_day,
    end_day
)
SELECT DISTINCT
    c.campaign_id,
    c.campaign_type,
    c.start_day,
    c.end_day
FROM retail_dw.stg_campaigns c
WHERE c.campaign_id IS NOT NULL
ON CONFLICT (campaign_id) DO NOTHING;

INSERT INTO retail_dw.dim_coupon (
    coupon_upc,
    product_id,
    campaign_id
)
SELECT
    c.coupon_upc,
    c.product_id,
    c.campaign_id
FROM (
    SELECT
        stg.*,
        ROW_NUMBER() OVER (
            PARTITION BY stg.coupon_upc
            ORDER BY
                stg.campaign_id,
                stg.product_id
        ) AS row_number
    FROM retail_dw.stg_coupons stg
    WHERE stg.coupon_upc IS NOT NULL
) c
WHERE c.row_number = 1
ON CONFLICT (coupon_upc) DO UPDATE SET
    product_id = EXCLUDED.product_id,
    campaign_id = EXCLUDED.campaign_id;

INSERT INTO retail_dw.dim_holiday (
    holiday_date,
    date_text,
    date_definition,
    official_name,
    details,
    holiday_name,
    holiday_type
)
SELECT DISTINCT
    NULL::DATE AS holiday_date,
    h."date" AS date_text,
    h.date_definition,
    h.official_name,
    h.details,
    h.official_name AS holiday_name,
    h.date_definition AS holiday_type
FROM retail_dw.stg_holidays h
WHERE h.official_name IS NOT NULL
    AND NOT EXISTS (
        SELECT 1
        FROM retail_dw.dim_holiday d
        WHERE d.official_name IS NOT DISTINCT FROM h.official_name
            AND d.date_text IS NOT DISTINCT FROM h."date"
    );

INSERT INTO retail_dw.fact_transaction_item (
    basket_id,
    household_key,
    product_key,
    store_key,
    date_key,
    household_id,
    product_id,
    store_id,
    week,
    transaction_timestamp,
    transaction_datetime,
    transaction_date,
    quantity,
    quantity_capped,
    sales_value,
    sales_value_capped,
    retail_disc,
    retail_disc_capped,
    coupon_disc,
    coupon_disc_capped,
    coupon_match_disc,
    quantity_is_invalid,
    coupon_was_used,
    retail_discount_was_applied,
    sales_value_is_possible_outlier,
    quantity_is_possible_outlier,
    retail_disc_is_possible_outlier,
    coupon_disc_is_possible_outlier
)
SELECT
    t.basket_id,
    COALESCE(h.household_key, 0) AS household_key,
    COALESCE(p.product_key, 0) AS product_key,
    COALESCE(s.store_key, 0) AS store_key,
    COALESCE(dd.date_key, 0) AS date_key,
    t.household_id,
    t.product_id,
    t.store_id,
    t.week,
    t.transaction_timestamp,
    t.transaction_datetime,
    t.transaction_date,
    t.quantity,
    t.quantity_capped,
    t.sales_value,
    t.sales_value_capped,
    t.retail_disc,
    t.retail_disc_capped,
    t.coupon_disc,
    t.coupon_disc_capped,
    t.coupon_match_disc,
    t.quantity_is_invalid,
    t.coupon_was_used,
    t.retail_discount_was_applied,
    t.sales_value_is_possible_outlier,
    t.quantity_is_possible_outlier,
    t.retail_disc_is_possible_outlier,
    t.coupon_disc_is_possible_outlier
FROM retail_dw.stg_transactions t
LEFT JOIN retail_dw.dim_household h
    ON h.household_id = t.household_id
LEFT JOIN retail_dw.dim_product p
    ON p.product_id = t.product_id
LEFT JOIN retail_dw.dim_store s
    ON s.store_id = t.store_id
LEFT JOIN retail_dw.dim_date dd
    ON dd.full_date = t.transaction_date
WHERE NOT EXISTS (
    SELECT 1
    FROM retail_dw.fact_transaction_item f
    WHERE f.basket_id IS NOT DISTINCT FROM t.basket_id
        AND f.household_id IS NOT DISTINCT FROM t.household_id
        AND f.product_id IS NOT DISTINCT FROM t.product_id
        AND f.store_id IS NOT DISTINCT FROM t.store_id
        AND f.transaction_datetime IS NOT DISTINCT FROM t.transaction_datetime
        AND f.quantity IS NOT DISTINCT FROM t.quantity
        AND f.sales_value IS NOT DISTINCT FROM t.sales_value
);

INSERT INTO retail_dw.fact_coupon_redemption (
    household_key,
    coupon_key,
    campaign_key,
    redemption_date_key,
    household_id,
    coupon_upc,
    campaign_id,
    redemption_date
)
SELECT
    COALESCE(h.household_key, 0) AS household_key,
    COALESCE(cpn.coupon_key, 0) AS coupon_key,
    COALESCE(cmp.campaign_key, 0) AS campaign_key,
    COALESCE(dd.date_key, 0) AS redemption_date_key,
    r.household_id,
    r.coupon_upc,
    r.campaign_id,
    r.redemption_date
FROM retail_dw.stg_coupon_redemptions r
LEFT JOIN retail_dw.dim_household h
    ON h.household_id = r.household_id
LEFT JOIN retail_dw.dim_coupon cpn
    ON cpn.coupon_upc = r.coupon_upc
LEFT JOIN retail_dw.dim_campaign cmp
    ON cmp.campaign_id = r.campaign_id
LEFT JOIN retail_dw.dim_date dd
    ON dd.full_date = r.redemption_date
WHERE NOT EXISTS (
    SELECT 1
    FROM retail_dw.fact_coupon_redemption f
    WHERE f.household_id IS NOT DISTINCT FROM r.household_id
        AND f.coupon_upc IS NOT DISTINCT FROM r.coupon_upc
        AND f.campaign_id IS NOT DISTINCT FROM r.campaign_id
        AND f.redemption_date IS NOT DISTINCT FROM r.redemption_date
);

INSERT INTO retail_dw.fact_campaign_participation (
    campaign_key,
    household_key,
    campaign_id,
    household_id,
    campaign_type,
    start_day,
    end_day
)
SELECT
    COALESCE(cmp.campaign_key, 0) AS campaign_key,
    COALESCE(h.household_key, 0) AS household_key,
    c.campaign_id,
    c.household_id,
    c.campaign_type,
    c.start_day,
    c.end_day
FROM retail_dw.stg_campaigns c
LEFT JOIN retail_dw.dim_campaign cmp
    ON cmp.campaign_id = c.campaign_id
LEFT JOIN retail_dw.dim_household h
    ON h.household_id = c.household_id
WHERE NOT EXISTS (
    SELECT 1
    FROM retail_dw.fact_campaign_participation f
    WHERE f.campaign_id IS NOT DISTINCT FROM c.campaign_id
        AND f.household_id IS NOT DISTINCT FROM c.household_id
);

INSERT INTO retail_dw.fact_product_promotion (
    product_key,
    store_key,
    product_id,
    store_id,
    week,
    display_location,
    mailer_location
)
SELECT
    COALESCE(p.product_key, 0) AS product_key,
    COALESCE(s.store_key, 0) AS store_key,
    pr.product_id,
    pr.store_id,
    pr.week,
    pr.display_location,
    pr.mailer_location
FROM retail_dw.stg_promotions pr
LEFT JOIN retail_dw.dim_product p
    ON p.product_id = pr.product_id
LEFT JOIN retail_dw.dim_store s
    ON s.store_id = pr.store_id
WHERE NOT EXISTS (
    SELECT 1
    FROM retail_dw.fact_product_promotion f
    WHERE f.product_id IS NOT DISTINCT FROM pr.product_id
        AND f.store_id IS NOT DISTINCT FROM pr.store_id
        AND f.week IS NOT DISTINCT FROM pr.week
        AND f.display_location IS NOT DISTINCT FROM pr.display_location
        AND f.mailer_location IS NOT DISTINCT FROM pr.mailer_location
);

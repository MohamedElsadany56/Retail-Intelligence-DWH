# Retail Intelligence DWH

A data warehouse and analytics project for building a retail intelligence platform using the Complete Journey grocery retail dataset.  
The project focuses on data warehousing, ETL, data quality validation, market basket analysis, campaign/coupon analytics, holiday-aware analysis, customer segmentation, and business reporting using Power BI.

---

## 1. Project Overview

This project builds a PostgreSQL-based data warehouse for retail transaction analysis.  
The main dataset is the Complete Journey grocery dataset, which includes transaction, product, household, campaign, coupon, promotion, and holiday-related data.

The goal is to transform cleaned retail data into a structured analytical warehouse that supports:

- Sales and product performance analysis
- Market basket analysis
- Coupon redemption analysis
- Campaign participation analysis
- Product promotion analysis
- Holiday-aware retail analysis
- Customer segmentation
- Recommendation system preparation
- Power BI reporting

---

## 2. Current Phase Completed

The current completed phase is:

```text
Azure PostgreSQL Data Warehouse + ETL + Power BI Data Model Preparation
````

In this phase, we completed the following:

1. Prepared cleaned Complete Journey CSV files.
2. Created an Azure PostgreSQL database connection plan.
3. Removed the old schema related to the previous Instacart version.
4. Created the new warehouse schema:

```text
retail_dw
```

5. Loaded staging tables into Azure PostgreSQL.
6. Built dimension tables.
7. Built fact tables.
8. Added validation views.
9. Fixed important data quality issues after loading.
10. Prepared the Power BI data model using facts and dimensions only.

---

## 3. Dataset Files

The project uses cleaned CSV files stored outside GitHub.

Expected cleaned files:

```text
basket_items_for_mba.csv
coupon_redemptions_clean.csv
campaigns_clean.csv
coupons_clean.csv
demographics_clean.csv
campaign_descriptions_clean.csv
products_clean.csv
promotions_clean.csv
transactions_clean.csv
```

Default local/Colab data path:

```text
/content/drive/MyDrive/complete_journey_data/preprocessed
```

Large CSV files are not committed to GitHub.

---

## 4. Database

Database platform:

```text
Azure PostgreSQL
```

Main schema:

```text
retail_dw
```

The old schema:

```text
instacart_dw
```

was identified as outdated because the project moved from Instacart to Complete Journey.

The new schema follows a simple warehouse naming convention:

```text
stg_   staging tables
dim_   dimension tables
fact_  fact tables
vw_    validation or analytical views
```

---

## 5. Staging Tables

The following staging tables were created and loaded:

```text
retail_dw.stg_transactions
retail_dw.stg_products
retail_dw.stg_promotions
retail_dw.stg_holidays
retail_dw.stg_demographics
retail_dw.stg_coupons
retail_dw.stg_coupon_redemptions
retail_dw.stg_campaigns
retail_dw.stg_campaign_descriptions
retail_dw.stg_basket_items_for_mba
```

Staging tables are used for raw cleaned data loading and validation.
They should not be used directly in the final Power BI model unless debugging is needed.

---

## 6. Dimension Tables

The following dimension tables were created:

```text
retail_dw.dim_date
retail_dw.dim_product
retail_dw.dim_household
retail_dw.dim_store
retail_dw.dim_campaign
retail_dw.dim_coupon
retail_dw.dim_holiday
```

Each dimension uses a surrogate key.

Example:

```text
product_key  = warehouse surrogate key
product_id   = original dataset product identifier
```

Unknown rows were included where needed to avoid losing fact rows when references are missing.

Example:

```text
campaign_key = 0
campaign_type = Unknown
```

---

## 7. Fact Tables

The following fact tables were created:

```text
retail_dw.fact_transaction_item
retail_dw.fact_coupon_redemption
retail_dw.fact_campaign_participation
retail_dw.fact_product_promotion
```

### 7.1 fact_transaction_item

Main grain:

```text
One row = one product purchased inside one basket by one household at one store and timestamp.
```

This table supports:

* Sales analysis
* Basket analysis
* Product analysis
* Discount analysis
* Coupon usage analysis
* Customer analysis
* Holiday impact analysis

Important columns include:

```text
transaction_item_key
basket_id
household_key
product_key
store_key
date_key
household_id
product_id
store_id
week
transaction_datetime
transaction_date
quantity
quantity_capped
sales_value
sales_value_capped
retail_disc
retail_disc_capped
coupon_disc
coupon_disc_capped
coupon_match_disc
quantity_is_invalid
coupon_was_used
retail_discount_was_applied
sales_value_is_possible_outlier
quantity_is_possible_outlier
retail_disc_is_possible_outlier
coupon_disc_is_possible_outlier
```

Both original and capped values were kept.

Reason:

```text
Original values are preserved for traceability, while capped values are used for robust analytical reporting.
```

### 7.2 fact_coupon_redemption

Main grain:

```text
One row = one coupon redeemed by one household in one campaign/date.
```

This table supports:

* Coupon redemption rate
* Customer coupon behavior
* Campaign coupon performance
* Discount-sensitive customer analysis

### 7.3 fact_campaign_participation

Main grain:

```text
One row = one household participating in one campaign.
```

Campaign descriptive fields such as campaign type, start date, end date, and duration are stored in `dim_campaign`.

### 7.4 fact_product_promotion

Main grain:

```text
One row = one product promoted in one store during one week.
```

This table supports:

* Product promotion analysis
* Store promotion analysis
* Promotion timing analysis

---

## 8. Validation Views

The following validation views were created:

```text
retail_dw.vw_table_row_counts
retail_dw.vw_data_quality_summary
```

They are used to validate:

* Staging row counts
* Dimension row counts
* Fact row counts
* Missing references
* Null surrogate keys
* Duplicate records
* Invalid quantity rows
* Coupon usage rows
* Outlier flags

These views can be loaded into Power BI for a Data Warehouse Validation page.

---

## 9. Data Quality Fixes Applied

### 9.1 Campaign Duration Fix

In `retail_dw.dim_campaign`, the columns `start_date` and `end_date` were populated, but `duration_days` was null.

The issue was fixed using:

```sql
UPDATE retail_dw.dim_campaign
SET duration_days = end_date - start_date
WHERE start_date IS NOT NULL
  AND end_date IS NOT NULL
  AND duration_days IS NULL;
```

Validation showed that all real campaigns with valid dates now have a calculated duration.

### 9.2 Holiday Date Fix

In `retail_dw.dim_holiday`, the `holiday_date` column was null after the initial load.
The date information existed as text in `date_text`, so real 2017 holiday dates were manually mapped.

The update used 2017 because campaign and transaction dates are based on the same analysis year.

Applied mapping:

```sql
UPDATE retail_dw.dim_holiday
SET holiday_date = CASE
    WHEN date_text = 'December 1' THEN DATE '2017-12-01'
    WHEN date_text = 'February 15–21' THEN DATE '2017-02-20'
    WHEN date_text = 'February 15-21' THEN DATE '2017-02-20'
    WHEN date_text = 'June 14' THEN DATE '2017-06-14'
    WHEN date_text = 'March 10' THEN DATE '2017-03-10'
    WHEN date_text = 'March 25–31' THEN DATE '2017-03-27'
    WHEN date_text = 'March 25-31' THEN DATE '2017-03-27'
    WHEN date_text = 'May 15–21' THEN DATE '2017-05-15'
    WHEN date_text = 'May 15-21' THEN DATE '2017-05-15'
    WHEN date_text = 'November 2–8' THEN DATE '2017-11-07'
    WHEN date_text = 'November 2-8' THEN DATE '2017-11-07'
    WHEN date_text = 'September 11' THEN DATE '2017-09-11'
    WHEN date_text = 'September 15–21' THEN DATE '2017-09-18'
    WHEN date_text = 'September 15-21' THEN DATE '2017-09-18'
    ELSE holiday_date
END
WHERE holiday_key <> 0;
```

The unknown holiday row remains null by design:

```text
holiday_key = 0
holiday_name = Unknown
holiday_date = NULL
```

---

## 10. Power BI Data Model

Only final warehouse tables should be kept in the Power BI model.

### Tables to Keep

```text
retail_dw_dim_date
retail_dw_dim_product
retail_dw_dim_household
retail_dw_dim_store
retail_dw_dim_campaign
retail_dw_dim_coupon
retail_dw_dim_holiday

retail_dw_fact_transaction_item
retail_dw_fact_coupon_redemption
retail_dw_fact_campaign_participation
retail_dw_fact_product_promotion

retail_dw_vw_table_row_counts
retail_dw_vw_data_quality_summary
```

### Tables to Disable or Remove

Staging tables should not be part of the final Power BI model:

```text
retail_dw_stg_transactions
retail_dw_stg_products
retail_dw_stg_promotions
retail_dw_stg_holidays
retail_dw_stg_demographics
retail_dw_stg_coupons
retail_dw_stg_coupon_redemptions
retail_dw_stg_campaigns
retail_dw_stg_campaign_descriptions
retail_dw_stg_basket_items_for_mba
```

Staging tables are useful for ETL and debugging only.

---

## 11. Recommended Power BI Relationships

Use a star schema model.

### Main Transaction Fact

```text
dim_date.date_key       → fact_transaction_item.date_key
dim_product.product_key → fact_transaction_item.product_key
dim_household.household_key → fact_transaction_item.household_key
dim_store.store_key     → fact_transaction_item.store_key
```

### Coupon Redemption Fact

```text
dim_coupon.coupon_key     → fact_coupon_redemption.coupon_key
dim_household.household_key → fact_coupon_redemption.household_key
dim_campaign.campaign_key → fact_coupon_redemption.campaign_key
dim_date.date_key         → fact_coupon_redemption.date_key
```

### Campaign Participation Fact

```text
dim_campaign.campaign_key → fact_campaign_participation.campaign_key
dim_household.household_key → fact_campaign_participation.household_key
```

### Product Promotion Fact

```text
dim_product.product_key → fact_product_promotion.product_key
dim_store.store_key     → fact_product_promotion.store_key
dim_date.date_key       → fact_product_promotion.date_key
```

### Holiday Relationship

Preferred relationship:

```text
dim_holiday.holiday_date → dim_date.full_date
```

If Power BI creates ambiguity, use holiday fields inside `dim_date` or keep `dim_holiday` as a descriptive lookup table.

Recommended relationship settings:

```text
Cardinality: One-to-many
Filter direction: Single
Dimension side: One
Fact side: Many
```

---

## 12. Duplicate Handling Rule

Duplicates should not be removed blindly from fact tables.

The correct rule is:

```text
Repeated dimension keys are normal.
Repeated full fact events against the same grain are suspicious.
```

Examples:

* `product_key` repeated many times in `fact_transaction_item` is normal.
* The same `basket_id + product_key + household_key + store_key + date_key` repeated may be a duplicate.
* The same `campaign_key + household_key` repeated in `fact_campaign_participation` may be a duplicate.
* The same `coupon_key + household_key + campaign_key + date_key` repeated may be a duplicate.

Duplicate handling should be done in PostgreSQL or ETL, not manually in Power BI.

---

## 13. Power Query Cleaning Notes

A Power BI-generated query using:

```powerquery
Table.SelectRowsWithErrors
```

was identified as an error-checking query, not a normal data loading query.

For final fact and dimension tables, the Power Query steps should be simple:

```text
Source → Changed Type
```

Error-detection queries should only be used for debugging.

---

## 14. Environment Variables

Do not commit the real `.env` file.

Use `.env.example` only.

Example:

```env
Azure_DB_HOST=your-server-name.postgres.database.azure.com
Azure_DB_PORT=5432
Azure_DB_NAME=postgres
Azure_DB_USER=your_user
Azure_DB_PASSWORD=your_password

ETL_SCHEMA=retail_dw
DATA_DIR=/content/drive/MyDrive/complete_journey_data/preprocessed
ETL_CHUNKSIZE=100000

FORCE_RELOAD_STAGING=false
FORCE_RELOAD_FACT=false
```


## 15. Next Phase

The next implementation phase should focus on data mining and analytics.

Planned next phase:

```text
Association Rule Mining + Customer Segmentation + Recommendation Outputs
```

Algorithms planned:

```text
Apriori
FP-Growth
ECLAT
K-Means
DBSCAN
Hierarchical Clustering
```

Expected outputs:

```text
association_rules_results.csv
algorithm_comparison.csv
customer_segments.csv
product_recommendations.csv
```

These outputs will later support:

* Market basket analysis dashboard
* Algorithm comparison dashboard
* Customer segmentation dashboard
* Recommendation engine dashboard
* IEEE-style project documentation

---

## 16. Project Status

Current status:

```text
Data preprocessing: Completed
Azure PostgreSQL staging load: Completed
Data warehouse schema: Completed
Dimensions and facts: Completed
Validation views: Completed
Power BI model preparation: In progress
Holiday date fix: Completed
Campaign duration fix: Completed
Next phase: Data mining implementation
```

```
```

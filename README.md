# Retail-Intelligence-DWH

## Objective

Build Phase 1 of a Retail Intelligence Platform using the Complete Journey grocery dataset. This phase creates an Azure PostgreSQL data warehouse, staging layer, dimensional model, fact tables, analytics views, and validation reports. Later phases will use this warehouse for Apriori, FP-Growth, ECLAT, K-Means, DBSCAN, Hierarchical Clustering, campaign analytics, coupon analytics, and recommendation outputs.

## Expected Dataset Files

Place the cleaned Complete Journey files in `DATA_DIR`. The default path is:

```text
/content/drive/MyDrive/complete_journey_data/preprocessed
```

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

Holiday staging uses `HOLIDAYS_FILE`, which can point outside `DATA_DIR`. For the current local setup:

```text
/home/elsadany/Downloads/proposed_federal_holidays.csv
```

## Simple Architecture

```text
Cleaned CSV files
    -> retail_dw staging tables
    -> retail_dw dimensions and facts
    -> indexes, materialized views, validation views
    -> validation CSV report in outputs/
```

## Repo Structure

```text
data/       Dataset notes only. Real CSV files are not committed.
sql/        PostgreSQL schema, DWH build, indexes, views, and validation SQL.
scripts/    Python ETL and validation scripts.
notebooks/  Academic walkthrough notebooks added in later phases.
outputs/    Validation reports and later mining outputs.
```

## Environment Setup

1. Create your local `.env` from the template:

```bash
cp .env.example .env
```

2. Fill in Azure PostgreSQL credentials and ETL settings:

```text
Azure_DB_HOST=
Azure_DB_PORT=5432
Azure_DB_NAME=postgres
Azure_DB_USER=
Azure_DB_PASSWORD=
ETL_SCHEMA=retail_dw
DATA_DIR=/content/drive/MyDrive/complete_journey_data/preprocessed
HOLIDAYS_FILE=/home/elsadany/Downloads/proposed_federal_holidays.csv
ETL_CHUNKSIZE=100000
FORCE_RELOAD_STAGING=false
FORCE_RELOAD_FACT=false
```

3. Install Python dependencies:

```bash
pip install -r requirements.txt
```

## How To Run

These scripts connect to Azure PostgreSQL. Run them only when you are ready to execute database work.

1. Load staging tables:

```bash
python3 scripts/01_load_staging.py
```

2. Build the data warehouse and analytics views:

```bash
python3 scripts/02_build_dwh.py
```

3. Validate the data warehouse:

```bash
python3 scripts/03_validate_dwh.py
```

The validation script prints query results and saves:

```text
outputs/dwh_validation_report.csv
```



## Next Phase

Mining, clustering, campaign analytics, coupon analytics, and recommendation scripts will be added after the DWH is loaded and validated.

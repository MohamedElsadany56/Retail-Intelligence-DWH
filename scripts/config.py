from pathlib import Path
import os

from dotenv import load_dotenv


load_dotenv()

AZURE_DB_HOST = os.getenv("Azure_DB_HOST")
AZURE_DB_PORT = os.getenv("Azure_DB_PORT", "5432")
AZURE_DB_NAME = os.getenv("Azure_DB_NAME", "postgres")
AZURE_DB_USER = os.getenv("Azure_DB_USER")
AZURE_DB_PASSWORD = os.getenv("Azure_DB_PASSWORD")

ETL_SCHEMA = os.getenv("ETL_SCHEMA", "retail_dw")
DATA_DIR = Path(os.getenv("DATA_DIR", "/content/drive/MyDrive/complete_journey_data/preprocessed"))
ETL_CHUNKSIZE = int(os.getenv("ETL_CHUNKSIZE", "100000"))

FORCE_RELOAD_STAGING = os.getenv("FORCE_RELOAD_STAGING", "false").lower() == "true"
FORCE_RELOAD_FACT = os.getenv("FORCE_RELOAD_FACT", "false").lower() == "true"

REQUIRED_ENV_VARS = [
    "Azure_DB_HOST",
    "Azure_DB_USER",
    "Azure_DB_PASSWORD",
]

CSV_FILES = {
    "stg_transactions": "transactions_clean.csv",
    "stg_products": "products_clean.csv",
    "stg_demographics": "demographics_clean.csv",
    "stg_campaigns": "campaigns_clean.csv",
    "stg_campaign_descriptions": "campaign_descriptions_clean.csv",
    "stg_coupons": "coupons_clean.csv",
    "stg_coupon_redemptions": "coupon_redemptions_clean.csv",
    "stg_promotions": "promotions_clean.csv",
    "stg_basket_items_for_mba": "basket_items_for_mba.csv",
}

CSV_COLUMNS = {
    "stg_transactions": [
        "household_id",
        "store_id",
        "basket_id",
        "product_id",
        "quantity",
        "sales_value",
        "retail_disc",
        "coupon_disc",
        "coupon_match_disc",
        "week",
        "transaction_timestamp",
        "transaction_datetime",
        "transaction_date",
        "sales_value_is_possible_outlier",
        "sales_value_capped",
        "quantity_is_possible_outlier",
        "quantity_capped",
        "retail_disc_is_possible_outlier",
        "retail_disc_capped",
        "coupon_disc_is_possible_outlier",
        "coupon_disc_capped",
        "quantity_is_invalid",
        "coupon_was_used",
        "retail_discount_was_applied",
    ],
    "stg_products": [
        "product_id",
        "manufacturer_id",
        "department",
        "brand",
        "product_category",
        "product_type",
        "package_size",
    ],
    "stg_demographics": [
        "household_id",
        "age",
        "income",
        "home_ownership",
        "marital_status",
        "household_size",
        "household_comp",
        "kids_count",
    ],
    "stg_campaigns": [
        "campaign_id",
        "household_id",
    ],
    "stg_campaign_descriptions": [
        "campaign_id",
        "campaign_type",
        "start_date",
        "end_date",
    ],
    "stg_coupons": [
        "coupon_upc",
        "product_id",
        "campaign_id",
    ],
    "stg_coupon_redemptions": [
        "household_id",
        "coupon_upc",
        "campaign_id",
        "redemption_date",
    ],
    "stg_promotions": [
        "product_id",
        "store_id",
        "display_location",
        "mailer_location",
        "week",
    ],
    "stg_basket_items_for_mba": [
        "basket_id",
        "product_id",
        "department",
        "product_category",
        "product_type",
    ],
}

CORE_FILES = {
    "transactions_clean.csv",
    "products_clean.csv",
    "demographics_clean.csv",
}

def validate_config() -> None:
    missing = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {missing}")

    if not DATA_DIR.exists():
        raise RuntimeError(f"DATA_DIR does not exist: {DATA_DIR}")

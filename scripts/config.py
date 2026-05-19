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

CORE_FILES = {
    "transactions_clean.csv",
    "products_clean.csv",
    "demographics_clean.csv",
}

LARGE_TABLES = {
    "stg_transactions",
    "stg_promotions",
    "stg_basket_items_for_mba",
}


def validate_config() -> None:
    missing = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {missing}")

    if not DATA_DIR.exists():
        raise RuntimeError(f"DATA_DIR does not exist: {DATA_DIR}")

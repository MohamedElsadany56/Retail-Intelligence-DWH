from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, URL

from config import (
    AZURE_DB_HOST,
    AZURE_DB_NAME,
    AZURE_DB_PASSWORD,
    AZURE_DB_PORT,
    AZURE_DB_USER,
    ETL_SCHEMA,
)


def get_connection_url() -> URL:
    return URL.create(
        "postgresql+psycopg2",
        username=AZURE_DB_USER,
        password=AZURE_DB_PASSWORD,
        host=AZURE_DB_HOST,
        port=int(AZURE_DB_PORT),
        database=AZURE_DB_NAME,
        query={"sslmode": "require"},
    )


def get_engine() -> Engine:
    return create_engine(
        get_connection_url(),
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        future=True,
    )


def run_sql_file(engine: Engine, sql_path: str | Path) -> None:
    path = Path(sql_path)
    with path.open("r", encoding="utf-8") as file:
        sql = file.read()

    statements = [stmt.strip() for stmt in sql.split(";") if stmt.strip()]

    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))


def ensure_schema(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {ETL_SCHEMA}"))

"""Read-only local metrics or an in-memory public aggregate demo."""
from contextlib import contextmanager
import os
from pathlib import Path
import sqlite3

import pandas as pd

ROOT = Path(__file__).resolve().parent


def uses_demo():
    return os.environ.get("RETAIL_DEMO_MODE") == "1" or not (ROOT / "data/processed/retail.sqlite").exists()


def query_file(selected=False):
    prefix = "demo_" if uses_demo() else ""
    name = "selected_customer_contribution" if selected else "customer_contribution"
    return f"sql/{prefix}{name}.sql"


def source_label():
    return "Kaggle Black Friday Dataset；经 SQL/Pandas 核验的14个客群汇总快照，无用户明细。" if uses_demo() else "Kaggle Black Friday Dataset；本地 purchases 表。"


@contextmanager
def connect():
    if uses_demo():
        connection = sqlite3.connect(":memory:")
        try:
            snapshot = pd.read_csv(ROOT / "reports/sql_customer_contribution.csv")
            if len(snapshot) != 14 or snapshot.duplicated(["age", "gender"]).any():
                raise ValueError("Invalid aggregate snapshot")
            if snapshot["user_count"].sum() != 5891 or snapshot["record_count"].sum() != 550068:
                raise ValueError("Aggregate totals mismatch")
            snapshot.to_sql("customer_segments", connection, index=False)
            connection.row_factory = sqlite3.Row
            yield connection
        finally:
            connection.close()
    else:
        database = ROOT / "data/processed/retail.sqlite"
        connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
        try:
            connection.row_factory = sqlite3.Row
            yield connection
        finally:
            connection.close()

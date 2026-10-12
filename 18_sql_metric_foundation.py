"""Build a local SQLite database and verify the first approved metric query."""
from pathlib import Path
import sqlite3

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent


def main():
    source = ROOT / "data/raw/black-friday-dataset/BlackFriday dataset.csv"
    database = ROOT / "data/processed/retail.sqlite"
    database.parent.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(source)
    required = {"User_ID", "Product_ID", "Age", "Gender", "Purchase"}
    if not required.issubset(df.columns):
        raise ValueError(f"Missing columns: {sorted(required - set(df.columns))}")
    if df[list(required)].isna().any().any():
        raise ValueError("Required metric fields contain missing values")
    # User attributes must be consistent for disjoint age/gender segments.
    if df.groupby("User_ID")[["Age", "Gender"]].nunique().gt(1).any().any():
        raise ValueError("Inconsistent age/gender attributes for a user")
    sql_path = ROOT / "sql/customer_contribution.sql"
    with sqlite3.connect(database) as connection:
        # Rebuild only this generated table; never modify the source CSV.
        df.to_sql("purchases", connection, if_exists="replace", index=False, chunksize=5000)
        connection.execute("CREATE INDEX idx_user ON purchases(User_ID)")
        count = connection.execute("SELECT COUNT(*) FROM purchases").fetchone()[0]
        if count != len(df):
            raise AssertionError("Database row count mismatch")
        actual = pd.read_sql_query(sql_path.read_text(encoding="utf-8"), connection)
    expected = df.groupby(["Age", "Gender"]).agg(
        user_count=("User_ID", "nunique"), record_count=("Purchase", "size"),
        total_purchase=("Purchase", "sum"), average_purchase=("Purchase", "mean"),
    ).reset_index().rename(columns={"Age": "age", "Gender": "gender"})
    expected["share_of_all_purchase"] = expected["total_purchase"] / df["Purchase"].sum()
    keys = ["age", "gender"]
    left = actual.sort_values(keys).reset_index(drop=True)
    right = expected.sort_values(keys).reset_index(drop=True)
    pd.testing.assert_frame_equal(left[keys], right[keys])
    checks = [{"check": "database_row_count", "passed": count == len(df)}]
    for column in ["user_count", "record_count", "total_purchase", "average_purchase", "share_of_all_purchase"]:
        passed = bool(np.allclose(left[column], right[column], rtol=1e-10, atol=1e-10))
        checks.append({"check": f"sql_vs_pandas_{column}", "passed": passed})
        if not passed:
            raise AssertionError(f"Metric mismatch: {column}")
    if not np.isclose(actual["share_of_all_purchase"].sum(), 1):
        raise AssertionError("Segment contribution does not sum to 1")
    checks.append({"check": "contribution_sum_is_one", "passed": True})
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    actual.to_csv(reports / "sql_customer_contribution.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(checks).to_csv(reports / "sql_metric_checks.csv", index=False, encoding="utf-8-sig")
    print("SQLite database:", database)
    print("Rows imported:", count)
    print("\n", actual.round(4).to_string(index=False))
    print("\nPASS: database row count, SQL/Pandas reconciliation and contribution total.")
    print("This is the verified data foundation; AI question routing is not implemented yet.")


if __name__ == "__main__":
    main()

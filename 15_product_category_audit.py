"""审计商品类别的一致性与缺失可恢复性，不修改原始数据。"""
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data/raw/black-friday-dataset/BlackFriday dataset.csv"
REPORT_DIR = ROOT / "reports"


def main():
    df = pd.read_csv(DATA_PATH)
    REPORT_DIR.mkdir(exist_ok=True)
    summary = []
    details = []
    for column in ["Product_Category_1", "Product_Category_2", "Product_Category_3"]:
        grouped = df.groupby("Product_ID")[column]
        # 不把缺失值当作一个已知类别；多个不同已知值代表冲突。
        known_counts = grouped.nunique(dropna=True)
        missing_counts = df[column].isna().groupby(df["Product_ID"]).sum()
        recoverable = df[column].isna() & df["Product_ID"].map(known_counts).eq(1)
        row = {
            "category": column,
            "missing_records": int(df[column].isna().sum()),
            "missing_rate": float(df[column].isna().mean()),
            "conflicting_products": int(known_counts.gt(1).sum()),
            "all_missing_products": int(known_counts.eq(0).sum()),
            "recoverable_missing_records": int(recoverable.sum()),
        }
        summary.append(row)
        details.append(pd.DataFrame({
            "Product_ID": known_counts.index,
            "category": column,
            "known_value_count": known_counts.values,
            "missing_records": missing_counts.reindex(known_counts.index).values,
        }))
    result = pd.DataFrame(summary)
    result.to_csv(REPORT_DIR / "product_category_audit.csv", index=False, encoding="utf-8-sig")
    pd.concat(details, ignore_index=True).to_csv(
        REPORT_DIR / "product_category_audit_details.csv", index=False, encoding="utf-8-sig"
    )
    print(result.to_string(index=False))
    print("\nReports saved to:", REPORT_DIR)
    print("Recoverable means exactly one known category for the same Product_ID.")
    print("Zero recoverable records means this method cannot fill the missing values.")


if __name__ == "__main__":
    main()

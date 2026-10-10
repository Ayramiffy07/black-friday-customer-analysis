from pathlib import Path

import pandas as pd


data_path = Path(
    "data/raw/black-friday-dataset/BlackFriday dataset.csv"
)

df = pd.read_csv(data_path)

category_summary = (
    df.groupby("Product_Category_1")
    .agg(
        record_count=("Purchase", "size"),
        user_count=("User_ID", "nunique"),
        total_purchase=("Purchase", "sum"),
        average_purchase=("Purchase", "mean"),
    )
    .sort_values("total_purchase", ascending=False)
)

category_summary["purchase_share"] = (
    category_summary["total_purchase"] / df["Purchase"].sum()
)

print("商品主类别消费表现（按总消费额降序）：")
print(category_summary.round(3))
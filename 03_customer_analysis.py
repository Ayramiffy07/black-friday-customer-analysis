from pathlib import Path

import pandas as pd


data_path = Path(
    "data/raw/black-friday-dataset/BlackFriday dataset.csv"
)

df = pd.read_csv(data_path)

age_summary = (
    df.groupby("Age")
    .agg(
        user_count=("User_ID", "nunique"),
        record_count=("User_ID", "size"),
        total_purchase=("Purchase", "sum"),
        average_purchase=("Purchase", "mean"),
    )
    .sort_values("total_purchase", ascending=False)
)

age_summary["total_purchase_share"] = (
    age_summary["total_purchase"] / age_summary["total_purchase"].sum()
)

print("各年龄段消费表现：")
print(age_summary.round(3))
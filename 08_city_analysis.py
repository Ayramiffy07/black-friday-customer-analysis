from pathlib import Path

import pandas as pd


data_path = Path(
    "data/raw/black-friday-dataset/BlackFriday dataset.csv"
)

df = pd.read_csv(data_path)

city_summary = (
    df.groupby("City_Category")
    .agg(
        user_count=("User_ID", "nunique"),
        record_count=("Purchase", "size"),
        total_purchase=("Purchase", "sum"),
        average_purchase=("Purchase", "mean"),
    )
)

city_summary["purchase_share"] = (
    city_summary["total_purchase"] / df["Purchase"].sum()
)

print("不同城市类别的消费表现：")
print(city_summary.round(3))
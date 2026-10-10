from pathlib import Path

import pandas as pd


data_path = Path(
    "data/raw/black-friday-dataset/BlackFriday dataset.csv"
)

df = pd.read_csv(data_path)

user_level = (
    df.groupby(["User_ID", "City_Category"])
    .agg(
        total_spend=("Purchase", "sum"),
        record_count=("Purchase", "size"),
    )
    .reset_index()
)

city_user_summary = (
    user_level.groupby("City_Category")
    .agg(
        user_count=("User_ID", "nunique"),
        average_spend_per_user=("total_spend", "mean"),
        median_spend_per_user=("total_spend", "median"),
        average_records_per_user=("record_count", "mean"),
    )
)

print("不同城市类别的用户级消费表现：")
print(city_user_summary.round(2))
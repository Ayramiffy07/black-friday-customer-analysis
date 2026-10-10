from pathlib import Path

import pandas as pd


data_path = Path(
    "data/raw/black-friday-dataset/BlackFriday dataset.csv"
)

df = pd.read_csv(data_path)

# 先按用户汇总，避免把同一用户的多条交易记录误当成不同用户
user_level = (
    df.groupby(["User_ID", "Age", "Gender"])
    .agg(
        total_spend=("Purchase", "sum"),
        record_count=("Purchase", "size"),
    )
    .reset_index()
)

summary = (
    user_level[user_level["Age"] == "26-35"]
    .groupby("Gender")
    .agg(
        user_count=("User_ID", "nunique"),
        average_spend_per_user=("total_spend", "mean"),
        median_spend_per_user=("total_spend", "median"),
        average_records_per_user=("record_count", "mean"),
    )
)

print("26–35岁用户的人均消费表现：")
print(summary.round(2))
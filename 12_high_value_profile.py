from pathlib import Path

import pandas as pd


data_path = Path(
    "data/raw/black-friday-dataset/BlackFriday dataset.csv"
)

df = pd.read_csv(data_path)

customers = (
    df.groupby("User_ID")
    .agg(
        Age=("Age", "first"),
        Gender=("Gender", "first"),
        total_spend=("Purchase", "sum"),
        record_count=("Purchase", "size"),
    )
    .reset_index()
)

top_count = int(len(customers) * 0.20)
top_user_ids = (
    customers.nlargest(top_count, "total_spend")["User_ID"]
)

customers["is_top_20"] = customers["User_ID"].isin(top_user_ids)

profile = (
    customers.groupby(["Age", "Gender"])
    .agg(
        user_count=("User_ID", "size"),
        top_20_users=("is_top_20", "sum"),
        average_spend_per_user=("total_spend", "mean"),
    )
)

profile["top_20_rate"] = (
    profile["top_20_users"] / profile["user_count"]
)

print("各年龄段、性别进入高消费20%客群的情况：")
print(profile.sort_values("top_20_rate", ascending=False).round(3))
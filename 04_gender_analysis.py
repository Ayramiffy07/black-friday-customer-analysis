from pathlib import Path

import pandas as pd


data_path = Path(
    "data/raw/black-friday-dataset/BlackFriday dataset.csv"
)

df = pd.read_csv(data_path)

summary = (
    df.groupby(["Age", "Gender"])
    .agg(
        user_count=("User_ID", "nunique"),
        record_count=("Purchase", "size"),
        total_purchase=("Purchase", "sum"),
        average_purchase=("Purchase", "mean"),
    )
)

summary["share_of_all_purchase"] = (
    summary["total_purchase"] / df["Purchase"].sum()
)

print("各年龄段 × 性别的消费表现：")
print(summary.round(3))

male_26_35 = summary.loc[("26-35", "M")]
age_26_35_total = df.loc[df["Age"] == "26-35", "Purchase"].sum()

print("\n26–35岁男性的总消费额占全体比例：")
print(round(male_26_35["total_purchase"] / df["Purchase"].sum() * 100, 2), "%")

print("26–35岁男性占该年龄段消费额比例：")
print(round(male_26_35["total_purchase"] / age_26_35_total * 100, 2), "%")
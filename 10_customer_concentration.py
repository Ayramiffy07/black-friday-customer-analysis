from pathlib import Path

import pandas as pd


data_path = Path(
    "data/raw/black-friday-dataset/BlackFriday dataset.csv"
)

df = pd.read_csv(data_path)

customer = (
    df.groupby("User_ID")
    .agg(
        total_spend=("Purchase", "sum"),
        record_count=("Purchase", "size"),
    )
    .sort_values("total_spend", ascending=False)
)

top_count = int(len(customer) * 0.20)
top_20 = customer.head(top_count)
other_80 = customer.iloc[top_count:]

top_20_share = top_20["total_spend"].sum() / customer["total_spend"].sum()

print("用户总数：", len(customer))
print("消费金额最高的20%用户数：", len(top_20))
print("最高消费20%用户贡献的消费额占比：", round(top_20_share * 100, 2), "%")
print("最高消费20%用户的人均累计消费：", round(top_20["total_spend"].mean(), 2))
print("其他用户的人均累计消费：", round(other_80["total_spend"].mean(), 2))
print("最高消费20%用户的平均购买记录数：", round(top_20["record_count"].mean(), 2))
print("其他用户的平均购买记录数：", round(other_80["record_count"].mean(), 2))
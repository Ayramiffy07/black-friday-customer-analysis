from pathlib import Path

import pandas as pd


data_path = Path(
    "data/raw/black-friday-dataset/BlackFriday dataset.csv"
)

df = pd.read_csv(data_path)

columns = [
    "Gender",
    "Age",
    "City_Category",
    "Stay_In_Current_City_Years",
    "Product_Category_1",
]

for column in columns:
    print(f"\n{column} 的记录数：")
    print(df[column].value_counts(dropna=False).sort_index())

print("\n用户总数：", df["User_ID"].nunique())
print("商品总数：", df["Product_ID"].nunique())

user_records = df.groupby("User_ID").size()

print("\n每位用户购买记录数的统计：")
print(user_records.describe())
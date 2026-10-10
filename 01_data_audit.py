from pathlib import Path

import pandas as pd


data_path = Path(
    "data/raw/black-friday-dataset/BlackFriday dataset.csv"
)

df = pd.read_csv(data_path)

print("数据规模：", df.shape)

print("\n前5行：")
print(df.head())

print("\n字段类型和非空数量：")
df.info()

print("\n每列缺失值数量：")
print(df.isna().sum())

print("\n完全重复的行数：")
print(df.duplicated().sum())
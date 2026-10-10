from pathlib import Path

import numpy as np
import pandas as pd


data_path = Path(
    "data/raw/black-friday-dataset/BlackFriday dataset.csv"
)

df = pd.read_csv(data_path)

customers = (
    df[df["Age"] == "26-35"]
    .groupby(["User_ID", "Gender"])["Purchase"]
    .sum()
    .reset_index(name="total_spend")
)

male = customers.loc[
    customers["Gender"] == "M", "total_spend"
].to_numpy()

female = customers.loc[
    customers["Gender"] == "F", "total_spend"
].to_numpy()

observed_difference = np.median(male) - np.median(female)

rng = np.random.default_rng(42)
bootstrap_differences = []

for _ in range(2000):
    male_sample = rng.choice(male, size=len(male), replace=True)
    female_sample = rng.choice(female, size=len(female), replace=True)

    difference = np.median(male_sample) - np.median(female_sample)
    bootstrap_differences.append(difference)

lower, upper = np.percentile(bootstrap_differences, [2.5, 97.5])

print("26–35岁男性人均消费中位数：", round(np.median(male), 2))
print("26–35岁女性人均消费中位数：", round(np.median(female), 2))
print("中位数差值（男 - 女）：", round(observed_difference, 2))
print("Bootstrap 95%区间：", (round(lower, 2), round(upper, 2)))
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


data_path = Path(
    "data/raw/black-friday-dataset/BlackFriday dataset.csv"
)
output_path = Path("reports/category_analysis.png")

df = pd.read_csv(data_path)

category_summary = (
    df.groupby("Product_Category_1")
    .agg(
        record_count=("Purchase", "size"),
        total_purchase=("Purchase", "sum"),
        average_purchase=("Purchase", "mean"),
    )
)

category_summary["purchase_share"] = (
    category_summary["total_purchase"] / df["Purchase"].sum()
)

# 图一：总消费额占比最高的10个类别
top_share = category_summary.sort_values(
    "purchase_share", ascending=False
).head(10).sort_values("purchase_share")

# 图二：只比较记录数至少5000的类别，降低小样本均值带来的干扰
enough_records = category_summary[
    category_summary["record_count"] >= 5000
]
top_average = enough_records.sort_values(
    "average_purchase", ascending=False
).head(10).sort_values("average_purchase")

plt.rcParams["font.family"] = ["Microsoft YaHei", "Arial"]
fig, axes = plt.subplots(1, 2, figsize=(14, 6))

axes[0].barh(
    top_share.index.astype(str),
    top_share["purchase_share"] * 100,
    color="#4472C4",
)
axes[0].set_title("Top Categories by Purchase Share")
axes[0].set_xlabel("Share of total purchase (%)")
axes[0].set_ylabel("Product category code")

axes[1].barh(
    top_average.index.astype(str),
    top_average["average_purchase"],
    color="#ED7D31",
)
axes[1].set_title("Average Purchase per Record")
axes[1].set_xlabel("Average purchase")
axes[1].set_ylabel("Product category code")

fig.tight_layout()
output_path.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(output_path, dpi=160, bbox_inches="tight")

print(f"图表已保存到：{output_path.resolve()}")
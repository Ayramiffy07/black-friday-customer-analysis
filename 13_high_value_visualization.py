from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


data_path = Path(
    "data/raw/black-friday-dataset/BlackFriday dataset.csv"
)
output_path = Path("reports/high_value_profile.png")

df = pd.read_csv(data_path)

customers = (
    df.groupby("User_ID")
    .agg(
        Age=("Age", "first"),
        Gender=("Gender", "first"),
        total_spend=("Purchase", "sum"),
    )
    .reset_index()
)

top_count = int(len(customers) * 0.20)
top_user_ids = customers.nlargest(
    top_count, "total_spend"
)["User_ID"]

customers["is_top_20"] = customers["User_ID"].isin(top_user_ids)

profile = (
    customers.groupby(["Age", "Gender"])
    .agg(
        user_count=("User_ID", "size"),
        top_20_users=("is_top_20", "sum"),
    )
    .reset_index()
)

profile["top_20_rate"] = (
    profile["top_20_users"] / profile["user_count"]
)

# 只展示至少200名用户的群体，减少小样本比例波动
profile = profile[profile["user_count"] >= 200].copy()
profile["group"] = (
    profile["Age"] + " " + profile["Gender"]
    + " (n=" + profile["user_count"].astype(str) + ")"
)
profile = profile.sort_values("top_20_rate")

fig, ax = plt.subplots(figsize=(9, 6))
bars = ax.barh(
    profile["group"],
    profile["top_20_rate"] * 100,
    color="#4472C4",
)

ax.axvline(20, color="#ED7D31", linestyle="--", label="Overall top-20% baseline")
ax.set_title("High-Spend Customer Rate by Age and Gender")
ax.set_xlabel("Share of group in overall top 20% (%)")
ax.set_ylabel("Age and gender group")
ax.legend()

for bar, rate in zip(bars, profile["top_20_rate"] * 100):
    ax.text(rate + 0.3, bar.get_y() + bar.get_height() / 2, f"{rate:.1f}%", va="center")

fig.tight_layout()
output_path.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(output_path, dpi=160, bbox_inches="tight")

print(f"图表已保存到：{output_path.resolve()}")
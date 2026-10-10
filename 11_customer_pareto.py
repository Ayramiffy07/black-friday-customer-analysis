from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


data_path = Path(
    "data/raw/black-friday-dataset/BlackFriday dataset.csv"
)
output_path = Path("reports/customer_pareto.png")

df = pd.read_csv(data_path)

customer = (
    df.groupby("User_ID")["Purchase"]
    .sum()
    .sort_values(ascending=False)
    .reset_index(name="total_spend")
)

customer["cumulative_customer_share"] = (
    customer.index + 1
) / len(customer)

customer["cumulative_spend_share"] = (
    customer["total_spend"].cumsum()
    / customer["total_spend"].sum()
)

top_count = int(len(customer) * 0.20)
top_20_spend_share = customer.loc[
    : top_count - 1, "total_spend"
].sum() / customer["total_spend"].sum()

plt.figure(figsize=(8, 6))
plt.plot(
    customer["cumulative_customer_share"] * 100,
    customer["cumulative_spend_share"] * 100,
    color="#4472C4",
    linewidth=2,
    label="Cumulative spend",
)
plt.plot([0, 100], [0, 100], linestyle="--", color="gray", label="Equal-spend line")
plt.axvline(20, linestyle=":", color="#ED7D31")
plt.axhline(
    top_20_spend_share * 100,
    linestyle=":",
    color="#ED7D31",
    label=f"Top 20% contribute {top_20_spend_share:.1%}",
)

plt.title("Customer Spend Concentration")
plt.xlabel("Cumulative share of customers (%)")
plt.ylabel("Cumulative share of spend (%)")
plt.xlim(0, 100)
plt.ylim(0, 100)
plt.legend()
plt.grid(alpha=0.2)
plt.tight_layout()

output_path.parent.mkdir(parents=True, exist_ok=True)
plt.savefig(output_path, dpi=160, bbox_inches="tight")

print(f"帕累托图已保存到：{output_path.resolve()}")
print(f"消费额最高的20%用户贡献：{top_20_spend_share:.2%}")
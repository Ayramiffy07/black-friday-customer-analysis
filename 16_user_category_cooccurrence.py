"""用户级类别关联：跨购买记录的共现，不是同单购物篮。"""
from itertools import permutations
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent


def main():
    df = pd.read_csv(ROOT / "data/raw/black-friday-dataset/BlackFriday dataset.csv")
    presence = pd.crosstab(df["User_ID"], df["Product_Category_1"]).gt(0)
    # 必须转换成整数，避免布尔矩阵乘法丢失共现人数。
    matrix = presence.to_numpy(dtype=np.int64)
    counts = matrix.sum(axis=0)
    joint = matrix.T @ matrix
    n = len(presence)
    rows = []
    for a, b in permutations(range(len(presence.columns)), 2):
        shared = int(joint[a, b])
        support = shared / n
        confidence = shared / counts[a]
        target_rate = counts[b] / n
        rows.append({
            "source_category": int(presence.columns[a]),
            "target_category": int(presence.columns[b]),
            "source_users": int(counts[a]),
            "target_users": int(counts[b]),
            "shared_users": shared,
            "support": support,
            "confidence": confidence,
            "target_user_share": target_rate,
            "lift": confidence / target_rate,
        })
    rules = pd.DataFrame(rows)
    assert rules["confidence"].between(0, 1).all()
    assert rules["support"].between(0, 1).all()
    # 探索性阈值，不代表显著性或业务最优阈值。
    filtered = rules[(rules["shared_users"] >= 100) & (rules["support"] >= 0.02)]
    filtered = filtered.sort_values(["lift", "shared_users"], ascending=False)
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    rules.to_csv(reports / "user_category_rules_all.csv", index=False, encoding="utf-8-sig")
    filtered.to_csv(reports / "user_category_rules_filtered.csv", index=False, encoding="utf-8-sig")
    print("Total users:", n)
    print("Unit: a user's observed purchase history, NOT an order.")
    print("Exploratory filter: shared users >= 100 and support >= 2%")
    print(filtered.head(10).round(4).to_string(index=False))
    print("\nSupport = shared users / all users")
    print("Confidence A->B = shared users / users who bought A")
    print("Lift A->B = confidence / share of all users who bought B")
    print("Association does not establish purchase order or causal effects.")


if __name__ == "__main__":
    main()

"""按购买记录数四分位分层，探索类别共现对记录数的敏感性。"""
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent


def main():
    df = pd.read_csv(ROOT / "data/raw/black-friday-dataset/BlackFriday dataset.csv")
    counts = df.groupby("User_ID").size().rename("record_count")
    presence = pd.crosstab(df["User_ID"], df["Product_Category_1"]).gt(0)
    users = presence.join(counts)
    # 相同记录数留在同一分组；重复分位边界自动合并。
    users["stratum"] = pd.qcut(users["record_count"], q=4, duplicates="drop")
    rows = []
    groups = [("ALL", users)] + [(str(label), group) for label, group in users.groupby("stratum", observed=True)]
    for label, group in groups:
        for a, b in [(17, 18), (9, 15)]:
            n = len(group)
            na = int(group[a].sum())
            nb = int(group[b].sum())
            shared = int((group[a] & group[b]).sum())
            confidence = shared / na if na else np.nan
            base = nb / n
            rows.append({
                "stratum": label,
                "min_records": int(group["record_count"].min()),
                "max_records": int(group["record_count"].max()),
                "users": n,
                "source_category": a,
                "target_category": b,
                "source_users": na,
                "shared_users": shared,
                "confidence": confidence,
                "target_user_share": base,
                "lift": confidence / base if base else np.nan,
            })
    result = pd.DataFrame(rows)
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    result.to_csv(reports / "cooccurrence_sensitivity.csv", index=False, encoding="utf-8-sig")
    print(result.round(4).to_string(index=False))
    print("\nStrata use purchase RECORD counts, not order frequency.")
    print("Small source/shared counts imply unstable estimates.")
    print("This exploratory check does not eliminate confounding or prove causality.")


if __name__ == "__main__":
    main()

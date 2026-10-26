"""Deterministic segment comparisons from verified aggregate query results."""
import pandas as pd


def build_analysis(rows):
    frame = pd.DataFrame(rows).copy()
    if frame.empty or (frame["user_count"] <= 0).any():
        raise ValueError("Segment counts must be positive")
    frame["segment"] = frame["age"] + "岁 · " + frame["gender"].map({"M": "男性", "F": "女性"})
    frame["spend_per_user"] = frame["total_purchase"] / frame["user_count"]
    frame["records_per_user"] = frame["record_count"] / frame["user_count"]
    baseline = frame["total_purchase"].sum() / frame["user_count"].sum()
    frame["spend_vs_baseline"] = frame["spend_per_user"] / baseline
    return frame, baseline


def build_brief(frame, baseline, source):
    contribution = frame.sort_values(["total_purchase", "age", "gender"], ascending=[False, True, True]).iloc[0]
    per_user = frame.sort_values(["spend_per_user", "age", "gender"], ascending=[False, True, True]).iloc[0]
    return (
        "# 客群分析简报\n\n"
        "范围：全部14个年龄×性别客群的观测记录，无日期筛选。\n\n"
        f"来源：{source}\n\n"
        f"- 消费贡献最高：{contribution['segment']}，占全体消费额 {contribution['share_of_all_purchase']:.2%}，用户数 {contribution['user_count']:,}。\n"
        f"- 人均累计消费最高：{per_user['segment']}，人均 {per_user['spend_per_user']:,.2f}，是全体均值的 {per_user['spend_vs_baseline']:.2f} 倍。\n"
        f"- 全体人均累计消费：{baseline:,.2f}（原始数据单位）。\n\n"
        "## 可验证的下一步\n\n"
        "消费贡献与人均消费回答不同问题。可将贡献较高客群作为触达实验候选，结合人数、人均消费和实验成本制定方案；不能仅凭历史贡献认定营销增量或预算最优。\n\n"
        "## 口径与限制\n\n"
        "人均累计消费=客群消费总额/客群去重用户数；人均购买记录数=客群购买记录数/客群用户数。购买记录不等于订单或复购次数。金额不是利润；没有日期，不能判断增长或未来价值。简报由固定规则生成，不是大模型分析。\n"
    )

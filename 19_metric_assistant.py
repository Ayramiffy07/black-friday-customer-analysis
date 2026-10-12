"""受控指标问答原型：规则路由 + 已批准 SQL，尚未接入大模型。"""
import argparse
import csv
import re
from pathlib import Path
import sqlite3


ROOT = Path(__file__).resolve().parent


def answer(question):
    q = question.strip()
    if not q:
        return {"status": "clarify", "answer": "请输入问题，例如：哪些年龄和性别的客群消费贡献最高？"}
    if any(word in q for word in ["昨天", "今天", "本月", "上月", "去年", "趋势", "最近", "今年", "本周"]):
        return {"status": "unsupported", "answer": "数据没有日期字段，不能查询指定时间或趋势。可以查询数据集全部记录的客群消费贡献。"}
    if any(word in q for word in ["复购", "订单", "频次", "购物篮"]):
        return {"status": "unsupported", "answer": "数据缺少订单编号和日期，不能计算订单频次、复购率或真实同单购物篮。购买记录数不等于订单数。"}
    if any(word in q for word in ["利润", "毛利", "收益"]):
        return {"status": "unsupported", "answer": "数据没有成本或利润字段，消费金额不能当作利润。"}
    if any(word in q for word in ["什么意思", "是什么", "定义", "口径"]):
        if "贡献" in q:
            return {"status": "definition", "answer": "消费贡献 = 某年龄与性别客群的 Purchase 总和 / 数据集全体 Purchase 总和。金额为原始数据单位，无日期筛选；不代表利润或未来价值。"}
        return {"status": "clarify", "answer": "当前支持解释消费贡献口径，请问你是否在问消费贡献？"}
    if any(word in q for word in ["城市", "职业", "商品", "类别"]):
        return {"status": "clarify", "answer": "当前尚不支持城市、职业或商品筛选，请查询年龄×性别客群贡献。"}
    normalized = re.sub(r"[–—－~～至到]", "-", q)
    ages = re.findall(r"(?<!\d)(\d+\s*-\s*\d+|55\s*\+)(?!\d)", normalized)
    genders = [code for word, code in [("男性", "M"), ("女性", "F")] if word in q]
    if ages or genders or re.search(r"\d", q):
        allowed_ages = {"0-17", "18-25", "26-35", "36-45", "46-50", "51-55", "55+"}
        age = re.sub(r"\s", "", ages[0]) if len(ages) == 1 else None
        if age not in allowed_ages or len(genders) != 1:
            return {"status": "clarify", "answer": "请指定一个数据集年龄段及男性或女性，例如：26–35岁女性消费贡献是多少？暂不支持自定义年龄段或多个客群比较。"}
        if not any(word in q for word in ["贡献", "消费", "占比", "比例"]):
            return {"status": "clarify", "answer": "当前支持消费贡献查询，请明确你要查询的指标。"}
        within_age = any(word in q for word in ["该年龄段", "同年龄段", "年龄段内", "年龄段消费", "年龄段的消费"])
        if within_age and any(word in q for word in ["全体", "全部", "总体"]):
            return {"status": "clarify", "answer": "请明确分母：全体用户消费额，还是该年龄段用户消费额？"}
        database = ROOT / "data/processed/retail.sqlite"
        if not database.exists():
            return {"status": "error", "answer": "数据库尚未准备，请先运行 18_sql_metric_foundation.py。"}
        params = {"age": age, "gender": genders[0]}
        query = "sql/selected_customer_contribution.sql"
        with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
            connection.row_factory = sqlite3.Row
            row = dict(connection.execute((ROOT / query).read_text(encoding="utf-8"), params).fetchone())
        if not row["record_count"]:
            return {"status": "empty", "answer": "没有找到该客群的记录。"}
        field = "share_of_age_purchase" if within_age else "share_of_all_purchase"
        denominator = "该年龄段用户消费额" if within_age else "全体用户消费额"
        return {
            "status": "answered", "mode": "selected", "parameters": params,
            "share_field": field, "denominator": denominator,
            "answer": f"{age} 岁{'男性' if genders[0] == 'M' else '女性'}：{row['user_count']:,} 名用户，累计消费 {row['total_purchase']:,}（原始数据单位），占{denominator} {row[field]:.2%}。",
            "evidence": [row], "query": query,
            "scope": f"全部观测记录；年龄={age}，性别={genders[0]}；所问占比的分母为{denominator}。无日期筛选。",
            "source": "Kaggle Black Friday Dataset；本地 purchases 表。",
        }
    if any(word in q for word in ["贡献", "消费", "客群"]):
        if not any(word in q for word in ["最高", "排名", "哪些", "不同", "分别", "各", "贡献"]):
            return {"status": "clarify", "answer": "你想查询全体年龄×性别客群的消费贡献排名吗？"}
        database = ROOT / "data/processed/retail.sqlite"
        if not database.exists():
            return {"status": "error", "answer": "数据库尚未准备，请先运行 18_sql_metric_foundation.py。"}
        sql_path = ROOT / "sql/customer_contribution.sql"
        with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
            connection.row_factory = sqlite3.Row
            rows = [dict(row) for row in connection.execute(sql_path.read_text(encoding="utf-8"))]
        top = rows[0]
        gender = {"M": "男性", "F": "女性"}.get(top["gender"], top["gender"])
        return {
            "status": "answered",
            "answer": f"按累计消费贡献排序，{top['age']} 岁{gender}客群排名第一：{top['user_count']:,} 名用户，累计消费 {top['total_purchase']:,}（原始数据单位），占全体消费额 {top['share_of_all_purchase']:.2%}。这不代表利润或未来价值。",
            "evidence": rows,
            "query": "sql/customer_contribution.sql",
            "scope": "全部观测记录，按年龄×性别分组；没有日期筛选。",
            "source": "Kaggle Black Friday Dataset；本地 purchases 表。",
        }
    return {"status": "clarify", "answer": "当前支持客群消费贡献排名与贡献口径解释。请改问：哪些客群消费贡献最高？"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("question", nargs="?")
    args = parser.parse_args()
    print("受控指标助手（规则版，未接入大模型）")
    while True:
        question = args.question if args.question is not None else input("\n请输入问题（输入 exit 退出）：")
        if question.strip().lower() == "exit":
            break
        response = answer(question)
        print(response["answer"])
        if "evidence" in response:
            print("查询：", response["query"])
            print("范围：", response["scope"])
            print("\n客群查询结果：" if response.get("mode") == "selected" else "\n消费贡献前 5 名（按累计消费额排序）：")
            for rank, row in enumerate(response["evidence"][:5], 1):
                gender = {"M": "男性", "F": "女性"}.get(row["gender"], row["gender"])
                share_field = response.get("share_field", "share_of_all_purchase")
                denominator = response.get("denominator", "全体用户消费额")
                print(
                    f"{rank}. {row['age']} 岁{gender} | 用户数 {row['user_count']:,}"
                    f" | 累计消费 {row['total_purchase']:,}"
                    f" | 占{denominator} {row[share_field]:.2%}"
                )
                if "share_of_age_purchase" in row:
                    other_field = "share_of_all_purchase" if share_field == "share_of_age_purchase" else "share_of_age_purchase"
                    other_label = "全体用户消费额" if other_field == "share_of_all_purchase" else "该年龄段用户消费额"
                    print(f"   补充口径：占{other_label} {row[other_field]:.2%}。")
            export = ROOT / "reports/assistant_customer_contribution.csv"
            export.parent.mkdir(exist_ok=True)
            headers = ["年龄段", "性别", "用户数", "购买记录数", "累计消费额", "单条记录平均消费额", "全体消费占比"]
            if response.get("mode") == "selected":
                headers.append("该年龄段消费占比")
            with export.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(headers)
                for row in response["evidence"]:
                    values = [
                        row["age"], {"M": "男性", "F": "女性"}.get(row["gender"], row["gender"]),
                        row["user_count"], row["record_count"], row["total_purchase"],
                        row["average_purchase"], row["share_of_all_purchase"],
                    ]
                    if "share_of_age_purchase" in row:
                        values.append(row["share_of_age_purchase"])
                    writer.writerow(values)
            print("\n完整结果已保存（CSV 占比列为 0–1 小数）：", export)
            print("来源：", response["source"])
            print(f"口径：本次占比 = 客群累计消费 / {response.get('denominator', '全体用户消费额')}；购买记录数不是订单数。")
        if args.question is not None:
            break


if __name__ == "__main__":
    main()

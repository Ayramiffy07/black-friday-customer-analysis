"""固定规则原型的冒烟验收；不是大模型准确率评测。"""
import importlib.util
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("metric_assistant", ROOT / "19_metric_assistant.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

cases = [
    ("哪些年龄和性别的客群消费贡献最高？", "answered"),
    ("不同年龄和性别分别贡献多少消费额？", "answered"),
    ("消费贡献是什么意思？", "definition"),
    ("昨天哪个客群消费最高？", "unsupported"),
    ("本月消费趋势如何？", "unsupported"),
    ("用户复购率是多少？", "unsupported"),
    ("哪个客群利润最高？", "unsupported"),
    ("26–35岁男性消费贡献是多少？", "answered"),
    ("26–35岁女性消费贡献是多少？", "answered"),
    ("26至35岁女性占该年龄段消费额多少？", "answered"),
    ("20-30岁女性消费贡献是多少？", "clarify"),
    ("26-35岁男性和女性消费贡献是多少？", "clarify"),
    ("26-35岁女性占全体和该年龄段消费额多少？", "clarify"),
    ("帮我分析一下", "clarify"),
    ("", "clarify"),
]
rows = []
for question, expected in cases:
    response = module.answer(question)
    passed = response["status"] == expected
    if expected == "answered" and passed:
        top = response["evidence"][0]
        female = "女性" in question
        passed = top["age"] == "26-35" and top["gender"] == ("F" if female else "M") and top["total_purchase"] == (442976233 if female else 1588794345)
        if response.get("mode") == "selected":
            import numpy as np
            passed = passed and np.isclose(top["share_of_age_purchase"], top["total_purchase"] / 2031770578)
            if "该年龄段" in question:
                passed = passed and "该年龄段用户消费额" in response["answer"]
    rows.append({"question": question, "expected": expected, "actual": response["status"], "passed": passed})
result = pd.DataFrame(rows)
result.to_csv(ROOT / "reports/assistant_rule_acceptance.csv", index=False, encoding="utf-8-sig")
print(result.to_string(index=False))
print(f"\nFixed rule smoke cases passed: {int(result.passed.sum())}/{len(result)}")
print("Not an independent benchmark or LLM accuracy score.")
if not result.passed.all():
    raise AssertionError("Acceptance case failed")

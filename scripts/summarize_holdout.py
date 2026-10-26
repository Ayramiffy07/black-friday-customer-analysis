"""Summarize frozen acceptance runs, including failures; no API requests."""
import csv
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evaluation_version import verify_freeze


def main():
    freeze = verify_freeze()
    archive = ROOT / "reports/evaluation_runs"
    selected = {"rule": {}, "model": {}}
    attempts = {"rule": [], "model": []}
    metadata_files = sorted(archive.glob("*_holdout_*_metadata.json"))
    model_names = set()
    for path in metadata_files:
        meta = json.loads(path.read_text(encoding="utf-8"))
        if meta.get("freeze") != freeze:
            raise ValueError(f"Version mismatch: {path.name}")
        mode = meta["mode"]
        if mode == "model":
            model_names.add(meta["model"])
        data_path = archive / f"{meta['utc']}_{mode}.csv"
        with data_path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                row = {**row, "source": str(data_path.relative_to(ROOT))}
                attempts[mode].append(row)
                # Retain first attempt, not best result after retries.
                selected[mode].setdefault(row["id"], row)
    ids = [f"H{i:02}" for i in range(1, 21)]
    if any(set(selected[mode]) != set(ids) for mode in selected):
        raise ValueError("Expected all 20 cases in both modes")
    rows = []
    for key in ids:
        rule, model = selected["rule"][key], selected["model"][key]
        if rule["question"] != model["question"] or rule["expected"] != model["expected"]:
            raise ValueError("Question/label mismatch")
        rows.append({"id": key, "question": model["question"], "expected": model["expected"], "rule_actual": rule["actual"], "rule_correct": rule["correct"], "system_actual": model["actual"], "system_correct": model["correct"], "decision_source": model.get("decision_source"), "elapsed_ms": model["elapsed_ms"], "prompt_tokens": model["prompt_tokens"], "completion_tokens": model["completion_tokens"], "source": model["source"]})
    report_dir = ROOT / "reports"
    with (report_dir / "holdout_v1_comparison.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    yes = lambda value: str(value).lower() == "true"
    rule_score = sum(yes(row["rule_correct"]) for row in rows)
    system_score = sum(yes(row["system_correct"]) for row in rows)
    model_rows = [row for row in rows if row["decision_source"] == "validated_model_plan"]
    guard_rows = [row for row in rows if row["decision_source"] == "program_guard"]
    ms = [float(row["elapsed_ms"]) / 1000 for row in model_rows]
    totals = {field: sum(int(row[field] or 0) for row in attempts["model"]) for field in ["prompt_tokens", "completion_tokens"]}
    errors = sum(row["actual"] in {"model_error", "interrupted"} for row in attempts["model"])
    numeric_rows = [row for row in selected["model"].values() if row["expected"] == "answered"]
    numeric_score = sum(yes(row["numeric_match"]) for row in numeric_rows)
    report = f"""# 冻结验收 v1：规则版与受控模型路径对照

## 范围与结果

20题AI编写、开发阶段未用于调整当前提示词的验收集。用户分四批执行模型路径，版本指纹核验一致。不是外部独立测评，也不是线上流量实验。

| 指标 | 结果 |
| --- | --- |
| 同题规则版符合预期 | {rule_score}/20 |
| 模型＋程序校验路径符合预期 | {system_score}/20 |
| 通过模型参数校验并执行对应处理 | {len(model_rows)}题 |
| 由程序双分母护栏直接澄清 | {len(guard_rows)}题 |
| 应答题目标金额、比例核验 | {numeric_score}/{len(numeric_rows)} |
| 归档中的调用失败或中断 | {errors}条 |
| 模型记录端到端耗时中位数 | {statistics.median(ms):.2f}秒 |
| 模型记录端到端耗时范围 | {min(ms):.2f}–{max(ms):.2f}秒 |
| 全部验收模型路径记录的输入/输出tokens | {totals['prompt_tokens']} / {totals['completion_tokens']} |

模型名：{', '.join(sorted(model_names))}。字段与判断规则见 holdout_v1_comparison.csv，逐题含归档文件路径；冻结清单见 evals/holdout_v1_manifest.json。tokens不包含开发测试、连接排查或未入档请求，不能当作账号总消费。

## 评分方法

状态必须匹配预期；应回答的问题还需目标年龄、性别、占比分母、消费金额和比例与汇总快照一致。拒答、澄清与定义题当前只自动核验状态，未自动证明文本质量或拒答理由正确，后续应人工复核原始返回。使用首条尝试，不挑选重试后的最好分数；失败与中断不能从分母删除。

## 能说明什么

这一小批样本支持继续试用受控模型理解环节，展示了同义表达与边界识别的改善。H11是程序护栏，不应写成模型自行识别。SQL参数白名单约束了执行范围，但结构校验不等于语义永远正确。

## 不能说明什么

不能宣称生产准确率100%、提示词注入普遍安全、客户验收完成或业务收益提升。模型alias未来可能更新，指纹固定的是本地实现与提示词，不保证提供方永久固定底层权重。各类题量少，只有一次输出，未验证重复运行稳定性；无真实用户任务反馈。

## 下一阶段

保留本轮冻结记录，不覆盖原失败开发数据。先做本地规则/模型模式切换与明确来源标识，测试超时/异常提示；真实用户试用后再考虑公开付费入口。公开部署需另补密钥管理、服务端访问控制、额度控制，预算30元当前不是代码实现的硬上限。
"""
    (report_dir / "holdout_v1_report.md").write_text(report, encoding="utf-8")
    print(f"Frozen v1: rule={rule_score}/20; controlled system={system_score}/20")
    print(f"Validated model plans={len(model_rows)}; program guards={len(guard_rows)}; numeric matches={numeric_score}/{len(numeric_rows)}")
    print(f"Tokens={totals}; latency median={statistics.median(ms):.2f}s; errors={errors}")
    print("No API calls. Small AI-authored acceptance set, not production accuracy.")


if __name__ == "__main__":
    main()

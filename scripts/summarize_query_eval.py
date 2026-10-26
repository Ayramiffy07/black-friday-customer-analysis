"""Summarize archived development runs without making network requests."""
import csv
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"


def main():
    # First archived non-interrupted result per ID, not best score across retries.
    selected = {}
    paths = sorted((REPORTS / "evaluation_runs").glob("*_model*.csv"))
    paths.append(REPORTS / "query_dev_model.csv")
    for path in paths:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                if row["actual"] in {"interrupted", "model_error"}:
                    continue
                if row["id"] not in selected:
                    selected[row["id"]] = {**row, "source_file": str(path.relative_to(ROOT))}
    with (REPORTS / "query_dev_rule.csv").open(encoding="utf-8-sig", newline="") as handle:
        rules = {r["id"]: r for r in csv.DictReader(handle)}
    rows = []
    for key in sorted(selected):
        model = selected[key]
        rule = rules.get(key)
        if rule is None:
            raise ValueError("Complete rule baseline required")
        rows.append({"id": key, "question": model["question"], "rule_actual": rule["actual"], "rule_correct": rule["correct"], "model_actual": model["actual"], "model_correct": model["correct"], "model_elapsed_ms": model["elapsed_ms"], "prompt_tokens": model["prompt_tokens"], "completion_tokens": model["completion_tokens"], "model_source": model["source_file"]})
    if not rows:
        raise ValueError("No completed development results")
    with (REPORTS / "query_development_comparison.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    n = len(rows)
    rule_correct = sum(r["rule_correct"].lower() == "true" for r in rows)
    model_correct = sum(r["model_correct"].lower() == "true" for r in rows)
    input_tokens = sum(int(r["prompt_tokens"] or 0) for r in rows)
    output_tokens = sum(int(r["completion_tokens"] or 0) for r in rows)
    latency = [float(r["model_elapsed_ms"]) / 1000 for r in rows]
    text = f"""# 受控模型解析：分批开发评测汇总

## 实测结果

- 覆盖：{n}道开发题，来自分批执行的历史记录，不是同一次完整运行。
- 同题规则版：{rule_correct}/{n}；受控模型路径：{model_correct}/{n}。
- 所选记录模型输入：{input_tokens} tokens；输出：{output_tokens} tokens。
- 所选记录端到端耗时中位数：{statistics.median(latency):.2f}秒；范围：{min(latency):.2f}–{max(latency):.2f}秒。

## 解释与限制

模型改善了女士、男士等改写识别，以及当前不支持指标的意图判别；D05同时请求两个分母时只回答一种，历史失败仍保留。后来添加的程序护栏只做过离线回归，不将其当作真实模型自身改进。

该样本在提示词开发时可见，题量少，不能写成总体准确率、生产准确率或独立测试成绩。不同批次间增加了双分母护栏和直连选项，因此不是单一冻结版本的受控实验。

聚合采用每题首次存档的非中断、非调用错误记录，不挑选最高成绩。所有接口错误和中断仍保存在历史文件中，但本表不评估整体调用成功率。tokens仅对应本表选中的请求，不代表账号全部用量或全部重试费用；实际费用以平台账单为准。

逐题证据：query_development_comparison.csv，包含源文件路径。

## 发布条件

当前仍不公开付费模型入口。下一阶段冻结独立测试问题，补单次运行版本信息、模型名、提示词指纹、完整调用失败统计和无密钥的网页测试。再接入本地模型模式与额度保护，并开展真实用户试用。
"""
    (REPORTS / "query_development_comparison.md").write_text(text, encoding="utf-8")
    print(f"Selected development results: rule={rule_correct}/{n}; model={model_correct}/{n}")
    print(f"Recorded tokens: input={input_tokens}, output={output_tokens}; median={statistics.median(latency):.2f}s")
    print("No API requests made. Not an independent benchmark.")


if __name__ == "__main__":
    main()

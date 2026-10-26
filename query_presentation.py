"""Human-readable, deterministic query evidence for product demonstrations."""
from datetime import datetime, timezone
import json


def condition_rows(response):
    plan = response.get("plan")
    params = response.get("parameters", {})
    selected = response.get("mode") == "selected"
    if plan:
        intent = {"ranking": "全体客群贡献排名", "segment": "指定客群贡献", "definition": "消费贡献口径解释", "clarify": "需要补充条件", "unsupported": "当前不支持的问题"}.get(plan["intent"], plan["intent"])
        age, gender = plan["age"], plan["gender"]
        denominator = plan["denominator"]
    elif response.get("status") == "answered":
        intent = "指定客群贡献" if selected else "全体客群贡献排名"
        age, gender = params.get("age"), params.get("gender")
        denominator = "age" if response.get("share_field") == "share_of_age_purchase" else "all"
    else:
        return []
    rows = [{"条件": "任务", "系统理解": intent}]
    if response.get("status") == "answered":
        rows += [
            {"条件": "年龄段", "系统理解": age or "全部允许年龄段"},
            {"条件": "性别", "系统理解": {"M": "男性", "F": "女性"}.get(gender, "全部性别")},
            {"条件": "占比分母", "系统理解": "该年龄段用户消费额" if denominator == "age" else "全体用户消费额"},
            {"条件": "时间范围", "系统理解": "全部观测记录；原数据无日期"},
        ]
    return rows


def query_receipt(question, response):
    # An explicit allowlist excludes configuration, keys and arbitrary response data.
    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "question": question,
        "status": response["status"],
        "answer": response["answer"],
        "conditions": condition_rows(response),
        "mode": response.get("ui_mode", "rule"),
        "decision_source": response.get("decision_source", "rule"),
        "query_file": response.get("query"),
        "parameters": response.get("parameters"),
        "source": response.get("source"),
        "scope": response.get("scope"),
        "evidence": response.get("evidence", []),
        "plan": response.get("plan"),
        "elapsed_ms": response.get("ui_elapsed_ms"),
        "model_usage": response.get("telemetry", {}).get("usage"),
        "error_code": response.get("error_code"),
        "note": "个人原型的本次查询凭据，不是企业审计日志。模型仅提取参数；金额由SQL计算。",
    }
    return json.dumps(receipt, ensure_ascii=False, indent=2)

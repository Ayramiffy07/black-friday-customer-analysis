"""LLM extracts a validated plan; only existing approved SQL may execute."""
import importlib.util
import json
import os
from pathlib import Path
import socket
import ssl
from http.client import IncompleteRead, RemoteDisconnected
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen, build_opener, ProxyHandler

ROOT = Path(__file__).resolve().parent
AGES = {"0-17", "18-25", "26-35", "36-45", "46-50", "51-55", "55+"}
REASONS = {"time", "orders", "profit", "dimension", "out_of_scope"}
spec = importlib.util.spec_from_file_location("rule_baseline", ROOT / "19_metric_assistant.py")
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)


class PlanError(ValueError):
    pass


class ModelError(RuntimeError):
    pass


def validate_plan(plan):
    if not isinstance(plan, dict) or set(plan) != {"intent", "age", "gender", "denominator", "reason"}:
        raise PlanError("invalid_fields")
    if any(value is not None and not isinstance(value, str) for value in plan.values()):
        raise PlanError("invalid_types")
    intent = plan["intent"]
    if intent not in {"ranking", "segment", "definition", "clarify", "unsupported"}:
        raise PlanError("invalid_intent")
    if plan["denominator"] not in {"all", "age"}:
        raise PlanError("invalid_denominator")
    if intent == "segment":
        if plan["age"] not in AGES or plan["gender"] not in {"M", "F"}:
            raise PlanError("invalid_segment")
    elif plan["age"] is not None or plan["gender"] is not None or plan["denominator"] != "all":
        raise PlanError("unexpected_filter")
    allowed_reason = {"missing_conditions", "ambiguous"} if intent == "clarify" else REASONS if intent == "unsupported" else {None}
    if plan["reason"] not in allowed_reason:
        raise PlanError("invalid_reason")
    return dict(plan)


def execute_plan(plan):
    plan = validate_plan(plan)
    if plan["intent"] == "clarify":
        return {"status": "clarify", "answer": "请补充一个允许的年龄段、男性或女性及占比分母；当前不支持自定义年龄段、多客群比较或依赖上轮条件的追问。"}
    if plan["intent"] == "unsupported":
        reasons = {"time": "缺少日期字段", "orders": "缺少订单编号与日期", "profit": "缺少成本与利润字段", "dimension": "当前查询未支持该筛选维度", "out_of_scope": "超出当前消费贡献查询范围"}
        return {"status": "unsupported", "answer": reasons[plan["reason"]] + "。可以查询全体客群排名或指定年龄与性别的消费贡献。"}
    if plan["intent"] == "definition":
        return baseline.answer("消费贡献是什么意思？")
    if plan["intent"] == "ranking":
        return baseline.answer("哪些客群消费贡献最高？")
    gender = "男性" if plan["gender"] == "M" else "女性"
    denominator = "全体用户" if plan["denominator"] == "all" else "该年龄段"
    return baseline.answer(f"{plan['age']}岁{gender}占{denominator}消费额多少？")


def request_plan(question, api_key, model="deepseek-flash", timeout=20, opener=None):
    if not api_key:
        raise ModelError("missing_api_key")
    if not api_key.isascii() or any(char.isspace() for char in api_key):
        raise ModelError("invalid_key_characters")
    if not isinstance(question, str) or not question.strip() or len(question) > 500:
        raise PlanError("question_length")
    # One supported denominator per query: never silently discard a second one.
    all_scope = any(word in question for word in ["全体", "全部", "总体", "所有用户"])
    age_scope = any(word in question for word in ["该年龄段", "同年龄段", "年龄段内", "同龄人"])
    if all_scope and age_scope:
        return {
            "status": "clarify",
            "answer": "你同时提到了全体与年龄段内两个分母。当前一次支持一种口径，请选择占全体消费额或占该年龄段消费额；如需两个结果，请分两次查询。",
            "decision_source": "program_guard", "model_called": False,
        }
    body = {
        "model": model,
        "messages": [{"role": "system", "content": (ROOT / "prompts/query_plan_v1.txt").read_text(encoding="utf-8")}, {"role": "user", "content": question}],
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},
        "max_tokens": 256,
        "stream": False,
    }
    request = Request("https://api.deepseek.com/chat/completions", data=json.dumps(body).encode("utf-8"), headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
    connection_mode = os.environ.get("RETAIL_CONNECTION_MODE", "system")
    if connection_mode not in {"system", "direct"}:
        raise ModelError("invalid_connection_mode")
    if opener is None:
        # Opt-in per process. TLS certificate verification remains enabled.
        opener = build_opener(ProxyHandler({})).open if connection_mode == "direct" else urlopen
    started = time.perf_counter()
    try:
        with opener(request, timeout=timeout) as response:
            raw = response.read(1000000)
            if not raw.strip():
                raise ModelError("empty_http_body")
            if raw.lstrip().startswith(b"<"):
                raise ModelError("html_instead_of_api_json")
            payload = json.loads(raw)
    except HTTPError as exc:
        raise ModelError(f"http_{exc.code}") from None
    except ssl.SSLError:
        raise ModelError("tls_certificate_or_handshake") from None
    except URLError as exc:
        reason = exc.reason
        code = "tls_certificate_or_handshake" if isinstance(reason, ssl.SSLError) else "network_or_proxy"
        raise ModelError(code) from None
    except (TimeoutError, socket.timeout):
        raise ModelError("request_timeout") from None
    except (IncompleteRead, RemoteDisconnected):
        raise ModelError("connection_interrupted") from None
    except json.JSONDecodeError:
        raise ModelError("http_body_not_json") from None
    except UnicodeError:
        raise ModelError("invalid_response_or_header_encoding") from None
    except ValueError:
        raise ModelError("invalid_http_request_or_response") from None
    except OSError:
        raise ModelError("connection_os_error") from None
    usage = payload.get("usage", {}) if isinstance(payload, dict) else {}
    telemetry = {"model": model, "connection_mode": connection_mode, "latency_ms": round((time.perf_counter() - started) * 1000, 2), "usage": usage}
    # Preserve provider token usage even if returned JSON or plan is invalid.
    try:
        choice = payload["choices"][0]
        if choice["finish_reason"] != "stop":
            raise PlanError("truncated_output")
        plan = validate_plan(json.loads(choice["message"]["content"]))
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        return {"status": "model_error", "answer": "模型参数解析未通过校验，本次未执行查询。可以改用规则模式。", "error_code": str(exc) if isinstance(exc, PlanError) else "invalid_model_json", "telemetry": telemetry}
    result = execute_plan(plan)
    result.update({"plan": plan, "telemetry": telemetry, "decision_source": "validated_model_plan", "model_called": True})
    return result


def answer(question, mode="rule"):
    if mode == "rule":
        return baseline.answer(question)
    if mode != "model":
        raise ValueError("Unknown mode")
    try:
        return request_plan(question, os.environ.get("DEEPSEEK_API_KEY", ""), os.environ.get("RETAIL_MODEL", "deepseek-flash"))
    except (ModelError, PlanError) as exc:
        return {"status": "model_error", "answer": "模型未配置或调用失败，本次没有执行模型查询。请使用规则模式。", "error_code": str(exc)}

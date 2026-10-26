"""Offline contract tests using fake responses, never calls a real API."""
import io
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from controlled_query import PlanError, ModelError, execute_plan, validate_plan, request_plan


good = {"intent": "segment", "age": "26-35", "gender": "F", "denominator": "age", "reason": None}
assert "21.80%" in execute_plan(good)["answer"]
assert "8.69%" in execute_plan({**good, "denominator": "all"})["answer"]
def must_not_call(request, timeout):
    raise AssertionError("Ambiguous denominator should not reach API")

for text in ["26-35岁女性占全体和该年龄段消费额多少？", "女士占所有用户和同龄人消费各多少？"]:
    guarded = request_plan(text, "fake", opener=must_not_call)
    assert guarded["status"] == "clarify" and guarded["model_called"] is False
bad = [dict(good, sql="DROP TABLE purchases"), dict(good, age="20-30"), dict(good, gender="women"), dict(good, denominator="profit"), dict(good, intent="execute_sql"), dict(good, reason=[])]
for plan in bad:
    try:
        validate_plan(plan)
        raise AssertionError("Invalid plan accepted")
    except PlanError:
        pass


def fake_opener(request, timeout):
    body = json.loads(request.data)
    assert body["thinking"]["type"] == "disabled"
    assert body["max_tokens"] == 256
    return io.BytesIO(json.dumps({"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(good)}}], "usage": {"prompt_tokens": 100, "completion_tokens": 30}}).encode())


result = request_plan("26至35岁女士占同龄人的消费多少？", "fake-not-a-real-key", opener=fake_opener)
assert result["plan"] == good and result["telemetry"]["usage"]["prompt_tokens"] == 100
assert "21.80%" in result["answer"]


def malformed(request, timeout):
    return io.BytesIO(json.dumps({"choices": [{"finish_reason": "stop", "message": {"content": "not json"}}], "usage": {"completion_tokens": 10}}).encode())


assert request_plan("test", "fake", opener=malformed)["status"] == "model_error"
for response_bytes, expected_error in [(b"", "empty_http_body"), (b"<html>proxy</html>", "html_instead_of_api_json"), (b"not json", "http_body_not_json")]:
    def broken_transport(request, timeout):
        return io.BytesIO(response_bytes)
    try:
        request_plan("test", "fake", opener=broken_transport)
        raise AssertionError("Bad transport accepted")
    except ModelError as exc:
        assert str(exc) == expected_error
try:
    request_plan("test", "")
    raise AssertionError("Missing key allowed")
except ModelError:
    pass
print("PASS: SQL parameter boundary, denominator, fake transport, bad JSON and missing key. No live model tested.")

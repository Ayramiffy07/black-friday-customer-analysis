"""Verify displayed conditions and receipt allowlist offline."""
from pathlib import Path
import sys
import json

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from query_presentation import condition_rows, query_receipt
from controlled_query import execute_plan

response = execute_plan({"intent": "segment", "age": "36-45", "gender": "M", "denominator": "age", "reason": None})
rows = condition_rows(response)
assert {r["条件"]: r["系统理解"] for r in rows}["占比分母"] == "该年龄段用户消费额"
response["unexpected_secret"] = "must-not-export"
receipt = query_receipt("36-45岁男性占该年龄段消费多少？", response)
parsed = json.loads(receipt)
assert "must-not-export" not in receipt
assert parsed["evidence"][0]["age"] == "36-45"
assert condition_rows({"status": "model_error", "answer": "timeout"}) == []
print("PASS: Chinese conditions, denominator and receipt allowlist; no model calls")

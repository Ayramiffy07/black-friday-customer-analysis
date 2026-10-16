"""Compare the public aggregate path with the local raw-data path."""
import importlib.util
import os
from pathlib import Path
import sys
import math

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("assistant", ROOT / "19_metric_assistant.py")
assistant = importlib.util.module_from_spec(spec)
spec.loader.exec_module(assistant)
questions = ["哪些客群消费贡献最高？", "26–35岁女性消费贡献是多少？", "26–35岁女性占该年龄段消费额多少？", "昨天哪个客群消费最高？", "20–30岁女性消费贡献是多少？"]
previous = os.environ.get("RETAIL_DEMO_MODE")
try:
    os.environ["RETAIL_DEMO_MODE"] = "0"
    local = [assistant.answer(q) for q in questions]
    os.environ["RETAIL_DEMO_MODE"] = "1"
    demo = [assistant.answer(q) for q in questions]
    for a, b in zip(local, demo):
        assert a["status"] == b["status"]
        assert a["answer"] == b["answer"]
        for row_a, row_b in zip(a.get("evidence", []), b.get("evidence", [])):
            for key, value in row_a.items():
                if isinstance(value, (int, float)):
                    assert math.isclose(value, row_b[key], rel_tol=1e-10, abs_tol=1e-10)
                else:
                    assert value == row_b[key]
    print("PASS: public demo matches local answers and numeric evidence for five scenarios")
finally:
    if previous is None:
        os.environ.pop("RETAIL_DEMO_MODE", None)
    else:
        os.environ["RETAIL_DEMO_MODE"] = previous

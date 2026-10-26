"""Local UI checks with fake model responses only, never real API calls."""
import os
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import controlled_query
from streamlit.testing.v1 import AppTest

plan = {"intent": "segment", "age": "18-25", "gender": "F", "denominator": "all", "reason": None}


def fake_answer(question, mode):
    result = controlled_query.execute_plan(plan)
    return {**result, "plan": plan, "model_called": True, "decision_source": "validated_model_plan", "telemetry": {"usage": {"prompt_tokens": 10, "completion_tokens": 5}}}


with patch.dict(os.environ, {"RETAIL_ENABLE_MODEL": "1", "DEEPSEEK_API_KEY": "fake-ui-only", "RETAIL_DEMO_MODE": "1"}):
    with patch.object(controlled_query, "answer", side_effect=fake_answer) as model:
        page = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
        assert not page.exception and model.call_count == 0
        page.radio[0].set_value("模型试用").run()
        assert model.call_count == 0
        page.text_input[0].set_value("18至25岁的姑娘在全部消费里占多少？")
        page.button[0].click().run()
        assert not page.exception and model.call_count == 1
        assert "18-25" in page.info[0].value
        page.run()
        assert model.call_count == 1
        page.session_state["model_attempts"] = 5
        page.button[0].click().run()
        assert model.call_count == 1 and any("5次" in e.value for e in page.error)
        page.session_state["model_attempts"] = 0
        model.side_effect = lambda *a, **k: {"status": "model_error", "answer": "模拟超时", "error_code": "request_timeout"}
        page.button[0].click().run()
        assert not page.exception and any("模拟超时" in e.value for e in page.error)
with patch.dict(os.environ, {"RETAIL_ENABLE_MODEL": "0", "RETAIL_DEMO_MODE": "1"}):
    with patch.object(controlled_query, "answer", side_effect=AssertionError("Public default called model")):
        page = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
        page.button[0].click().run()
        assert not page.exception and len(page.radio) == 0
print("PASS: local mode, no automatic calls, session cap, failure display and public default; only fake model responses used.")

"""Streamlit RAG UI checks with fake generation; never calls a paid API."""
from __future__ import annotations

import os
from pathlib import Path
import sys
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import controlled_rag
from streamlit.testing.v1 import AppTest


FAKE_RESULT = {
    "status": "answered",
    "answer": "购买记录数是数据行数；由于没有订单编号，不能解释为订单数。",
    "citations": [
        {
            "source_id": "S1",
            "citation": "[KB-METRIC-001 · 购买记录数 · v1.0]",
            "doc_id": "KB-METRIC-001",
            "document_title": "客群指标字典",
            "section": "购买记录数",
            "version": "1.0",
            "source": "knowledge/metric_dictionary.md",
            "text": "购买记录数是符合条件的数据行数，不能解释为订单数。",
            "retrieval_score": 1.0,
        }
    ],
    "telemetry": {
        "prompt_version": "rag_answer_v2",
        "latency_ms": 100.0,
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    },
    "decision_source": "validated_rag_answer",
    "model_called": True,
}


with patch.dict(
    os.environ,
    {"RETAIL_ENABLE_MODEL": "1", "DEEPSEEK_API_KEY": "fake-ui-only", "RETAIL_DEMO_MODE": "1"},
):
    with patch.object(controlled_rag, "answer", return_value=FAKE_RESULT) as model:
        page = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
        assert not page.exception and model.call_count == 0
        page.text_input[1].set_value("购买记录数是不是订单数？")
        page.button[2].click().run()
        assert not page.exception and model.call_count == 1
        assert any("不能解释为订单数" in item.value for item in page.success)
        assert any("rag_answer_v2" in item.value for item in page.markdown)
        page.run()
        assert model.call_count == 1

with patch.dict(os.environ, {"RETAIL_ENABLE_MODEL": "0", "RETAIL_DEMO_MODE": "1"}):
    with patch.object(controlled_rag, "answer", side_effect=AssertionError("Public RAG called model")):
        page = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
        page.text_input[1].set_value("购买记录数是不是订单数？")
        page.button[2].click().run()
        assert not page.exception
        assert any("公开模式仅展示免费检索依据" in item.value for item in page.info)

print("PASS: RAG UI generation, citations, rerun safety and public retrieval-only mode; fake model only.")


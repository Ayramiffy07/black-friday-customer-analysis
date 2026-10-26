from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from controlled_rag import RagModelError, request_grounded_answer


class FakeResponse:
    def __init__(self, payload: dict[str, object]):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self, limit: int) -> bytes:
        return json.dumps(self.payload, ensure_ascii=False).encode("utf-8")


def provider_payload(content: dict[str, object]) -> dict[str, object]:
    return {
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"content": json.dumps(content, ensure_ascii=False)},
            }
        ],
        "usage": {"prompt_tokens": 120, "completion_tokens": 30},
    }


def main() -> None:
    calls = 0

    def valid_opener(request, timeout):
        nonlocal calls
        calls += 1
        body = json.loads(request.data.decode("utf-8"))
        if "APPROVED_CONTEXT" not in body["messages"][1]["content"]:
            raise AssertionError("context not sent")
        return FakeResponse(
            provider_payload(
                {
                    "answer": "购买记录数是数据行数；由于没有订单编号，不能解释为订单数。",
                    "cited_source_ids": ["S1"],
                    "grounded": True,
                }
            )
        )

    success = request_grounded_answer("购买记录数是不是订单数？", "sk-test", opener=valid_opener)
    assert success["status"] == "answered"
    assert success["citations"] and success["citations"][0]["doc_id"] == "KB-METRIC-001"
    assert success["telemetry"]["usage"]["prompt_tokens"] == 120
    print("PASS grounded answer with approved citation")

    def invalid_citation_opener(request, timeout):
        return FakeResponse(
            provider_payload(
                {
                    "answer": "错误引用测试。",
                    "cited_source_ids": ["S99"],
                    "grounded": True,
                }
            )
        )

    invalid = request_grounded_answer(
        "购买记录数是不是订单数？", "sk-test", opener=invalid_citation_opener
    )
    assert invalid["status"] == "model_error" and invalid["error_code"] == "unknown_citation"
    assert not invalid["citations"]
    print("PASS unknown citation rejected")

    before = calls
    unrelated = request_grounded_answer("帮我预测明天北京天气和推荐餐厅", "", opener=valid_opener)
    assert unrelated["status"] == "unsupported" and unrelated["model_called"] is False
    assert calls == before
    print("PASS retrieval guard rejects unrelated question without model call")

    try:
        request_grounded_answer("记录数是什么意思？", "")
    except RagModelError as exc:
        assert str(exc) == "missing_api_key"
    else:
        raise AssertionError("missing key was not rejected")
    print("PASS missing key rejected for relevant question")

    print("Controlled RAG checks passed; no paid model calls were made.")


if __name__ == "__main__":
    main()


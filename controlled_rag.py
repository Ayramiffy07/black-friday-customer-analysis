"""Grounded RAG answers over approved project documents only."""
from __future__ import annotations

import json
import os
import socket
import ssl
import time
from http.client import IncompleteRead, RemoteDisconnected
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener, urlopen

from rag_retriever import RetrievalHit, retrieve


ROOT = Path(__file__).resolve().parent
PROMPT_VERSION = "rag_answer_v2"


class RagPlanError(ValueError):
    pass


class RagModelError(RuntimeError):
    pass


def _context_payload(hits: list[RetrievalHit]) -> tuple[str, dict[str, RetrievalHit]]:
    source_map = {f"S{index}": hit for index, hit in enumerate(hits, start=1)}
    blocks = []
    for source_id, hit in source_map.items():
        chunk = hit.chunk
        blocks.append(
            "\n".join(
                [
                    f"source_id: {source_id}",
                    f"citation: {chunk.citation}",
                    f"source: {chunk.source}",
                    f"content: {chunk.text}",
                ]
            )
        )
    return "\n\n".join(blocks), source_map


def validate_model_answer(payload: object, allowed_sources: set[str]) -> dict[str, object]:
    if not isinstance(payload, dict) or set(payload) != {"answer", "cited_source_ids", "grounded"}:
        raise RagPlanError("invalid_fields")
    answer = payload["answer"]
    source_ids = payload["cited_source_ids"]
    grounded = payload["grounded"]
    if not isinstance(answer, str) or not answer.strip() or len(answer) > 800:
        raise RagPlanError("invalid_answer")
    if not isinstance(source_ids, list) or any(not isinstance(item, str) for item in source_ids):
        raise RagPlanError("invalid_citations")
    if not isinstance(grounded, bool):
        raise RagPlanError("invalid_grounded")
    if len(source_ids) != len(set(source_ids)) or any(item not in allowed_sources for item in source_ids):
        raise RagPlanError("unknown_citation")
    if grounded and not source_ids:
        raise RagPlanError("grounded_without_citation")
    if not grounded and source_ids:
        raise RagPlanError("ungrounded_with_citation")
    return {
        "answer": answer.strip(),
        "cited_source_ids": source_ids,
        "grounded": grounded,
    }


def request_grounded_answer(
    question: str,
    api_key: str,
    *,
    model: str = "deepseek-flash",
    timeout: int = 20,
    opener=None,
    top_k: int = 3,
) -> dict[str, object]:
    if not isinstance(question, str) or not question.strip() or len(question) > 500:
        raise RagPlanError("question_length")

    hits = retrieve(question, top_k=top_k)
    if not hits:
        return {
            "status": "unsupported",
            "answer": "现有知识库中没有足够依据回答这个问题。",
            "citations": [],
            "decision_source": "retrieval_guard",
            "model_called": False,
        }
    if not api_key:
        raise RagModelError("missing_api_key")
    if not api_key.isascii() or any(char.isspace() for char in api_key):
        raise RagModelError("invalid_key_characters")

    context, source_map = _context_payload(hits)
    body = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (ROOT / f"prompts/{PROMPT_VERSION}.txt").read_text(encoding="utf-8"),
            },
            {
                "role": "user",
                "content": f"QUESTION:\n{question}\n\nAPPROVED_CONTEXT:\n{context}",
            },
        ],
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},
        "max_tokens": 512,
        "stream": False,
    }
    request = Request(
        "https://api.deepseek.com/chat/completions",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    connection_mode = os.environ.get("RETAIL_CONNECTION_MODE", "system")
    if connection_mode not in {"system", "direct"}:
        raise RagModelError("invalid_connection_mode")
    if opener is None:
        opener = build_opener(ProxyHandler({})).open if connection_mode == "direct" else urlopen

    started = time.perf_counter()
    try:
        with opener(request, timeout=timeout) as response:
            raw = response.read(1_000_000)
            if not raw.strip():
                raise RagModelError("empty_http_body")
            if raw.lstrip().startswith(b"<"):
                raise RagModelError("html_instead_of_api_json")
            provider_payload = json.loads(raw)
    except HTTPError as exc:
        raise RagModelError(f"http_{exc.code}") from None
    except ssl.SSLError:
        raise RagModelError("tls_certificate_or_handshake") from None
    except URLError as exc:
        code = "tls_certificate_or_handshake" if isinstance(exc.reason, ssl.SSLError) else "network_or_proxy"
        raise RagModelError(code) from None
    except (TimeoutError, socket.timeout):
        raise RagModelError("request_timeout") from None
    except (IncompleteRead, RemoteDisconnected):
        raise RagModelError("connection_interrupted") from None
    except json.JSONDecodeError:
        raise RagModelError("http_body_not_json") from None
    except (UnicodeError, ValueError, OSError):
        raise RagModelError("invalid_http_response") from None

    telemetry = {
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "connection_mode": connection_mode,
        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        "usage": provider_payload.get("usage", {}) if isinstance(provider_payload, dict) else {},
    }
    try:
        choice = provider_payload["choices"][0]
        if choice["finish_reason"] != "stop":
            raise RagPlanError("truncated_output")
        answer_payload = validate_model_answer(
            json.loads(choice["message"]["content"]), set(source_map)
        )
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        error_code = str(exc) if isinstance(exc, RagPlanError) else "invalid_model_json"
        return {
            "status": "model_error",
            "answer": "模型回答未通过引用校验，本次不展示生成内容。",
            "error_code": error_code,
            "citations": [],
            "telemetry": telemetry,
            "model_called": True,
        }

    citations = []
    for source_id in answer_payload["cited_source_ids"]:
        hit = source_map[source_id]
        citations.append(
            {
                "source_id": source_id,
                "citation": hit.chunk.citation,
                "doc_id": hit.chunk.doc_id,
                "document_title": hit.chunk.document_title,
                "section": hit.chunk.section,
                "version": hit.chunk.version,
                "source": hit.chunk.source,
                "text": hit.chunk.text,
                "retrieval_score": hit.score,
            }
        )
    return {
        "status": "answered" if answer_payload["grounded"] else "unsupported",
        "answer": answer_payload["answer"],
        "citations": citations,
        "retrieved_sources": [
            {
                "source_id": source_id,
                "citation": hit.chunk.citation,
                "source": hit.chunk.source,
                "retrieval_score": hit.score,
            }
            for source_id, hit in source_map.items()
        ],
        "telemetry": telemetry,
        "decision_source": "validated_rag_answer",
        "model_called": True,
    }


def answer(question: str) -> dict[str, object]:
    try:
        return request_grounded_answer(
            question,
            os.environ.get("DEEPSEEK_API_KEY", ""),
            model=os.environ.get("RETAIL_MODEL", "deepseek-flash"),
        )
    except (RagModelError, RagPlanError) as exc:
        return {
            "status": "model_error",
            "answer": "知识问答模型未配置或调用失败。",
            "error_code": str(exc),
            "citations": [],
            "model_called": False,
        }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ask one grounded question over approved documents.")
    parser.add_argument("question", help="Knowledge question")
    args = parser.parse_args()
    print(json.dumps(answer(args.question), ensure_ascii=False, indent=2))


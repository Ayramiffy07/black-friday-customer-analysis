from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rag_retriever import load_knowledge, retrieval_response, retrieve


CASES = [
    ("购买记录数是不是订单数？", "KB-METRIC-001", "购买记录数"),
    ("为什么不能看本月同比？", "KB-DATA-001", "没有日期字段"),
    ("这个数据可以分析复购率吗？", "KB-DATA-001", "没有订单编号"),
    ("人均累计消费是怎么计算的？", "KB-METRIC-001", "人均累计消费"),
    ("模型会不会直接生成SQL？", "KB-PRODUCT-001", "规则与模型模式"),
    ("模型接口超时后系统怎么处理？", "KB-PRODUCT-001", "模型失败"),
    ("规则版和模型版评测结果如何？", "KB-EVAL-001", "冻结验收结果"),
    ("20/20能叫生产准确率100%吗？", "KB-EVAL-001", "评测集性质"),
]


def main() -> None:
    chunks = load_knowledge()
    if len(chunks) != 30:
        raise SystemExit(f"FAIL expected 30 chunks, got {len(chunks)}")

    failures: list[str] = []
    for question, expected_doc, expected_section in CASES:
        hits = retrieve(question, top_k=3, chunks=chunks)
        top = hits[0] if hits else None
        passed = bool(
            top
            and top.chunk.doc_id == expected_doc
            and top.chunk.section == expected_section
        )
        print(
            f"{'PASS' if passed else 'FAIL'} {question} -> "
            f"{top.chunk.doc_id + '/' + top.chunk.section if top else 'no hit'}"
        )
        if not passed:
            failures.append(question)

    unrelated = retrieval_response("帮我预测明天北京天气和推荐餐厅")
    refusal_ok = unrelated["status"] == "unsupported" and not unrelated["citations"]
    print(f"{'PASS' if refusal_ok else 'FAIL'} unrelated question -> {unrelated['status']}")
    if not refusal_ok:
        failures.append("unrelated refusal")

    if failures:
        raise SystemExit(f"Retriever checks failed: {', '.join(failures)}")
    print(f"RAG retrieval baseline valid: {len(CASES)} relevant cases + 1 refusal.")


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from controlled_rag import answer as model_answer
from rag_retriever import retrieval_response


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate Retail Insight RAG retrieval or grounded answers.")
    parser.add_argument("--mode", choices=("retrieval", "model"), default="retrieval")
    parser.add_argument("--ids", default="", help="Comma-separated case IDs")
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--allow-paid", action="store_true")
    parser.add_argument("--connection", choices=("system", "direct"), default="system")
    return parser.parse_args()


def selected_cases(cases: list[dict[str, object]], ids: str, limit: int) -> list[dict[str, object]]:
    if limit < 1 or limit > 30:
        raise SystemExit("--limit must be between 1 and 30")
    wanted = {item.strip() for item in ids.split(",") if item.strip()}
    chosen = [case for case in cases if not wanted or case["id"] in wanted]
    missing = wanted - {case["id"] for case in chosen}
    if missing:
        raise SystemExit(f"Unknown case IDs: {', '.join(sorted(missing))}")
    return chosen[:limit]


def result_row(case: dict[str, object], result: dict[str, object], mode: str) -> dict[str, object]:
    citations = result.get("citations", [])
    if not isinstance(citations, list):
        citations = []
    actual_status = result.get("status", "error")
    if mode == "retrieval":
        actual_status = "answered" if actual_status == "retrieved" else actual_status

    expected_doc = case.get("expected_doc_id")
    expected_section = case.get("expected_section")
    citation_correct = (
        not expected_doc
        if case["expected_status"] == "unsupported"
        else any(
            citation.get("doc_id") == expected_doc
            and citation.get("section") == expected_section
            for citation in citations
            if isinstance(citation, dict)
        )
    )
    answer_text = str(result.get("answer", ""))
    required_points = [str(item) for item in case.get("required_points", [])]
    point_hits = [point for point in required_points if point.lower() in answer_text.lower()]
    points_complete = len(point_hits) == len(required_points) if mode == "model" else ""
    status_correct = actual_status == case["expected_status"]
    automatic_pass = status_correct and citation_correct
    if mode == "model" and required_points:
        automatic_pass = automatic_pass and bool(points_complete)

    telemetry = result.get("telemetry", {})
    if not isinstance(telemetry, dict):
        telemetry = {}
    usage = telemetry.get("usage", {})
    if not isinstance(usage, dict):
        usage = {}
    return {
        "id": case["id"],
        "question": case["question"],
        "mode": mode,
        "expected_status": case["expected_status"],
        "actual_status": actual_status,
        "expected_doc_id": expected_doc or "",
        "expected_section": expected_section or "",
        "cited_doc_ids": "|".join(
            str(item.get("doc_id", "")) for item in citations if isinstance(item, dict)
        ),
        "cited_sections": "|".join(
            str(item.get("section", "")) for item in citations if isinstance(item, dict)
        ),
        "status_correct": status_correct,
        "citation_correct": citation_correct,
        "required_points": "|".join(required_points),
        "point_hits": "|".join(point_hits),
        "points_complete": points_complete,
        "automatic_pass": automatic_pass,
        "answer": answer_text,
        "error_code": result.get("error_code", ""),
        "model_called": result.get("model_called", False),
        "prompt_version": telemetry.get("prompt_version", ""),
        "latency_ms": telemetry.get("latency_ms", ""),
        "prompt_tokens": usage.get("prompt_tokens", ""),
        "completion_tokens": usage.get("completion_tokens", ""),
        "total_tokens": usage.get("total_tokens", ""),
        "human_review": "pending" if mode == "model" else "not_applicable",
    }


def write_rows(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    if args.mode == "model" and not args.allow_paid:
        raise SystemExit("Model mode may consume paid tokens; add --allow-paid to continue.")
    os.environ["RETAIL_CONNECTION_MODE"] = args.connection

    cases = json.loads((ROOT / "evals" / "rag_dev.json").read_text(encoding="utf-8"))
    chosen = selected_cases(cases, args.ids, args.limit)
    print(f"Cases selected: {', '.join(str(case['id']) for case in chosen)}")
    print(f"Mode: {args.mode}; connection: {args.connection}")

    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    archive_dir = reports / "evaluation_runs"
    archive_dir.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    archive = archive_dir / f"{stamp}_rag_dev_{args.mode}.csv"

    rows: list[dict[str, object]] = []
    for index, case in enumerate(chosen, start=1):
        print(f"[{index}/{len(chosen)}] Starting {case['id']}...")
        if args.mode == "retrieval":
            result = retrieval_response(str(case["question"]), top_k=3)
        else:
            result = model_answer(str(case["question"]))
        row = result_row(case, result, args.mode)
        rows.append(row)
        print(
            f"  {case['id']}: {row['actual_status']}; "
            f"citation={row['citation_correct']}; pass={row['automatic_pass']}"
        )
        # Paid or interrupted runs must survive a later error or a locked latest file.
        write_rows(archive, rows)

    output = reports / f"rag_dev_{args.mode}.csv"
    latest_saved = True
    try:
        write_rows(output, rows)
    except PermissionError:
        latest_saved = False
        print(f"WARNING latest file is locked and was not replaced: {output}")

    passed = sum(bool(row["automatic_pass"]) for row in rows)
    prompt_tokens = sum(int(row["prompt_tokens"] or 0) for row in rows)
    completion_tokens = sum(int(row["completion_tokens"] or 0) for row in rows)
    print(f"Development cases: {passed}/{len(rows)} automatic checks passed.")
    print(f"Recorded tokens: input={prompt_tokens}, output={completion_tokens}.")
    print(f"Archived: {archive}")
    if latest_saved:
        print(f"Saved latest: {output}")
    else:
        print("Close the CSV in Excel before the next run; the unique archive is complete.")
    if args.mode == "model":
        print("Model answers still require human review; this is a development set, not independent evaluation.")


if __name__ == "__main__":
    main()

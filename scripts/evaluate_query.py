"""Development comparison; real model requests require --allow-paid explicitly."""
import argparse
import csv
import json
from pathlib import Path
import sys
import time
from datetime import datetime, timezone
import shutil
import os
import hashlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from controlled_query import answer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["rule", "model"], default="rule")
    parser.add_argument("--suite", choices=["dev", "holdout"], default="dev")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--ids", help="Comma-separated case IDs, for example D06,D07,D08,D09,D10")
    parser.add_argument("--allow-paid", action="store_true")
    parser.add_argument("--connection", choices=["system", "direct"], default="system", help="Direct skips proxy discovery for this process only")
    args = parser.parse_args()
    os.environ["RETAIL_CONNECTION_MODE"] = args.connection
    if not 1 <= args.limit <= 50:
        parser.error("limit must be between 1 and 50")
    if args.mode == "model" and not args.allow_paid:
        parser.error("Real API calls may incur charges; explicitly pass --allow-paid")
    manifest = None
    if args.suite == "holdout":
        from evaluation_version import verify_freeze
        try:
            manifest = verify_freeze()
        except ValueError as exc:
            parser.error(str(exc))
    case_path = ROOT / "evals" / ("query_dev.json" if args.suite == "dev" else "query_holdout_v1.json")
    cases = json.loads(case_path.read_text(encoding="utf-8"))
    if args.ids:
        wanted = [value.strip() for value in args.ids.split(",") if value.strip()]
        known = {case["id"] for case in cases}
        if not wanted or len(wanted) != len(set(wanted)) or not set(wanted).issubset(known):
            parser.error("Case IDs must be unique and present in evals/query_dev.json")
        cases = [case for case in cases if case["id"] in wanted]
    cases = cases[:args.limit]
    print("Cases selected:", ", ".join(case["id"] for case in cases))
    print("Connection mode:", args.connection, flush=True)
    rows = []
    for index, case in enumerate(cases, 1):
        print(f"[{index}/{len(cases)}] Starting {case['id']}...", flush=True)
        start = time.perf_counter()
        interrupted = False
        try:
            result = answer(case["question"], mode=args.mode)
        except KeyboardInterrupt:
            interrupted = True
            result = {"status": "interrupted", "error_code": "user_interrupted_usage_unknown"}
        expected = case["expected"]
        correct = result["status"] == expected["status"]
        numeric_match = None
        if expected["status"] == "answered":
            evidence = result.get("evidence", [{}])[0]
            correct = correct and evidence.get("age") == expected["age"] and evidence.get("gender") == expected["gender"]
            field = result.get("share_field", "share_of_all_purchase")
            correct = correct and field == expected["share_field"]
            # Compare returned values to the verified snapshot, not model text.
            import pandas as pd
            snapshot = pd.read_csv(ROOT / "reports/sql_customer_contribution.csv")
            segment = snapshot[(snapshot.age == expected["age"]) & (snapshot.gender == expected["gender"])].iloc[0]
            numeric_match = evidence.get("total_purchase") == int(segment.total_purchase)
            if expected["share_field"] == "share_of_age_purchase":
                denominator = snapshot.loc[snapshot.age == expected["age"], "total_purchase"].sum()
            else:
                denominator = snapshot.total_purchase.sum()
            import math
            numeric_match = numeric_match and math.isclose(evidence.get(expected["share_field"], -1), segment.total_purchase / denominator, rel_tol=1e-9)
            correct = correct and numeric_match
        usage = result.get("telemetry", {}).get("usage", {})
        rows.append({"id": case["id"], "group": case["group"], "question": case["question"], "mode": args.mode, "expected": expected["status"], "actual": result["status"], "correct": bool(correct), "numeric_match": numeric_match, "elapsed_ms": round((time.perf_counter()-start)*1000, 2), "prompt_tokens": usage.get("prompt_tokens"), "completion_tokens": usage.get("completion_tokens"), "decision_source": result.get("decision_source", "rule" if args.mode == "rule" else "model_call_or_error"), "model_called": result.get("model_called"), "error": result.get("error_code"), "plan": json.dumps(result.get("plan"), ensure_ascii=False)})
        print(f"    {case['id']}: {result['status']}; correct={bool(correct)}", flush=True)
        if interrupted:
            print("Interrupted: saving attempted cases only; remaining cases NOT run.", flush=True)
            break
    output = ROOT / "reports" / f"query_{args.suite}_{args.mode}.csv"
    archive = ROOT / "reports/evaluation_runs"
    archive.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    if output.exists():
        shutil.copy2(output, archive / f"{stamp}_{args.mode}_previous.csv")
    with output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    shutil.copy2(output, archive / f"{stamp}_{args.mode}.csv")
    metadata = {"suite": args.suite, "mode": args.mode, "model": os.environ.get("RETAIL_MODEL", "deepseek-flash") if args.mode == "model" else None, "connection": args.connection, "selected_ids": [c["id"] for c in cases], "attempted_ids": [r["id"] for r in rows], "utc": stamp, "case_sha256": hashlib.sha256(case_path.read_bytes()).hexdigest(), "prompt_sha256": hashlib.sha256((ROOT / "prompts/query_plan_v1.txt").read_bytes()).hexdigest(), "freeze": manifest}
    (archive / f"{stamp}_{args.suite}_{args.mode}_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{args.suite} cases: {sum(r['correct'] for r in rows)}/{len(rows)}; mode={args.mode}")
    print("Saved:", output)
    print("AI-authored acceptance/development set, not external independent evaluation; missing usage is unknown cost.")


if __name__ == "__main__":
    main()

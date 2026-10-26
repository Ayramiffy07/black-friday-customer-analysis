"""Content fingerprints freeze the evaluated implementation, not a Git branch."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FILES = ["prompts/query_plan_v1.txt", "controlled_query.py", "19_metric_assistant.py", "metric_store.py", "scripts/evaluate_query.py", "evals/query_holdout_v1.json", "reports/sql_customer_contribution.csv"]
FILES += [str(p.relative_to(ROOT)).replace("\\", "/") for p in sorted((ROOT / "sql").glob("*.sql"))]
MANIFEST = ROOT / "evals/holdout_v1_manifest.json"


def fingerprints():
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in FILES}


def verify_freeze():
    if not MANIFEST.exists():
        raise ValueError("No freeze manifest: run scripts/freeze_evaluation.py first")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest["sha256"] != fingerprints():
        raise ValueError("Frozen files changed. Do not overwrite v1 freeze or tune against held-out results.")
    return manifest

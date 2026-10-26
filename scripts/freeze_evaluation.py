"""Create a one-time manifest after human review; never overwrite a freeze."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evaluation_version import MANIFEST, fingerprints

if MANIFEST.exists():
    raise SystemExit("Freeze already exists. Will not overwrite it.")
manifest = {"suite": "holdout_v1", "created_utc": datetime.now(timezone.utc).isoformat(), "sha256": fingerprints(), "note": "AI-authored pre-run acceptance set; labels require human review. Not external independent evaluation."}
with MANIFEST.open("x", encoding="utf-8") as handle:
    json.dump(manifest, handle, ensure_ascii=False, indent=2)
print("Frozen:", MANIFEST)
print("Do not tune prompt/code based on v1 results and still report v1 as unseen evaluation.")

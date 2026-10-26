from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_DIR = ROOT / "knowledge"
REQUIRED_META = ("doc_id", "title", "version", "status", "updated")


def parse_document(path: Path) -> tuple[dict[str, str], list[str]]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError("missing front matter")
    parts = text.split("---\n", 2)
    if len(parts) != 3:
        raise ValueError("invalid front matter")

    metadata: dict[str, str] = {}
    for line in parts[1].splitlines():
        if not line.strip():
            continue
        if ":" not in line:
            raise ValueError(f"invalid metadata line: {line}")
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip()

    sections = re.findall(r"^##\s+(.+?)\s*$", parts[2], flags=re.MULTILINE)
    return metadata, sections


def main() -> None:
    paths = sorted(
        path for path in KNOWLEDGE_DIR.glob("*.md") if path.name.lower() != "readme.md"
    )
    if not paths:
        raise SystemExit("No knowledge documents found.")

    seen_ids: set[str] = set()
    total_sections = 0
    for path in paths:
        try:
            metadata, sections = parse_document(path)
            missing = [key for key in REQUIRED_META if not metadata.get(key)]
            if missing:
                raise ValueError(f"missing metadata: {', '.join(missing)}")
            if metadata["status"] != "approved":
                raise ValueError("status must be approved")
            if metadata["doc_id"] in seen_ids:
                raise ValueError(f"duplicate doc_id: {metadata['doc_id']}")
            if not sections:
                raise ValueError("no level-2 sections")
            seen_ids.add(metadata["doc_id"])
            total_sections += len(sections)
            print(f"PASS {metadata['doc_id']}: {len(sections)} sections ({path.name})")
        except ValueError as exc:
            raise SystemExit(f"FAIL {path.name}: {exc}") from exc

    print(f"Knowledge base valid: {len(paths)} documents, {total_sections} sections.")


if __name__ == "__main__":
    main()

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent
KNOWLEDGE_DIR = ROOT / "knowledge"

# Chinese function words add noise in character n-gram matching. The list is
# deliberately small and deterministic so the baseline remains explainable.
STOP_PHRASES = {
    "什么",
    "怎么",
    "如何",
    "是否",
    "可以",
    "能够",
    "这个",
    "那个",
    "项目",
    "数据",
    "目前",
    "一下",
    "为什么",
}

TOKEN_ALIASES = {
    "token": ("用量",),
    "tokens": ("用量",),
    "sql": ("sql",),
}


@dataclass(frozen=True)
class KnowledgeChunk:
    doc_id: str
    document_title: str
    version: str
    section: str
    text: str
    source: str

    @property
    def citation(self) -> str:
        return f"[{self.doc_id} · {self.section} · v{self.version}]"


@dataclass(frozen=True)
class RetrievalHit:
    chunk: KnowledgeChunk
    score: float
    matched_terms: tuple[str, ...]


def _parse_front_matter(block: str) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for line in block.splitlines():
        if not line.strip() or ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip()
    return metadata


def load_knowledge(directory: Path = KNOWLEDGE_DIR) -> list[KnowledgeChunk]:
    chunks: list[KnowledgeChunk] = []
    for path in sorted(directory.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        raw = path.read_text(encoding="utf-8")
        parts = raw.split("---\n", 2)
        if len(parts) != 3:
            continue
        metadata = _parse_front_matter(parts[1])
        if metadata.get("status") != "approved":
            continue

        current_section = ""
        lines: list[str] = []
        for line in parts[2].splitlines():
            if line.startswith("## "):
                if current_section and lines:
                    text = "\n".join(lines).strip()
                    if text:
                        chunks.append(
                            KnowledgeChunk(
                                doc_id=metadata["doc_id"],
                                document_title=metadata["title"],
                                version=metadata["version"],
                                section=current_section,
                                text=text,
                                source=f"knowledge/{path.name}",
                            )
                        )
                current_section = line[3:].strip()
                lines = []
            elif current_section and line.strip():
                lines.append(line.strip())
        if current_section and lines:
            text = "\n".join(lines).strip()
            if text:
                chunks.append(
                    KnowledgeChunk(
                        doc_id=metadata["doc_id"],
                        document_title=metadata["title"],
                        version=metadata["version"],
                        section=current_section,
                        text=text,
                        source=f"knowledge/{path.name}",
                    )
                )
    return chunks


def _tokens(text: str) -> list[str]:
    normalized = re.sub(r"\s+", "", text.lower())
    normalized = re.sub(r"[^\u4e00-\u9fff0-9a-z_]+", "", normalized)
    latin = re.findall(r"[a-z_]+|\d+(?:\.\d+)?", normalized)
    chinese_runs = re.findall(r"[\u4e00-\u9fff]+", normalized)
    chinese: list[str] = []
    for run in chinese_runs:
        chinese.extend(run[index : index + 2] for index in range(max(0, len(run) - 1)))
        chinese.extend(run[index : index + 3] for index in range(max(0, len(run) - 2)))
    tokens = [token for token in latin + chinese if token not in STOP_PHRASES]
    expanded = list(tokens)
    for token in tokens:
        expanded.extend(TOKEN_ALIASES.get(token, ()))
    return expanded


def retrieve(
    question: str,
    *,
    top_k: int = 3,
    min_score: float = 0.11,
    chunks: list[KnowledgeChunk] | None = None,
) -> list[RetrievalHit]:
    if not question.strip() or top_k < 1:
        return []
    corpus = chunks if chunks is not None else load_knowledge()
    if not corpus:
        return []

    query_counts = Counter(_tokens(question))
    if not query_counts:
        return []

    doc_tokens = [Counter(_tokens(f"{chunk.document_title}{chunk.section}{chunk.text}")) for chunk in corpus]
    document_frequency = Counter(
        token for counts in doc_tokens for token in counts.keys()
    )

    results: list[RetrievalHit] = []
    for chunk, counts in zip(corpus, doc_tokens):
        shared = set(query_counts) & set(counts)
        if not shared:
            continue
        weighted_overlap = 0.0
        query_weight = 0.0
        for token, frequency in query_counts.items():
            inverse_frequency = math.log((len(corpus) + 1) / (document_frequency[token] + 1)) + 1
            query_weight += frequency * inverse_frequency
            if token in counts:
                weighted_overlap += min(frequency, counts[token]) * inverse_frequency

        title_tokens = set(_tokens(chunk.section))
        title_bonus = sum(0.15 for token in shared if token in title_tokens)
        score = weighted_overlap / max(query_weight, 1.0) + title_bonus
        results.append(
            RetrievalHit(
                chunk=chunk,
                score=round(score, 4),
                matched_terms=tuple(sorted(shared)),
            )
        )

    results.sort(key=lambda hit: (-hit.score, hit.chunk.doc_id, hit.chunk.section))
    accepted = [hit for hit in results if hit.score >= min_score]
    return accepted[:top_k]


def retrieval_response(question: str, *, top_k: int = 3) -> dict[str, object]:
    hits = retrieve(question, top_k=top_k)
    if not hits:
        return {
            "status": "unsupported",
            "message": "现有知识库中没有足够依据回答这个问题。",
            "citations": [],
        }
    return {
        "status": "retrieved",
        "message": "已找到可用于回答的知识依据。",
        "citations": [
            {
                "citation": hit.chunk.citation,
                "doc_id": hit.chunk.doc_id,
                "document_title": hit.chunk.document_title,
                "section": hit.chunk.section,
                "version": hit.chunk.version,
                "source": hit.chunk.source,
                "score": hit.score,
                "text": hit.chunk.text,
            }
            for hit in hits
        ],
    }


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Search the approved Retail Insight knowledge base.")
    parser.add_argument("question", help="Question to retrieve evidence for")
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()
    print(json.dumps(retrieval_response(args.question, top_k=args.top_k), ensure_ascii=False, indent=2))


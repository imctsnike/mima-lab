from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

import chromadb

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetrievedChunk:
    text: str
    source: str
    relevance: float


class KnowledgeBase:
    def __init__(
        self,
        knowledge_dir: Path,
        chroma_dir: Path,
        top_k: int = 4,
    ) -> None:
        self.knowledge_dir = knowledge_dir
        self.top_k = top_k
        chroma_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(chroma_dir))
        self.collection = self.client.get_or_create_collection(
            name="mima_knowledge",
            metadata={"hnsw:space": "cosine"},
        )
        self._ingest_documents()

    def _ingest_documents(self) -> None:
        files = sorted(self.knowledge_dir.rglob("*.txt"))
        documents: list[str] = []
        ids: list[str] = []
        metadatas: list[dict[str, str]] = []
        for path in files:
            source = path.relative_to(self.knowledge_dir).as_posix()
            for index, text in enumerate(_chunk_text(path.read_text(encoding="utf-8"))):
                digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
                documents.append(text)
                ids.append(f"{source}:{index}:{digest}")
                metadatas.append({"source": source})

        existing = self.collection.get(include=["metadatas"])
        existing_ids = existing.get("ids", [])
        keep = set(ids)
        stale = [identifier for identifier in existing_ids if identifier not in keep]
        if stale:
            self.collection.delete(ids=stale)
        if documents:
            self.collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
        elif not files:
            logger.warning("No .txt knowledge documents found in %s", self.knowledge_dir)
        logger.info("Loaded %d knowledge chunks", len(documents))

    def search(self, query: str) -> list[RetrievedChunk]:
        if not query.strip() or self.collection.count() == 0:
            return []
        results = self.collection.query(
            query_texts=[query],
            n_results=min(self.top_k, self.collection.count()),
            include=["documents", "metadatas", "distances"],
        )
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]
        chunks: list[RetrievedChunk] = []
        for text, metadata, distance in zip(documents, metadatas, distances):
            relevance = max(0.0, min(1.0, 1.0 - float(distance) / 2.0))
            if relevance >= 0.15:
                chunks.append(
                    RetrievedChunk(
                        text=text,
                        source=metadata["source"],
                        relevance=relevance,
                    )
                )
        return chunks

    @staticmethod
    def format_citations(evidence: list[RetrievedChunk]) -> str:
        return ", ".join(dict.fromkeys(chunk.source for chunk in evidence))


def confidence_score(evidence: list[RetrievedChunk]) -> int:
    """Estimate grounding strength, not the language model's calibrated certainty."""
    if not evidence:
        return 20
    best_match = max(chunk.relevance for chunk in evidence)
    source_count = len({chunk.source for chunk in evidence})
    diversity_bonus = min(15, max(0, source_count - 1) * 5)
    return round(min(100, best_match * 85 + diversity_bonus))


def _chunk_text(text: str, max_chars: int = 1000, overlap: int = 150) -> list[str]:
    paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        while len(paragraph) > max_chars:
            segment = paragraph[:max_chars]
            if current:
                chunks.append(current)
                current = ""
            chunks.append(segment)
            paragraph = paragraph[max_chars - overlap :]
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) > max_chars and current:
            chunks.append(current)
            current = paragraph
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks
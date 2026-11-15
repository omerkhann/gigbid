"""Fixed-size chunking (the V0 baseline). Later variants (V5 multi-vector, V6 contextual) chunk
differently; they live in their own variant modules."""

from __future__ import annotations

from dataclasses import dataclass

from rag.ingest.loaders import Document


@dataclass
class Chunk:
    chunk_id: str
    doc: Document
    text: str
    index: int


def fixed_chunks(doc: Document, size: int = 900, overlap: int = 150) -> list[Chunk]:
    """Split on character windows, preferring to break at a paragraph or line end."""
    text = doc.text.strip()
    if len(text) <= size:
        return [Chunk(f"{doc.doc_id}#0", doc, text, 0)]
    out, start, i = [], 0, 0
    while start < len(text):
        end = min(len(text), start + size)
        if end < len(text):
            cut = max(text.rfind("\n\n", start, end), text.rfind("\n", start, end))
            if cut > start + size // 2:
                end = cut
        out.append(Chunk(f"{doc.doc_id}#{i}", doc, text[start:end].strip(), i))
        if end >= len(text):
            break
        start, i = max(end - overlap, start + 1), i + 1
    return [c for c in out if c.text]


def chunk_all(docs: list[Document], size: int = 900, overlap: int = 150) -> list[Chunk]:
    return [c for d in docs for c in fixed_chunks(d, size, overlap)]

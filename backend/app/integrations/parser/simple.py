import re
from collections import Counter
from pathlib import Path

from app.integrations.parser.base import BaseParserProvider

STOP_WORDS = {
    "the", "and", "for", "that", "with", "this", "from", "have", "your",
    "into", "about", "what", "when", "where", "which", "while", "will",
    "course", "class", "file", "material", "page", "chapter", "using",
}


class SimpleParserProvider(BaseParserProvider):
    def parse(self, file_path: str, mime_type: str, file_name: str) -> dict:
        text = self._extract_text(file_path, mime_type, file_name)
        chunks = self._chunk_text(text, file_name)
        keywords = self._keywords(text, file_name)
        content_items = [{
            "type": "text",
            "text": text[:4000],
            "metadata": {"source_name": file_name, "mime_type": mime_type},
        }]
        return {
            "text": text,
            "chunks": chunks,
            "keywords": keywords,
            "content_items": content_items,
            "summary": text[:500],
        }

    def _extract_text(self, file_path: str, mime_type: str, file_name: str) -> str:
        path = Path(file_path)
        suffix = path.suffix.lower()
        raw = path.read_bytes()[:200_000]

        if suffix in {".txt", ".md", ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".csv", ".html", ".css"}:
            return raw.decode("utf-8", errors="ignore").strip() or f"Uploaded file {file_name}"

        decoded = raw.decode("utf-8", errors="ignore")
        printable = "".join(char for char in decoded if char.isprintable() or char in "\n\t ")
        printable = re.sub(r"\s+", " ", printable).strip()
        if len(printable) >= 80:
            return printable

        return (
            f"Uploaded material: {file_name}. "
            f"MIME type: {mime_type}. "
            "This file was indexed with the fallback parser, so retrieval will rely on "
            "the filename, metadata, and any text that could be extracted."
        )

    def _chunk_text(self, text: str, file_name: str) -> list[dict]:
        normalized = re.sub(r"\s+", " ", text).strip()
        if not normalized:
            normalized = f"Uploaded material {file_name}"

        chunks = []
        size = 500
        overlap = 80
        start = 0
        index = 1
        while start < len(normalized):
            chunk_text = normalized[start:start + size]
            chunks.append({
                "chunk_id": f"{Path(file_name).stem}-chunk-{index}",
                "text": chunk_text,
                "page": index,
                "source_name": file_name,
                "source_type": Path(file_name).suffix.lower().lstrip(".") or "file",
            })
            if start + size >= len(normalized):
                break
            start += size - overlap
            index += 1
        return chunks

    def _keywords(self, text: str, file_name: str) -> list[str]:
        latin_tokens = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", f"{file_name} {text}".lower())
        cjk_tokens = re.findall(r"[\u4e00-\u9fff]{2,8}", f"{file_name} {text}")
        counter = Counter(token for token in latin_tokens if token not in STOP_WORDS)
        counter.update(cjk_tokens)
        return [token for token, _ in counter.most_common(12)]

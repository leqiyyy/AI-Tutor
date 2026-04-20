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
        content_items = self._build_content_items(
            text=text,
            file_name=file_name,
            mime_type=mime_type,
        )
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

    def _build_content_items(self, *, text: str, file_name: str, mime_type: str) -> list[dict]:
        source_type = Path(file_name).suffix.lower().lstrip(".") or "file"
        items: list[dict] = [{
            "type": "text",
            "text": text[:4000],
            "metadata": {
                "source_name": file_name,
                "mime_type": mime_type,
                "source_type": source_type,
                "page": 1,
            },
        }]

        table_md = self._extract_table_markdown(text)
        if table_md:
            items.append({
                "type": "table",
                "text": "Detected tabular content from source material.",
                "table_markdown": table_md,
                "metadata": {
                    "source_name": file_name,
                    "mime_type": mime_type,
                    "source_type": source_type,
                    "page": 1,
                },
            })

        formula = self._extract_formula(text)
        if formula:
            items.append({
                "type": "equation",
                "equation": formula,
                "text": f"Detected formula: {formula}",
                "metadata": {
                    "source_name": file_name,
                    "mime_type": mime_type,
                    "source_type": source_type,
                    "page": 1,
                },
            })

        suffix = Path(file_name).suffix.lower()
        if mime_type.startswith("image/") or suffix in {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}:
            ocr_text = self._image_ocr_fallback(text)
            items.append({
                "type": "figure",
                "caption": "Detected image-based material.",
                "ocr_text": ocr_text,
                "metadata": {
                    "source_name": file_name,
                    "mime_type": mime_type,
                    "source_type": source_type or "image",
                    "page": 1,
                    "layout_type": "figure",
                    "image_path": file_name,
                },
            })
        return items

    def _extract_table_markdown(self, text: str) -> str | None:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        pipe_lines = [line for line in lines if line.count("|") >= 2]
        if len(pipe_lines) >= 2:
            return "\n".join(pipe_lines[:6])

        csv_lines = [line for line in lines if "," in line]
        if len(csv_lines) >= 2:
            return "\n".join(csv_lines[:6])
        return None

    def _extract_formula(self, text: str) -> str | None:
        patterns = [
            r"\$([^$\n]{2,120})\$",
            r"\\\(([^)\n]{2,120})\\\)",
            r"\\\[([^\]\n]{2,120})\\\]",
            r"\b[A-Za-z][A-Za-z0-9_]*\s*=\s*[\w\+\-\*/\^\(\)\.\s]{2,80}",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                formula = (match.group(1) if match.lastindex else match.group(0)).strip()
                if formula:
                    return formula
        return None

    def _image_ocr_fallback(self, text: str) -> str:
        candidate = re.sub(r"\s+", " ", text).strip()
        if not candidate:
            return ""
        if candidate.lower().startswith("uploaded material:"):
            return ""
        return candidate[:200]

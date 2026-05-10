"""Run a lightweight raw-text retrieval baseline for thesis experiments.

This baseline deliberately avoids the system's RAG-Anything/MinerU/VLM output.
It extracts text directly from source files where possible, chunks the raw text,
and ranks chunks with a dependency-free lexical BM25 scorer. Images are kept as
file-name-only placeholders, which makes the baseline useful for showing the
gap between ordinary text retrieval and the system's multimodal indexing.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import time
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


WORD_RE = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _tokenize(text: str) -> list[str]:
    return [token.lower() for token in WORD_RE.findall(text or "")]


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _xml_text_from_zip(path: Path, members: list[str]) -> str:
    parts: list[str] = []
    try:
        with zipfile.ZipFile(path) as zf:
            selected = []
            for member in zf.namelist():
                if any(re.fullmatch(pattern, member) for pattern in members):
                    selected.append(member)
            for member in sorted(selected):
                try:
                    root = ET.fromstring(zf.read(member))
                except Exception:
                    continue
                for node in root.iter():
                    if node.tag.endswith("}t") and node.text:
                        parts.append(node.text)
                parts.append("\n")
    except zipfile.BadZipFile:
        return ""
    return _normalize_text(" ".join(parts))


def _extract_docx(path: Path) -> str:
    return _xml_text_from_zip(
        path,
        [
            r"word/document\.xml",
            r"word/header\d+\.xml",
            r"word/footer\d+\.xml",
            r"word/footnotes\.xml",
            r"word/endnotes\.xml",
        ],
    )


def _extract_pptx(path: Path) -> str:
    return _xml_text_from_zip(path, [r"ppt/slides/slide\d+\.xml", r"ppt/notesSlides/notesSlide\d+\.xml"])


def _extract_pdf(path: Path, pdftotext_bin: str, pdf_text_dir: Path | None = None) -> tuple[str, str]:
    if pdf_text_dir:
        sidecar = pdf_text_dir / f"{path.name}.txt"
        if sidecar.exists():
            return sidecar.read_text(encoding="utf-8", errors="ignore"), ""
    if not pdftotext_bin:
        return "", "pdftotext not configured"
    try:
        proc = subprocess.run(
            [pdftotext_bin, "-layout", str(path), "-"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=60,
        )
    except FileNotFoundError:
        return "", f"{pdftotext_bin} not found"
    except subprocess.TimeoutExpired:
        return "", "pdftotext timeout"
    if proc.returncode != 0:
        return "", proc.stderr.strip()[:300]
    return _normalize_text(proc.stdout), ""


def _extract_file(path: Path, pdftotext_bin: str, pdf_text_dir: Path | None = None) -> tuple[str, str]:
    suffix = path.suffix.lower()
    if suffix in {".md", ".txt"}:
        return path.read_text(encoding="utf-8", errors="ignore"), ""
    if suffix == ".docx":
        return _extract_docx(path), ""
    if suffix == ".pptx":
        return _extract_pptx(path), ""
    if suffix == ".pdf":
        return _extract_pdf(path, pdftotext_bin, pdf_text_dir)
    if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        return f"Image file: {path.name}", "image_content_not_extracted"
    return "", f"unsupported file type: {suffix}"


def _chunk_text(text: str, size: int, overlap: int) -> list[str]:
    text = _normalize_text(text)
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        chunk = text[start : start + size].strip()
        if chunk:
            chunks.append(chunk)
        if start + size >= len(text):
            break
        start += max(1, size - overlap)
    return chunks


def _expected_sources(item: dict[str, Any]) -> set[str]:
    names = set()
    for source in item.get("golden_sources") or []:
        name = str(source.get("file") or source.get("file_name") or "").strip().lower()
        if name:
            names.add(name)
    for name in item.get("expected_source_names") or []:
        token = str(name or "").strip().lower()
        if token:
            names.add(token)
    return names


def _build_index(
    data_dir: Path,
    chunk_size: int,
    chunk_overlap: int,
    pdftotext_bin: str,
    pdf_text_dir: Path | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    chunks: list[dict[str, Any]] = []
    files: list[dict[str, Any]] = []
    for file_path in sorted(path for path in data_dir.iterdir() if path.is_file()):
        text, warning = _extract_file(file_path, pdftotext_bin, pdf_text_dir)
        file_chunks = _chunk_text(text, chunk_size, chunk_overlap)
        if not file_chunks and text:
            file_chunks = [text]
        for idx, chunk in enumerate(file_chunks, start=1):
            chunks.append(
                {
                    "chunk_id": f"{file_path.name}#raw-{idx}",
                    "file_name": file_path.name,
                    "text": chunk,
                    "tokens": _tokenize(chunk),
                }
            )
        files.append(
            {
                "file_name": file_path.name,
                "text_length": len(text),
                "chunk_count": len(file_chunks),
                "warning": warning,
            }
        )
    return chunks, files


def _score_bm25(query_tokens: list[str], chunk_tokens: list[str], doc_freq: Counter[str], avg_len: float, total_docs: int) -> float:
    if not query_tokens or not chunk_tokens:
        return 0.0
    tf = Counter(chunk_tokens)
    doc_len = len(chunk_tokens)
    score = 0.0
    k1 = 1.5
    b = 0.75
    for token in Counter(query_tokens):
        freq = tf.get(token, 0)
        if freq <= 0:
            continue
        df = doc_freq.get(token, 0)
        idf = math.log(1 + (total_docs - df + 0.5) / (df + 0.5))
        denom = freq + k1 * (1 - b + b * doc_len / max(avg_len, 1))
        score += idf * (freq * (k1 + 1)) / denom
    return score


def _evaluate_sources(ranked: list[dict[str, Any]], expected: set[str], k: int) -> dict[str, Any]:
    top = ranked[:k]
    if not expected:
        return {"scored": False, "recall": None, "mrr": None, "ndcg": None, "first_rank": None}
    matched: set[str] = set()
    first_rank: int | None = None
    ranked_relevance: list[int] = []
    seen_expected: set[str] = set()
    for rank, source in enumerate(top, start=1):
        file_name = str(source.get("file_name") or "").strip().lower()
        is_match = file_name in expected
        if is_match:
            matched.add(file_name)
            if first_rank is None:
                first_rank = rank
        if is_match and file_name not in seen_expected:
            seen_expected.add(file_name)
            ranked_relevance.append(1)
        else:
            ranked_relevance.append(0)
    dcg = sum(rel / math.log2(idx + 2) for idx, rel in enumerate(ranked_relevance))
    idcg = sum(1 / math.log2(idx + 2) for idx in range(min(len(expected), k)))
    return {
        "scored": True,
        "recall": len(matched) / len(expected),
        "mrr": 1.0 / first_rank if first_rank else 0.0,
        "ndcg": dcg / idcg if idcg else 0.0,
        "first_rank": first_rank,
    }


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [row for row in rows if row["metrics"]["scored"]]

    def avg(key: str) -> float | None:
        values = [row["metrics"][key] for row in scored if row["metrics"][key] is not None]
        return round(sum(values) / len(values), 4) if values else None

    return {
        "query_count": len(rows),
        "scored_queries": len(scored),
        "recall_at_k": avg("recall"),
        "mrr": avg("mrr"),
        "ndcg_at_k": avg("ndcg"),
        "avg_latency_ms": round(sum(float(row["latency_ms"]) for row in rows) / len(rows), 2) if rows else None,
    }


def _slice(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["dataset"].get(key, "unknown"))].append(row)
    return {name: _summarize(group_rows) for name, group_rows in sorted(grouped.items())}


def run(args: argparse.Namespace) -> dict[str, Any]:
    started = time.perf_counter()
    dataset_payload = _read_json(args.dataset)
    questions = dataset_payload.get("questions", dataset_payload) if isinstance(dataset_payload, dict) else dataset_payload
    chunks, files = _build_index(args.data_dir, args.chunk_size, args.chunk_overlap, args.pdftotext_bin, args.pdf_text_dir)

    doc_freq: Counter[str] = Counter()
    for chunk in chunks:
        doc_freq.update(set(chunk["tokens"]))
    avg_len = sum(len(chunk["tokens"]) for chunk in chunks) / len(chunks) if chunks else 0.0

    rows: list[dict[str, Any]] = []
    for idx, item in enumerate(questions, start=1):
        started_query = time.perf_counter()
        query = str(item.get("question") or item.get("text") or "")
        query_tokens = _tokenize(query)
        scored_chunks = []
        for chunk in chunks:
            score = _score_bm25(query_tokens, chunk["tokens"], doc_freq, avg_len, len(chunks))
            if score > 0:
                scored_chunks.append(
                    {
                        "chunk_id": chunk["chunk_id"],
                        "file_name": chunk["file_name"],
                        "score": round(score, 6),
                        "snippet": chunk["text"][:320],
                    }
                )
        scored_chunks.sort(key=lambda row: row["score"], reverse=True)
        # Deduplicate by file for file-level thesis metrics, while keeping the best chunk.
        ranked_files: list[dict[str, Any]] = []
        seen_files: set[str] = set()
        for chunk in scored_chunks:
            if chunk["file_name"] in seen_files:
                continue
            seen_files.add(chunk["file_name"])
            ranked_files.append(chunk)
            if len(ranked_files) >= args.top_k:
                break
        metrics = _evaluate_sources(ranked_files, _expected_sources(item), args.top_k)
        rows.append(
            {
                "seq": idx,
                "question_id": item.get("question_id") or item.get("id"),
                "question": query,
                "dataset": item,
                "latency_ms": round((time.perf_counter() - started_query) * 1000, 2),
                "sources": ranked_files,
                "metrics": metrics,
            }
        )

    report = {
        "mode_hint": "raw_text_bm25",
        "dataset": str(args.dataset),
        "data_dir": str(args.data_dir),
        "chunk_size": args.chunk_size,
        "chunk_overlap": args.chunk_overlap,
        "top_k": args.top_k,
        "build": {
            "file_count": len(files),
            "chunk_count": len(chunks),
            "avg_chunk_tokens": round(avg_len, 2),
            "files": files,
        },
        "query_count": len(rows),
        "elapsed_seconds": round(time.perf_counter() - started, 2),
        "overall": _summarize(rows),
        "slices": {
            "question_type": _slice(rows, "question_type"),
            "expected_modality": _slice(rows, "expected_modality"),
            "difficulty": _slice(rows, "difficulty"),
            "answerable": _slice(rows, "answerable"),
        },
        "query_results": rows,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run raw text BM25 baseline.")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, default=Path("test_data"))
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--chunk-size", type=int, default=900)
    parser.add_argument("--chunk-overlap", type=int, default=120)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--pdftotext-bin", default="pdftotext")
    parser.add_argument(
        "--pdf-text-dir",
        type=Path,
        help="Optional directory containing sidecar files named '<pdf-file-name>.txt'.",
    )
    return parser.parse_args()


def main() -> None:
    report = run(parse_args())
    print(json.dumps(report["overall"], ensure_ascii=False, indent=2))
    warnings = [file for file in report["build"]["files"] if file.get("warning")]
    if warnings:
        print("Extraction warnings:")
        for item in warnings:
            print(f"- {item['file_name']}: {item['warning']}")


if __name__ == "__main__":
    main()

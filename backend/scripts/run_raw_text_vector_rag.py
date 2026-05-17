"""Run a raw-text dense-vector RAG baseline for thesis experiments.

This baseline is intentionally separate from the system knowledge base. It
extracts raw text directly from the original files, chunks it, embeds chunks
with the configured embedding API, retrieves top-k chunks by cosine similarity,
and asks the configured LLM to answer only from those raw-text contexts.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from run_raw_text_baseline import (
    _build_index,
    _evaluate_sources,
    _expected_sources,
    _read_json,
    _slice,
    _summarize,
)


def _load_env_file(path: Path | None) -> None:
    if not path or not path.exists():
        return
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _normalize_base(url: str) -> str:
    return (url or "").rstrip("/")


def _post_json(url: str, payload: dict[str, Any], api_key: str, timeout: int) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _request_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None,
    api_key: str,
    timeout: int,
) -> dict[str, Any]:
    data = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["api-key"] = api_key
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def _with_retry(fn, *, retries: int, label: str) -> Any:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            return fn()
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            last_error = exc
            if attempt == retries:
                break
            time.sleep(min(2 * attempt, 8))
    raise RuntimeError(f"{label} failed after {retries} attempts: {last_error}") from last_error


def _embed_batch(texts: list[str], args: argparse.Namespace) -> list[list[float]]:
    if not texts:
        return []
    base = _normalize_base(args.embedding_api_base)
    url = f"{base}/embeddings"
    payload = {"model": args.embedding_model, "input": texts}

    def call() -> dict[str, Any]:
        return _post_json(url, payload, args.embedding_api_key, args.api_timeout)

    response = _with_retry(call, retries=args.retries, label="embedding")
    data = response.get("data") or []
    data = sorted(data, key=lambda item: item.get("index", 0))
    vectors = [item.get("embedding") for item in data]
    if len(vectors) != len(texts) or any(not isinstance(vec, list) for vec in vectors):
        raise ValueError(f"embedding response length mismatch: expected={len(texts)} got={len(vectors)}")
    return vectors


def _embed_texts(texts: list[str], args: argparse.Namespace) -> list[list[float]]:
    vectors: list[list[float]] = []
    for start in range(0, len(texts), args.embedding_batch_size):
        batch = texts[start : start + args.embedding_batch_size]
        vectors.extend(_embed_batch(batch, args))
        print(f"embedded {min(start + len(batch), len(texts))}/{len(texts)}", flush=True)
    return vectors


def _cosine(a: list[float], b: list[float]) -> float:
    dot = 0.0
    aa = 0.0
    bb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        aa += x * x
        bb += y * y
    if aa <= 0 or bb <= 0:
        return 0.0
    return dot / (math.sqrt(aa) * math.sqrt(bb))


def _qdrant_request(args: argparse.Namespace, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{_normalize_base(args.qdrant_url)}{path}"
    return _request_json(method, url, payload, args.qdrant_api_key, args.api_timeout)


def _qdrant_collection_exists(args: argparse.Namespace) -> bool:
    try:
        _qdrant_request(args, "GET", f"/collections/{args.qdrant_collection}", None)
        return True
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return False
        raise


def _qdrant_prepare_collection(vector_size: int, args: argparse.Namespace) -> None:
    if args.qdrant_recreate and _qdrant_collection_exists(args):
        _qdrant_request(args, "DELETE", f"/collections/{args.qdrant_collection}", None)
    if not _qdrant_collection_exists(args):
        _qdrant_request(
            args,
            "PUT",
            f"/collections/{args.qdrant_collection}",
            {"vectors": {"size": vector_size, "distance": "Cosine"}},
        )


def _qdrant_upsert(chunks: list[dict[str, Any]], args: argparse.Namespace) -> None:
    points: list[dict[str, Any]] = []
    for idx, chunk in enumerate(chunks, start=1):
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{args.qdrant_collection}:{chunk['chunk_id']}"))
        points.append(
            {
                "id": point_id,
                "vector": chunk["embedding"],
                "payload": {
                    "chunk_id": chunk["chunk_id"],
                    "file_name": chunk["file_name"],
                    "text": chunk["text"],
                    "baseline": "raw_text_vector_rag",
                    "dataset": str(args.dataset),
                },
            }
        )
        chunk["point_id"] = point_id
        if len(points) >= args.qdrant_batch_size:
            _qdrant_request(args, "PUT", f"/collections/{args.qdrant_collection}/points?wait=true", {"points": points})
            print(f"qdrant upserted {idx}/{len(chunks)}", flush=True)
            points = []
    if points:
        _qdrant_request(args, "PUT", f"/collections/{args.qdrant_collection}/points?wait=true", {"points": points})
        print(f"qdrant upserted {len(chunks)}/{len(chunks)}", flush=True)


def _qdrant_search(query_vector: list[float], args: argparse.Namespace, limit: int) -> list[dict[str, Any]]:
    try:
        response = _qdrant_request(
            args,
            "POST",
            f"/collections/{args.qdrant_collection}/points/search",
            {"vector": query_vector, "limit": limit, "with_payload": True, "with_vector": False},
        )
    except urllib.error.HTTPError:
        response = _qdrant_request(
            args,
            "POST",
            f"/collections/{args.qdrant_collection}/points/query",
            {"query": query_vector, "limit": limit, "with_payload": True, "with_vector": False},
        )
    result = response.get("result") or []
    if isinstance(result, dict):
        result = result.get("points") or []
    rows: list[dict[str, Any]] = []
    for item in result:
        payload = item.get("payload") or {}
        rows.append(
            {
                "chunk_id": payload.get("chunk_id"),
                "file_name": payload.get("file_name"),
                "score": round(float(item.get("score") or 0.0), 6),
                "snippet": str(payload.get("text") or "")[:500],
                "text": str(payload.get("text") or ""),
                "point_id": item.get("id"),
            }
        )
    return rows


def _make_prompt(question: str, contexts: list[dict[str, Any]]) -> str:
    context_lines: list[str] = []
    for idx, source in enumerate(contexts, start=1):
        text = str(source.get("text") or source.get("snippet") or "")
        context_lines.append(
            f"[{idx}] source={source.get('file_name')} chunk={source.get('chunk_id')}\n{text}"
        )
    joined_context = "\n\n".join(context_lines)
    return (
        "你是课程资料问答助手。请只依据给定的 Context 回答问题；"
        "如果 Context 不足以回答，请明确说明课程资料中信息不足。"
        "回答使用简体中文，先给出结论，再用要点解释。\n\n"
        f"Question:\n{question}\n\n"
        f"Context:\n{joined_context}\n\n"
        "Answer:"
    )


def _generate_answer(question: str, contexts: list[dict[str, Any]], args: argparse.Namespace) -> str:
    base = _normalize_base(args.llm_api_base)
    url = f"{base}/chat/completions"
    payload = {
        "model": args.llm_model,
        "messages": [
            {
                "role": "system",
                "content": "你是严谨的课程资料问答助手，必须基于检索上下文回答。",
            },
            {"role": "user", "content": _make_prompt(question, contexts)},
        ],
        "temperature": 0.1,
        "max_tokens": args.max_answer_tokens,
    }

    def call() -> dict[str, Any]:
        return _post_json(url, payload, args.llm_api_key, args.api_timeout)

    response = _with_retry(call, retries=args.retries, label="chat completion")
    choices = response.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    return str(message.get("content") or "").strip()


def _reference_answer(item: dict[str, Any]) -> str:
    for key in ("standard_answer", "reference_answer", "expected_answer", "answer", "ground_truth"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    points = item.get("must_include") or []
    if points:
        return "；".join(str(point) for point in points)
    sources = item.get("golden_sources") or []
    snippets = [str(source.get("snippet") or "").strip() for source in sources if source.get("snippet")]
    return "；".join(snippets)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(payload, ensure_ascii=False) + "\n")


def run(args: argparse.Namespace) -> dict[str, Any]:
    _load_env_file(args.env_file)
    args.embedding_api_base = args.embedding_api_base or os.getenv("EMBEDDING_API_BASE") or os.getenv("LLM_API_BASE")
    args.embedding_api_key = args.embedding_api_key or os.getenv("EMBEDDING_API_KEY") or os.getenv("LLM_API_KEY")
    args.embedding_model = args.embedding_model or os.getenv("EMBEDDING_MODEL") or "BAAI/bge-m3"
    args.llm_api_base = args.llm_api_base or os.getenv("LLM_API_BASE")
    args.llm_api_key = args.llm_api_key or os.getenv("LLM_API_KEY")
    args.llm_model = args.llm_model or os.getenv("LLM_MODEL") or "Qwen/Qwen3.5-122B-A10B"
    args.qdrant_url = args.qdrant_url or os.getenv("VECTOR_DB_URL") or "http://qdrant:6333"
    args.qdrant_api_key = args.qdrant_api_key or os.getenv("VECTOR_DB_API_KEY") or ""
    if not args.embedding_api_base or not args.embedding_api_key:
        raise SystemExit("Missing embedding API config.")
    if not args.skip_generation and (not args.llm_api_base or not args.llm_api_key):
        raise SystemExit("Missing LLM API config.")

    started = time.perf_counter()
    dataset_payload = _read_json(args.dataset)
    questions = dataset_payload.get("questions", dataset_payload) if isinstance(dataset_payload, dict) else dataset_payload
    chunks, files = _build_index(args.data_dir, args.chunk_size, args.chunk_overlap, args.pdftotext_bin, args.pdf_text_dir)
    print(f"raw files={len(files)} chunks={len(chunks)} questions={len(questions)}", flush=True)

    chunk_texts = [chunk["text"] for chunk in chunks]
    chunk_vectors = _embed_texts(chunk_texts, args)
    for chunk, vector in zip(chunks, chunk_vectors):
        chunk["embedding"] = vector
    vector_size = len(chunk_vectors[0]) if chunk_vectors else 0
    if args.vector_store == "qdrant":
        if not vector_size:
            raise SystemExit("No chunk embeddings created; cannot initialize Qdrant collection.")
        _qdrant_prepare_collection(vector_size, args)
        _qdrant_upsert(chunks, args)

    query_texts = [str(item.get("question") or item.get("text") or "") for item in questions]
    query_vectors = _embed_texts(query_texts, args)

    run_id = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    jsonl_path = args.output_dir / f"benchmark_{run_id}.jsonl"
    report_path = args.output_dir / f"benchmark_{run_id}.json"
    ragas_path = args.output_dir / f"ragas_input_{run_id}.jsonl"

    rows: list[dict[str, Any]] = []
    for idx, (item, query_vector) in enumerate(zip(questions, query_vectors), start=1):
        query_started = time.perf_counter()
        query = str(item.get("question") or item.get("text") or "")
        if args.vector_store == "qdrant":
            scored_chunks = _qdrant_search(query_vector, args, args.candidate_k)
        else:
            scored_chunks = []
            for chunk in chunks:
                score = _cosine(query_vector, chunk["embedding"])
                scored_chunks.append(
                    {
                        "chunk_id": chunk["chunk_id"],
                        "file_name": chunk["file_name"],
                        "score": round(score, 6),
                        "snippet": chunk["text"][:500],
                        "text": chunk["text"],
                    }
                )
            scored_chunks.sort(key=lambda row: row["score"], reverse=True)

        ranked_files: list[dict[str, Any]] = []
        seen_files: set[str] = set()
        for chunk in scored_chunks:
            if args.deduplicate_files and chunk["file_name"] in seen_files:
                continue
            seen_files.add(chunk["file_name"])
            ranked_files.append(chunk)
            if len(ranked_files) >= args.top_k:
                break

        answer = ""
        generation_error = ""
        if not args.skip_generation:
            try:
                answer = _generate_answer(query, ranked_files, args)
            except Exception as exc:  # pragma: no cover - runtime diagnostics
                generation_error = str(exc)

        metrics = _evaluate_sources(ranked_files, _expected_sources(item), args.top_k)
        row = {
            "seq": idx,
            "question_id": item.get("question_id") or item.get("id"),
            "question": query,
            "dataset": item,
            "success": not generation_error,
            "error": generation_error,
            "latency_ms": round((time.perf_counter() - query_started) * 1000, 2),
            "answer": answer,
            "sources": ranked_files,
            "metrics": metrics,
        }
        rows.append(row)
        _append_jsonl(jsonl_path, row)
        _append_jsonl(
            ragas_path,
            {
                "question_id": row["question_id"],
                "question": query,
                "answer": answer,
                "contexts": [source["text"] for source in ranked_files],
                "ground_truth": _reference_answer(item),
                "reference": _reference_answer(item),
                "metadata": {
                    "question_type": item.get("question_type"),
                    "expected_modality": item.get("expected_modality"),
                    "difficulty": item.get("difficulty"),
                    "answerable": item.get("answerable"),
                    "mode": "raw_text_vector_rag",
                },
            },
        )
        print(
            f"[{idx}/{len(questions)}] {row['question_id']} "
            f"success={row['success']} sources={len(ranked_files)} latency_ms={row['latency_ms']}",
            flush=True,
        )

    report = {
        "mode_hint": "raw_text_vector_rag",
        "dataset": str(args.dataset),
        "data_dir": str(args.data_dir),
        "chunk_size": args.chunk_size,
        "chunk_overlap": args.chunk_overlap,
        "top_k": args.top_k,
        "embedding_model": args.embedding_model,
        "llm_model": args.llm_model,
        "vector_store": args.vector_store,
        "qdrant_collection": args.qdrant_collection if args.vector_store == "qdrant" else None,
        "generation_enabled": not args.skip_generation,
        "build": {
            "file_count": len(files),
            "chunk_count": len(chunks),
            "files": files,
        },
        "query_count": len(rows),
        "success_count": sum(1 for row in rows if row.get("success")),
        "elapsed_seconds": round(time.perf_counter() - started, 2),
        "overall": _summarize(rows),
        "slices": {
            "question_type": _slice(rows, "question_type"),
            "expected_modality": _slice(rows, "expected_modality"),
            "difficulty": _slice(rows, "difficulty"),
            "answerable": _slice(rows, "answerable"),
        },
        "query_results": rows,
        "jsonl_path": str(jsonl_path),
        "ragas_input_path": str(ragas_path),
    }
    _write_json(report_path, report)
    latest_path = args.output_dir / "benchmark_raw_text_vector_rag_v2.json"
    _write_json(latest_path, report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run raw text dense-vector RAG baseline.")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, default=Path("test_data"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--chunk-size", type=int, default=900)
    parser.add_argument("--chunk-overlap", type=int, default=120)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--candidate-k", type=int, default=20)
    parser.add_argument("--pdftotext-bin", default="pdftotext")
    parser.add_argument("--pdf-text-dir", type=Path)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--embedding-api-base", default="")
    parser.add_argument("--embedding-api-key", default="")
    parser.add_argument("--embedding-model", default="")
    parser.add_argument("--embedding-batch-size", type=int, default=32)
    parser.add_argument("--llm-api-base", default="")
    parser.add_argument("--llm-api-key", default="")
    parser.add_argument("--llm-model", default="")
    parser.add_argument("--max-answer-tokens", type=int, default=700)
    parser.add_argument("--api-timeout", type=int, default=180)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--skip-generation", action="store_true")
    parser.add_argument("--deduplicate-files", action="store_true", default=True)
    parser.add_argument("--vector-store", choices=["memory", "qdrant"], default="qdrant")
    parser.add_argument("--qdrant-url", default="")
    parser.add_argument("--qdrant-api-key", default="")
    parser.add_argument("--qdrant-collection", default="baseline_raw_text_vector_rag_bge_m3_1024d")
    parser.add_argument("--qdrant-recreate", action="store_true", default=True)
    parser.add_argument("--qdrant-batch-size", type=int, default=64)
    return parser.parse_args()


def main() -> None:
    report = run(parse_args())
    print(json.dumps(report["overall"], ensure_ascii=False, indent=2))
    print(f"Report: {report['mode_hint']} -> {report['query_count']} queries")


if __name__ == "__main__":
    main()

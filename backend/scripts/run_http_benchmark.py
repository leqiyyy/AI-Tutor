"""Run a thesis RAG benchmark against the live backend HTTP API.

This runner avoids FastAPI TestClient so LightRAG/RAG-Anything keeps the same
runtime event loop as the deployed API service.
"""

from __future__ import annotations

import argparse
import json
import math
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _append_jsonl(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _post_json(base_url: str, path: str, payload: dict[str, Any], token: str | None = None, timeout: int = 900) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(base_url.rstrip("/") + path, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get_json(base_url: str, path: str, token: str, params: dict[str, Any] | None = None, timeout: int = 120) -> dict[str, Any]:
    url = base_url.rstrip("/") + path
    if params:
        query = urllib.parse.urlencode(params)
        url = f"{url}?{query}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"}, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _login(base_url: str, account: str, password: str, role: str) -> str:
    print(f"Logging in as {account} ({role})...", flush=True)
    payload = _post_json(base_url, "/auth/login", {"account": account, "password": password, "role": role}, timeout=60)
    print(f"Login success: {account}", flush=True)
    return str(payload["data"]["access_token"])


def _normalize(value: Any) -> str:
    return str(value or "").strip().lower()


def _source_tokens(source: dict[str, Any]) -> set[str]:
    tokens: set[str] = set()
    for key in ("name", "file_name", "title", "source_name", "chunk_id", "doc_id", "source_id"):
        token = _normalize(source.get(key))
        if token:
            tokens.add(token)
    return tokens


def _expected_tokens(item: dict[str, Any]) -> set[str]:
    tokens: set[str] = set()
    for key in ("expected_source_names", "expected_chunk_ids", "expected_doc_ids"):
        for value in item.get(key) or []:
            token = _normalize(value)
            if token:
                tokens.add(token)
    return tokens


def _evaluate(rows: list[dict[str, Any]], k: int) -> dict[str, Any]:
    details: list[dict[str, Any]] = []
    recalls: list[float] = []
    ndcgs: list[float] = []
    mrrs: list[float] = []
    citation_valid_flags: list[int] = []
    for row in rows:
        expected = _expected_tokens(row.get("query_item") or {})
        if not expected:
            continue
        sources = (row.get("sources") or [])[:k]
        first_rank: int | None = None
        matched: set[str] = set()
        rels: list[int] = []
        ranked_expected_tokens: list[str] = []
        for idx, source in enumerate(sources, start=1):
            tokens = _source_tokens(source or {})
            source_matches = sorted(tokens.intersection(expected))
            ok = bool(source_matches)
            rels.append(1 if ok else 0)
            ranked_expected_tokens.append(source_matches[0] if source_matches else "")
            if ok:
                matched.update(source_matches)
                if first_rank is None:
                    first_rank = idx
        recall = len(matched) / len(expected) if expected else 0.0
        mrr = 1.0 / first_rank if first_rank else 0.0
        seen_relevant: set[str] = set()
        dedup_rels: list[int] = []
        for token in ranked_expected_tokens:
            if token and token not in seen_relevant:
                seen_relevant.add(token)
                dedup_rels.append(1)
            else:
                dedup_rels.append(0)
        dcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(dedup_rels))
        idcg = sum(1 / math.log2(i + 2) for i in range(min(len(expected), k)))
        ndcg = dcg / idcg if idcg else 0.0
        recalls.append(recall)
        mrrs.append(mrr)
        ndcgs.append(ndcg)
        citation_valid_flags.append(1 if sources else 0)
        details.append(
            {
                "question_id": row.get("question_id"),
                "success": row.get("success"),
                "status_code": row.get("status_code"),
                "source_count": len(row.get("sources") or []),
                "first_relevant_rank": first_rank,
                "recall_at_k": round(recall, 4),
                "mrr": round(mrr, 4),
                "ndcg_at_k": round(ndcg, 4),
            }
        )
    return {
        "status": "scored" if details else "not_scored_no_ground_truth",
        "k": k,
        "total_queries": len(rows),
        "scored_queries": len(details),
        "recall_at_k": round(sum(recalls) / len(recalls), 4) if recalls else None,
        "mrr": round(sum(mrrs) / len(mrrs), 4) if mrrs else None,
        "ndcg_at_k": round(sum(ndcgs) / len(ndcgs), 4) if ndcgs else None,
        "citation_valid_rate": round(sum(citation_valid_flags) / len(citation_valid_flags), 4) if citation_valid_flags else None,
        "details": details,
    }


def _load_questions(spec_path: Path) -> list[dict[str, Any]]:
    payload = _read_json(spec_path)
    return [item for item in payload.get("questions", []) if str(item.get("text") or "").strip()]


def run(args: argparse.Namespace) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc)
    run_id = started_at.strftime("%Y%m%dT%H%M%S%fZ")
    output_dir = args.output_dir.resolve()
    jsonl_path = output_dir / f"benchmark_{run_id}.jsonl"
    report_path = output_dir / f"benchmark_{run_id}.json"
    md_path = output_dir / f"benchmark_{run_id}.md"
    questions = _load_questions(args.benchmark_spec)
    print(
        f"Starting live benchmark: questions={len(questions)} class_id={args.class_id} "
        f"base_url={args.base_url} mode={args.mode_hint}",
        flush=True,
    )

    query_token = _login(args.base_url, args.query_account, args.query_password, args.query_role)
    admin_token = _login(args.base_url, args.admin_account, args.admin_password, "admin")

    rows: list[dict[str, Any]] = []
    for idx, item in enumerate(questions, start=1):
        question = str(item.get("text") or "")
        print(f"[{idx}/{len(questions)}] start {item.get('id')}: {question[:80]}", flush=True)
        request_started = time.perf_counter()
        status_code = 0
        response_payload: dict[str, Any] = {}
        error = ""
        try:
            response_payload = _post_json(
                args.base_url,
                "/chat/query",
                {"class_id": args.class_id, "message": question, "attachments": [], "answer_mode": args.answer_mode},
                token=query_token,
                timeout=args.timeout,
            )
            status_code = 200
        except urllib.error.HTTPError as exc:
            status_code = exc.code
            error = exc.read().decode("utf-8", errors="replace")
        except Exception as exc:  # pragma: no cover - runtime diagnostics
            error = str(exc)
        elapsed_ms = round((time.perf_counter() - request_started) * 1000, 2)
        data = response_payload.get("data") or {}
        response_code = response_payload.get("code")
        is_success = status_code == 200 and (response_code in (None, 200, "200"))
        row = {
            "seq": idx,
            "question_id": item.get("id"),
            "question": question,
            "query_item": item,
            "status_code": status_code,
            "success": is_success,
            "error": error,
            "latency_ms": elapsed_ms,
            "answer": data.get("content") or data.get("answer") or data.get("message") or "",
            "confidence": data.get("confidence"),
            "needs_review": data.get("needs_review"),
            "sources": data.get("sources") or data.get("citations") or [],
            "route_meta": data.get("route_meta") or {},
        }
        rows.append(row)
        _append_jsonl(jsonl_path, row)
        print(
            f"[{idx}/{len(questions)}] {row['question_id']} "
            f"success={row['success']} sources={len(row['sources'])} latency_ms={elapsed_ms}",
            flush=True,
        )
        if args.sleep_seconds > 0 and idx < len(questions):
            time.sleep(args.sleep_seconds)

    eval_result = _evaluate(rows, args.retrieval_k)
    perf = _get_json(args.base_url, "/admin/rag-performance", admin_token, {"days": args.days, "class_id": args.class_id})
    ablation = _get_json(args.base_url, "/admin/rag-ablation", admin_token, {"days": args.days, "class_id": args.class_id})
    experiment = _get_json(args.base_url, "/admin/experiment-results", admin_token, {"days": args.days, "class_id": args.class_id})
    report = {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "started_at": started_at.isoformat(),
        "class_id": args.class_id,
        "mode_hint": args.mode_hint,
        "query_count": len(rows),
        "success_count": sum(1 for row in rows if row.get("success")),
        "query_results": rows,
        "retrieval_eval": eval_result,
        "rag_performance": perf.get("data") or {},
        "rag_ablation": ablation.get("data") or {},
        "experiment_results": experiment.get("data") or {},
        "jsonl_path": str(jsonl_path),
        "report_json_path": str(report_path),
        "report_md_path": str(md_path),
    }
    _write_json(report_path, report)
    md_lines = [
        "# Live HTTP Benchmark Report",
        "",
        f"- Run ID: `{run_id}`",
        f"- Class ID: `{args.class_id}`",
        f"- Mode Hint: `{args.mode_hint}`",
        f"- Query Count: `{len(rows)}`",
        f"- Success Count: `{report['success_count']}`",
        f"- Recall@{args.retrieval_k}: `{eval_result.get('recall_at_k')}`",
        f"- nDCG@{args.retrieval_k}: `{eval_result.get('ndcg_at_k')}`",
        f"- MRR: `{eval_result.get('mrr')}`",
        f"- Citation Valid Rate: `{eval_result.get('citation_valid_rate')}`",
        f"- JSONL Progress: `{jsonl_path}`",
        f"- JSON Report: `{report_path}`",
        "",
    ]
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run live HTTP RAG benchmark.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/api/v1")
    parser.add_argument("--class-id", required=True)
    parser.add_argument("--benchmark-spec", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("backend/runtime_tmp/experiment_reports/http_mix"))
    parser.add_argument("--retrieval-k", type=int, default=5)
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--query-account", default="teacher@aitutor.local")
    parser.add_argument("--query-password", default="Teacher123!")
    parser.add_argument("--query-role", default="teacher")
    parser.add_argument("--admin-account", default="admin@aitutor.local")
    parser.add_argument("--admin-password", default="Admin123!")
    parser.add_argument("--answer-mode", default="strict_course")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--sleep-seconds", type=float, default=1.0)
    parser.add_argument("--mode-hint", default="mix")
    return parser.parse_args()


def main() -> None:
    report = run(parse_args())
    print("Benchmark completed.")
    print(f"JSON report: {report['report_json_path']}")
    print(f"Markdown report: {report['report_md_path']}")


if __name__ == "__main__":
    main()

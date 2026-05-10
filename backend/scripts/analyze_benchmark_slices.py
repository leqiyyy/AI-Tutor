"""Analyze RAG benchmark reports by dataset slices.

The live benchmark report gives overall Recall/MRR/nDCG. This helper joins the
report with the richer thesis dataset and recomputes metrics by question type,
expected modality, difficulty, and answerability. It is intentionally
dependency-free so it can run locally or inside the backend container.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize(value: Any) -> str:
    return str(value or "").strip().lower()


def _expected_sources(item: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for source in item.get("golden_sources") or []:
        name = _normalize(source.get("file") or source.get("file_name"))
        if name:
            names.add(name)
    for name in item.get("expected_source_names") or []:
        token = _normalize(name)
        if token:
            names.add(token)
    return names


def _source_tokens(source: dict[str, Any]) -> set[str]:
    tokens: set[str] = set()
    for key in ("name", "file_name", "title", "source_name", "chunk_id", "doc_id", "source_id"):
        token = _normalize(source.get(key))
        if token:
            tokens.add(token)
    return tokens


def _row_metrics(row: dict[str, Any], dataset_item: dict[str, Any], k: int) -> dict[str, Any]:
    expected = _expected_sources(dataset_item)
    sources = (row.get("sources") or [])[:k]
    if not expected:
        return {
            "scored": False,
            "recall": None,
            "mrr": None,
            "ndcg": None,
            "first_rank": None,
            "source_count": len(sources),
        }

    first_rank: int | None = None
    matched: set[str] = set()
    ranked_matches: list[str] = []
    for rank, source in enumerate(sources, start=1):
        matches = sorted(_source_tokens(source).intersection(expected))
        ranked_matches.append(matches[0] if matches else "")
        if matches:
            matched.update(matches)
            if first_rank is None:
                first_rank = rank

    seen: set[str] = set()
    dedup_rels: list[int] = []
    for token in ranked_matches:
        if token and token not in seen:
            seen.add(token)
            dedup_rels.append(1)
        else:
            dedup_rels.append(0)
    dcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(dedup_rels))
    idcg = sum(1 / math.log2(i + 2) for i in range(min(len(expected), k)))
    return {
        "scored": True,
        "recall": len(matched) / len(expected),
        "mrr": 1.0 / first_rank if first_rank else 0.0,
        "ndcg": dcg / idcg if idcg else 0.0,
        "first_rank": first_rank,
        "source_count": len(sources),
    }


def _must_include_coverage(answer: str, item: dict[str, Any]) -> float | None:
    terms = [str(term).strip() for term in item.get("must_include") or [] if str(term).strip()]
    if not terms:
        return None
    answer_norm = answer.lower()
    hits = sum(1 for term in terms if term.lower() in answer_norm)
    return hits / len(terms)


def _refusal_hit(answer: str) -> bool:
    answer = answer.lower()
    markers = ("资料不足", "未提供", "没有提供", "无法根据", "课程资料中未", "不能根据")
    return any(marker in answer for marker in markers)


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [row for row in rows if row["retrieval"]["scored"]]
    answerable = [row for row in rows if row["dataset"].get("answerable", True)]
    unanswerable = [row for row in rows if not row["dataset"].get("answerable", True)]

    def avg(key: str) -> float | None:
        values = [row["retrieval"][key] for row in scored if row["retrieval"][key] is not None]
        return round(sum(values) / len(values), 4) if values else None

    coverage_values = [
        row["must_include_coverage"]
        for row in answerable
        if row["must_include_coverage"] is not None
    ]
    refusal_values = [1 if _refusal_hit(row["answer"]) else 0 for row in unanswerable]
    latencies = [float(row.get("latency_ms") or 0) / 1000 for row in rows]
    return {
        "query_count": len(rows),
        "scored_queries": len(scored),
        "success_rate": round(sum(1 for row in rows if row.get("success")) / len(rows), 4) if rows else None,
        "recall_at_k": avg("recall"),
        "mrr": avg("mrr"),
        "ndcg_at_k": avg("ndcg"),
        "avg_source_count": round(sum(row["retrieval"]["source_count"] for row in rows) / len(rows), 2) if rows else None,
        "avg_latency_seconds": round(sum(latencies) / len(latencies), 2) if latencies else None,
        "must_include_coverage": round(sum(coverage_values) / len(coverage_values), 4) if coverage_values else None,
        "refusal_accuracy": round(sum(refusal_values) / len(refusal_values), 4) if refusal_values else None,
    }


def analyze(dataset_path: Path, report_path: Path, k: int) -> dict[str, Any]:
    dataset_payload = _read_json(dataset_path)
    dataset_items = dataset_payload.get("questions", dataset_payload) if isinstance(dataset_payload, dict) else dataset_payload
    dataset_by_id = {str(item.get("question_id") or item.get("id")): item for item in dataset_items}

    report = _read_json(report_path)
    joined: list[dict[str, Any]] = []
    for row in report.get("query_results") or []:
        qid = str(row.get("question_id") or "")
        item = dataset_by_id.get(qid) or row.get("query_item") or {}
        answer = str(row.get("answer") or "")
        joined.append(
            {
                "question_id": qid,
                "success": bool(row.get("success")),
                "latency_ms": row.get("latency_ms"),
                "answer": answer,
                "dataset": item,
                "retrieval": _row_metrics(row, item, k),
                "must_include_coverage": _must_include_coverage(answer, item),
            }
        )

    groups: dict[str, dict[str, list[dict[str, Any]]]] = {
        "question_type": defaultdict(list),
        "expected_modality": defaultdict(list),
        "difficulty": defaultdict(list),
        "answerable": defaultdict(list),
    }
    for row in joined:
        item = row["dataset"]
        groups["question_type"][str(item.get("question_type", "unknown"))].append(row)
        groups["expected_modality"][str(item.get("expected_modality", "unknown"))].append(row)
        groups["difficulty"][str(item.get("difficulty", "unknown"))].append(row)
        groups["answerable"][str(item.get("answerable", True))].append(row)

    return {
        "dataset": str(dataset_path),
        "report": str(report_path),
        "mode_hint": report.get("mode_hint"),
        "k": k,
        "overall": _summarize(joined),
        "slices": {
            group_name: {key: _summarize(value) for key, value in sorted(group_values.items())}
            for group_name, group_values in groups.items()
        },
    }


def _write_markdown(summary: dict[str, Any], output_path: Path) -> None:
    lines = [
        "# Benchmark Slice Analysis",
        "",
        f"- Report: `{summary['report']}`",
        f"- Mode: `{summary.get('mode_hint')}`",
        f"- k: `{summary['k']}`",
        "",
        "## Overall",
        "",
    ]

    def table(rows: dict[str, dict[str, Any]]) -> list[str]:
        out = [
            "| Slice | Count | Scored | Recall@k | MRR | nDCG@k | Must Include | Refusal | Avg Latency(s) |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for key, item in rows.items():
            out.append(
                "| {key} | {query_count} | {scored_queries} | {recall_at_k} | {mrr} | {ndcg_at_k} | {must_include_coverage} | {refusal_accuracy} | {avg_latency_seconds} |".format(
                    key=key,
                    **{k: ("" if v is None else v) for k, v in item.items()},
                )
            )
        return out

    lines.extend(table({"overall": summary["overall"]}))
    for group_name, rows in summary["slices"].items():
        lines.extend(["", f"## {group_name}", ""])
        lines.extend(table(rows))
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze benchmark report by dataset slices.")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path)
    parser.add_argument("--k", type=int, default=5)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = analyze(args.dataset, args.report, args.k)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        _write_markdown(summary, args.output_md)
    print(json.dumps(summary["overall"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

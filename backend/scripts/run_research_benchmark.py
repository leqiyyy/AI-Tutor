"""Offline research benchmark runner for backend-only reproducible experiments.

Usage (from backend directory):
    python scripts/run_research_benchmark.py
    python scripts/run_research_benchmark.py --days 14 --include-fixtures
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import math
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.seed import seed_data
from app.main import app


DEFAULT_QUESTIONS = [
    "Explain TCP slow start with one short example.",
    "Compare Go-Back-N and Selective Repeat in two key points.",
    "What does CIDR /24 mean and why does it matter?",
]


METRIC_DIRECTION = {
    "query_success_rate": "higher",
    "main_chain_success_rate": "higher",
    "fallback_rate": "lower",
    "avg_confidence": "higher",
    "p95_latency_ms": "lower",
    "recall_at_k": "higher",
    "ndcg_at_k": "higher",
    "mrr": "higher",
}


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _round4(value: float | None) -> float | None:
    return round(value, 4) if value is not None else None


def _norm_token(value: Any) -> str:
    return str(value or "").strip().lower()


def _load_benchmark_spec(
    spec_path: Path | None,
    fallback_questions: list[str] | None = None,
) -> list[dict[str, Any]]:
    if not spec_path:
        questions = fallback_questions or DEFAULT_QUESTIONS
        return [{"id": f"q{i+1}", "text": text} for i, text in enumerate(questions)]
    payload = json.loads(spec_path.resolve().read_text(encoding="utf-8"))
    questions = payload.get("questions") or []
    items: list[dict[str, Any]] = []
    for i, raw in enumerate(questions):
        text = str(raw.get("text") or "").strip()
        if not text:
            continue
        items.append({
            "id": raw.get("id") or f"q{i+1}",
            "text": text,
            "expected_source_names": raw.get("expected_source_names") or [],
            "expected_chunk_ids": raw.get("expected_chunk_ids") or [],
            "expected_doc_ids": raw.get("expected_doc_ids") or [],
        })
    return items


def _extract_expected_tokens(query_item: dict[str, Any]) -> set[str]:
    tokens: set[str] = set()
    for key in ("expected_source_names", "expected_chunk_ids", "expected_doc_ids"):
        values = query_item.get(key) or []
        for value in values:
            token = _norm_token(value)
            if token:
                tokens.add(token)
    return tokens


def _extract_source_tokens(source: dict[str, Any]) -> set[str]:
    tokens: set[str] = set()
    for key in ("name", "chunk_id", "doc_id", "source_id"):
        token = _norm_token(source.get(key))
        if token:
            tokens.add(token)
    return tokens


def _evaluate_retrieval(
    query_results: list[dict[str, Any]],
    *,
    k: int,
) -> dict[str, Any]:
    per_query: list[dict[str, Any]] = []
    recalls: list[float] = []
    ndcgs: list[float] = []
    mrrs: list[float] = []

    for row in query_results:
        expected_tokens = _extract_expected_tokens(row.get("query_item") or {})
        if not expected_tokens:
            continue
        sources = (row.get("sources") or [])[:k]
        matched_tokens: set[str] = set()
        relevance_flags: list[int] = []
        first_relevant_rank: int | None = None
        for idx, source in enumerate(sources, start=1):
            source_tokens = _extract_source_tokens(source or {})
            is_relevant = bool(source_tokens.intersection(expected_tokens))
            relevance_flags.append(1 if is_relevant else 0)
            if is_relevant and first_relevant_rank is None:
                first_relevant_rank = idx
            if is_relevant:
                matched_tokens.update(source_tokens.intersection(expected_tokens))

        expected_count = len(expected_tokens)
        matched_count = len(matched_tokens)
        recall = matched_count / expected_count if expected_count else 0.0
        mrr = 1.0 / first_relevant_rank if first_relevant_rank else 0.0
        dcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(relevance_flags))
        ideal_rels = [1] * min(expected_count, k)
        idcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(ideal_rels))
        ndcg = dcg / idcg if idcg > 0 else 0.0

        recalls.append(recall)
        ndcgs.append(ndcg)
        mrrs.append(mrr)
        per_query.append({
            "question_id": row.get("question_id"),
            "question": row.get("question"),
            "expected_relevant_count": expected_count,
            "retrieved_count_at_k": len(sources),
            "matched_relevant_count_at_k": matched_count,
            "first_relevant_rank": first_relevant_rank,
            "recall_at_k": round(recall, 4),
            "ndcg_at_k": round(ndcg, 4),
            "mrr": round(mrr, 4),
        })

    if not per_query:
        return {
            "status": "not_scored_no_ground_truth",
            "k": k,
            "total_queries": len(query_results),
            "scored_queries": 0,
            "recall_at_k": None,
            "ndcg_at_k": None,
            "mrr": None,
            "details": [],
        }

    return {
        "status": "scored",
        "k": k,
        "total_queries": len(query_results),
        "scored_queries": len(per_query),
        "recall_at_k": round(sum(recalls) / len(recalls), 4),
        "ndcg_at_k": round(sum(ndcgs) / len(ndcgs), 4),
        "mrr": round(sum(mrrs) / len(mrrs), 4),
        "details": per_query,
    }


def _extract_comparison_metrics(report: dict[str, Any]) -> dict[str, float | None]:
    summary = report.get("summary") or {}
    rag_perf = report.get("rag_performance") or {}
    rates = rag_perf.get("rates") or {}
    quality = rag_perf.get("quality") or {}
    latency = rag_perf.get("latency_ms") or {}
    retrieval_eval = report.get("retrieval_eval") or {}
    return {
        "query_success_rate": _safe_float(summary.get("query_success_rate")),
        "main_chain_success_rate": _safe_float(rates.get("main_chain_success_rate")),
        "fallback_rate": _safe_float(rates.get("fallback_rate")),
        "avg_confidence": _safe_float(quality.get("avg_confidence")),
        "p95_latency_ms": _safe_float(latency.get("p95")),
        "recall_at_k": _safe_float(retrieval_eval.get("recall_at_k")),
        "ndcg_at_k": _safe_float(retrieval_eval.get("ndcg_at_k")),
        "mrr": _safe_float(retrieval_eval.get("mrr")),
    }


def _build_baseline_comparison(
    current_report: dict[str, Any],
    baseline_path: Path | None,
) -> dict[str, Any] | None:
    if baseline_path is None:
        return None
    baseline_path = baseline_path.resolve()
    if not baseline_path.exists():
        return {
            "status": "baseline_not_found",
            "baseline_report_path": str(baseline_path),
            "metrics": [],
            "summary": {"compared_metrics": 0, "improved": 0, "regressed": 0, "unchanged": 0},
        }

    baseline_report = json.loads(baseline_path.read_text(encoding="utf-8"))
    current_metrics = _extract_comparison_metrics(current_report)
    baseline_metrics = _extract_comparison_metrics(baseline_report)
    metrics: list[dict[str, Any]] = []
    improved = 0
    regressed = 0
    unchanged = 0
    for metric_name, direction in METRIC_DIRECTION.items():
        current_value = current_metrics.get(metric_name)
        baseline_value = baseline_metrics.get(metric_name)
        if current_value is None or baseline_value is None:
            continue
        delta = current_value - baseline_value
        if abs(delta) < 1e-9:
            trend = "unchanged"
            unchanged += 1
        elif direction == "higher":
            trend = "improved" if delta > 0 else "regressed"
        else:
            trend = "improved" if delta < 0 else "regressed"
        if trend == "improved":
            improved += 1
        elif trend == "regressed":
            regressed += 1
        metrics.append({
            "name": metric_name,
            "direction": direction,
            "baseline": _round4(baseline_value),
            "current": _round4(current_value),
            "delta": _round4(delta),
            "trend": trend,
        })

    return {
        "status": "compared",
        "baseline_report_path": str(baseline_path),
        "metrics": metrics,
        "summary": {
            "compared_metrics": len(metrics),
            "improved": improved,
            "regressed": regressed,
            "unchanged": unchanged,
        },
    }


def _login(client: TestClient, account: str, password: str, role: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"account": account, "password": password, "role": role},
    )
    if response.status_code != 200:
        raise RuntimeError(f"Login failed for {role}: {response.status_code} {response.text}")
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _resolve_class_id(client: TestClient, headers: dict[str, str]) -> str:
    courses = client.get("/api/v1/courses", headers=headers)
    if courses.status_code == 200:
        rows = courses.json().get("data") or []
        if rows and rows[0].get("class_id"):
            return str(rows[0]["class_id"])

    classes = client.get("/api/v1/classes", headers=headers)
    if classes.status_code != 200:
        raise RuntimeError(f"Unable to resolve class id: {classes.status_code} {classes.text}")
    class_rows = classes.json().get("data") or []
    if not class_rows:
        raise RuntimeError("No class found for benchmark user")
    return str(class_rows[0]["id"])


def _resolve_teacher_course_id(client: TestClient, teacher_headers: dict[str, str]) -> str:
    response = client.get("/api/v1/courses", headers=teacher_headers)
    if response.status_code != 200:
        raise RuntimeError(f"Unable to list teacher courses: {response.status_code} {response.text}")
    rows = response.json().get("data") or []
    if not rows:
        raise RuntimeError("No course found for teacher benchmark flow")
    return str(rows[0]["id"])


def _build_fixture_bytes(entry: dict[str, Any], fixture_dir: Path) -> bytes:
    content_file = entry.get("content_file")
    if content_file:
        return (fixture_dir / str(content_file)).read_bytes()
    encoding = str(entry.get("encoding") or "").lower()
    if encoding == "base64":
        return base64.b64decode(str(entry.get("content_base64") or ""))
    if encoding == "utf-8":
        return str(entry.get("content") or "").encode("utf-8")
    raise ValueError(f"Unsupported fixture encoding: {entry.get('id')}")


def _run_multimodal_fixture_check(
    client: TestClient,
    teacher_headers: dict[str, str],
    fixture_manifest: Path,
) -> dict[str, Any]:
    fixture_manifest = fixture_manifest.resolve()
    fixture_dir = fixture_manifest.parent
    payload = json.loads(fixture_manifest.read_text(encoding="utf-8"))
    fixtures = payload.get("fixtures") or []

    if not fixtures:
        return {
            "enabled": True,
            "fixture_count": 0,
            "passed": False,
            "reason": "fixture_manifest has no fixtures",
            "fixtures": [],
        }

    course_id = _resolve_teacher_course_id(client, teacher_headers)
    marker = uuid.uuid4().hex[:8]
    class_resp = client.post(
        "/api/v1/classes",
        headers=teacher_headers,
        json={
            "course_id": course_id,
            "name": f"Benchmark MM {marker}",
            "semester": "2026 Spring",
            "announcement": "benchmark multimodal class",
        },
    )
    if class_resp.status_code != 200:
        raise RuntimeError(f"Failed to create multimodal benchmark class: {class_resp.status_code} {class_resp.text}")
    class_id = class_resp.json()["data"]["id"]

    fixture_results: list[dict[str, Any]] = []
    uploaded_material_ids: list[str] = []
    observed_modalities: set[str] = set()

    for entry in fixtures:
        file_bytes = _build_fixture_bytes(entry, fixture_dir)
        upload = client.post(
            f"/api/v1/courses/{course_id}/files/upload",
            headers=teacher_headers,
            files={"file": (entry["file_name"], io.BytesIO(file_bytes), entry["mime_type"])},
            data={"title": f"Benchmark Fixture {entry['id']}", "class_id": class_id},
        )
        if upload.status_code != 200:
            fixture_results.append({
                "id": entry.get("id"),
                "passed": False,
                "error": f"upload failed: {upload.status_code}",
            })
            continue

        material_id = upload.json()["data"]["id"]
        uploaded_material_ids.append(material_id)
        analysis = client.get(
            f"/api/v1/courses/{course_id}/files/{material_id}/analysis",
            headers=teacher_headers,
        )
        if analysis.status_code != 200:
            fixture_results.append({
                "id": entry.get("id"),
                "material_id": material_id,
                "passed": False,
                "error": f"analysis failed: {analysis.status_code}",
            })
            continue

        analysis_data = analysis.json()["data"]
        actual_modalities = {
            str(item.get("modality", "")).lower()
            for item in analysis_data.get("content_items", [])
        }
        expected_modalities = {
            str(mod).lower()
            for mod in entry.get("expected_modalities", [])
        }
        observed_modalities.update(actual_modalities)
        passed = expected_modalities.issubset(actual_modalities)
        fixture_results.append({
            "id": entry.get("id"),
            "material_id": material_id,
            "passed": passed,
            "expected_modalities": sorted(expected_modalities),
            "actual_modalities": sorted(actual_modalities),
            "schema": analysis_data.get("content_items_schema"),
            "quality": analysis_data.get("raganything_quality"),
        })

    graph = client.get(f"/api/v1/courses/{course_id}/graph", headers=teacher_headers)
    graph_has_fixture_provenance = False
    if graph.status_code == 200:
        nodes = graph.json().get("data", {}).get("nodes", [])
        graph_has_fixture_provenance = any(
            set((node.get("provenance") or {}).get("source_material_ids") or []).intersection(uploaded_material_ids)
            for node in nodes
        )

    all_passed = all(item.get("passed") for item in fixture_results) if fixture_results else False
    return {
        "enabled": True,
        "fixture_count": len(fixtures),
        "passed": bool(all_passed and graph_has_fixture_provenance),
        "observed_modalities": sorted(observed_modalities),
        "graph_has_fixture_provenance": graph_has_fixture_provenance,
        "fixtures": fixture_results,
    }


def _write_json(output_path: Path, payload: dict[str, Any]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_markdown(output_path: Path, payload: dict[str, Any]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary = payload.get("summary") or {}
    rag_perf = payload.get("rag_performance") or {}
    rates = rag_perf.get("rates") or {}
    totals = rag_perf.get("totals") or {}
    routing = payload.get("personalization_routing") or {}
    routing_summary = routing.get("summary") or {}
    fixture = payload.get("multimodal_fixture_check") or {}
    retrieval_eval = payload.get("retrieval_eval") or {}
    baseline_comp = payload.get("baseline_comparison") or {}

    lines = [
        "# Offline Research Benchmark Report",
        "",
        f"- Run ID: `{payload.get('run_id')}`",
        f"- Generated At (UTC): `{payload.get('generated_at')}`",
        f"- Window Days: `{payload.get('window_days')}`",
        f"- Class ID: `{payload.get('class_id')}`",
        "",
        "## Query Execution",
        f"- Questions executed: `{summary.get('query_count', 0)}`",
        f"- Query success count: `{summary.get('query_success_count', 0)}`",
        f"- Query success rate: `{summary.get('query_success_rate', 0.0)}`",
        "",
        "## RAG Performance Snapshot",
        f"- Total queries: `{totals.get('queries', 0)}`",
        f"- Main-chain success rate: `{rates.get('main_chain_success_rate', 0.0)}`",
        f"- Fallback rate: `{rates.get('fallback_rate', 0.0)}`",
        "",
        "## Personalization Routing Snapshot",
        f"- Total routing slices: `{routing_summary.get('total_slices', 0)}`",
        f"- Best confidence slice: `{routing_summary.get('best_confidence_slice')}`",
        f"- Lowest fallback slice: `{routing_summary.get('lowest_fallback_slice')}`",
        "",
        "## Multimodal Fixture Check",
        f"- Enabled: `{fixture.get('enabled', False)}`",
        f"- Passed: `{fixture.get('passed', False)}`",
        f"- Fixture count: `{fixture.get('fixture_count', 0)}`",
        "",
        "## Retrieval Evaluation",
        f"- Status: `{retrieval_eval.get('status')}`",
        f"- K: `{retrieval_eval.get('k')}`",
        f"- Scored queries: `{retrieval_eval.get('scored_queries', 0)}`",
        f"- Recall@K: `{retrieval_eval.get('recall_at_k')}`",
        f"- nDCG@K: `{retrieval_eval.get('ndcg_at_k')}`",
        f"- MRR: `{retrieval_eval.get('mrr')}`",
        "",
        "## Baseline Comparison",
        f"- Status: `{baseline_comp.get('status')}`",
        f"- Compared metrics: `{(baseline_comp.get('summary') or {}).get('compared_metrics')}`",
        f"- Improved: `{(baseline_comp.get('summary') or {}).get('improved')}`",
        f"- Regressed: `{(baseline_comp.get('summary') or {}).get('regressed')}`",
        f"- Unchanged: `{(baseline_comp.get('summary') or {}).get('unchanged')}`",
        "",
        "## Files",
        f"- JSON report: `{payload.get('report_json_path')}`",
        f"- Markdown report: `{payload.get('report_md_path')}`",
        f"- Comparison JSON: `{payload.get('comparison_json_path')}`",
        f"- Comparison Markdown: `{payload.get('comparison_md_path')}`",
        "",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")


def _write_comparison_markdown(output_path: Path, comparison: dict[str, Any], run_id: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary = comparison.get("summary") or {}
    lines = [
        "# Benchmark Baseline Comparison",
        "",
        f"- Run ID: `{run_id}`",
        f"- Status: `{comparison.get('status')}`",
        f"- Baseline report: `{comparison.get('baseline_report_path')}`",
        "",
        "## Summary",
        f"- Compared metrics: `{summary.get('compared_metrics', 0)}`",
        f"- Improved: `{summary.get('improved', 0)}`",
        f"- Regressed: `{summary.get('regressed', 0)}`",
        f"- Unchanged: `{summary.get('unchanged', 0)}`",
        "",
        "## Metric Details",
    ]
    for metric in comparison.get("metrics") or []:
        lines.append(
            f"- {metric.get('name')}: baseline={metric.get('baseline')} current={metric.get('current')} "
            f"delta={metric.get('delta')} trend={metric.get('trend')}"
        )
    lines.append("")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def run_offline_benchmark(
    *,
    days: int,
    class_id: str | None,
    output_dir: Path,
    include_fixtures: bool,
    fixture_manifest: Path,
    questions: list[str],
    benchmark_spec_path: Path | None = None,
    retrieval_k: int = 5,
    baseline_report_path: Path | None = None,
) -> dict[str, Any]:
    seed_data()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    query_items = _load_benchmark_spec(benchmark_spec_path, fallback_questions=questions)
    if not query_items:
        query_items = [{"id": f"q{i+1}", "text": text} for i, text in enumerate(questions)]

    with TestClient(app) as client:
        student_headers = _login(client, "student@aitutor.local", "Student123!", "student")
        admin_headers = _login(client, "admin@aitutor.local", "Admin123!", "admin")
        teacher_headers = _login(client, "teacher@aitutor.local", "Teacher123!", "teacher")

        target_class_id = class_id or _resolve_class_id(client, student_headers)
        query_results: list[dict[str, Any]] = []
        for item in query_items:
            question = str(item.get("text") or "")
            response = client.post(
                "/api/v1/chat/query",
                headers=student_headers,
                json={
                    "class_id": target_class_id,
                    "message": question,
                    "attachments": [],
                },
            )
            payload = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
            data = payload.get("data") or {}
            query_results.append({
                "question_id": item.get("id"),
                "question": question,
                "query_item": item,
                "status_code": response.status_code,
                "success": response.status_code == 200 and bool(payload.get("success", False)),
                "response_message": payload.get("message"),
                "sources": data.get("sources") or [],
                "confidence": data.get("confidence"),
                "needs_review": data.get("needs_review"),
            })

        perf_resp = client.get(
            "/api/v1/admin/rag-performance",
            headers=admin_headers,
            params={"days": days, "class_id": target_class_id},
        )
        ablation_resp = client.get(
            "/api/v1/admin/rag-ablation",
            headers=admin_headers,
            params={"days": days, "class_id": target_class_id},
        )
        routing_resp = client.get(
            "/api/v1/admin/personalization-routing-metrics",
            headers=admin_headers,
            params={"days": days, "class_id": target_class_id, "top_n": 12},
        )
        experiment_resp = client.get(
            "/api/v1/admin/experiment-results",
            headers=admin_headers,
            params={"days": days, "class_id": target_class_id},
        )

        multimodal_result: dict[str, Any]
        if include_fixtures:
            multimodal_result = _run_multimodal_fixture_check(client, teacher_headers, fixture_manifest)
        else:
            multimodal_result = {"enabled": False, "passed": None, "fixture_count": 0, "fixtures": []}

    query_success_count = sum(1 for item in query_results if item["success"])
    query_count = len(query_results)
    summary = {
        "query_count": query_count,
        "query_success_count": query_success_count,
        "query_success_rate": round(query_success_count / query_count, 4) if query_count > 0 else 0.0,
    }
    retrieval_eval = _evaluate_retrieval(query_results, k=max(1, int(retrieval_k)))

    output_dir = output_dir.resolve()
    json_path = output_dir / f"benchmark_{run_id}.json"
    md_path = output_dir / f"benchmark_{run_id}.md"
    comparison_json_path = output_dir / f"benchmark_compare_{run_id}.json"
    comparison_md_path = output_dir / f"benchmark_compare_{run_id}.md"

    result_payload = {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_days": days,
        "class_id": target_class_id,
        "summary": summary,
        "query_results": query_results,
        "rag_performance": (perf_resp.json().get("data") if perf_resp.status_code == 200 else {}),
        "rag_ablation": (ablation_resp.json().get("data") if ablation_resp.status_code == 200 else {}),
        "personalization_routing": (routing_resp.json().get("data") if routing_resp.status_code == 200 else {}),
        "experiment_results": (experiment_resp.json().get("data") if experiment_resp.status_code == 200 else {}),
        "multimodal_fixture_check": multimodal_result,
        "retrieval_eval": retrieval_eval,
        "benchmark_spec_path": str(benchmark_spec_path.resolve()) if benchmark_spec_path else None,
    }
    result_payload["baseline_comparison"] = _build_baseline_comparison(result_payload, baseline_report_path)
    result_payload["report_json_path"] = str(json_path)
    result_payload["report_md_path"] = str(md_path)
    result_payload["comparison_json_path"] = str(comparison_json_path) if baseline_report_path else None
    result_payload["comparison_md_path"] = str(comparison_md_path) if baseline_report_path else None

    _write_json(json_path, result_payload)
    _write_markdown(md_path, result_payload)
    if baseline_report_path and result_payload["baseline_comparison"] is not None:
        _write_json(comparison_json_path, result_payload["baseline_comparison"])
        _write_comparison_markdown(comparison_md_path, result_payload["baseline_comparison"], run_id)
    return result_payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run offline benchmark and export experiment report.")
    parser.add_argument("--days", type=int, default=30, help="Metrics aggregation window in days.")
    parser.add_argument("--class-id", type=str, default=None, help="Optional class id filter.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("runtime_tmp") / "experiment_reports",
        help="Directory for generated json/markdown reports.",
    )
    parser.add_argument(
        "--include-fixtures",
        action="store_true",
        help="Run multimodal fixture upload/analysis checks before report export.",
    )
    parser.add_argument(
        "--fixture-manifest",
        type=Path,
        default=Path("tests") / "fixtures" / "multimodal" / "fixture_manifest.json",
        help="Path to multimodal fixture manifest.",
    )
    parser.add_argument(
        "--benchmark-spec",
        type=Path,
        default=None,
        help="Optional benchmark spec json path (questions + expected source/chunk/doc ids).",
    )
    parser.add_argument(
        "--retrieval-k",
        type=int,
        default=5,
        help="Top-k for retrieval metrics calculation (Recall@k / nDCG@k).",
    )
    parser.add_argument(
        "--baseline-report",
        type=Path,
        default=None,
        help="Optional previous benchmark json report path for baseline-vs-current comparison.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_offline_benchmark(
        days=max(1, int(args.days)),
        class_id=args.class_id,
        output_dir=args.output_dir,
        include_fixtures=bool(args.include_fixtures),
        fixture_manifest=args.fixture_manifest,
        questions=DEFAULT_QUESTIONS,
        benchmark_spec_path=args.benchmark_spec,
        retrieval_k=max(1, int(args.retrieval_k)),
        baseline_report_path=args.baseline_report,
    )
    print("Benchmark completed.")
    print(f"JSON report: {result['report_json_path']}")
    print(f"Markdown report: {result['report_md_path']}")


if __name__ == "__main__":
    main()

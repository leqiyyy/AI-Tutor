"""Evaluate RAG answers with an LLM-as-a-Judge.

The script reads one or more benchmark JSON reports, joins them with the thesis
dataset to get reference answers/rubrics, and asks an OpenAI-compatible judge
model to score each answer on correctness, faithfulness, completeness,
relevance, citation support, and teaching quality.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import statistics
import time
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any


SCORE_KEYS = (
    "correctness",
    "faithfulness",
    "completeness",
    "relevance",
    "citation_support",
    "teaching_quality",
)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _load_env_file(path: Path | None) -> None:
    if not path or not path.exists():
        return
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _normalize_base(url: str) -> str:
    return str(url or "").rstrip("/")


def _post_json(url: str, payload: dict[str, Any], api_key: str, timeout: int) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
        headers["x-api-key"] = api_key
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _with_retry(fn, *, retries: int, label: str) -> Any:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            return fn()
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError) as exc:
            last_error = exc
            if attempt == retries:
                break
            time.sleep(min(2 * attempt, 8))
    raise RuntimeError(f"{label} failed after {retries} attempts: {last_error}") from last_error


def _dataset_items(path: Path) -> dict[str, dict[str, Any]]:
    payload = _read_json(path)
    items = payload.get("questions", payload) if isinstance(payload, dict) else payload
    return {str(item.get("question_id") or item.get("id")): item for item in items}


def _parse_report_spec(spec: str) -> tuple[str, Path]:
    if "=" in spec:
        label, path = spec.split("=", 1)
        return label.strip(), Path(path.strip())
    path = Path(spec)
    return path.parent.name or path.stem, path


def _source_text(source: dict[str, Any], max_chars: int) -> str:
    metadata = source.get("metadata") if isinstance(source.get("metadata"), dict) else {}
    candidates = (
        source.get("text"),
        source.get("raw_text"),
        source.get("snippet"),
        metadata.get("text"),
        metadata.get("raw_text"),
        metadata.get("content"),
    )
    for value in candidates:
        text = str(value or "").strip()
        if text:
            return text[:max_chars]
    return ""


def _source_name(source: dict[str, Any]) -> str:
    metadata = source.get("metadata") if isinstance(source.get("metadata"), dict) else {}
    for key in ("file_name", "name", "source_name", "title", "doc_id", "chunk_id"):
        value = source.get(key) or metadata.get(key)
        if str(value or "").strip():
            return str(value).strip()
    return "unknown"


def _contexts(row: dict[str, Any], max_contexts: int, max_context_chars: int) -> list[dict[str, Any]]:
    contexts = []
    for idx, source in enumerate(row.get("sources") or [], start=1):
        text = _source_text(source or {}, max_context_chars)
        contexts.append(
            {
                "index": idx,
                "source": _source_name(source or {}),
                "chunk_id": (source or {}).get("chunk_id"),
                "score": (source or {}).get("score") or (source or {}).get("retrieval_score"),
                "text": text,
            }
        )
        if len(contexts) >= max_contexts:
            break
    return contexts


def _reference_answer(item: dict[str, Any]) -> str:
    for key in ("standard_answer", "reference_answer", "expected_answer", "answer", "ground_truth"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    snippets = [
        str(source.get("snippet") or "").strip()
        for source in item.get("golden_sources") or []
        if str(source.get("snippet") or "").strip()
    ]
    return "\n".join(snippets)


def _gold_sources(item: dict[str, Any]) -> list[str]:
    names = []
    for source in item.get("golden_sources") or []:
        value = source.get("file") or source.get("file_name") or source.get("location")
        if str(value or "").strip():
            names.append(str(value).strip())
    for value in item.get("expected_source_names") or []:
        if str(value or "").strip():
            names.append(str(value).strip())
    return list(dict.fromkeys(names))


def _build_prompt(sample: dict[str, Any]) -> tuple[str, str]:
    system = (
        "You are a strict but fair evaluator for a course RAG system. "
        "Evaluate only the answer quality for the given question, reference answer, rubric, and retrieved contexts. "
        "Do not reward unsupported claims. Return JSON only."
    )
    rubric = {
        "score_scale": {
            "1": "very poor or absent",
            "2": "mostly wrong or unsupported",
            "3": "partially correct with important gaps",
            "4": "mostly correct and supported",
            "5": "fully correct, complete, and well supported",
        },
        "dimensions": {
            "correctness": "Does the answer match the reference answer and course facts?",
            "faithfulness": "Is the answer supported by retrieved contexts without hallucination?",
            "completeness": "Does it cover the key points and must_include terms?",
            "relevance": "Does it directly answer the question?",
            "citation_support": "Do the retrieved contexts/sources support the answer?",
            "teaching_quality": "Is it clear and pedagogically useful for students?",
        },
    }
    user = {
        "task": "Score the model answer. Return JSON with integer scores 1-5 for each dimension, a boolean hallucination flag, and a short Chinese reason.",
        "output_schema": {
            "correctness": 1,
            "faithfulness": 1,
            "completeness": 1,
            "relevance": 1,
            "citation_support": 1,
            "teaching_quality": 1,
            "hallucination": False,
            "reason": "简短中文说明",
        },
        "rubric": rubric,
        "sample": sample,
    }
    return system, json.dumps(user, ensure_ascii=False)


def _extract_json(text: str) -> dict[str, Any] | None:
    text = str(text or "").strip()
    if not text:
        return None
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE | re.DOTALL).strip()
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        text = match.group(0)
    try:
        payload = json.loads(text)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _call_judge(sample: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    system, user = _build_prompt(sample)
    payload = {
        "model": args.judge_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": args.temperature,
        "top_p": args.top_p,
        "max_tokens": args.max_tokens,
    }
    if args.response_format_json:
        payload["response_format"] = {"type": "json_object"}
    if args.disable_qwen_thinking and "qwen" in args.judge_model.lower():
        payload["extra_body"] = {"enable_thinking": False, "thinking_budget": 0}

    def call() -> dict[str, Any]:
        return _post_json(
            f"{_normalize_base(args.judge_api_base)}/chat/completions",
            payload,
            args.judge_api_key,
            args.timeout,
        )

    response = _with_retry(call, retries=args.retries, label="judge")
    choices = response.get("choices") or []
    content = ""
    if choices:
        content = str((choices[0].get("message") or {}).get("content") or "")
    parsed = _extract_json(content)
    if not parsed:
        raise ValueError(f"judge returned invalid JSON: {content[:500]}")
    return parsed


def _normalize_judgment(raw: dict[str, Any]) -> dict[str, Any]:
    judgment: dict[str, Any] = {}
    for key in SCORE_KEYS:
        value = raw.get(key)
        try:
            score = int(round(float(value)))
        except Exception:
            score = 1
        judgment[key] = max(1, min(5, score))
    hallucination = raw.get("hallucination", False)
    if isinstance(hallucination, str):
        hallucination = hallucination.strip().lower() in {"true", "yes", "1", "是", "有"}
    judgment["hallucination"] = bool(hallucination)
    judgment["reason"] = str(raw.get("reason") or raw.get("rationale") or "")[:1000]
    judgment["overall"] = round(sum(judgment[key] for key in SCORE_KEYS) / len(SCORE_KEYS), 4)
    return judgment


def _load_existing(path: Path) -> set[tuple[str, str]]:
    done: set[tuple[str, str]] = set()
    if not path.exists():
        return done
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        done.add((str(row.get("method")), str(row.get("question_id"))))
    return done


def _iter_samples(args: argparse.Namespace) -> list[dict[str, Any]]:
    dataset_by_id = _dataset_items(args.dataset)
    samples: list[dict[str, Any]] = []
    for report_spec in args.report:
        method, path = _parse_report_spec(report_spec)
        report = _read_json(path)
        for row in report.get("query_results") or []:
            qid = str(row.get("question_id") or "")
            item = dataset_by_id.get(qid) or row.get("dataset") or row.get("query_item") or {}
            samples.append(
                {
                    "method": method,
                    "question_id": qid,
                    "question": str(row.get("question") or item.get("question") or item.get("text") or ""),
                    "answer": str(row.get("answer") or ""),
                    "reference_answer": _reference_answer(item),
                    "must_include": item.get("must_include") or [],
                    "gold_sources": _gold_sources(item),
                    "answerable": item.get("answerable", True),
                    "question_type": item.get("question_type") or item.get("type"),
                    "expected_modality": item.get("expected_modality"),
                    "difficulty": item.get("difficulty"),
                    "contexts": _contexts(row, args.max_contexts, args.max_context_chars),
                    "source_count": len(row.get("sources") or []),
                    "latency_ms": row.get("latency_ms"),
                }
            )
    if args.shuffle:
        random.Random(args.seed).shuffle(samples)
    return samples


def _avg(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [float(row["judgment"][key]) for row in rows if row.get("judgment")]
    return round(sum(values) / len(values), 4) if values else None


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ok = [row for row in rows if row.get("success") and row.get("judgment")]
    return {
        "count": len(rows),
        "success_count": len(ok),
        "success_rate": round(len(ok) / len(rows), 4) if rows else None,
        **{f"avg_{key}": _avg(ok, key) for key in SCORE_KEYS},
        "avg_overall": _avg(ok, "overall"),
        "hallucination_rate": round(
            sum(1 for row in ok if row["judgment"].get("hallucination")) / len(ok), 4
        ) if ok else None,
    }


def _group_summary(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(key, "unknown"))].append(row)
    return {name: _summarize(items) for name, items in sorted(grouped.items())}


def _write_md(summary: dict[str, Any], path: Path) -> None:
    lines = [
        "# LLM-as-a-Judge RAG Answer Evaluation",
        "",
        f"- Judge Model: `{summary['judge_model']}`",
        f"- Dataset: `{summary['dataset']}`",
        "",
        "## Overall By Method",
        "",
        "| Method | Count | Success | Correctness | Faithfulness | Completeness | Relevance | Citation Support | Teaching Quality | Overall | Hallucination |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for method, row in summary["by_method"].items():
        def f(key: str) -> str:
            value = row.get(key)
            return "" if value is None else str(value)
        lines.append(
            f"| {method} | {f('count')} | {f('success_rate')} | {f('avg_correctness')} | "
            f"{f('avg_faithfulness')} | {f('avg_completeness')} | {f('avg_relevance')} | "
            f"{f('avg_citation_support')} | {f('avg_teaching_quality')} | {f('avg_overall')} | "
            f"{f('hallucination_rate')} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> dict[str, Any]:
    _load_env_file(args.env_file)
    args.judge_api_base = args.judge_api_base or os.getenv("JUDGE_API_BASE") or os.getenv("OPENAI_API_BASE") or os.getenv("LLM_API_BASE")
    args.judge_api_key = args.judge_api_key or os.getenv("JUDGE_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")
    if not args.judge_api_base or not args.judge_api_key:
        raise SystemExit("Missing judge API config. Set --judge-api-base and --judge-api-key, or JUDGE_API_BASE/JUDGE_API_KEY.")

    output_dir = args.output_dir.resolve()
    run_id = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    jsonl_path = output_dir / f"judge_{run_id}.jsonl"
    summary_path = output_dir / f"judge_summary_{run_id}.json"
    md_path = output_dir / f"judge_summary_{run_id}.md"
    latest_summary = output_dir / "judge_summary_latest.json"
    latest_md = output_dir / "judge_summary_latest.md"

    samples = _iter_samples(args)
    if args.limit:
        samples = samples[: args.limit]
    done = _load_existing(jsonl_path) if args.resume else set()
    rows: list[dict[str, Any]] = []

    for idx, sample in enumerate(samples, start=1):
        identity = (sample["method"], sample["question_id"])
        if identity in done:
            continue
        started = time.perf_counter()
        success = True
        error = ""
        judgment: dict[str, Any] | None = None
        try:
            raw = _call_judge(sample, args)
            judgment = _normalize_judgment(raw)
        except Exception as exc:
            success = False
            error = str(exc)[:1000]
        row = {
            **{key: sample.get(key) for key in (
                "method",
                "question_id",
                "question_type",
                "expected_modality",
                "difficulty",
                "answerable",
                "source_count",
                "latency_ms",
            )},
            "success": success,
            "error": error,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            "judgment": judgment,
        }
        rows.append(row)
        _append_jsonl(jsonl_path, row)
        print(
            f"[{idx}/{len(samples)}] {sample['method']} {sample['question_id']} "
            f"success={success} overall={(judgment or {}).get('overall')}",
            flush=True,
        )
        if args.sleep_seconds > 0:
            time.sleep(args.sleep_seconds)

    if jsonl_path.exists():
        all_rows = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    else:
        all_rows = rows
    summary = {
        "judge_model": args.judge_model,
        "dataset": str(args.dataset),
        "report_specs": args.report,
        "row_count": len(all_rows),
        "overall": _summarize(all_rows),
        "by_method": _group_summary(all_rows, "method"),
        "by_question_type": _group_summary(all_rows, "question_type"),
        "by_expected_modality": _group_summary(all_rows, "expected_modality"),
        "by_difficulty": _group_summary(all_rows, "difficulty"),
        "jsonl_path": str(jsonl_path),
        "summary_path": str(summary_path),
        "markdown_path": str(md_path),
    }
    _write_json(summary_path, summary)
    _write_json(latest_summary, summary)
    _write_md(summary, md_path)
    _write_md(summary, latest_md)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Judge RAG benchmark answers with an LLM.")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--report", action="append", required=True, help="Use label=path or just path. Can be repeated.")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--judge-api-base", default="")
    parser.add_argument("--judge-api-key", default="")
    parser.add_argument("--judge-model", default="gpt-5.1")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top-p", type=float, default=1.0)
    parser.add_argument("--max-tokens", type=int, default=700)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--max-contexts", type=int, default=5)
    parser.add_argument("--max-context-chars", type=int, default=1200)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--shuffle", action="store_true")
    parser.add_argument("--seed", type=int, default=20260515)
    parser.add_argument("--sleep-seconds", type=float, default=0.0)
    parser.add_argument("--response-format-json", action="store_true", default=True)
    parser.add_argument("--disable-qwen-thinking", action="store_true", default=True)
    parser.add_argument("--resume", action="store_true", default=True)
    return parser.parse_args()


def main() -> None:
    summary = run(parse_args())
    print(json.dumps(summary["by_method"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

from __future__ import annotations

import asyncio
import json
import mimetypes
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.database import SessionLocal
from app.integrations.preprocessors import detect_material_file_type
from app.integrations.rag import get_rag_engine
from app.integrations.rag.runtime_check import build_raganything_runtime_report
from app.models.course import Class, Material
from app.models.knowledge import FileParseTask


DEFAULT_SMOKE_QUESTION = "Please summarize the key teaching points in this material."
DEFAULT_REVIEW_QUESTION = "What does this smoke-test material mainly cover?"
DEFAULT_REVIEW_ANSWER = "This is a teacher-verified smoke-test answer written back into the RAG-Anything knowledge base."
DEFAULT_REVIEW_VERIFICATION_QUESTION = "Repeat the teacher-verified smoke-test token for this material."
DEFAULT_SMOKE_REPORT_DIR = Path("runtime_tmp") / "rag_smoke_reports"


def run_raganything_smoke_check(
    *,
    file_path: str,
    class_id: str | None = None,
    create_isolated_class: bool = False,
    question: str = DEFAULT_SMOKE_QUESTION,
    review_question: str = DEFAULT_REVIEW_QUESTION,
    review_answer: str = DEFAULT_REVIEW_ANSWER,
    include_review_sync: bool = True,
    verify_review_query: bool = True,
) -> dict[str, Any]:
    return asyncio.run(
        arun_raganything_smoke_check(
            file_path=file_path,
            class_id=class_id,
            create_isolated_class=create_isolated_class,
            question=question,
            review_question=review_question,
            review_answer=review_answer,
            include_review_sync=include_review_sync,
            verify_review_query=verify_review_query,
        )
    )


async def arun_raganything_smoke_check(
    *,
    file_path: str,
    class_id: str | None = None,
    create_isolated_class: bool = False,
    question: str = DEFAULT_SMOKE_QUESTION,
    review_question: str = DEFAULT_REVIEW_QUESTION,
    review_answer: str = DEFAULT_REVIEW_ANSWER,
    include_review_sync: bool = True,
    verify_review_query: bool = True,
) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc).isoformat()
    resolved_path = Path(file_path).expanduser().resolve()
    runtime = build_raganything_runtime_report()
    mime_type = _guess_mime_type(resolved_path)
    file_type = detect_material_file_type(resolved_path.name, mime_type)
    review_token = f"SMOKE_SYNC_{uuid.uuid4().hex[:10].upper()}"
    review_answer_with_token = f"{review_answer}\n\nSmoke verification token: {review_token}"
    payload: dict[str, Any] = {
        "started_at": started_at,
        "status": "blocked" if runtime["status"] != "ready" else "running",
        "engine": "raganything",
        "strict_mode": True,
        "runtime": runtime,
        "input": {
            "file_path": str(resolved_path),
            "file_name": resolved_path.name,
            "mime_type": mime_type,
            "file_type": file_type,
            "requested_class_id": class_id,
            "create_isolated_class": create_isolated_class,
            "question": question,
            "include_review_sync": include_review_sync,
            "verify_review_query": bool(include_review_sync and verify_review_query),
        },
        "artifacts": {},
        "steps": [],
    }

    if not resolved_path.exists():
        payload["status"] = "failed"
        payload["steps"].append({
            "name": "input_file",
            "status": "fail",
            "message": f"Input file does not exist: {resolved_path}",
        })
        payload["finished_at"] = datetime.now(timezone.utc).isoformat()
        return payload

    payload["steps"].append({
        "name": "runtime_check",
        "status": "pass" if runtime["status"] == "ready" else "fail",
        "message": "RAG-Anything runtime is ready." if runtime["status"] == "ready" else "RAG-Anything runtime is blocked.",
    })
    if runtime["status"] != "ready":
        payload["finished_at"] = datetime.now(timezone.utc).isoformat()
        return payload

    base_cls = _resolve_target_class(class_id)
    cls = _create_isolated_smoke_class(base_cls) if create_isolated_class else base_cls
    created_material = _create_smoke_material(
        class_id=cls.id,
        uploaded_by=cls.teacher_id,
        file_path=resolved_path,
        mime_type=mime_type,
        file_type=file_type,
    )
    payload["artifacts"].update({
        "course_id": cls.course_id,
        "class_id": cls.id,
        "base_class_id": base_cls.id if create_isolated_class else None,
        "isolated_class_created": create_isolated_class,
        "material_id": created_material.id,
        "material_file_name": created_material.file_name,
    })
    payload["steps"].append({
        "name": "register_material",
        "status": "pass",
        "message": "Smoke-test material record created.",
        "material_id": created_material.id,
        "class_id": cls.id,
    })

    engine = get_rag_engine("raganything")

    try:
        ingest_ok = await engine.ingest_material(
            cls.id,
            created_material.id,
            str(resolved_path),
            mime_type,
        )
    except Exception as exc:
        payload["status"] = "failed"
        payload["steps"].append({
            "name": "ingest_material",
            "status": "fail",
            "message": str(exc),
        })
        payload["finished_at"] = datetime.now(timezone.utc).isoformat()
        return payload

    parse_task = _latest_parse_task_for_material(created_material.id)
    parse_task_payload = engine.get_parse_task(parse_task.id) if parse_task else None
    payload["artifacts"]["parse_task_id"] = parse_task.id if parse_task else None
    payload["steps"].append({
        "name": "ingest_material",
        "status": "pass" if ingest_ok else "fail",
        "message": "Material ingestion finished." if ingest_ok else "Material ingestion returned a non-success status.",
        "parse_task_id": parse_task.id if parse_task else None,
        "parse_task": parse_task_payload,
    })
    if not ingest_ok:
        payload["status"] = "failed"
        payload["finished_at"] = datetime.now(timezone.utc).isoformat()
        return payload

    try:
        query_result = await engine.query(
            question=question,
            class_id=cls.id,
            history=[],
            attachments=[],
            role="teacher",
        )
    except Exception as exc:
        payload["status"] = "failed"
        payload["steps"].append({
            "name": "query",
            "status": "fail",
            "message": str(exc),
        })
        payload["finished_at"] = datetime.now(timezone.utc).isoformat()
        return payload

    query_failed_closed = bool((query_result.meta or {}).get("fallback_disabled"))
    query_ok = not query_failed_closed
    payload["steps"].append({
        "name": "query",
        "status": "pass" if query_ok else "fail",
        "message": (
            "Main-chain query finished."
            if query_ok
            else "RAG-Anything main-chain query was unavailable; no Simple fallback was used."
        ),
        "answer_preview": (query_result.answer or "")[:300],
        "source_count": len(query_result.sources or []),
        "confidence": query_result.confidence,
        "meta": query_result.meta,
    })
    if not query_ok:
        payload["status"] = "failed"
        payload["finished_at"] = datetime.now(timezone.utc).isoformat()
        return payload

    if include_review_sync:
        try:
            review_ok = await engine.add_qa_pair(
                cls.id,
                review_question,
                review_answer_with_token,
            )
        except Exception as exc:
            payload["status"] = "failed"
            payload["steps"].append({
                "name": "teacher_review_sync",
                "status": "fail",
                "message": str(exc),
            })
            payload["finished_at"] = datetime.now(timezone.utc).isoformat()
            return payload

        payload["steps"].append({
            "name": "teacher_review_sync",
            "status": "pass" if review_ok else "fail",
            "message": "Teacher review answer synced into RAG-Anything." if review_ok else "Teacher review sync returned a non-success status.",
            "review_question": review_question,
            "review_token": review_token,
        })
        if not review_ok:
            payload["status"] = "failed"
            payload["finished_at"] = datetime.now(timezone.utc).isoformat()
            return payload

        if verify_review_query:
            try:
                review_query_result = await engine.query(
                    question=DEFAULT_REVIEW_VERIFICATION_QUESTION,
                    class_id=cls.id,
                    history=[],
                    attachments=[],
                    role="teacher",
                )
            except Exception as exc:
                payload["status"] = "failed"
                payload["steps"].append({
                    "name": "teacher_review_query",
                    "status": "fail",
                    "message": str(exc),
                })
                payload["finished_at"] = datetime.now(timezone.utc).isoformat()
                return payload

            verification = _verify_review_query_result(
                answer=review_query_result.answer,
                sources=review_query_result.sources,
                expected_token=review_token,
            )
            payload["steps"].append({
                "name": "teacher_review_query",
                "status": "pass" if verification["verified"] else "fail",
                "message": (
                    "Teacher review write-back was retrieved by the strict RAG-Anything main chain."
                    if verification["verified"]
                    else "Teacher review write-back query completed, but the verification token was not found in the answer or retrieved evidence."
                ),
                "question": DEFAULT_REVIEW_VERIFICATION_QUESTION,
                "answer_preview": (review_query_result.answer or "")[:300],
                "source_count": len(review_query_result.sources or []),
                "confidence": review_query_result.confidence,
                "verification": verification,
                "meta": review_query_result.meta,
            })
            if not verification["verified"]:
                payload["status"] = "failed"
                payload["finished_at"] = datetime.now(timezone.utc).isoformat()
                return payload

    payload["status"] = "passed"
    payload["finished_at"] = datetime.now(timezone.utc).isoformat()
    return payload


def _resolve_target_class(class_id: str | None) -> Class:
    with SessionLocal() as db:
        query = db.query(Class).filter(Class.is_active == True)
        if class_id:
            cls = query.filter(Class.id == class_id).first()
        else:
            cls = query.order_by(Class.created_at.asc()).first()
        if not cls:
            requested = class_id or "<first_active_class>"
            raise RuntimeError(f"Unable to resolve target class for smoke check: {requested}")
        db.expunge(cls)
        return cls


def _create_isolated_smoke_class(base_cls: Class) -> Class:
    now = datetime.now(timezone.utc)
    cls = Class(
        course_id=base_cls.course_id,
        teacher_id=base_cls.teacher_id,
        name=f"[SMOKE] isolated {now.strftime('%Y%m%d%H%M%S')}",
        semester=base_cls.semester,
        invite_code=f"SMK{uuid.uuid4().hex[:10].upper()}",
        announcement="Temporary isolated class created by strict RAG-Anything smoke check.",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    with SessionLocal() as db:
        db.add(cls)
        db.commit()
        db.refresh(cls)
        db.expunge(cls)
    return cls


def _create_smoke_material(
    *,
    class_id: str,
    uploaded_by: str,
    file_path: Path,
    mime_type: str,
    file_type: str,
) -> Material:
    now = datetime.now(timezone.utc)
    material = Material(
        class_id=class_id,
        uploaded_by=uploaded_by,
        title=f"[SMOKE] {file_path.stem}",
        file_name=file_path.name,
        file_path=str(file_path),
        file_size=file_path.stat().st_size if file_path.exists() else None,
        mime_type=mime_type,
        file_type=file_type,
        kb_status="pending",
        description="Temporary material created by strict RAG-Anything smoke check.",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    with SessionLocal() as db:
        db.add(material)
        db.commit()
        db.refresh(material)
        db.expunge(material)
    return material


def _latest_parse_task_for_material(material_id: str) -> FileParseTask | None:
    with SessionLocal() as db:
        task = db.query(FileParseTask).filter(
            FileParseTask.material_id == material_id,
        ).order_by(FileParseTask.updated_at.desc()).first()
        if task:
            db.expunge(task)
        return task


def _guess_mime_type(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(str(path))
    return guessed or "application/octet-stream"


def _verify_review_query_result(
    *,
    answer: str | None,
    sources: list[dict[str, Any]] | None,
    expected_token: str,
) -> dict[str, Any]:
    answer_text = str(answer or "")
    answer_has_token = expected_token in answer_text
    matched_sources: list[dict[str, Any]] = []
    for index, source in enumerate(sources or []):
        haystacks = [
            str(source.get("snippet") or ""),
            str(source.get("raw_text") or ""),
            str(source.get("content") or ""),
            str(source.get("text") or ""),
            str(source.get("name") or ""),
        ]
        if any(expected_token in item for item in haystacks):
            matched_sources.append({
                "index": index,
                "name": source.get("name"),
                "chunk_id": source.get("chunk_id"),
                "score": source.get("score"),
            })

    return {
        "expected_token": expected_token,
        "answer_has_token": answer_has_token,
        "matched_source_count": len(matched_sources),
        "matched_sources": matched_sources,
        "verified": bool(answer_has_token or matched_sources),
    }


def write_raganything_smoke_report(
    report: dict[str, Any],
    *,
    output_dir: str | Path = DEFAULT_SMOKE_REPORT_DIR,
) -> dict[str, str]:
    base_dir = Path(output_dir).resolve()
    base_dir.mkdir(parents=True, exist_ok=True)

    run_id = _build_smoke_run_id(report)
    json_path = base_dir / f"raganything_smoke_{run_id}.json"
    md_path = base_dir / f"raganything_smoke_{run_id}.md"

    report["report_json_path"] = str(json_path)
    report["report_md_path"] = str(md_path)

    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    md_path.write_text(_build_smoke_markdown(report), encoding="utf-8")
    return {
        "json_path": str(json_path),
        "md_path": str(md_path),
    }


def _build_smoke_run_id(report: dict[str, Any]) -> str:
    started_at = str(report.get("started_at") or datetime.now(timezone.utc).isoformat())
    normalized = (
        started_at.replace("+00:00", "Z")
        .replace("-", "")
        .replace(":", "")
        .replace(".", "")
        .replace("T", "_")
    )
    return normalized[:32]


def _build_smoke_markdown(report: dict[str, Any]) -> str:
    runtime = report.get("runtime") or {}
    input_meta = report.get("input") or {}
    artifacts = report.get("artifacts") or {}
    steps = report.get("steps") or []

    lines = [
        "# RAG-Anything Smoke Report",
        "",
        f"- Status: `{report.get('status')}`",
        f"- Started At (UTC): `{report.get('started_at')}`",
        f"- Finished At (UTC): `{report.get('finished_at')}`",
        f"- Engine: `{report.get('engine')}`",
        f"- Strict Mode: `{report.get('strict_mode')}`",
        "",
        "## Input",
        f"- File Path: `{input_meta.get('file_path')}`",
        f"- File Name: `{input_meta.get('file_name')}`",
        f"- MIME Type: `{input_meta.get('mime_type')}`",
        f"- File Type: `{input_meta.get('file_type')}`",
        f"- Class ID: `{artifacts.get('class_id') or input_meta.get('requested_class_id')}`",
        f"- Course ID: `{artifacts.get('course_id')}`",
        "",
        "## Runtime",
        f"- Runtime Status: `{runtime.get('status')}`",
        f"- Blocker Count: `{runtime.get('blocker_count')}`",
        "",
        "## Artifacts",
        f"- Material ID: `{artifacts.get('material_id')}`",
        f"- Parse Task ID: `{artifacts.get('parse_task_id')}`",
        "",
        "## Steps",
    ]

    for step in steps:
        lines.append(f"- `{step.get('name')}`: `{step.get('status')}` - {step.get('message')}")

    lines.extend([
        "",
        "## Notes",
        "- If `teacher_review_query` is `pass`, the smoke run verified that teacher-reviewed QA write-back could be retrieved again by the formal RAG-Anything main chain.",
        "- If runtime status is not `ready`, fix the blockers reported by `python scripts/check_raganything_runtime.py` first.",
        "",
    ])
    return "\n".join(lines)

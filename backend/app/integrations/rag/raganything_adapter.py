import importlib
import inspect
import json
import os
import re
import sys
import asyncio
import hashlib
import contextvars
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Awaitable, Callable

import httpx
from app.ai.base import RAGResult
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.logging import get_logger
from app.integrations.preprocessors import PreprocessResult, preprocess_for_raganything
from app.integrations.rag.education_prompts import (
    apply_framework_prompt_overrides,
    build_lightrag_addon_params,
    build_query_user_prompt,
)
from app.integrations.rag.query_rewrite import build_query_rewrite_bundle
from app.integrations.rag.storage_config import (
    build_lightrag_storage_plan,
    build_runtime_rag_storage_config_snapshot,
)
from app.integrations.reranker import get_reranker
from app.models.course import Class, Course, Material
from app.models.knowledge import FileParseTask, KBSpace, KnowledgeEntity, KnowledgeRelation
from app.services import model_routing_service

logger = get_logger(__name__)

_QUERY_TRACE_CONTEXT: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "raganything_query_trace",
    default=None,
)
_INGEST_TRACE_CONTEXT: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "raganything_ingest_trace",
    default=None,
)
ProgressCallback = Callable[[dict[str, Any]], Awaitable[None]]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

PROJECTION_FILE_LABEL_RE = re.compile(
    r"\.(?:txt|pdf|docx?|pptx?|xlsx?|csv|md|png|jpe?g|gif|webp|mp4|mov|avi|zip)$",
    re.IGNORECASE,
)
PROJECTION_UUID_RE = re.compile(
    r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$",
    re.IGNORECASE,
)
PROJECTION_FILE_HASH_RE = re.compile(
    r"(?:^|[._-])[a-f0-9]{8,}(?:$|[._-])",
    re.IGNORECASE,
)
PROJECTION_STOPWORDS = {
    "course",
    "csv",
    "doc",
    "docx",
    "file",
    "image",
    "indexed",
    "material",
    "md",
    "notes",
    "pdf",
    "ppt",
    "pptx",
    "rag",
    "raganything",
    "txt",
    "through",
    "upload",
    "xlsx",
}
PROJECTION_COURSE_ARTIFACT_TERMS = {
    "表",
    "表格",
    "表格结构",
    "表的结构",
    "表的组织",
    "表头",
    "行",
    "列",
    "单元格",
    "图片",
    "图像",
    "公式",
    "文件",
    "文档",
    "材料",
    "页面",
    "markdown",
    "markdown table",
    "table",
    "table structure",
    "table organization",
    "row",
    "column",
    "cell",
    "header",
    "image",
    "figure",
    "equation",
    "formula",
    "document",
    "file",
    "material",
}
KG_CONTEXT_FILTER_CACHE_TAG = "AI_TUTOR_KG_CONTEXT_FILTER_V1"
KG_CONTEXT_NOISE_ENTITY_NAMES = {
    "unknown_entity",
    "unknown_entity (unknown)",
    "背景内容",
    "总体描述",
    "表格内容",
    "表内容",
    "表组织",
    "表结构",
    "行意义",
    "列意义",
    "若干行",
    "若干列",
    "若干行的行意义",
    "表的具体内容",
}
KG_CONTEXT_NOISE_TYPE_VALUES = {"", "none", "null", "unknown", "unknown_entity", "UNKNOWN"}
KG_CONTEXT_NOISE_RE = re.compile(
    r"(?:"
    r"unknown[_ ]?entity|"
    r"(?:若干|某些|清晰|明确|具体|总体|背景).{0,10}(?:行|列|表|表格|结构|组织|意义|描述|方式)|"
    r"(?:行|列|表|表格).{0,8}(?:意义|组织|描述|方式)|"
    r"(?:表的|表格的).{0,12}(?:具体|组织|意义|描述|方式|内容)|"
    r"^(?:行意义|列意义|总体描述|背景内容|问题分布)$"
    r")",
    re.IGNORECASE,
)


class RAGAnythingAdapter:
    """Official RAG-Anything-backed adapter with local DB metadata support."""

    def __init__(self) -> None:
        self._instances: dict[str, object] = {}
        self._instance_route_signatures: dict[str, str] = {}

    def _start_parse_stage(
        self,
        db: Any,
        task: FileParseTask,
        stage: str,
        *,
        label: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> float:
        started = perf_counter()
        extra = dict(task.extra_data or {})
        trace = dict(extra.get("stage_trace") or {})
        stages = dict(trace.get("stages") or {})
        previous = dict(stages.get(stage) or {})
        stages[stage] = {
            **previous,
            "stage": stage,
            "label": label or stage,
            "status": "running",
            "started_at": _utc_now_iso(),
            "finished_at": None,
            "elapsed_ms": None,
            "error": None,
            "details": details or previous.get("details") or {},
        }
        trace.update({
            "version": 1,
            "updated_at": _utc_now_iso(),
            "stages": stages,
        })
        extra["stage_trace"] = trace
        task.extra_data = extra
        db.add(task)
        db.commit()
        return started

    def _finish_parse_stage(
        self,
        db: Any,
        task: FileParseTask,
        stage: str,
        *,
        started: float | None = None,
        status: str = "completed",
        details: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        extra = dict(task.extra_data or {})
        trace = dict(extra.get("stage_trace") or {})
        stages = dict(trace.get("stages") or {})
        current = dict(stages.get(stage) or {"stage": stage, "label": stage})
        merged_details = dict(current.get("details") or {})
        if details:
            merged_details.update(details)
        current.update({
            "status": status,
            "finished_at": _utc_now_iso(),
            "elapsed_ms": round((perf_counter() - started) * 1000, 2) if started is not None else current.get("elapsed_ms"),
            "error": self._trace_preview(error, limit=800) if error else None,
            "details": merged_details,
        })
        stages[stage] = current
        trace.update({
            "version": 1,
            "updated_at": _utc_now_iso(),
            "stages": stages,
        })
        extra["stage_trace"] = trace
        task.extra_data = extra
        db.add(task)
        db.commit()

    def _attach_ingest_trace_summary(self, task: FileParseTask, trace: dict[str, Any] | None) -> None:
        if not isinstance(trace, dict):
            return
        extra = dict(task.extra_data or {})
        extra["model_call_trace"] = {
            "llm_call_count": int(trace.get("llm_call_count") or 0),
            "vision_call_count": int(trace.get("vision_call_count") or 0),
            "embedding_call_count": int(trace.get("embedding_call_count") or 0),
            "llm_timing_summary_ms": trace.get("llm_timing_summary_ms") or {},
            "vision_timing_summary_ms": trace.get("vision_timing_summary_ms") or {},
            "embedding_timing_summary_ms": trace.get("embedding_timing_summary_ms") or {},
            "llm_token_usage_summary": trace.get("llm_token_usage_summary") or {},
            "vision_token_usage_summary": trace.get("vision_token_usage_summary") or {},
            "embedding_token_estimate_summary": trace.get("embedding_token_estimate_summary") or {},
            "keyword_extraction_latency_ms": trace.get("keyword_extraction_latency_ms"),
            "knowledge_extraction_latency_ms": trace.get("knowledge_extraction_latency_ms"),
            "vlm_describe_latency_ms": trace.get("vlm_describe_latency_ms"),
        }
        extra["model_token_usage"] = {
            "llm": trace.get("llm_token_usage_summary") or {},
            "vision": trace.get("vision_token_usage_summary") or {},
            "embedding_estimate": trace.get("embedding_token_estimate_summary") or {},
            "note": (
                "LLM/VLM token usage is populated only when the provider returns usage. "
                "Embedding usage is estimated from indexed text because the LightRAG embedding wrapper does not expose provider usage."
            ),
        }
        task.extra_data = extra

    def _normalize_model_usage(self, usage: Any) -> dict[str, Any]:
        if usage is None:
            return {}
        if hasattr(usage, "model_dump"):
            raw = usage.model_dump()
        elif isinstance(usage, dict):
            raw = dict(usage)
        else:
            raw = {}
            for key in (
                "prompt_tokens",
                "completion_tokens",
                "total_tokens",
                "input_tokens",
                "output_tokens",
                "prompt_tokens_details",
                "completion_tokens_details",
            ):
                value = getattr(usage, key, None)
                if value is not None:
                    raw[key] = value
        prompt_tokens = self._safe_int(raw.get("prompt_tokens", raw.get("input_tokens")))
        completion_tokens = self._safe_int(raw.get("completion_tokens", raw.get("output_tokens")))
        total_tokens = self._safe_int(raw.get("total_tokens"))
        if total_tokens is None and prompt_tokens is not None and completion_tokens is not None:
            total_tokens = prompt_tokens + completion_tokens

        normalized = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }
        for key in ("input_tokens", "output_tokens", "prompt_tokens_details", "completion_tokens_details"):
            if raw.get(key) is not None:
                normalized[key] = raw.get(key)
        return {key: value for key, value in normalized.items() if value is not None}

    def _safe_int(self, value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _accumulate_token_usage(
        self,
        trace: dict[str, Any],
        *,
        summary_key: str,
        usage: dict[str, Any],
        purpose: str,
        model: str | None,
    ) -> None:
        if not usage:
            return
        summary = trace.setdefault(summary_key, {})
        if not isinstance(summary, dict):
            return

        def add_to(bucket: dict[str, Any]) -> None:
            bucket["count"] = int(bucket.get("count") or 0) + 1
            for key in ("prompt_tokens", "completion_tokens", "total_tokens", "input_tokens", "output_tokens"):
                value = self._safe_int(usage.get(key))
                if value is not None:
                    bucket[key] = int(bucket.get(key) or 0) + value

        total = summary.setdefault("total", {})
        if isinstance(total, dict):
            add_to(total)
        by_purpose = summary.setdefault("by_purpose", {})
        if isinstance(by_purpose, dict):
            bucket = by_purpose.setdefault(purpose or "unknown", {})
            if isinstance(bucket, dict):
                add_to(bucket)
        by_model = summary.setdefault("by_model", {})
        if isinstance(by_model, dict):
            bucket = by_model.setdefault(model or "unknown", {})
            if isinstance(bucket, dict):
                add_to(bucket)

    def _estimate_text_tokens(self, text: str) -> int:
        if not text:
            return 0
        cjk_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
        non_cjk_chars = max(0, len(text) - cjk_chars)
        return int(cjk_chars + max(1, round(non_cjk_chars / 4))) if text else 0

    def _record_embedding_trace(self, *, texts: list[str], model: str) -> dict[str, Any] | None:
        if not bool(getattr(settings, "RAG_QUERY_TRACE_ENABLED", True)):
            return None
        trace = _QUERY_TRACE_CONTEXT.get() or _INGEST_TRACE_CONTEXT.get()
        if not isinstance(trace, dict):
            return None
        calls = trace.setdefault("embedding_calls", [])
        if not isinstance(calls, list):
            return None
        normalized_texts = [str(text or "") for text in (texts or [])]
        char_count = sum(len(text) for text in normalized_texts)
        estimated_tokens = sum(self._estimate_text_tokens(text) for text in normalized_texts)
        call_trace = {
            "index": len(calls) + 1,
            "purpose": "embedding",
            "model": model,
            "started_at": _utc_now_iso(),
            "text_count": len(normalized_texts),
            "text_chars": char_count,
            "estimated_tokens": estimated_tokens,
        }
        calls.append(call_trace)
        trace["embedding_call_count"] = len(calls)
        return call_trace

    def _finish_embedding_trace(
        self,
        call_trace: dict[str, Any] | None,
        *,
        started_at: float,
        success: bool,
        error: str | None = None,
    ) -> None:
        if not isinstance(call_trace, dict):
            return
        elapsed_ms = round((perf_counter() - started_at) * 1000, 2)
        call_trace["elapsed_ms"] = elapsed_ms
        call_trace["success"] = bool(success)
        call_trace["finished_at"] = _utc_now_iso()
        if error:
            call_trace["error"] = self._trace_preview(error, limit=500)

        trace = _QUERY_TRACE_CONTEXT.get() or _INGEST_TRACE_CONTEXT.get()
        if not isinstance(trace, dict):
            return
        summary = trace.setdefault(
            "embedding_timing_summary_ms",
            {"count": 0, "total": 0.0, "max": 0.0, "success": 0, "failed": 0},
        )
        if isinstance(summary, dict):
            summary["count"] = int(summary.get("count") or 0) + 1
            summary["total"] = round(float(summary.get("total") or 0.0) + elapsed_ms, 2)
            summary["max"] = round(max(float(summary.get("max") or 0.0), elapsed_ms), 2)
            if success:
                summary["success"] = int(summary.get("success") or 0) + 1
            else:
                summary["failed"] = int(summary.get("failed") or 0) + 1
        estimate = trace.setdefault(
            "embedding_token_estimate_summary",
            {"count": 0, "text_count": 0, "text_chars": 0, "estimated_tokens": 0},
        )
        if isinstance(estimate, dict):
            estimate["count"] = int(estimate.get("count") or 0) + 1
            estimate["text_count"] = int(estimate.get("text_count") or 0) + int(call_trace.get("text_count") or 0)
            estimate["text_chars"] = int(estimate.get("text_chars") or 0) + int(call_trace.get("text_chars") or 0)
            estimate["estimated_tokens"] = int(estimate.get("estimated_tokens") or 0) + int(
                call_trace.get("estimated_tokens") or 0
            )

    async def _emit_progress(
        self,
        progress_callback: ProgressCallback | None,
        *,
        stage: str,
        status: str,
        label: str,
        started_at: float,
        details: dict[str, Any] | None = None,
    ) -> None:
        if progress_callback is None:
            return
        event: dict[str, Any] = {
            "stage": stage,
            "status": status,
            "label": label,
            "elapsed_ms": round((perf_counter() - started_at) * 1000, 2),
        }
        if details:
            event["details"] = details
        try:
            await progress_callback(event)
        except Exception as exc:  # pragma: no cover - progress reporting must be best-effort
            logger.debug("rag_progress_emit_failed", stage=stage, error=str(exc))

    def __del__(self):  # pragma: no cover - interpreter shutdown timing is environment-specific
        instances = list(getattr(self, "_instances", {}).items())
        for _, instance in instances:
            close = getattr(instance, "close", None)
            if not callable(close):
                continue
            try:
                result = close()
                if inspect.isawaitable(result):
                    try:
                        loop = asyncio.get_running_loop()
                    except RuntimeError:
                        asyncio.run(result)
                    else:
                        loop.create_task(result)
            except Exception:
                pass

    def _prepare_environment(self) -> None:
        python_dir = Path(sys.executable).resolve().parent
        candidate_dirs = [python_dir]
        if os.name == "nt":
            candidate_dirs.append(python_dir / "Scripts")
        else:
            candidate_dirs.append(python_dir / "bin")

        path_parts = [part for part in os.environ.get("PATH", "").split(os.pathsep) if part]
        for candidate in candidate_dirs:
            if candidate.exists():
                candidate_text = str(candidate)
                if candidate_text not in path_parts:
                    os.environ["PATH"] = candidate_text + os.pathsep + os.environ.get("PATH", "")
                    path_parts.insert(0, candidate_text)

        if settings.LIBREOFFICE_PATH:
            soffice_path = Path(settings.LIBREOFFICE_PATH)
            if soffice_path.exists():
                os.environ["SOFFICE_PATH"] = str(soffice_path)
                soffice_dir = str(soffice_path.parent)
                if soffice_dir not in path_parts:
                    os.environ["PATH"] = soffice_dir + os.pathsep + os.environ.get("PATH", "")

    def _apply_storage_env_overrides(self, env_overrides: dict[str, str]) -> None:
        for key, value in (env_overrides or {}).items():
            if value:
                os.environ[key] = str(value)

    def _schedule_close(self, instance: object | None, *, class_id: str | None = None, reason: str) -> None:
        if instance is None:
            return
        close = getattr(instance, "close", None)
        if not callable(close):
            return
        try:
            result = close()
            if inspect.isawaitable(result):
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    asyncio.run(result)
                else:
                    loop.create_task(result)
            logger.info(
                "raganything_instance_close_scheduled",
                class_id=class_id,
                reason=reason,
            )
        except Exception as exc:  # pragma: no cover - defensive cleanup path
            logger.warning(
                "raganything_instance_close_failed",
                class_id=class_id,
                reason=reason,
                error=str(exc),
            )

    async def aclose(self) -> None:
        for class_id, instance in list(self._instances.items()):
            close = getattr(instance, "close", None)
            if not callable(close):
                continue
            try:
                result = close()
                if inspect.isawaitable(result):
                    await result
                logger.info("raganything_instance_closed", class_id=class_id, reason="adapter_shutdown")
            except Exception as exc:  # pragma: no cover - defensive cleanup path
                logger.warning(
                    "raganything_instance_close_failed",
                    class_id=class_id,
                    reason="adapter_shutdown",
                    error=str(exc),
                )
        self._instances.clear()
        self._instance_route_signatures.clear()

    def _require_model_config(self, routing_snapshot: dict[str, Any]) -> None:
        generation = routing_snapshot.get("generation") or {}
        embedding = routing_snapshot.get("embedding") or {}

        if generation.get("effective_backend") == "mock":
            raise RuntimeError("RAG-Anything requires non-mock generation backend (api/local)")
        if embedding.get("effective_backend") == "mock":
            raise RuntimeError("RAG-Anything requires non-mock embedding backend (api/local)")
        if not generation.get("model"):
            raise RuntimeError("RAG-Anything requires llm model to be configured")
        if not embedding.get("model"):
            raise RuntimeError("RAG-Anything requires embedding model to be configured")

    async def _call_llm_api(
        self,
        *,
        prompt: str,
        system_prompt: str | None,
        history_messages: list[dict] | None,
        model: str,
        base_url: str,
        api_key: str,
        wire_api: str,
    ) -> tuple[str, dict[str, Any]]:
        if wire_api == "responses":
            input_items = []
            if system_prompt:
                input_items.append({
                    "role": "system",
                    "content": [{"type": "input_text", "text": system_prompt}],
                })
            for message in self._normalize_llm_history_messages(history_messages):
                input_items.append({
                    "role": message["role"],
                    "content": [{"type": "input_text", "text": message["content"]}],
                })
            input_items.append({
                "role": "user",
                "content": [{"type": "input_text", "text": prompt}],
            })

            endpoint = base_url.rstrip("/") + "/responses"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "x-api-key": api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            payload = {
                "model": model,
                "input": input_items,
            }
            last_error = None
            async with httpx.AsyncClient(timeout=180.0) as client:
                for attempt in range(3):
                    try:
                        response = await client.post(endpoint, headers=headers, json=payload)
                        response.raise_for_status()
                        data = response.json()
                        break
                    except httpx.HTTPStatusError as exc:
                        last_error = exc
                        if exc.response.status_code not in {429, 500, 502, 503, 504} or attempt == 2:
                            raise
                        await asyncio.sleep(2 ** attempt)
                    except Exception as exc:
                        last_error = exc
                        if attempt == 2:
                            raise
                        await asyncio.sleep(2 ** attempt)
                else:  # pragma: no cover
                    raise last_error

            usage = self._normalize_model_usage(data.get("usage"))
            if data.get("output_text"):
                return data["output_text"], usage

            texts = []
            for item in data.get("output", []) or []:
                for content in item.get("content", []) or []:
                    text = content.get("text")
                    if text:
                        texts.append(text)
            return "\n".join(texts), usage

        openai_module = importlib.import_module("openai")
        AsyncOpenAI = getattr(openai_module, "AsyncOpenAI")
        client = AsyncOpenAI(
            base_url=base_url or None,
            api_key=api_key,
        )
        try:
            chat_messages = []
            if system_prompt:
                chat_messages.append({"role": "system", "content": system_prompt})
            chat_messages.extend(self._normalize_llm_history_messages(history_messages))
            chat_messages.append({"role": "user", "content": prompt})
            response = await client.chat.completions.create(
                model=model,
                messages=chat_messages,
            )
            usage = self._normalize_model_usage(getattr(response, "usage", None))
            return response.choices[0].message.content or "", usage
        finally:
            await client.close()

    def _build_llm_func(self, routing_snapshot: dict[str, Any]):
        generation = routing_snapshot.get("generation") or {}
        extract_model = settings.EFFECTIVE_EXTRACT_MODEL
        extract_base = settings.EFFECTIVE_EXTRACT_API_BASE
        extract_api_key = settings.EFFECTIVE_EXTRACT_API_KEY
        generation_model = str(generation.get("model") or settings.LLM_MODEL)
        generation_base = str(generation.get("api_base") or settings.EFFECTIVE_LLM_API_BASE)
        generation_api_key = settings.EFFECTIVE_LLM_API_KEY

        async def _llm(prompt, system_prompt=None, history_messages=None, keyword_extraction=False, **kwargs):
            use_generation_model = self._is_answer_generation_prompt(prompt, system_prompt, keyword_extraction)
            model = generation_model if use_generation_model else extract_model
            base_url = generation_base if use_generation_model else extract_base
            api_key = generation_api_key if use_generation_model else extract_api_key
            wire_api = settings.LLM_WIRE_API if use_generation_model else settings.EXTRACT_WIRE_API
            call_trace = self._record_llm_trace(
                prompt=prompt,
                system_prompt=system_prompt,
                history_messages=history_messages,
                keyword_extraction=keyword_extraction,
                use_generation_model=use_generation_model,
                model=model,
                wire_api=wire_api,
            )
            started_at = perf_counter()
            try:
                llm_result = await self._call_llm_api(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    history_messages=history_messages,
                    model=model,
                    base_url=base_url,
                    api_key=api_key,
                    wire_api=wire_api,
                )
                if isinstance(llm_result, tuple):
                    response_text, usage = llm_result
                else:
                    response_text, usage = llm_result, {}
            except Exception as exc:
                self._finish_llm_trace(
                    call_trace,
                    started_at=started_at,
                    success=False,
                    error=str(exc),
                )
                raise
            self._finish_llm_trace(
                call_trace,
                started_at=started_at,
                success=True,
                response_text=response_text,
                usage=usage,
            )
            return response_text

        return _llm

    def _record_llm_trace(
        self,
        *,
        prompt: Any,
        system_prompt: Any,
        history_messages: list[dict] | None,
        keyword_extraction: bool,
        use_generation_model: bool,
        model: str,
        wire_api: str,
    ) -> dict[str, Any] | None:
        if not bool(getattr(settings, "RAG_QUERY_TRACE_ENABLED", True)):
            return None
        trace = _QUERY_TRACE_CONTEXT.get() or _INGEST_TRACE_CONTEXT.get()
        if not isinstance(trace, dict):
            return None

        calls = trace.setdefault("llm_calls", [])
        if not isinstance(calls, list):
            return None

        prompt_text = str(prompt or "")
        system_text = str(system_prompt or "")
        purpose = self._classify_llm_trace_purpose(
            prompt_text=prompt_text,
            system_text=system_text,
            keyword_extraction=keyword_extraction,
            use_generation_model=use_generation_model,
        )
        normalized_history = self._normalize_llm_history_messages(history_messages)
        call_trace = {
            "index": len(calls) + 1,
            "purpose": purpose,
            "keyword_extraction": bool(keyword_extraction),
            "uses_generation_model": bool(use_generation_model),
            "model": model,
            "wire_api": wire_api,
            "started_at": _utc_now_iso(),
            "prompt_chars": len(prompt_text),
            "system_prompt_chars": len(system_text),
            "history_message_count": len(normalized_history),
            "prompt_preview": self._trace_preview(prompt_text),
            "system_prompt_preview": self._trace_preview(system_text, limit=500),
        }
        calls.append(call_trace)
        trace["llm_call_count"] = len(calls)
        if purpose == "answer_generation":
            trace["final_generation_input"] = call_trace
        return call_trace

    def _classify_llm_trace_purpose(
        self,
        *,
        prompt_text: str,
        system_text: str,
        keyword_extraction: bool,
        use_generation_model: bool,
    ) -> str:
        if keyword_extraction:
            return "keyword_extraction"
        text = f"{system_text}\n{prompt_text}".lower()
        answer_markers = (
            "generate a comprehensive",
            "provided **context**",
            "provided context",
            "document chunks",
            "knowledge graph data",
            "answer user queries",
            "answer the user query",
            "references section",
            "reference document list",
            "strictly adhere to the provided context",
            "only using the information within the provided",
        )
        if use_generation_model or any(marker in text for marker in answer_markers):
            return "answer_generation"
        return "knowledge_extraction"

    def _finish_llm_trace(
        self,
        call_trace: dict[str, Any] | None,
        *,
        started_at: float,
        success: bool,
        response_text: Any = None,
        usage: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        if not isinstance(call_trace, dict):
            return
        elapsed_ms = round((perf_counter() - started_at) * 1000, 2)
        call_trace["elapsed_ms"] = elapsed_ms
        call_trace["success"] = bool(success)
        call_trace["finished_at"] = _utc_now_iso()
        if success:
            call_trace["response_chars"] = len(str(response_text or ""))
            normalized_usage = self._normalize_model_usage(usage)
            if normalized_usage:
                call_trace["token_usage"] = normalized_usage
        elif error:
            call_trace["error"] = self._trace_preview(error, limit=500)

        trace = _QUERY_TRACE_CONTEXT.get() or _INGEST_TRACE_CONTEXT.get()
        if not isinstance(trace, dict):
            return
        if success:
            normalized_usage = call_trace.get("token_usage") if isinstance(call_trace, dict) else None
            if isinstance(normalized_usage, dict) and normalized_usage:
                self._accumulate_token_usage(
                    trace,
                    summary_key="llm_token_usage_summary",
                    usage=normalized_usage,
                    purpose=str(call_trace.get("purpose") or "unknown"),
                    model=str(call_trace.get("model") or "unknown"),
                )
        purpose = str(call_trace.get("purpose") or "unknown")
        summary = trace.setdefault("llm_timing_summary_ms", {})
        if isinstance(summary, dict):
            bucket = summary.setdefault(
                purpose,
                {"count": 0, "total": 0.0, "max": 0.0, "success": 0, "failed": 0},
            )
            if isinstance(bucket, dict):
                bucket["count"] = int(bucket.get("count") or 0) + 1
                bucket["total"] = round(float(bucket.get("total") or 0.0) + elapsed_ms, 2)
                bucket["max"] = round(max(float(bucket.get("max") or 0.0), elapsed_ms), 2)
                if success:
                    bucket["success"] = int(bucket.get("success") or 0) + 1
                else:
                    bucket["failed"] = int(bucket.get("failed") or 0) + 1
        trace["llm_total_latency_ms"] = round(
            sum(
                float(call.get("elapsed_ms") or 0.0)
                for call in (trace.get("llm_calls") or [])
                if isinstance(call, dict)
            ),
            2,
        )
        for key in ("keyword_extraction", "answer_generation", "knowledge_extraction"):
            bucket = summary.get(key) if isinstance(summary, dict) else None
            if isinstance(bucket, dict):
                trace[f"{key}_latency_ms"] = round(float(bucket.get("total") or 0.0), 2)

    def _record_vision_trace(
        self,
        *,
        prompt: Any,
        system_prompt: Any,
        model: str,
        has_image: bool,
    ) -> dict[str, Any] | None:
        if not bool(getattr(settings, "RAG_QUERY_TRACE_ENABLED", True)):
            return None
        trace = _QUERY_TRACE_CONTEXT.get() or _INGEST_TRACE_CONTEXT.get()
        if not isinstance(trace, dict):
            return None
        calls = trace.setdefault("vision_calls", [])
        if not isinstance(calls, list):
            return None
        prompt_text = str(prompt or "")
        system_text = str(system_prompt or "")
        call_trace = {
            "index": len(calls) + 1,
            "purpose": "vlm_describe",
            "model": model,
            "has_image": bool(has_image),
            "started_at": _utc_now_iso(),
            "prompt_chars": len(prompt_text),
            "system_prompt_chars": len(system_text),
            "prompt_preview": self._trace_preview(prompt_text),
            "system_prompt_preview": self._trace_preview(system_text, limit=500),
        }
        calls.append(call_trace)
        trace["vision_call_count"] = len(calls)
        return call_trace

    def _finish_vision_trace(
        self,
        call_trace: dict[str, Any] | None,
        *,
        started_at: float,
        success: bool,
        response_text: Any = None,
        usage: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        if not isinstance(call_trace, dict):
            return
        elapsed_ms = round((perf_counter() - started_at) * 1000, 2)
        call_trace["elapsed_ms"] = elapsed_ms
        call_trace["success"] = bool(success)
        call_trace["finished_at"] = _utc_now_iso()
        if success:
            call_trace["response_chars"] = len(str(response_text or ""))
            normalized_usage = self._normalize_model_usage(usage)
            if normalized_usage:
                call_trace["token_usage"] = normalized_usage
        elif error:
            call_trace["error"] = self._trace_preview(error, limit=500)

        trace = _QUERY_TRACE_CONTEXT.get() or _INGEST_TRACE_CONTEXT.get()
        if not isinstance(trace, dict):
            return
        if success:
            normalized_usage = call_trace.get("token_usage") if isinstance(call_trace, dict) else None
            if isinstance(normalized_usage, dict) and normalized_usage:
                self._accumulate_token_usage(
                    trace,
                    summary_key="vision_token_usage_summary",
                    usage=normalized_usage,
                    purpose=str(call_trace.get("purpose") or "vlm_describe"),
                    model=str(call_trace.get("model") or "unknown"),
                )
        summary = trace.setdefault(
            "vision_timing_summary_ms",
            {"count": 0, "total": 0.0, "max": 0.0, "success": 0, "failed": 0},
        )
        if isinstance(summary, dict):
            summary["count"] = int(summary.get("count") or 0) + 1
            summary["total"] = round(float(summary.get("total") or 0.0) + elapsed_ms, 2)
            summary["max"] = round(max(float(summary.get("max") or 0.0), elapsed_ms), 2)
            if success:
                summary["success"] = int(summary.get("success") or 0) + 1
            else:
                summary["failed"] = int(summary.get("failed") or 0) + 1
            trace["vlm_describe_latency_ms"] = round(float(summary.get("total") or 0.0), 2)

    def _normalize_llm_history_messages(self, history_messages: list[dict] | None) -> list[dict[str, str]]:
        normalized: list[dict[str, str]] = []
        role_map = {
            "ai": "assistant",
            "assistant": "assistant",
            "bot": "assistant",
            "model": "assistant",
            "user": "user",
            "human": "user",
            "system": "system",
        }
        for message in history_messages or []:
            if not isinstance(message, dict):
                continue
            role = role_map.get(str(message.get("role") or "user").strip().lower(), "user")
            content = str(message.get("content") or "").strip()
            if not content:
                continue
            if role == "assistant" and self._looks_like_garbled_answer(content):
                logger.info("rag_llm_history_garbled_assistant_message_skipped")
                continue
            normalized.append({"role": role, "content": content})
        return normalized

    def _build_aquery_history(
        self,
        *,
        history: list[dict] | None,
        query_text: str,
    ) -> tuple[list[dict[str, str]], dict[str, Any]]:
        policy = str(getattr(settings, "RAG_AQUERY_HISTORY_POLICY", "compact") or "compact").strip().lower()
        normalized_history = self._normalize_llm_history_messages(history)
        max_messages = max(0, int(getattr(settings, "RAG_AQUERY_HISTORY_MAX_MESSAGES", 4) or 0))
        max_chars = max(80, int(getattr(settings, "RAG_AQUERY_HISTORY_MESSAGE_MAX_CHARS", 500) or 500))
        meta: dict[str, Any] = {
            "policy": policy,
            "input_count": len(normalized_history),
            "max_messages": max_messages,
            "message_max_chars": max_chars,
            "submitted_count": 0,
            "dropped_count": len(normalized_history),
        }
        if policy in {"none", "off", "disabled"} or max_messages <= 0 or not normalized_history:
            return [], meta

        candidates = normalized_history[-max_messages:] if policy == "full" else self._select_compact_aquery_history(
            history=normalized_history,
            query_text=query_text,
            max_messages=max_messages,
        )
        submitted = [
            {
                "role": item["role"],
                "content": self._truncate_history_content(item["content"], max_chars=max_chars),
            }
            for item in candidates[-max_messages:]
        ]
        meta.update({
            "submitted_count": len(submitted),
            "dropped_count": max(0, len(normalized_history) - len(submitted)),
            "submitted_roles": [item["role"] for item in submitted],
        })
        return submitted, meta

    def _select_compact_aquery_history(
        self,
        *,
        history: list[dict[str, str]],
        query_text: str,
        max_messages: int,
    ) -> list[dict[str, str]]:
        query_terms = set(self._history_overlap_terms(query_text))
        if not query_terms:
            return []
        selected: list[dict[str, str]] = []
        for message in reversed(history[-max(max_messages * 3, max_messages):]):
            content = message.get("content") or ""
            message_terms = set(self._history_overlap_terms(content))
            if not message_terms:
                continue
            if query_terms.intersection(message_terms) or self._history_text_overlaps_query(content, query_text):
                selected.append(message)
                if len(selected) >= max_messages:
                    break
        return list(reversed(selected))

    def _history_overlap_terms(self, text: str) -> list[str]:
        normalized = str(text or "").lower()
        latin = re.findall(r"[a-z][a-z0-9_./-]{1,}", normalized)
        cjk = re.findall(r"[\u4e00-\u9fff]{2,8}", normalized)
        terms = [term for term in [*latin, *cjk] if not self._is_noisy_retrieval_term(term)]
        return terms[:80]

    def _history_text_overlaps_query(self, content: str, query_text: str) -> bool:
        content_norm = re.sub(r"\s+", " ", str(content or "")).strip().lower()
        query_norm = re.sub(r"\s+", " ", str(query_text or "")).strip().lower()
        if len(content_norm) < 8 or len(query_norm) < 8:
            return False
        probe = content_norm[:120]
        return probe in query_norm or query_norm[:120] in content_norm

    def _truncate_history_content(self, content: str, *, max_chars: int) -> str:
        text = re.sub(r"\s+", " ", str(content or "")).strip()
        if len(text) <= max_chars:
            return text
        return text[:max_chars].rstrip() + "..."

    def _is_answer_generation_prompt(
        self,
        prompt: Any,
        system_prompt: Any,
        keyword_extraction: bool,
    ) -> bool:
        if keyword_extraction:
            return False
        text = f"{system_prompt or ''}\n{prompt or ''}".lower()
        answer_markers = (
            "generate a comprehensive",
            "provided **context**",
            "provided context",
            "document chunks",
            "knowledge graph data",
            "answer user queries",
            "answer the user query",
            "user query:",
            "references section",
            "reference document list",
            "strictly adhere to the provided context",
            "only using the information within the provided",
        )
        extraction_markers = (
            "entity_extraction",
            "extract entities",
            "entity_types",
            "relationship",
            "gleaning",
            "tuple_delimiter",
            "record_delimiter",
        )
        return any(marker in text for marker in answer_markers) and not any(
            marker in text for marker in extraction_markers
        )

    def _build_embedding_func(self, routing_snapshot: dict[str, Any]):
        embedding = routing_snapshot.get("embedding") or {}
        embedding_model = embedding.get("model") or settings.EMBEDDING_MODEL
        embedding_base = embedding.get("api_base") or settings.EFFECTIVE_EMBEDDING_API_BASE
        embedding_api_key = settings.EFFECTIVE_EMBEDDING_API_KEY

        openai_module = importlib.import_module("lightrag.llm.openai")
        utils_module = importlib.import_module("lightrag.utils")
        openai_embed = getattr(openai_module, "openai_embed")
        wrap_embedding_func_with_attrs = getattr(utils_module, "wrap_embedding_func_with_attrs")

        @wrap_embedding_func_with_attrs(
            embedding_dim=settings.EMBEDDING_DIM,
            max_token_size=8192,
            model_name=embedding_model,
        )
        async def _embedding(texts: list[str], **kwargs):
            normalized_texts = [str(text or "") for text in (texts or [])]
            call_trace = self._record_embedding_trace(texts=normalized_texts, model=embedding_model)
            started_at = perf_counter()
            try:
                result = await openai_embed.func(
                    texts,
                    model=embedding_model,
                    base_url=embedding_base or None,
                    api_key=embedding_api_key,
                    embedding_dim=settings.EMBEDDING_DIM,
                    **kwargs,
                )
            except Exception as exc:
                self._finish_embedding_trace(
                    call_trace,
                    started_at=started_at,
                    success=False,
                    error=str(exc),
                )
                raise
            self._finish_embedding_trace(
                call_trace,
                started_at=started_at,
                success=True,
            )
            return result

        return _embedding

    def _build_rerank_func(self, routing_snapshot: dict[str, Any]):
        reranker = routing_snapshot.get("reranker") or {}
        if reranker.get("effective_backend") in {None, "mock", "none"}:
            return None

        async def _rerank(query: str, documents: list[str], top_n: int | None = None, **kwargs):
            _ = kwargs
            candidates = [
                {
                    "_rerank_index": index,
                    "chunk_id": f"lightrag-rerank-{index}",
                    "raw_text": str(document or ""),
                    "retrieval_score": 0.0,
                }
                for index, document in enumerate(documents or [])
            ]
            reranked = await get_reranker().rerank(
                query=query,
                candidates=candidates,
                context={"retrieval_strategy": "lightrag_internal"},
            )
            results = []
            for item in reranked[: top_n or len(reranked)]:
                components = item.get("rerank_components") or {}
                score = (
                    components.get("remote_score")
                    or components.get("semantic_score")
                    or item.get("rerank_score")
                    or item.get("score")
                    or 0.0
                )
                results.append({
                    "index": int(item.get("_rerank_index", 0)),
                    "relevance_score": float(score),
                })
            return results

        return _rerank

    def _build_vision_func(self, routing_snapshot: dict[str, Any]):
        vlm = routing_snapshot.get("vlm") or {}
        vlm_base = vlm.get("api_base") or settings.EFFECTIVE_VLM_API_BASE
        vlm_model = vlm.get("model") or settings.EFFECTIVE_VLM_MODEL
        vlm_api_key = settings.EFFECTIVE_VLM_API_KEY

        async def _vision(prompt, image_data=None, system_prompt=None, messages=None, **kwargs):
            call_trace = self._record_vision_trace(
                prompt=prompt,
                system_prompt=system_prompt,
                model=vlm_model,
                has_image=bool(image_data),
            )
            started_at = perf_counter()
            openai_module = importlib.import_module("openai")
            AsyncOpenAI = getattr(openai_module, "AsyncOpenAI")
            client = AsyncOpenAI(
                base_url=vlm_base or None,
                api_key=vlm_api_key,
            )
            try:
                if messages is None:
                    built_messages = []
                    if system_prompt:
                        built_messages.append({"role": "system", "content": system_prompt})
                    if image_data:
                        content = []
                        if prompt:
                            content.append({"type": "text", "text": prompt})
                        content.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_data}"},
                        })
                        built_messages.append({"role": "user", "content": content})
                    else:
                        built_messages.append({"role": "user", "content": prompt})
                else:
                    built_messages = messages

                response = await client.chat.completions.create(
                    model=vlm_model,
                    messages=built_messages,
                    temperature=0.1,
                )
                response_text = response.choices[0].message.content or ""
                usage = self._normalize_model_usage(getattr(response, "usage", None))
                self._finish_vision_trace(
                    call_trace,
                    started_at=started_at,
                    success=True,
                    response_text=response_text,
                    usage=usage,
                )
                return response_text
            except Exception as exc:
                self._finish_vision_trace(
                    call_trace,
                    started_at=started_at,
                    success=False,
                    error=str(exc),
                )
                raise
            finally:
                await client.close()

        return _vision

    async def _describe_image_attachment(self, attachment: dict, question: str) -> str | None:
        image_data = (
            attachment.get("image_base64")
            or attachment.get("base64")
            or attachment.get("image_data")
        )
        if not image_data:
            url = attachment.get("data_url") or attachment.get("url")
            if isinstance(url, str) and url.startswith("data:image"):
                image_data = url.split(",", 1)[-1]
        routing_snapshot = self._load_runtime_routing_snapshot()
        vlm = routing_snapshot.get("vlm") or {}
        if not image_data or vlm.get("effective_backend") == "mock":
            return None

        vision = self._build_vision_func(routing_snapshot)
        description = await vision(
            prompt=f"Describe the educational content in this image to help answer the question: {question}",
            image_data=image_data,
            system_prompt="You are assisting a course AI tutor. Extract the question content, visible text, diagrams, and any problem-solving cues from the image.",
        )
        return description.strip() if description else None

    def _install_lightrag_context_filter(self) -> None:
        if not bool(getattr(settings, "RAG_KG_CONTEXT_FILTER_ENABLED", True)):
            return
        try:
            operate_module = importlib.import_module("lightrag.operate")
        except Exception as exc:
            logger.warning("lightrag_context_filter_install_failed", error=str(exc))
            return

        existing = getattr(operate_module, "_build_query_context", None)
        if existing is None or getattr(existing, "_ai_tutor_kg_filter_installed", False):
            return

        adapter = self

        async def _filtered_build_query_context(
            query: str,
            ll_keywords: str,
            hl_keywords: str,
            knowledge_graph_inst: Any,
            entities_vdb: Any,
            relationships_vdb: Any,
            text_chunks_db: Any,
            query_param: Any,
            chunks_vdb: Any = None,
        ) -> Any:
            if not query:
                operate_module.logger.warning("Query is empty, skipping context building")
                return None

            search_result = await operate_module._perform_kg_search(
                query,
                ll_keywords,
                hl_keywords,
                knowledge_graph_inst,
                entities_vdb,
                relationships_vdb,
                text_chunks_db,
                query_param,
                chunks_vdb,
            )
            filter_report = adapter._filter_lightrag_search_result(
                search_result=search_result,
                query=query,
                ll_keywords=ll_keywords,
                hl_keywords=hl_keywords,
                query_param=query_param,
            )

            if not search_result["final_entities"] and not search_result["final_relations"]:
                if query_param.mode != "mix":
                    return None
                if not search_result["chunk_tracking"]:
                    return None

            truncation_result = await operate_module._apply_token_truncation(
                search_result,
                query_param,
                text_chunks_db.global_config,
            )

            merged_chunks = await operate_module._merge_all_chunks(
                filtered_entities=truncation_result["filtered_entities"],
                filtered_relations=truncation_result["filtered_relations"],
                vector_chunks=search_result["vector_chunks"],
                query=query,
                knowledge_graph_inst=knowledge_graph_inst,
                text_chunks_db=text_chunks_db,
                query_param=query_param,
                chunks_vdb=chunks_vdb,
                chunk_tracking=search_result["chunk_tracking"],
                query_embedding=search_result["query_embedding"],
            )

            if (
                not merged_chunks
                and not truncation_result["entities_context"]
                and not truncation_result["relations_context"]
            ):
                return None

            context, raw_data = await operate_module._build_context_str(
                entities_context=truncation_result["entities_context"],
                relations_context=truncation_result["relations_context"],
                merged_chunks=merged_chunks,
                query=query,
                query_param=query_param,
                global_config=text_chunks_db.global_config,
                chunk_tracking=search_result["chunk_tracking"],
                entity_id_to_original=truncation_result["entity_id_to_original"],
                relation_id_to_original=truncation_result["relation_id_to_original"],
            )

            metadata = raw_data.setdefault("metadata", {})
            metadata["keywords"] = {
                "high_level": hl_keywords.split(", ") if hl_keywords else [],
                "low_level": ll_keywords.split(", ") if ll_keywords else [],
            }
            metadata["processing_info"] = {
                "total_entities_found": filter_report["entities_before"],
                "total_relations_found": filter_report["relations_before"],
                "entities_after_filter": filter_report["entities_after"],
                "relations_after_filter": filter_report["relations_after"],
                "entities_after_truncation": len(truncation_result.get("filtered_entities", [])),
                "relations_after_truncation": len(truncation_result.get("filtered_relations", [])),
                "merged_chunks_count": len(merged_chunks),
                "final_chunks_count": len(raw_data.get("data", {}).get("chunks", [])),
            }
            metadata["ai_tutor_kg_context_filter"] = filter_report
            return operate_module.QueryContextResult(context=context, raw_data=raw_data)

        _filtered_build_query_context._ai_tutor_kg_filter_installed = True  # type: ignore[attr-defined]
        _filtered_build_query_context._ai_tutor_original = existing  # type: ignore[attr-defined]
        operate_module._build_query_context = _filtered_build_query_context
        logger.info("lightrag_context_filter_installed")

    def _filter_lightrag_search_result(
        self,
        *,
        search_result: dict[str, Any],
        query: str,
        ll_keywords: str,
        hl_keywords: str,
        query_param: Any,
    ) -> dict[str, Any]:
        entities = list(search_result.get("final_entities") or [])
        relations = list(search_result.get("final_relations") or [])
        vector_chunks = list(search_result.get("vector_chunks") or [])
        mode = str(getattr(query_param, "mode", "") or "")
        terms = self._kg_filter_terms(query=query, ll_keywords=ll_keywords, hl_keywords=hl_keywords)
        preferred_files = self._preferred_vector_files(vector_chunks, terms=terms)
        kept_vector_chunks = self._filter_vector_chunks_by_preferred_files(
            vector_chunks,
            preferred_files=preferred_files if mode == "mix" else set(),
        )
        if len(kept_vector_chunks) != len(vector_chunks):
            kept_chunk_ids = {
                str(chunk.get("chunk_id") or chunk.get("id") or "")
                for chunk in kept_vector_chunks
                if isinstance(chunk, dict)
            }
            chunk_tracking = dict(search_result.get("chunk_tracking") or {})
            search_result["chunk_tracking"] = {
                chunk_id: value
                for chunk_id, value in chunk_tracking.items()
                if chunk_id in kept_chunk_ids
            }
            search_result["vector_chunks"] = kept_vector_chunks

        kept_entities = []
        dropped_entity_reasons: dict[str, int] = {}
        kept_entity_names: set[str] = set()
        for entity in entities:
            keep, reason = self._should_keep_kg_entity(
                entity,
                terms=terms,
                preferred_files=preferred_files if mode == "mix" else set(),
            )
            if keep:
                kept_entities.append(entity)
                name = self._kg_entity_name(entity)
                if name:
                    kept_entity_names.add(name)
            else:
                dropped_entity_reasons[reason] = dropped_entity_reasons.get(reason, 0) + 1

        kept_relations = []
        dropped_relation_reasons: dict[str, int] = {}
        for relation in relations:
            keep, reason = self._should_keep_kg_relation(
                relation,
                terms=terms,
                preferred_files=preferred_files if mode == "mix" else set(),
                kept_entity_names=kept_entity_names,
            )
            if keep:
                kept_relations.append(relation)
            else:
                dropped_relation_reasons[reason] = dropped_relation_reasons.get(reason, 0) + 1

        search_result["final_entities"] = kept_entities
        search_result["final_relations"] = kept_relations
        report = {
            "enabled": True,
            "mode": mode,
            "cache_tag": KG_CONTEXT_FILTER_CACHE_TAG,
            "preferred_vector_file_limit": max(
                0,
                int(getattr(settings, "RAG_KG_CONTEXT_FILTER_VECTOR_FILE_LIMIT", 3) or 0),
            ),
            "preferred_vector_files": sorted(preferred_files),
            "terms": sorted(terms)[:24],
            "entities_before": len(entities),
            "entities_after": len(kept_entities),
            "entities_dropped": len(entities) - len(kept_entities),
            "entity_drop_reasons": dropped_entity_reasons,
            "relations_before": len(relations),
            "relations_after": len(kept_relations),
            "relations_dropped": len(relations) - len(kept_relations),
            "relation_drop_reasons": dropped_relation_reasons,
            "vector_chunks_before": len(vector_chunks),
            "vector_chunks_after": len(kept_vector_chunks),
            "vector_chunks_dropped": len(vector_chunks) - len(kept_vector_chunks),
        }
        logger.info(
            "lightrag_context_filter_applied",
            mode=mode,
            entities_before=len(entities),
            entities_after=len(kept_entities),
            relations_before=len(relations),
            relations_after=len(kept_relations),
            vector_chunks_before=len(vector_chunks),
            vector_chunks_after=len(kept_vector_chunks),
            preferred_files=len(preferred_files),
        )
        return report

    def _preferred_vector_files(self, vector_chunks: list[dict], *, terms: set[str]) -> set[str]:
        limit = max(0, int(getattr(settings, "RAG_KG_CONTEXT_FILTER_VECTOR_FILE_LIMIT", 3) or 0))
        if limit <= 0:
            return set()
        preferred: list[str] = []
        fallback: list[str] = []
        for chunk in vector_chunks:
            path = self._kg_item_file(chunk)
            if path and path not in fallback:
                fallback.append(path)
            chunk_text = self._kg_item_text(chunk)
            if path and path not in preferred and self._kg_text_matches_terms(chunk_text, terms):
                preferred.append(path)
            if len(preferred) >= limit:
                break
        if not preferred:
            preferred = fallback[:1]
        return set(preferred)

    def _filter_vector_chunks_by_preferred_files(
        self,
        vector_chunks: list[dict],
        *,
        preferred_files: set[str],
    ) -> list[dict]:
        if not preferred_files:
            return vector_chunks
        return [
            chunk
            for chunk in vector_chunks
            if self._kg_item_file(chunk) in preferred_files
        ]

    def _kg_filter_terms(self, *, query: str, ll_keywords: str, hl_keywords: str) -> set[str]:
        text = f"{query or ''},{ll_keywords or ''},{hl_keywords or ''}"
        pieces = [
            item.strip()
            for item in re.split(r"[,，;；、\s:：?？!！()（）\[\]【】\"'“”‘’]+", text)
            if len(item.strip()) >= 2
        ]
        terms: set[str] = set(pieces)
        for cjk in re.findall(r"[\u4e00-\u9fff]{2,}", text):
            if len(cjk) <= 12:
                terms.add(cjk)
            max_n = min(6, len(cjk))
            for size in range(2, max_n + 1):
                for index in range(0, len(cjk) - size + 1):
                    terms.add(cjk[index:index + size])
        return {term for term in terms if not self._is_generic_kg_filter_term(term)}

    def _is_generic_kg_filter_term(self, term: str) -> bool:
        normalized = str(term or "").strip().lower()
        return normalized in {
            "什么",
            "是谁",
            "做了",
            "事情",
            "是什么",
            "为什么",
            "如何",
            "怎么",
            "哪些",
            "the",
            "and",
            "what",
            "how",
            "why",
        }

    def _should_keep_kg_entity(
        self,
        entity: Any,
        *,
        terms: set[str],
        preferred_files: set[str],
    ) -> tuple[bool, str]:
        name = self._kg_entity_name(entity)
        text = self._kg_item_text(entity)
        item_file = self._kg_item_file(entity)
        term_match = self._kg_text_matches_terms(text, terms)
        preferred_source = bool(item_file and item_file in preferred_files)
        noisy = self._is_noisy_kg_entity(entity)

        if noisy and not term_match:
            return False, "noisy_entity"
        if preferred_files and not preferred_source and not term_match:
            return False, "outside_preferred_vector_files"
        if not name:
            return False, "missing_entity_name"
        return True, "kept"

    def _should_keep_kg_relation(
        self,
        relation: Any,
        *,
        terms: set[str],
        preferred_files: set[str],
        kept_entity_names: set[str],
    ) -> tuple[bool, str]:
        src, tgt = self._kg_relation_endpoints(relation)
        text = self._kg_item_text(relation)
        item_file = self._kg_item_file(relation)
        term_match = self._kg_text_matches_terms(text, terms)
        preferred_source = bool(item_file and item_file in preferred_files)

        if self._is_noisy_kg_relation(relation):
            return False, "noisy_relation"
        if kept_entity_names and src not in kept_entity_names and tgt not in kept_entity_names:
            return False, "endpoint_not_kept"
        if preferred_files and not preferred_source and not term_match:
            return False, "outside_preferred_vector_files"
        if not src or not tgt:
            return False, "missing_relation_endpoint"
        return True, "kept"

    def _is_noisy_kg_entity(self, entity: Any) -> bool:
        if not isinstance(entity, dict):
            return True
        name = self._kg_entity_name(entity)
        entity_type = str(entity.get("entity_type") or entity.get("type") or "").strip()
        text = self._kg_item_text(entity)
        normalized_name = name.strip().lower()
        if normalized_name in KG_CONTEXT_NOISE_ENTITY_NAMES:
            return True
        if "unknown_entity" in normalized_name:
            return True
        if entity_type in KG_CONTEXT_NOISE_TYPE_VALUES and KG_CONTEXT_NOISE_RE.search(text):
            return True
        return bool(KG_CONTEXT_NOISE_RE.search(name))

    def _is_noisy_kg_relation(self, relation: Any) -> bool:
        if not isinstance(relation, dict):
            return True
        src, tgt = self._kg_relation_endpoints(relation)
        text = self._kg_item_text(relation)
        if KG_CONTEXT_NOISE_RE.search(src) or KG_CONTEXT_NOISE_RE.search(tgt):
            return True
        if "unknown_entity" in src.lower() or "unknown_entity" in tgt.lower():
            return True
        return bool(KG_CONTEXT_NOISE_RE.search(text))

    def _kg_entity_name(self, entity: Any) -> str:
        if not isinstance(entity, dict):
            return ""
        return str(entity.get("entity_name") or entity.get("entity") or entity.get("name") or "").strip()

    def _kg_relation_endpoints(self, relation: Any) -> tuple[str, str]:
        if not isinstance(relation, dict):
            return "", ""
        if isinstance(relation.get("src_tgt"), (list, tuple)) and len(relation["src_tgt"]) >= 2:
            return str(relation["src_tgt"][0] or "").strip(), str(relation["src_tgt"][1] or "").strip()
        return str(relation.get("src_id") or relation.get("entity1") or "").strip(), str(
            relation.get("tgt_id") or relation.get("entity2") or ""
        ).strip()

    def _kg_item_file(self, item: Any) -> str:
        if not isinstance(item, dict):
            return ""
        path = str(item.get("file_path") or item.get("source_path") or item.get("path") or "").strip()
        return path

    def _kg_item_text(self, item: Any) -> str:
        if not isinstance(item, dict):
            return ""
        values = [
            item.get("entity_name"),
            item.get("entity"),
            item.get("name"),
            item.get("entity_type"),
            item.get("type"),
            item.get("src_id"),
            item.get("tgt_id"),
            item.get("entity1"),
            item.get("entity2"),
            item.get("description"),
            item.get("keywords"),
            item.get("content"),
            item.get("text"),
            item.get("snippet"),
        ]
        return " ".join(str(value or "") for value in values)

    def _kg_text_matches_terms(self, text: str, terms: set[str]) -> bool:
        if not text or not terms:
            return False
        return any(term in text for term in terms if len(term) >= 2)

    def _get_instance(self, class_id: str):
        routing_snapshot = self._load_runtime_routing_snapshot()
        storage_plan = build_lightrag_storage_plan(class_id)
        routing_signature = self._routing_signature(routing_snapshot, storage_plan)
        if class_id in self._instances and self._instance_route_signatures.get(class_id) == routing_signature:
            return self._instances[class_id]
        stale_instance = self._instances.get(class_id)

        self._prepare_environment()
        self._apply_storage_env_overrides(storage_plan.get("env_overrides") or {})
        self._require_model_config(routing_snapshot)

        raganything_module = importlib.import_module("raganything")
        config_module = importlib.import_module("raganything.config")
        self._install_lightrag_context_filter()
        RAGAnything = getattr(raganything_module, "RAGAnything")
        RAGAnythingConfig = getattr(config_module, "RAGAnythingConfig")
        prompt_override_status = apply_framework_prompt_overrides(settings)

        working_dir = (Path(settings.RAGANYTHING_WORKING_DIR) / class_id).resolve()
        output_dir = (Path(settings.RAGANYTHING_OUTPUT_DIR) / class_id).resolve()
        working_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        config = RAGAnythingConfig(
            working_dir=str(working_dir),
            parser_output_dir=str(output_dir),
            parser=settings.RAGANYTHING_PARSER,
            parse_method=settings.RAGANYTHING_PARSE_METHOD,
            max_concurrent_files=settings.RAGANYTHING_MAX_CONCURRENT_FILES,
            use_full_path=True,
        )

        generation = routing_snapshot.get("generation") or {}
        embedding = routing_snapshot.get("embedding") or {}
        vlm = routing_snapshot.get("vlm") or {}
        llm_model_name = settings.EFFECTIVE_EXTRACT_MODEL or generation.get("model") or settings.LLM_MODEL
        embedding_func = self._build_embedding_func(routing_snapshot)
        rerank_func = self._build_rerank_func(routing_snapshot)
        lightrag_kwargs = {
            "llm_model_name": llm_model_name,
            "embedding_func": embedding_func,
            "working_dir": str(working_dir),
            "llm_model_max_async": 1,
            "default_llm_timeout": settings.RAGANYTHING_DEFAULT_LLM_TIMEOUT_SECONDS,
        }
        lightrag_kwargs.update(storage_plan.get("lightrag_kwargs") or {})
        self._attach_lightrag_addon_params(lightrag_kwargs)
        if rerank_func is not None:
            lightrag_kwargs["rerank_model_func"] = rerank_func

        instance = RAGAnything(
            llm_model_func=self._build_llm_func(routing_snapshot),
            vision_model_func=self._build_vision_func(routing_snapshot) if vlm.get("effective_backend") != "mock" else None,
            embedding_func=embedding_func,
            config=config,
            lightrag_kwargs=lightrag_kwargs,
        )
        if not instance.check_parser_installation():
            raise RuntimeError("RAG-Anything parser installation check failed")

        self._instances[class_id] = instance
        self._instance_route_signatures[class_id] = routing_signature
        if prompt_override_status.get("enabled"):
            logger.info(
                "raganything_education_prompts_active",
                class_id=class_id,
                status=prompt_override_status,
                addon_params=bool(lightrag_kwargs.get("addon_params")),
            )
        if stale_instance is not None and stale_instance is not instance:
            self._schedule_close(stale_instance, class_id=class_id, reason="route_signature_changed")
        return instance

    def _attach_lightrag_addon_params(self, lightrag_kwargs: dict[str, Any]) -> None:
        addon_params = build_lightrag_addon_params(settings)
        if not addon_params:
            return
        try:
            lightrag_module = importlib.import_module("lightrag")
            LightRAG = getattr(lightrag_module, "LightRAG", None)
            supports_addon_params = (
                LightRAG is not None
                and "addon_params" in inspect.signature(LightRAG).parameters
            )
        except Exception as exc:  # pragma: no cover - depends on optional package version
            logger.debug("lightrag_addon_params_probe_failed", reason=str(exc))
            supports_addon_params = False

        if not supports_addon_params:
            logger.info("lightrag_addon_params_not_supported_by_runtime")
            return
        lightrag_kwargs["addon_params"] = {
            **dict(lightrag_kwargs.get("addon_params") or {}),
            **addon_params,
        }

    def _load_runtime_routing_snapshot(self) -> dict[str, Any]:
        snapshot = model_routing_service.build_runtime_model_routing_snapshot()
        if snapshot:
            return snapshot
        return model_routing_service.build_model_routing_snapshot()

    def _routing_signature(self, snapshot: dict[str, Any], storage_plan: dict[str, Any] | None = None) -> str:
        generation = snapshot.get("generation") or {}
        embedding = snapshot.get("embedding") or {}
        vlm = snapshot.get("vlm") or {}
        reranker = snapshot.get("reranker") or {}
        parts = [
            str(generation.get("effective_backend") or ""),
            str(generation.get("model") or ""),
            str(generation.get("api_base") or ""),
            str(embedding.get("effective_backend") or ""),
            str(embedding.get("model") or ""),
            str(embedding.get("api_base") or ""),
            str(vlm.get("effective_backend") or ""),
            str(vlm.get("model") or ""),
            str(vlm.get("api_base") or ""),
            str(reranker.get("effective_backend") or ""),
            str(reranker.get("model") or ""),
            str(reranker.get("api_base") or ""),
        ]
        if storage_plan:
            parts.extend([
                str(storage_plan.get("requested_backend") or ""),
                str(storage_plan.get("effective_backend") or ""),
                str(storage_plan.get("workspace") or ""),
                str((storage_plan.get("lightrag_kwargs") or {}).get("vector_storage") or ""),
                str((storage_plan.get("lightrag_kwargs") or {}).get("graph_storage") or ""),
            ])
            for key, value in sorted((storage_plan.get("env_overrides") or {}).items()):
                if any(token in key for token in {"KEY", "PASSWORD"}):
                    value = hashlib.sha256(str(value).encode("utf-8")).hexdigest()
                parts.append(f"{key}={value}")
        return "|".join(parts)

    async def _insert_preprocessed_content_list(
        self,
        *,
        rag: object,
        preprocess_result: PreprocessResult,
        material_id: str,
    ) -> None:
        method = getattr(rag, "insert_content_list", None)
        if method is None:
            raise RuntimeError("RAG-Anything instance does not expose insert_content_list for preprocessed multimodal input")

        kwargs = {
            "content_list": preprocess_result.content_list,
            "file_path": preprocess_result.source_file,
            "doc_id": material_id,
        }
        try:
            result = method(**kwargs)
        except TypeError:
            result = method(preprocess_result.content_list)
        if inspect.isawaitable(result):
            await result

    async def delete_material_index(
        self,
        *,
        class_id: str,
        material_id: str,
        delete_llm_cache: bool = False,
    ) -> dict[str, Any]:
        """Delete a material's document-level LightRAG index when supported."""

        try:
            rag = self._get_instance(class_id)
            lightrag = getattr(rag, "lightrag", None)
            delete_method = getattr(lightrag, "adelete_by_doc_id", None) if lightrag is not None else None
            if not callable(delete_method):
                return {
                    "supported": False,
                    "deleted": False,
                    "reason": "lightrag_doc_delete_not_available",
                }

            result = delete_method(material_id, delete_llm_cache=delete_llm_cache)
            if inspect.isawaitable(result):
                result = await result
            return {
                "supported": True,
                "deleted": True,
                "doc_id": material_id,
                "result": str(result)[:500],
            }
        except Exception as exc:
            logger.warning(
                "raganything_material_index_delete_failed",
                class_id=class_id,
                material_id=material_id,
                error=str(exc),
            )
            return {
                "supported": True,
                "deleted": False,
                "doc_id": material_id,
                "error": str(exc),
            }

    def _build_content_list_processing_status(self, preprocess_result: PreprocessResult) -> dict[str, Any]:
        has_text = any((item.get("text") or item.get("caption")) for item in preprocess_result.content_list)
        has_visual = any((item.get("type") in {"image", "figure"}) for item in preprocess_result.content_list)
        metadata_only = preprocess_result.metadata.get("preprocess_quality") == "metadata_only"
        return {
            "text_processed": bool(has_text),
            "multimodal_processed": preprocess_result.modality != "video" or has_visual,
            "fully_processed": bool(has_text) and not preprocess_result.warnings and not metadata_only,
            "preprocess_warnings": preprocess_result.warnings,
            "preprocess": self._preprocess_result_to_metadata(preprocess_result),
            "entrypoint": "insert_content_list",
        }

    async def _get_document_processing_status(
        self,
        rag: object,
        material_id: str,
        preprocess_result: PreprocessResult,
    ) -> dict[str, Any]:
        method = getattr(rag, "get_document_processing_status", None)
        if not callable(method):
            return {}
        try:
            status = method(material_id)
            if inspect.isawaitable(status):
                status = await status
        except Exception as exc:
            logger.warning(
                "raganything_document_status_lookup_failed",
                material_id=material_id,
                error=str(exc),
            )
            return {}
        if not isinstance(status, dict):
            return {}
        normalized = self._normalize_processing_status(status, preprocess_result)
        raw_status = str(normalized.get("status") or "").strip().lower()
        has_error = bool(self._extract_processing_error(normalized).get("message"))
        if raw_status in {"failed", "error"} or has_error:
            normalized["fully_processed"] = False
        return normalized

    def _normalize_processing_status(
        self,
        status: Any,
        preprocess_result: PreprocessResult,
    ) -> dict[str, Any]:
        if not isinstance(status, dict):
            status = {"raw_status": status}
        normalized = {
            **status,
            "entrypoint": status.get("entrypoint") or preprocess_result.metadata.get("raganything_entrypoint"),
            "preprocess": self._preprocess_result_to_metadata(preprocess_result),
        }
        normalized.setdefault("text_processed", bool(status.get("text_processed") or status.get("fully_processed")))
        normalized.setdefault("multimodal_processed", bool(status.get("multimodal_processed") or status.get("fully_processed")))
        normalized.setdefault("fully_processed", bool(status.get("fully_processed")))
        return normalized

    def _extract_processing_error(self, status: dict[str, Any]) -> dict[str, str | None]:
        message = self._find_payload_text(status, {"error_msg", "error_message", "error", "exception", "traceback"})
        if not message:
            return {"message": None, "category": None}

        lowered = message.lower()
        if "api key is invalid" in lowered or "authenticationerror" in lowered or "401" in lowered:
            category = "llm_authentication"
        elif "permissiondenied" in lowered or "request was blocked" in lowered or "403" in lowered:
            category = "llm_permission"
        elif "rate limit" in lowered or "429" in lowered:
            category = "llm_rate_limit"
        elif "timeout" in lowered or "timed out" in lowered:
            category = "llm_timeout"
        else:
            category = "raganything_processing"

        clean_message = re.sub(r"\s+", " ", message).strip()
        return {"message": clean_message[:1200], "category": category}

    def _build_metadata_payload(
        self,
        *,
        class_id: str,
        material_id: str,
        status: dict[str, Any],
        preprocess_result: PreprocessResult,
        file_path: str,
        mime_type: str,
        file_name: str,
    ) -> dict[str, Any]:
        content_items = self._find_payload_list(status, {"content_items", "contents", "multimodal_content"})
        chunks = self._find_payload_list(status, {"chunks", "text_chunks", "chunk_list"})
        keywords = self._normalize_keywords(
            self._find_payload_list(status, {"keywords", "key_words", "entities", "entity_names"})
        )
        summary = self._find_payload_text(status, {"summary", "document_summary", "abstract"})
        metadata_source = "raganything"

        lightrag_output = None
        if preprocess_result.mode == "direct_document" and (not content_items or not chunks or not summary):
            official_output = self._load_official_output_metadata(
                class_id=class_id,
                file_path=file_path,
                file_name=file_name,
                mime_type=mime_type,
            )
            if official_output:
                content_items = content_items or official_output["content_items"]
                chunks = chunks or official_output["chunks"]
                summary = summary or official_output["summary"]
                metadata_source = official_output["metadata_source"]

        lightrag_output = self._load_lightrag_document_metadata(
            class_id=class_id,
            material_id=material_id,
            file_name=file_name,
        )
        if lightrag_output:
            content_items = (
                self._merge_content_items(content_items, lightrag_output["content_items"])
                if content_items
                else lightrag_output["content_items"]
            )
            chunks = self._merge_metadata_chunks(lightrag_output["chunks"], chunks)
            keywords = keywords or lightrag_output["keywords"]
            if not summary or self._is_media_only_markdown(summary):
                summary = lightrag_output["summary"]
            metadata_source = (
                f"{metadata_source}+{lightrag_output['metadata_source']}"
                if metadata_source and metadata_source != lightrag_output["metadata_source"]
                else lightrag_output["metadata_source"]
            )

        if preprocess_result.content_list:
            if content_items:
                content_items = self._merge_content_items(content_items, preprocess_result.content_list)
                if "preprocessed_content_list" not in metadata_source:
                    metadata_source = f"{metadata_source}+preprocessed_content_list"
            else:
                content_items = preprocess_result.content_list
                metadata_source = "preprocessed_content_list"
            chunks = self._merge_metadata_chunks(
                chunks,
                self._chunks_from_content_items(preprocess_result.content_list, file_name),
            )
        if not chunks and content_items:
            chunks = self._chunks_from_content_items(content_items, file_name)
        text = self._text_from_chunks_or_items(chunks, content_items)

        has_official_payload = bool(chunks or content_items or keywords or summary)
        if settings.RAGANYTHING_REQUIRE_OFFICIAL_METADATA and preprocess_result.mode == "direct_document" and not has_official_payload:
            raise RuntimeError(
                "RAG-Anything did not expose official chunks/content metadata for this document. "
                "Disable RAGANYTHING_REQUIRE_OFFICIAL_METADATA or add a result extractor for the configured RAG-Anything version."
            )

        if settings.RAGANYTHING_METADATA_FALLBACK_ENABLED and (not chunks or not text):
            fallback = self._build_adapter_metadata_fallback(file_path, mime_type, file_name)
            if not chunks:
                chunks = fallback["chunks"]
            if not text:
                text = fallback["text"]
            if not content_items:
                content_items = fallback["content_items"]
            if not keywords:
                keywords = fallback["keywords"]
            if not summary:
                summary = fallback["summary"]
            metadata_source = f"{metadata_source}+adapter_metadata_fallback"

        if not summary:
            summary = (text or f"Indexed material: {file_name}")[:500]
        if not keywords:
            keywords = self._fallback_keywords(text or file_name)

        return {
            "text": text or summary,
            "chunks": chunks or self._chunks_from_content_items(content_items, file_name),
            "keywords": keywords,
            "content_items": content_items,
            "summary": summary,
            "metadata_source": metadata_source,
        }

    def _load_official_output_metadata(
        self,
        *,
        class_id: str,
        file_path: str,
        file_name: str,
        mime_type: str,
    ) -> dict[str, Any] | None:
        stem = Path(file_name).stem
        storage_stem = Path(file_path).stem
        class_output_root = (Path(settings.RAGANYTHING_OUTPUT_DIR) / class_id).resolve()
        output_roots = [
            class_output_root / stem,
            class_output_root / storage_stem,
        ]
        if class_output_root.exists():
            output_roots.extend(class_output_root.glob(f"{storage_stem}_*"))
            output_roots.extend(class_output_root.glob(f"{stem}_*"))
        output_roots = [root for root in output_roots if root.exists()]
        if not output_roots:
            return None

        content_list_path = self._latest_existing_path(
            output_roots,
            [f"{stem}_content_list.json", f"{stem}_content_list_v2.json"],
        )
        if not content_list_path and storage_stem != stem:
            content_list_path = self._latest_existing_path(
                output_roots,
                [f"{storage_stem}_content_list.json", f"{storage_stem}_content_list_v2.json"],
            )
        markdown_path = self._latest_existing_path(
            output_roots,
            [f"{stem}.md", f"{stem}.markdown", f"{stem}.txt"],
        )
        if not markdown_path and storage_stem != stem:
            markdown_path = self._latest_existing_path(
                output_roots,
                [f"{storage_stem}.md", f"{storage_stem}.markdown", f"{storage_stem}.txt"],
            )

        content_items = self._read_official_content_items(content_list_path)
        markdown_text = self._safe_read_text(markdown_path)
        if not content_items and not markdown_text:
            return None

        text = markdown_text or self._text_from_chunks_or_items([], content_items)
        chunks = self._chunks_from_content_items(content_items, file_name) if content_items else self._build_adapter_metadata_fallback(file_path, mime_type, file_name)["chunks"]
        return {
            "text": text,
            "chunks": chunks,
            "content_items": content_items,
            "summary": (text or f"Indexed material: {file_name}")[:500],
            "metadata_source": "raganything_output_files",
        }

    def _load_lightrag_document_metadata(
        self,
        *,
        class_id: str,
        material_id: str,
        file_name: str,
    ) -> dict[str, Any] | None:
        storage_plan = build_lightrag_storage_plan(class_id)
        workspace = storage_plan.get("workspace") or class_id
        base_dir = Path(settings.RAGANYTHING_WORKING_DIR) / class_id / str(workspace)
        text_chunks = self._load_json_file(base_dir / "kv_store_text_chunks.json")
        full_entities = self._load_json_file(base_dir / "kv_store_full_entities.json")

        if not isinstance(text_chunks, dict):
            return None

        chunks = []
        for chunk_id, chunk in text_chunks.items():
            if not isinstance(chunk, dict) or chunk.get("full_doc_id") != material_id:
                continue
            content = self._clean_lightrag_chunk_text(chunk.get("content"))
            if not content:
                continue
            chunks.append({
                "chunk_id": str(chunk_id),
                "text": content,
                "page": chunk.get("page_idx") or chunk.get("page") or 0,
                "source_name": file_name,
                "source_type": "lightrag_chunk",
                "metadata": {
                    "source": "lightrag_kv",
                    "full_doc_id": material_id,
                    "file_path": chunk.get("file_path"),
                    "tokens": chunk.get("tokens"),
                },
            })

        if not chunks:
            return None

        text = "\n\n".join(chunk["text"] for chunk in chunks)
        entities_payload = (full_entities or {}).get(material_id) if isinstance(full_entities, dict) else {}
        keywords = []
        if isinstance(entities_payload, dict):
            keywords = [
                str(name).strip()
                for name in entities_payload.get("entity_names", [])
                if str(name).strip()
            ]

        return {
            "text": text,
            "chunks": chunks,
            "content_items": [{
                "type": "text",
                "text": text,
                "page_idx": 0,
                "metadata": {
                    "source_name": file_name,
                    "source_type": "lightrag_kv",
                    "full_doc_id": material_id,
                },
            }],
            "keywords": keywords,
            "summary": text[:500],
            "metadata_source": "lightrag_kv",
        }

    def _merge_metadata_chunks(
        self,
        primary: list[dict[str, Any]] | None,
        extra: list[dict[str, Any]] | None,
    ) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        seen: set[str] = set()
        for chunk in list(primary or []) + list(extra or []):
            if not isinstance(chunk, dict):
                continue
            text = re.sub(r"\s+", " ", str(chunk.get("text") or "")).strip()
            if not text:
                continue
            key = text[:500].lower()
            if key in seen:
                continue
            seen.add(key)
            merged.append(chunk)
        return merged

    def _merge_content_items(
        self,
        primary: list[dict[str, Any]] | None,
        extra: list[dict[str, Any]] | None,
    ) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in list(primary or []) + list(extra or []):
            if not isinstance(item, dict):
                continue
            key_payload = {
                "type": item.get("type"),
                "text": re.sub(r"\s+", " ", str(item.get("text") or "")).strip()[:800],
                "caption": re.sub(r"\s+", " ", str(item.get("caption") or "")).strip()[:800],
                "table_markdown": re.sub(r"\s+", " ", str(item.get("table_markdown") or "")).strip()[:800],
                "equation": re.sub(r"\s+", " ", str(item.get("equation") or item.get("formula_latex") or "")).strip()[:500],
                "img_path": str(item.get("img_path") or item.get("image_path") or ""),
            }
            key = json.dumps(key_payload, sort_keys=True, ensure_ascii=False)
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
        return merged

    def _is_media_only_markdown(self, text: str | None) -> bool:
        value = str(text or "").strip()
        if not value:
            return False
        stripped = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", value).strip()
        return not stripped

    def _clean_lightrag_chunk_text(self, text: Any) -> str:
        value = str(text or "")
        for marker in ("Visual Analysis:", "Analysis:"):
            if marker in value:
                prefix, suffix = value.split(marker, 1)
                if "Table Analysis:" in prefix and "Structure:" in prefix:
                    structure = prefix.split("Structure:", 1)[1]
                    value = f"Structure: {structure}\nAnalysis: {suffix}"
                else:
                    value = suffix
                break
        value = re.sub(r"Image Path:\s*/app/[^\n\r]+", "", value)
        value = re.sub(r"/app/(?:uploads|rag_storage|rag_output|runtime_tmp)/[^\s\]\)\r\n]+", "[系统内部路径]", value)
        value = re.sub(r"^\s*(Image Content Analysis:|Table Analysis:|Captions?:\s*None|Footnotes:\s*None)\s*", "", value, flags=re.I)
        value = re.sub(r"\b(?:Captions?|Footnotes|Image Path):\s*None\b", "", value, flags=re.I)
        value = re.sub(r"\bStructure:\s*None\b", "", value, flags=re.I)
        value = value.replace("\\n", "\n").replace("\\t", " ")
        value = re.sub(r"\\{2,}", " ", value)
        value = re.sub(r'"\s*[,;]\s*"', "；", value)
        return re.sub(r"\s+", " ", value).strip()

    def _latest_existing_path(self, root: Path | list[Path], candidate_names: list[str]) -> Path | None:
        matches: list[Path] = []
        roots = root if isinstance(root, list) else [root]
        for name in candidate_names:
            for item in roots:
                matches.extend(item.rglob(name))
        if not matches:
            return None
        matches.sort(key=lambda item: item.stat().st_mtime, reverse=True)
        return matches[0]

    def _read_official_content_items(self, path: Path | None) -> list[dict[str, Any]]:
        if path is None:
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        except (OSError, json.JSONDecodeError):
            return []

        if isinstance(payload, list) and payload and isinstance(payload[0], dict):
            return [item for item in payload if isinstance(item, dict)]

        flattened: list[dict[str, Any]] = []
        if isinstance(payload, list):
            for page_idx, page in enumerate(payload):
                if not isinstance(page, list):
                    continue
                for item in page:
                    if not isinstance(item, dict):
                        continue
                    normalized = self._flatten_official_content_item(item)
                    normalized.setdefault("page_idx", page_idx)
                    flattened.append(normalized)
        return flattened

    def _flatten_official_content_item(self, item: dict[str, Any]) -> dict[str, Any]:
        raw_type = str(item.get("type") or "text").strip().lower()
        content = item.get("content")
        text = item.get("text")
        if not text and isinstance(content, dict):
            paragraph_items = content.get("paragraph_content")
            if isinstance(paragraph_items, list):
                text = "".join(
                    str(part.get("content") or part.get("text") or "")
                    for part in paragraph_items
                    if isinstance(part, dict)
                ).strip()
        normalized_type = "text" if raw_type in {"paragraph", "text"} else raw_type
        return {
            "type": normalized_type,
            "text": text or "",
            "bbox": item.get("bbox"),
            "page_idx": item.get("page_idx"),
            "metadata": {
                "raganything_raw_type": raw_type,
            },
        }

    def _safe_read_text(self, path: Path | None) -> str:
        if path is None:
            return ""
        try:
            return path.read_text(encoding="utf-8", errors="ignore").strip()
        except OSError:
            return ""

    def _build_adapter_metadata_fallback(self, file_path: str, mime_type: str, file_name: str) -> dict[str, Any]:
        path = Path(file_path)
        text = ""
        if path.suffix.lower() in {".txt", ".md"}:
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                text = ""
        if not text:
            text = f"Material indexed through RAG-Anything: {file_name}"
        chunk_id = hashlib.sha256(f"{file_path}|{text[:120]}".encode("utf-8")).hexdigest()[:16]
        content_item = {
            "type": "text",
            "text": text[:2000],
            "page_idx": 0,
            "metadata": {
                "file_name": file_name,
                "mime_type": mime_type,
                "fallback_source": "raganything_adapter_metadata_fallback",
            },
        }
        return {
            "text": text,
            "chunks": [{
                "chunk_id": f"{Path(file_name).stem}-{chunk_id}",
                "text": text[:2000],
                "source_name": file_name,
                "source_type": mime_type,
                "page": 1,
            }],
            "content_items": [content_item],
            "keywords": self._fallback_keywords(text or file_name),
            "summary": text[:500],
        }

    def _fallback_keywords(self, text: str, limit: int = 12) -> list[str]:
        ranked: dict[str, int] = {}
        for token in self._terms(text):
            if len(token) < 2:
                continue
            ranked[token] = ranked.get(token, 0) + 1
        return [
            token
            for token, _ in sorted(ranked.items(), key=lambda item: (-item[1], item[0]))[:limit]
        ]

    def _preprocess_result_to_metadata(self, preprocess_result: PreprocessResult) -> dict[str, Any]:
        return {
            "mode": preprocess_result.mode,
            "modality": preprocess_result.modality,
            "source_file": preprocess_result.source_file,
            "file_name": preprocess_result.file_name,
            "warnings": preprocess_result.warnings,
            "metadata": preprocess_result.metadata,
            "content_item_count": len(preprocess_result.content_list),
        }

    def _annotate_content_items(
        self,
        content_items: list[dict[str, Any]] | None,
        *,
        material_id: str,
        file_name: str,
    ) -> list[dict[str, Any]]:
        annotated: list[dict[str, Any]] = []
        for index, item in enumerate(content_items or [], start=1):
            if not isinstance(item, dict):
                continue
            next_item = dict(item)
            metadata = dict(next_item.get("metadata") or {})
            raw_type = str(next_item.get("type") or metadata.get("source_type") or "text").strip().lower()
            modality = self._normalize_content_modality(raw_type)
            content_fingerprint = {
                "material_id": material_id,
                "index": index,
                "type": raw_type,
                "page": next_item.get("page_idx") or next_item.get("page") or metadata.get("page_idx") or metadata.get("page"),
                "text": str(
                    next_item.get("text")
                    or next_item.get("caption")
                    or next_item.get("ocr_text")
                    or next_item.get("table_markdown")
                    or next_item.get("equation")
                    or next_item.get("formula_latex")
                    or next_item.get("img_path")
                    or next_item.get("image_path")
                    or ""
                )[:2000],
            }
            digest = hashlib.sha256(
                json.dumps(content_fingerprint, sort_keys=True, ensure_ascii=False).encode("utf-8")
            ).hexdigest()[:16]
            atomic_id = str(
                next_item.get("atomic_id")
                or next_item.get("item_id")
                or metadata.get("atomic_id")
                or f"{material_id}-au-{index}-{digest[:8]}"
            )
            metadata.update({
                "atomic_id": atomic_id,
                "content_index": metadata.get("content_index") or index,
                "material_id": material_id,
                "source_name": metadata.get("source_name") or next_item.get("source_name") or file_name,
                "modality": metadata.get("modality") or modality,
            })
            next_item["atomic_id"] = atomic_id
            next_item["item_id"] = str(next_item.get("item_id") or next_item.get("id") or atomic_id)
            next_item["modality"] = next_item.get("modality") or modality
            next_item["metadata"] = metadata
            annotated.append(next_item)
        return annotated

    def _normalize_content_modality(self, value: str) -> str:
        normalized = str(value or "text").strip().lower()
        mapping = {
            "paragraph": "text",
            "figure": "image",
            "equation": "formula",
            "formula": "formula",
            "dataframe": "table",
            "csv": "table",
            "spreadsheet": "table",
        }
        return mapping.get(normalized, normalized or "text")

    def _build_index_quality_report(
        self,
        *,
        preprocess_result: PreprocessResult,
        parsed: dict[str, Any],
        status: dict[str, Any],
        graph_projection: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        content_items = [item for item in (parsed.get("content_items") or []) if isinstance(item, dict)]
        modality_counts: dict[str, int] = {}
        items_missing_atomic_id = 0
        table_items_with_rows = 0
        for item in content_items:
            modality = self._normalize_content_modality(
                str(item.get("modality") or item.get("type") or (item.get("metadata") or {}).get("modality") or "text")
            )
            modality_counts[modality] = modality_counts.get(modality, 0) + 1
            metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
            if not (item.get("atomic_id") or item.get("item_id") or metadata.get("atomic_id")):
                items_missing_atomic_id += 1
            if modality == "table" and (item.get("table_rows") or metadata.get("row_count")):
                table_items_with_rows += 1

        graph_projection = graph_projection or {}
        explicit_entity_count = len(self._extract_graph_entities(status))
        explicit_relation_count = len(self._extract_graph_relations(status))
        return {
            "content_item_count": len(content_items),
            "modality_counts": modality_counts,
            "chunk_count": len(parsed.get("chunks") or []),
            "items_missing_atomic_id": items_missing_atomic_id,
            "table_items_with_rows": table_items_with_rows,
            "metadata_source": parsed.get("metadata_source"),
            "entrypoint": status.get("entrypoint") or preprocess_result.metadata.get("raganything_entrypoint"),
            "text_processed": bool(status.get("text_processed")),
            "multimodal_processed": bool(status.get("multimodal_processed")),
            "fully_processed": bool(status.get("fully_processed")),
            "explicit_entity_count": explicit_entity_count,
            "explicit_relation_count": explicit_relation_count,
            "graph_used_explicit_entities": bool(graph_projection.get("used_explicit_raganything_graph")),
            "graph_entity_count": graph_projection.get("entity_count"),
            "graph_relation_count": graph_projection.get("relation_count"),
        }

    def _find_payload_list(self, payload: Any, keys: set[str]) -> list[Any]:
        found = self._find_payload_value(payload, keys)
        if isinstance(found, list):
            return found
        if isinstance(found, tuple):
            return list(found)
        if isinstance(found, dict):
            return list(found.values())
        return []

    def _find_payload_text(self, payload: Any, keys: set[str]) -> str:
        found = self._find_payload_value(payload, keys)
        return found.strip() if isinstance(found, str) else ""

    def _find_payload_value(self, payload: Any, keys: set[str]) -> Any:
        if isinstance(payload, dict):
            for key, value in payload.items():
                if key in keys and value:
                    return value
            for value in payload.values():
                nested = self._find_payload_value(value, keys)
                if nested:
                    return nested
        elif isinstance(payload, list):
            for item in payload:
                nested = self._find_payload_value(item, keys)
                if nested:
                    return nested
        return None

    def _normalize_keywords(self, values: list[Any]) -> list[str]:
        keywords: list[str] = []
        for item in values:
            if isinstance(item, str):
                candidate = item.strip()
            elif isinstance(item, dict):
                candidate = str(item.get("name") or item.get("entity_name") or item.get("keyword") or "").strip()
            else:
                candidate = ""
            if candidate and candidate not in keywords:
                keywords.append(candidate)
        return keywords[:24]

    def _chunks_from_content_items(self, content_items: list[dict[str, Any]], file_name: str) -> list[dict[str, Any]]:
        chunks: list[dict[str, Any]] = []
        for index, item in enumerate(content_items or [], start=1):
            if not isinstance(item, dict):
                continue
            text = item.get("text") or item.get("caption") or item.get("ocr_text") or item.get("table_markdown") or ""
            if not text:
                continue
            metadata = item.get("metadata") or {}
            source_name = metadata.get("source_name") or item.get("source_name") or file_name
            atomic_id = item.get("atomic_id") or item.get("item_id") or metadata.get("atomic_id")
            chunks.append({
                "chunk_id": item.get("chunk_id") or atomic_id or f"{Path(file_name).stem}-raganything-item-{index}",
                "text": str(text)[:2000],
                "page": item.get("page_idx") or item.get("page") or metadata.get("page") or index,
                "source_name": source_name,
                "source_type": metadata.get("source_type") or item.get("type") or "content_item",
                "metadata": {
                    **metadata,
                    "atomic_id": atomic_id,
                    "item_id": item.get("item_id") or atomic_id,
                    "modality": item.get("modality") or metadata.get("modality"),
                },
            })
        return chunks

    def _text_from_chunks_or_items(
        self,
        chunks: list[dict[str, Any]],
        content_items: list[dict[str, Any]],
    ) -> str:
        texts = []
        for chunk in chunks or []:
            text = chunk.get("text") if isinstance(chunk, dict) else None
            if text:
                texts.append(str(text))
        if not texts:
            for item in content_items or []:
                if not isinstance(item, dict):
                    continue
                text = item.get("text") or item.get("caption") or item.get("ocr_text") or item.get("table_markdown")
                if text:
                    texts.append(str(text))
        return "\n\n".join(texts)

    def _sync_raganything_graph_projection(
        self,
        db,
        *,
        class_id: str,
        material_id: str,
        file_name: str,
        parsed: dict[str, Any],
        status: dict[str, Any],
    ) -> dict[str, Any]:
        """Project RAG-Anything graph/content metadata into the app's graph tables.

        The app graph is a visualization and business-query layer. The source of
        truth for retrieval remains RAG-Anything/LightRAG; this projection avoids
        the old keyword co-occurrence graph by linking entities to materials,
        content items and explicit RAG-Anything relations when available.
        """

        now_iso = datetime.now(timezone.utc).isoformat()
        source_span_seed = self._build_source_span_seed(
            material_id=material_id,
            chunks=parsed.get("chunks") or [],
            content_items=parsed.get("content_items") or [],
        )
        provenance_base = {
            "source": "raganything_projection",
            "source_material_ids": [material_id],
            "first_seen_at": now_iso,
            "last_seen_at": now_iso,
            "occurrence_count": 1,
        }

        material_entity = self._upsert_graph_entity(
            db,
            class_id=class_id,
            name=file_name,
            entity_type="material",
            description=f"Course material indexed by RAG-Anything: {file_name}",
            material_id=material_id,
            confidence=0.95,
            source_span={**source_span_seed, "kind": "material"},
            provenance=provenance_base,
        )
        entity_count = 1
        relation_count = 0

        storage_graph = self._extract_lightrag_storage_graph(
            class_id=class_id,
            material_id=material_id,
        )
        explicit_entities = self._extract_graph_entities(status) or storage_graph.get("entities", [])
        explicit_relations = self._extract_graph_relations(status) or storage_graph.get("relations", [])
        entity_by_name: dict[str, KnowledgeEntity] = {material_entity.name.lower(): material_entity}
        projectable_explicit_entities = [
            item for item in explicit_entities[:48]
            if self._is_projection_course_entity(
                item.get("name"),
                entity_type=item.get("entity_type"),
                description=item.get("description"),
            )
        ]
        for item in projectable_explicit_entities:
            entity = self._upsert_graph_entity(
                db,
                class_id=class_id,
                name=item["name"],
                entity_type=item.get("entity_type") or "concept",
                description=item.get("description") or f"RAG-Anything extracted entity from {file_name}",
                material_id=material_id,
                confidence=item.get("confidence") or 0.75,
                source_span={**source_span_seed, **(item.get("source_span") or {}), "kind": "raganything_entity"},
                provenance={**provenance_base, "raganything_entity": item},
            )
            entity_by_name[entity.name.lower()] = entity
            entity_count += 1
            if self._upsert_graph_relation(
                db,
                class_id=class_id,
                source=entity,
                target=material_entity,
                relation_type="appears_in",
                confidence=item.get("confidence") or 0.72,
                source_span={**source_span_seed, "kind": "entity_material_link"},
                provenance=provenance_base,
            ):
                relation_count += 1

        candidate_keywords = self._projection_candidate_keywords(parsed, limit=80)
        if not projectable_explicit_entities:
            for keyword in candidate_keywords[:12]:
                normalized_keyword = str(keyword or "").strip()[:300]
                if not self._is_projection_candidate_concept(normalized_keyword):
                    continue
                is_identifier_keyword = self._is_projection_identifier_keyword(normalized_keyword)
                provenance_payload = provenance_base
                fallback_reason = "raganything_metadata_keywords"
                confidence = 0.62
                if is_identifier_keyword:
                    source_material_ids = self._material_ids_referencing_projection_keyword(
                        db,
                        class_id=class_id,
                        keyword=normalized_keyword,
                        current_material_id=material_id,
                    )
                    provenance_payload = {
                        **provenance_base,
                        "source_material_ids": source_material_ids,
                        "occurrence_count": max(
                            int(provenance_base.get("occurrence_count", 1) or 1),
                            len(source_material_ids),
                        ),
                    }
                    fallback_reason = "raganything_metadata_identifier_keyword"
                    confidence = 0.7
                entity = self._upsert_graph_entity(
                    db,
                    class_id=class_id,
                    name=normalized_keyword,
                    entity_type="candidate_concept",
                    description=f"Candidate concept projected from RAG-Anything metadata for {file_name}",
                    material_id=material_id,
                    confidence=confidence,
                    source_span={**source_span_seed, "kind": "candidate_concept", "keyword": normalized_keyword},
                    provenance={**provenance_payload, "fallback": fallback_reason},
                )
                entity_by_name[entity.name.lower()] = entity
                entity_count += 1
                if self._upsert_graph_relation(
                    db,
                    class_id=class_id,
                    source=entity,
                    target=material_entity,
                    relation_type="appears_in",
                    confidence=0.6,
                    source_span={**source_span_seed, "kind": "candidate_material_link"},
                    provenance={**provenance_payload, "fallback": fallback_reason},
                ):
                    relation_count += 1
        else:
            for keyword in candidate_keywords[:48]:
                normalized_keyword = str(keyword or "").strip()[:300]
                if (
                    not self._is_projection_candidate_concept(normalized_keyword)
                    or normalized_keyword.lower() in entity_by_name
                ):
                    continue
                existing_entity = db.query(KnowledgeEntity).filter(
                    KnowledgeEntity.class_id == class_id,
                    KnowledgeEntity.name == normalized_keyword,
                ).first()
                is_identifier_keyword = self._is_projection_identifier_keyword(normalized_keyword)
                if not existing_entity and not is_identifier_keyword:
                    continue
                provenance_payload = provenance_base
                if is_identifier_keyword:
                    source_material_ids = self._material_ids_referencing_projection_keyword(
                        db,
                        class_id=class_id,
                        keyword=normalized_keyword,
                        current_material_id=material_id,
                    )
                    provenance_payload = {
                        **provenance_base,
                        "source_material_ids": source_material_ids,
                        "occurrence_count": max(
                            int(provenance_base.get("occurrence_count", 1) or 1),
                            len(source_material_ids),
                        ),
                    }
                entity = self._upsert_graph_entity(
                    db,
                    class_id=class_id,
                    name=normalized_keyword,
                    entity_type=(existing_entity.entity_type if existing_entity else None) or "candidate_concept",
                    description=(
                        (existing_entity.description if existing_entity else None)
                        or f"Candidate concept projected from RAG-Anything metadata for {file_name}"
                    ),
                    material_id=material_id,
                    confidence=max(float((existing_entity.confidence if existing_entity else None) or 0.6), 0.6),
                    source_span={
                        **source_span_seed,
                        "kind": "candidate_concept_existing" if existing_entity else "candidate_concept_identifier",
                        "keyword": normalized_keyword,
                    },
                    provenance={
                        **provenance_payload,
                        "fallback": (
                            "raganything_metadata_existing_keyword"
                            if existing_entity
                            else "raganything_metadata_identifier_keyword"
                        ),
                    },
                )
                entity_by_name[entity.name.lower()] = entity
                entity_count += 1
                if self._upsert_graph_relation(
                    db,
                    class_id=class_id,
                    source=entity,
                    target=material_entity,
                    relation_type="appears_in",
                    confidence=0.6,
                    source_span={**source_span_seed, "kind": "candidate_material_link_existing"},
                    provenance={**provenance_base, "fallback": "raganything_metadata_existing_keyword"},
                ):
                    relation_count += 1

        for item in explicit_relations[:64]:
            source_name = item.get("source") or item.get("source_entity") or item.get("head")
            target_name = item.get("target") or item.get("target_entity") or item.get("tail")
            if not source_name or not target_name:
                continue
            if not (
                self._is_projection_course_entity(source_name)
                and self._is_projection_course_entity(target_name)
            ):
                continue
            source = entity_by_name.get(str(source_name).lower()) or self._upsert_graph_entity(
                db,
                class_id=class_id,
                name=str(source_name),
                entity_type="concept",
                description=f"RAG-Anything relation endpoint from {file_name}",
                material_id=material_id,
                confidence=0.7,
                source_span={**source_span_seed, "kind": "relation_endpoint"},
                provenance=provenance_base,
            )
            target = entity_by_name.get(str(target_name).lower()) or self._upsert_graph_entity(
                db,
                class_id=class_id,
                name=str(target_name),
                entity_type="concept",
                description=f"RAG-Anything relation endpoint from {file_name}",
                material_id=material_id,
                confidence=0.7,
                source_span={**source_span_seed, "kind": "relation_endpoint"},
                provenance=provenance_base,
            )
            if self._upsert_graph_relation(
                db,
                class_id=class_id,
                source=source,
                target=target,
                relation_type=item.get("relation_type") or item.get("type") or "related_to",
                confidence=item.get("confidence") or 0.7,
                source_span={
                    **source_span_seed,
                    **(item.get("source_span") or {}),
                    "kind": "raganything_relation",
                    "evidence": item.get("evidence"),
                },
                provenance={**provenance_base, "raganything_relation": item},
            ):
                relation_count += 1

        return {
            "graph_source": "raganything_projection",
            "entity_count": entity_count,
            "relation_count": relation_count,
            "used_explicit_raganything_graph": bool(projectable_explicit_entities),
            "filtered_explicit_entity_count": max(0, len(explicit_entities[:48]) - len(projectable_explicit_entities)),
            "explicit_graph_source": storage_graph.get("source") if storage_graph.get("entities") else "raganything_status",
        }

    def _projection_candidate_keywords(self, parsed: dict[str, Any], *, limit: int = 80) -> list[str]:
        values: list[str] = []

        text_parts = [str(parsed.get("text") or ""), str(parsed.get("summary") or "")]
        for chunk in parsed.get("chunks") or []:
            if isinstance(chunk, dict):
                text_parts.append(str(chunk.get("text") or chunk.get("content") or ""))
        for item in parsed.get("content_items") or []:
            if isinstance(item, dict):
                text_parts.append(
                    str(
                        item.get("text")
                        or item.get("caption")
                        or item.get("ocr_text")
                        or item.get("table_markdown")
                        or item.get("equation")
                        or ""
                    )
                )

        joined_text = "\n".join(text_parts)
        values.extend(self._projection_identifier_keywords_from_text(joined_text, limit=24))

        for keyword in parsed.get("keywords") or []:
            if keyword:
                values.append(str(keyword))

        values.extend(self._fallback_keywords(joined_text, limit=limit))

        deduped = []
        seen = set()
        for value in values:
            normalized = str(value or "").strip()[:300]
            key = normalized.lower()
            if not normalized or key in seen or self._is_low_quality_projection_keyword(normalized):
                continue
            seen.add(key)
            deduped.append(normalized)
            if len(deduped) >= limit:
                break
        return deduped

    def _projection_identifier_keywords_from_text(self, text: str, *, limit: int = 24) -> list[str]:
        identifiers: list[str] = []
        for match in re.findall(r"\b[A-Za-z][A-Za-z0-9_-]{7,79}\b", text or ""):
            if not any(char.isdigit() for char in match):
                continue
            if self._is_low_quality_projection_keyword(match):
                continue
            if match not in identifiers:
                identifiers.append(match)
            if len(identifiers) >= limit:
                break
        return identifiers

    def _is_low_quality_projection_keyword(self, keyword: str) -> bool:
        normalized = str(keyword or "").strip()
        if not normalized:
            return True

        basename = os.path.basename(normalized)
        if PROJECTION_FILE_LABEL_RE.search(basename):
            return True
        if PROJECTION_UUID_RE.fullmatch(normalized):
            return True
        if PROJECTION_FILE_HASH_RE.search(normalized):
            return True
        if re.fullmatch(r"[a-f0-9]{12,}", normalized, flags=re.IGNORECASE):
            return True
        if re.fullmatch(r"[A-Za-z0-9_-]{16,}", normalized) and any(char.isdigit() for char in normalized):
            return True
        if "/" in normalized or "\\" in normalized:
            return True
        return False

    def _is_projection_candidate_concept(self, keyword: str) -> bool:
        normalized = str(keyword or "").strip()
        if len(normalized) < 2 or len(normalized) > 80:
            return False
        if self._is_low_quality_projection_keyword(normalized):
            return False
        if self._is_projection_artifact_label(normalized):
            return False
        if normalized.lower() in PROJECTION_STOPWORDS:
            return False
        if re.search(r"[\u4e00-\u9fff]", normalized):
            return True
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", normalized):
            return not any(char.isdigit() for char in normalized) and len(normalized) >= 4
        return False

    def _is_projection_identifier_keyword(self, keyword: str) -> bool:
        normalized = str(keyword or "").strip()
        if self._is_low_quality_projection_keyword(normalized):
            return False
        if len(normalized) < 8 or len(normalized) > 80:
            return False
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]+", normalized):
            return False
        return any(char.isdigit() for char in normalized)

    def _is_projection_course_entity(
        self,
        name: Any,
        *,
        entity_type: Any = None,
        description: Any = None,
    ) -> bool:
        normalized = str(name or "").strip()
        if not normalized or len(normalized) > 120:
            return False
        if self._is_low_quality_projection_keyword(normalized):
            return False
        if self._is_projection_artifact_label(normalized):
            return False

        entity_type_text = str(entity_type or "").strip().lower()
        if entity_type_text in {"material", "document", "file", "page", "chunk", "table", "image", "figure"}:
            return False

        description_text = str(description or "")
        artifact_hits = sum(
            1
            for term in ("表格结构", "表的结构", "表头", "行列", "markdown table", "table structure", "image path")
            if term.lower() in description_text.lower()
        )
        if artifact_hits and not self._has_course_semantic_signal(normalized, description_text):
            return False
        return True

    def _is_projection_artifact_label(self, label: str) -> bool:
        normalized = re.sub(r"\s+", " ", str(label or "").strip()).lower()
        if not normalized:
            return True
        compact = re.sub(r"[\s_：:：-]+", "", normalized)
        if normalized in PROJECTION_COURSE_ARTIFACT_TERMS or compact in {
            re.sub(r"[\s_：:：-]+", "", item.lower())
            for item in PROJECTION_COURSE_ARTIFACT_TERMS
        }:
            return True
        artifact_patterns = (
            r"^(?:第?\d+[行列]|row\s*\d+|column\s*\d+)$",
            r"^(?:表格?|table)\s*(?:\d+|结构|内容|组织|摘要|描述)?$",
            r"^(?:图片|图像|figure|image)\s*(?:\d+|内容|描述|摘要)?$",
            r"^(?:公式|equation|formula)\s*(?:\d+|内容|描述|摘要)?$",
            r"^(?:页码|页面|page)\s*\d*$",
        )
        return any(re.fullmatch(pattern, normalized, flags=re.IGNORECASE) for pattern in artifact_patterns)

    def _has_course_semantic_signal(self, *values: str) -> bool:
        name = str(values[0] if values else "").strip()
        if re.search(r"[\u4e00-\u9fff]{2,}", name) and not self._is_projection_artifact_label(name):
            return True
        text = " ".join(str(value or "") for value in values).lower()
        course_markers = (
            "concept",
            "algorithm",
            "theorem",
            "formula",
            "model",
            "method",
            "protocol",
            "network",
            "learning",
            "objective",
            "example",
            "exercise",
            "dataset",
            "experiment",
        )
        return any(marker in text for marker in course_markers)

    def _material_ids_referencing_projection_keyword(
        self,
        db,
        *,
        class_id: str,
        keyword: str,
        current_material_id: str,
    ) -> list[str]:
        normalized = str(keyword or "").strip().lower()
        material_ids: list[str] = []
        if current_material_id:
            material_ids.append(current_material_id)
        if not normalized:
            return material_ids

        tasks = db.query(FileParseTask).filter(
            FileParseTask.class_id == class_id,
            FileParseTask.status == "completed",
        ).all()
        for task in tasks:
            material_id = str(task.material_id or "")
            if not material_id or material_id in material_ids:
                continue
            if self._parse_task_contains_projection_keyword(task, normalized):
                material_ids.append(material_id)
        return material_ids

    def _parse_task_contains_projection_keyword(self, task: FileParseTask, normalized_keyword: str) -> bool:
        text_parts = [
            str(task.extracted_text or ""),
            str(task.summary or ""),
        ]
        for chunk in task.chunks or []:
            if isinstance(chunk, dict):
                text_parts.append(str(chunk.get("text") or chunk.get("content") or ""))
            elif chunk:
                text_parts.append(str(chunk))

        extra = task.extra_data or {}
        for keyword in extra.get("keywords") or []:
            text_parts.append(str(keyword or ""))
        for item in extra.get("content_items") or []:
            if isinstance(item, dict):
                text_parts.append(
                    str(
                        item.get("text")
                        or item.get("caption")
                        or item.get("ocr_text")
                        or item.get("table_markdown")
                        or item.get("equation")
                        or ""
                    )
                )
        return normalized_keyword in "\n".join(text_parts).lower()

    def _extract_lightrag_storage_graph(
        self,
        *,
        class_id: str,
        material_id: str,
    ) -> dict[str, Any]:
        """Read LightRAG persisted graph metadata for app-level projection."""

        storage_plan = build_lightrag_storage_plan(class_id)
        workspace = storage_plan.get("workspace") or class_id
        base_dir = Path(settings.RAGANYTHING_WORKING_DIR) / class_id / str(workspace)
        full_entities = self._load_json_file(base_dir / "kv_store_full_entities.json")
        full_relations = self._load_json_file(base_dir / "kv_store_full_relations.json")
        entity_chunks = self._load_json_file(base_dir / "kv_store_entity_chunks.json")
        relation_chunks = self._load_json_file(base_dir / "kv_store_relation_chunks.json")

        material_entities = (full_entities or {}).get(material_id) or {}
        entity_names = []
        if isinstance(material_entities, dict):
            entity_names = [
                str(name).strip()
                for name in material_entities.get("entity_names", [])
                if str(name).strip()
            ]

        material_relations = (full_relations or {}).get(material_id) or {}
        relation_pairs = []
        if isinstance(material_relations, dict):
            relation_pairs = [
                pair
                for pair in material_relations.get("relation_pairs", [])
                if isinstance(pair, (list, tuple)) and len(pair) >= 2
            ]

        if not entity_names and not relation_pairs:
            return {"source": "none", "entities": [], "relations": []}

        neo4j_graph = self._extract_lightrag_neo4j_graph(
            class_id=class_id,
            entity_names=entity_names,
            relation_pairs=relation_pairs,
        )
        neo4j_entities = neo4j_graph.get("entities", {})
        neo4j_relations = neo4j_graph.get("relations", {})

        entities = []
        for name in entity_names:
            neo4j_entity = neo4j_entities.get(name, {})
            chunk_payload = (entity_chunks or {}).get(name) if isinstance(entity_chunks, dict) else None
            chunk_ids = []
            if isinstance(chunk_payload, dict):
                chunk_ids = [str(chunk_id) for chunk_id in chunk_payload.get("chunk_ids", []) if chunk_id]
            entities.append({
                "name": name,
                "entity_type": neo4j_entity.get("entity_type") or "concept",
                "description": neo4j_entity.get("description") or f"LightRAG extracted entity: {name}",
                "confidence": 0.82,
                "source_span": {
                    "chunk_ids": chunk_ids,
                    "file_path": neo4j_entity.get("file_path"),
                    "source_id": neo4j_entity.get("source_id"),
                },
            })

        relations = []
        for pair in relation_pairs:
            source_name = str(pair[0]).strip()
            target_name = str(pair[1]).strip()
            if not source_name or not target_name:
                continue
            relation_key = f"{source_name}<SEP>{target_name}"
            neo4j_relation = neo4j_relations.get(relation_key, {})
            chunk_payload = (relation_chunks or {}).get(relation_key) if isinstance(relation_chunks, dict) else None
            chunk_ids = []
            if isinstance(chunk_payload, dict):
                chunk_ids = [str(chunk_id) for chunk_id in chunk_payload.get("chunk_ids", []) if chunk_id]
            relations.append({
                "source": source_name,
                "target": target_name,
                "relation_type": neo4j_relation.get("relation_type") or "related_to",
                "confidence": 0.82,
                "evidence": neo4j_relation.get("description") or neo4j_relation.get("keywords"),
                "source_span": {
                    "chunk_ids": chunk_ids,
                    "file_path": neo4j_relation.get("file_path"),
                    "source_id": neo4j_relation.get("source_id"),
                    "keywords": neo4j_relation.get("keywords"),
                },
            })

        return {
            "source": "lightrag_kv_neo4j" if neo4j_graph.get("available") else "lightrag_kv",
            "entities": entities,
            "relations": relations,
        }

    def _load_json_file(self, path: Path) -> Any:
        try:
            if not path.exists():
                return None
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning(
                "lightrag_storage_json_load_failed",
                path=str(path),
                error=str(exc),
            )
            return None

    def _extract_lightrag_neo4j_graph(
        self,
        *,
        class_id: str,
        entity_names: list[str],
        relation_pairs: list[Any],
    ) -> dict[str, Any]:
        if not settings.GRAPH_DB_URL or not settings.GRAPH_DB_USERNAME:
            return {"available": False, "entities": {}, "relations": {}}

        try:
            from neo4j import GraphDatabase
        except Exception:
            return {"available": False, "entities": {}, "relations": {}}

        relation_keys = {
            f"{str(pair[0]).strip()}<SEP>{str(pair[1]).strip()}"
            for pair in relation_pairs
            if isinstance(pair, (list, tuple)) and len(pair) >= 2
        }
        try:
            driver = GraphDatabase.driver(
                settings.GRAPH_DB_URL,
                auth=(settings.GRAPH_DB_USERNAME, settings.GRAPH_DB_PASSWORD),
            )
            with driver:
                with driver.session(database=settings.GRAPH_DB_DATABASE or None) as session:
                    entity_rows = session.run(
                        """
                        MATCH (n)
                        WHERE $workspace IN labels(n) AND n.entity_id IN $entity_names
                        RETURN n.entity_id AS name,
                               n.entity_type AS entity_type,
                               n.description AS description,
                               n.source_id AS source_id,
                               n.file_path AS file_path
                        """,
                        workspace=class_id,
                        entity_names=entity_names,
                    )
                    entities = {
                        row["name"]: {
                            "entity_type": row["entity_type"],
                            "description": row["description"],
                            "source_id": row["source_id"],
                            "file_path": row["file_path"],
                        }
                        for row in entity_rows
                        if row["name"]
                    }
                    relation_rows = session.run(
                        """
                        MATCH (a)-[r]->(b)
                        WHERE $workspace IN labels(a) AND $workspace IN labels(b)
                        RETURN a.entity_id AS source,
                               b.entity_id AS target,
                               type(r) AS relation_type,
                               r.description AS description,
                               r.keywords AS keywords,
                               r.source_id AS source_id,
                               r.file_path AS file_path
                        """,
                        workspace=class_id,
                    )
                    relations = {}
                    for row in relation_rows:
                        key = f"{row['source']}<SEP>{row['target']}"
                        if key not in relation_keys:
                            continue
                        relations[key] = {
                            "relation_type": row["relation_type"],
                            "description": row["description"],
                            "keywords": row["keywords"],
                            "source_id": row["source_id"],
                            "file_path": row["file_path"],
                        }
            return {"available": True, "entities": entities, "relations": relations}
        except Exception as exc:
            logger.warning(
                "lightrag_neo4j_graph_projection_load_failed",
                class_id=class_id,
                error=str(exc),
            )
            return {"available": False, "entities": {}, "relations": {}}

    def _upsert_graph_entity(
        self,
        db,
        *,
        class_id: str,
        name: str,
        entity_type: str,
        description: str,
        material_id: str,
        confidence: float,
        source_span: dict[str, Any],
        provenance: dict[str, Any],
    ) -> KnowledgeEntity:
        normalized_name = str(name or "").strip()[:300]
        entity = db.query(KnowledgeEntity).filter(
            KnowledgeEntity.class_id == class_id,
            KnowledgeEntity.name == normalized_name,
        ).first()
        if not entity:
            entity = KnowledgeEntity(
                class_id=class_id,
                name=normalized_name,
                entity_type=entity_type,
                description=description,
                source_material_id=material_id,
                confidence=round(float(confidence or 0.6), 4),
                source_span=source_span,
                provenance=provenance,
                status="approved",
            )
            db.add(entity)
            db.flush()
            return entity

        entity.entity_type = entity.entity_type or entity_type
        entity.description = entity.description or description
        entity.source_material_id = material_id
        entity.confidence = self._blended_confidence(entity.confidence, confidence)
        entity.source_span = self._merge_source_span(entity.source_span, source_span)
        entity.provenance = self._merge_provenance(
            entity.provenance,
            [*self._source_material_ids_from_provenance(provenance), material_id],
            provenance.get("last_seen_at") or datetime.now(timezone.utc).isoformat(),
        )
        db.add(entity)
        return entity

    def _upsert_graph_relation(
        self,
        db,
        *,
        class_id: str,
        source: KnowledgeEntity,
        target: KnowledgeEntity,
        relation_type: str,
        confidence: float,
        source_span: dict[str, Any],
        provenance: dict[str, Any],
    ) -> bool:
        if source.id == target.id:
            return False
        relation = db.query(KnowledgeRelation).filter(
            KnowledgeRelation.class_id == class_id,
            KnowledgeRelation.source_id == source.id,
            KnowledgeRelation.target_id == target.id,
            KnowledgeRelation.relation_type == relation_type,
        ).first()
        if not relation:
            db.add(KnowledgeRelation(
                class_id=class_id,
                source_id=source.id,
                target_id=target.id,
                relation_type=relation_type,
                weight=1.0,
                confidence=round(float(confidence or 0.6), 4),
                source_span=source_span,
                provenance=provenance,
            ))
            return True

        relation.weight = round(min(5.0, float(relation.weight or 1.0) + 0.2), 4)
        relation.confidence = self._blended_confidence(relation.confidence, confidence)
        relation.source_span = self._merge_source_span(relation.source_span, source_span)
        relation.provenance = self._merge_provenance(
            relation.provenance,
            self._source_material_ids_from_provenance(provenance),
            provenance.get("last_seen_at") or datetime.now(timezone.utc).isoformat(),
        )
        db.add(relation)
        return False

    def _extract_graph_entities(self, payload: Any) -> list[dict[str, Any]]:
        values = self._find_payload_list(payload, {"knowledge_entities", "entities", "nodes", "graph_nodes"})
        entities = []
        for item in values:
            if isinstance(item, str):
                entities.append({"name": item, "entity_type": "concept"})
            elif isinstance(item, dict):
                name = item.get("name") or item.get("entity_name") or item.get("id") or item.get("label")
                if name:
                    entities.append({
                        "name": str(name),
                        "entity_type": item.get("entity_type") or item.get("type") or item.get("label_type"),
                        "description": item.get("description") or item.get("summary"),
                        "confidence": self._safe_float(item.get("confidence")) or self._safe_float(item.get("score")),
                        "source_span": item.get("source_span") or item.get("span") or {},
                    })
        return entities

    def _extract_graph_relations(self, payload: Any) -> list[dict[str, Any]]:
        values = self._find_payload_list(payload, {"knowledge_relations", "relations", "edges", "graph_edges"})
        relations = []
        for item in values:
            if isinstance(item, dict):
                relations.append({
                    "source": item.get("source") or item.get("source_entity") or item.get("head") or item.get("src"),
                    "target": item.get("target") or item.get("target_entity") or item.get("tail") or item.get("dst"),
                    "relation_type": item.get("relation_type") or item.get("type") or item.get("label"),
                    "confidence": self._safe_float(item.get("confidence")) or self._safe_float(item.get("score")),
                    "evidence": item.get("evidence") or item.get("description"),
                })
        return relations

    def _build_source_span_seed(
        self,
        *,
        material_id: str,
        chunks: list[dict[str, Any]],
        content_items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        pages: list[int] = []
        chunk_ids: list[str] = []
        bbox = None

        for chunk in chunks or []:
            page = chunk.get("page")
            if isinstance(page, int) and page not in pages:
                pages.append(page)
            chunk_id = chunk.get("chunk_id")
            if chunk_id and chunk_id not in chunk_ids:
                chunk_ids.append(str(chunk_id))

        for item in content_items or []:
            page = item.get("page") if isinstance(item, dict) else None
            if page is None and isinstance(item, dict):
                page = item.get("page_idx")
            if isinstance(page, int) and page not in pages:
                pages.append(page)
            if bbox is None and isinstance(item, dict):
                bbox = item.get("bbox")

        return {
            "material_id": material_id,
            "pages": pages[:8],
            "chunk_ids": chunk_ids[:8],
            "bbox": bbox,
        }

    def _merge_source_span(self, existing: Any, incoming: dict[str, Any]) -> dict[str, Any]:
        merged = dict(existing or {})
        for key, value in (incoming or {}).items():
            if key in {"pages", "chunk_ids"}:
                current = merged.get(key) or []
                if not isinstance(current, list):
                    current = [current]
                additions = value if isinstance(value, list) else [value]
                merged[key] = list(dict.fromkeys([*current, *[item for item in additions if item is not None]]))[:16]
            elif key == "bbox":
                merged[key] = merged.get(key) or value
            else:
                merged[key] = value if value is not None else merged.get(key)
        return merged

    def _source_material_ids_from_provenance(self, provenance: Any) -> list[str]:
        if not isinstance(provenance, dict):
            return []
        source_material_ids = provenance.get("source_material_ids") or []
        if not isinstance(source_material_ids, list):
            source_material_ids = [source_material_ids]
        return [str(material_id) for material_id in source_material_ids if material_id]

    def _merge_provenance(self, existing: Any, material_ids: str | list[str] | tuple[str, ...] | None, seen_at: str) -> dict[str, Any]:
        provenance = dict(existing or {})
        source_material_ids = provenance.get("source_material_ids") or []
        if not isinstance(source_material_ids, list):
            source_material_ids = [source_material_ids]
        incoming_ids = material_ids if isinstance(material_ids, (list, tuple, set)) else [material_ids]
        for material_id in incoming_ids:
            if material_id and material_id not in source_material_ids:
                source_material_ids.append(material_id)
        provenance["source_material_ids"] = source_material_ids
        provenance["occurrence_count"] = int(provenance.get("occurrence_count", 0) or 0) + 1
        provenance["first_seen_at"] = provenance.get("first_seen_at") or seen_at
        provenance["last_seen_at"] = seen_at
        return provenance

    async def ingest_material(
        self,
        class_id: str,
        material_id: str,
        file_path: str,
        mime_type: str,
    ) -> bool:
        with SessionLocal() as db:
            material = db.query(Material).filter(Material.id == material_id).first()
            cls = db.query(Class).filter(Class.id == class_id).first()
            if not material or not cls:
                return False

            kb_space = self._ensure_kb_space(db, course_id=cls.course_id, class_id=class_id)
            task = db.query(FileParseTask).filter(FileParseTask.material_id == material_id).first()
            if not task:
                task = FileParseTask(
                    kb_space_id=kb_space.id,
                    course_id=cls.course_id,
                    class_id=class_id,
                    material_id=material_id,
                    parser_name="raganything",
                    status="pending",
                )
                db.add(task)
                db.flush()

            preprocess_started = self._start_parse_stage(
                db,
                task,
                "preprocess",
                label="文件预处理",
                details={"mime_type": mime_type, "file_name": material.file_name},
            )
            try:
                preprocess_result = preprocess_for_raganything(
                    file_path=file_path,
                    mime_type=mime_type,
                    file_name=material.file_name,
                )
                preprocess_result.content_list = self._annotate_content_items(
                    preprocess_result.content_list,
                    material_id=material_id,
                    file_name=material.file_name,
                )
            except Exception as exc:
                self._finish_parse_stage(
                    db,
                    task,
                    "preprocess",
                    started=preprocess_started,
                    status="failed",
                    error=str(exc),
                )
                raise
            self._finish_parse_stage(
                db,
                task,
                "preprocess",
                started=preprocess_started,
                details={
                    "mode": preprocess_result.mode,
                    "modality": preprocess_result.modality,
                    "content_item_count": len(preprocess_result.content_list or []),
                },
            )
            if (
                preprocess_result.metadata.get("preprocess_quality") == "metadata_only"
                and not settings.MULTIMODAL_ALLOW_METADATA_ONLY_INDEX
            ):
                raise RuntimeError(
                    f"{preprocess_result.modality} preprocessing produced metadata only; "
                    "configure ASR/keyframe extraction or enable MULTIMODAL_ALLOW_METADATA_ONLY_INDEX"
                )

            task.status = "processing"
            db.expire(task, ["extra_data"])
            task.extra_data = {
                **(task.extra_data or {}),
                "preprocess": self._preprocess_result_to_metadata(preprocess_result),
            }
            material.kb_status = "processing"
            db.commit()

            rag = self._get_instance(class_id)
            ingest_trace: dict[str, Any] = {
                "trace_version": 1,
                "class_id": class_id,
                "material_id": material_id,
                "file_name": material.file_name,
                "llm_calls": [],
                "vision_calls": [],
            }
            trace_token = _INGEST_TRACE_CONTEXT.set(ingest_trace)
            if preprocess_result.use_content_list:
                insert_started = self._start_parse_stage(
                    db,
                    task,
                    "lightrag_insert",
                    label="预处理内容写入索引",
                    details={"mode": preprocess_result.mode},
                )
                try:
                    await self._insert_preprocessed_content_list(
                        rag=rag,
                        preprocess_result=preprocess_result,
                        material_id=material_id,
                    )
                except Exception as exc:
                    self._finish_parse_stage(
                        db,
                        task,
                        "lightrag_insert",
                        started=insert_started,
                        status="failed",
                        error=str(exc),
                    )
                    raise
                self._finish_parse_stage(
                    db,
                    task,
                    "lightrag_insert",
                    started=insert_started,
                    details={"content_item_count": len(preprocess_result.content_list or [])},
                )
                content_list_status = self._build_content_list_processing_status(preprocess_result)
                document_status = await self._get_document_processing_status(
                    rag,
                    material_id,
                    preprocess_result,
                )
                status = {
                    **content_list_status,
                    **document_status,
                    "content_list_status": content_list_status,
                }
                if preprocess_result.modality == "image":
                    status["text_processed"] = bool(
                        status.get("text_processed")
                        or document_status.get("chunks_count")
                    )
                    status["multimodal_processed"] = bool(
                        status.get("multimodal_processed")
                        or content_list_status.get("multimodal_processed")
                    )
                    status["fully_processed"] = bool(
                        status.get("fully_processed")
                        or status.get("multimodal_processed")
                    )
                if document_status:
                    raw_doc_status = str(document_status.get("status") or "").strip().lower()
                    if raw_doc_status in {"failed", "error"} or self._extract_processing_error(document_status).get("message"):
                        status["fully_processed"] = False
                        status["text_processed"] = bool(
                            content_list_status.get("text_processed")
                            or document_status.get("text_processed")
                            or document_status.get("chunks_count")
                        )
                        status["multimodal_processed"] = bool(
                            content_list_status.get("multimodal_processed")
                            or document_status.get("multimodal_processed")
                        )
            else:
                document_started = self._start_parse_stage(
                    db,
                    task,
                    "mineru_parse",
                    label="MinerU版面解析与官方文档处理",
                    details={
                        "entrypoint": "process_document_complete",
                        "parse_method": settings.RAGANYTHING_PARSE_METHOD,
                        "timing_granularity": "raganything_document_pipeline",
                    },
                )
                try:
                    await rag.process_document_complete(
                        file_path=file_path,
                        output_dir=str((Path(settings.RAGANYTHING_OUTPUT_DIR) / class_id).resolve()),
                        parse_method=settings.RAGANYTHING_PARSE_METHOD,
                        doc_id=material_id,
                        file_name=material.file_name,
                    )
                except Exception as exc:
                    self._finish_parse_stage(
                        db,
                        task,
                        "mineru_parse",
                        started=document_started,
                        status="failed",
                        error=str(exc),
                    )
                    raise
                self._finish_parse_stage(
                    db,
                    task,
                    "mineru_parse",
                    started=document_started,
                    details={
                        "entrypoint": "process_document_complete",
                        "includes_downstream_indexing": True,
                    },
                )

                status = rag.get_document_processing_status(material_id)
                if inspect.isawaitable(status):
                    status = await status
                status = self._normalize_processing_status(status, preprocess_result)
                self._finish_parse_stage(
                    db,
                    task,
                    "vlm_describe",
                    status="completed" if status.get("multimodal_processed") else "skipped",
                    details={
                        "observed_by": "model_call_trace",
                        "vision_call_count": int(ingest_trace.get("vision_call_count") or 0),
                        "latency_ms": ingest_trace.get("vlm_describe_latency_ms"),
                        "multimodal_processed": bool(status.get("multimodal_processed")),
                    },
                )
                self._finish_parse_stage(
                    db,
                    task,
                    "lightrag_insert",
                    status="completed" if status.get("text_processed") else "failed",
                    details={
                        "observed_by": "raganything_status",
                        "chunks_count": status.get("chunks_count"),
                        "text_processed": bool(status.get("text_processed")),
                    },
                    error=None if status.get("text_processed") else self._extract_processing_error(status).get("message"),
                )
                self._finish_parse_stage(
                    db,
                    task,
                    "entity_relation_extract",
                    status="completed" if ingest_trace.get("knowledge_extraction_latency_ms") else "unknown",
                    details={
                        "observed_by": "llm_call_trace",
                        "llm_call_count": int(ingest_trace.get("llm_call_count") or 0),
                        "knowledge_extraction_latency_ms": ingest_trace.get("knowledge_extraction_latency_ms"),
                    },
                )

            self._finish_parse_stage(
                db,
                task,
                "vlm_describe",
                status="completed" if status.get("multimodal_processed") else "skipped",
                details={
                    "observed_by": "model_call_trace",
                    "vision_call_count": int(ingest_trace.get("vision_call_count") or 0),
                    "latency_ms": ingest_trace.get("vlm_describe_latency_ms"),
                    "multimodal_processed": bool(status.get("multimodal_processed")),
                },
            )
            self._finish_parse_stage(
                db,
                task,
                "entity_relation_extract",
                status="completed" if ingest_trace.get("knowledge_extraction_latency_ms") else "unknown",
                details={
                    "observed_by": "llm_call_trace",
                    "llm_call_count": int(ingest_trace.get("llm_call_count") or 0),
                    "knowledge_extraction_latency_ms": ingest_trace.get("knowledge_extraction_latency_ms"),
                },
            )
            _INGEST_TRACE_CONTEXT.reset(trace_token)

            parsed = self._build_metadata_payload(
                class_id=class_id,
                material_id=material_id,
                status=status,
                preprocess_result=preprocess_result,
                file_path=file_path,
                mime_type=mime_type,
                file_name=material.file_name,
            )
            parsed["content_items"] = self._annotate_content_items(
                parsed.get("content_items") or [],
                material_id=material_id,
                file_name=material.file_name,
            )
            parsed["chunks"] = self._merge_metadata_chunks(
                [],
                parsed.get("chunks") or self._chunks_from_content_items(parsed["content_items"], material.file_name),
            )

            text_processed = bool(status.get("text_processed"))
            multimodal_processed = bool(status.get("multimodal_processed"))
            indexing_succeeded = text_processed or (
                preprocess_result.modality == "image" and multimodal_processed
            )
            fully_processed = bool(status.get("fully_processed"))
            quality = self._build_processing_quality(status)
            processing_error = self._extract_processing_error(status)
            active_storage_plan = build_lightrag_storage_plan(class_id)

            task.status = "completed" if indexing_succeeded else "failed"
            task.parser_name = "raganything"
            task.summary = parsed["summary"]
            task.extracted_text = parsed["text"]
            task.chunks = parsed["chunks"]
            task.error_message = None if task.status == "completed" else processing_error["message"]
            db.expire(task, ["extra_data"])
            existing_extra = task.extra_data or {}
            task.extra_data = {
                **existing_extra,
                "keywords": parsed["keywords"],
                "content_items": parsed["content_items"],
                "metadata_source": parsed.get("metadata_source"),
                "preprocess": self._preprocess_result_to_metadata(preprocess_result),
                "raganything_status": status,
                "raganything_quality": quality,
                "raganything_error": processing_error,
                "raganything_storage": {
                    **build_runtime_rag_storage_config_snapshot(),
                    "active_lightrag_storage": {
                        "requested_backend": active_storage_plan.get("requested_backend"),
                        "effective_backend": active_storage_plan.get("effective_backend"),
                        "workspace": active_storage_plan.get("workspace"),
                        "vector_storage": (active_storage_plan.get("lightrag_kwargs") or {}).get("vector_storage"),
                        "graph_storage": (active_storage_plan.get("lightrag_kwargs") or {}).get("graph_storage"),
                    },
                    "class_working_dir": str((Path(settings.RAGANYTHING_WORKING_DIR) / class_id).resolve()),
                    "class_output_dir": str((Path(settings.RAGANYTHING_OUTPUT_DIR) / class_id).resolve()),
                },
            }
            self._attach_ingest_trace_summary(task, ingest_trace)
            material.kb_status = "indexed" if task.status == "completed" else "failed"
            if task.status == "completed" and not fully_processed:
                if text_processed and not multimodal_processed:
                    material.kb_error = "RAG-Anything text indexing succeeded, but multimodal/KG extraction only partially completed"
                else:
                    material.kb_error = (
                        "RAG-Anything indexed text successfully, but some advanced extraction steps failed"
                        + (
                            f": {processing_error['message']}"
                            if processing_error.get("message")
                            else ""
                        )
                    )
            else:
                material.kb_error = None if task.status == "completed" else (
                    processing_error["message"] or "RAG-Anything processing incomplete"
                )

            graph_started = self._start_parse_stage(
                db,
                task,
                "graph_projection",
                label="知识图谱投影同步",
                details={"source": "raganything_projection"},
            )
            try:
                graph_projection = self._sync_raganything_graph_projection(
                    db,
                    class_id=class_id,
                    material_id=material_id,
                    file_name=material.file_name,
                    parsed=parsed,
                    status=status,
                )
            except Exception as exc:
                self._finish_parse_stage(
                    db,
                    task,
                    "graph_projection",
                    started=graph_started,
                    status="failed",
                    error=str(exc),
                )
                raise
            self._finish_parse_stage(
                db,
                task,
                "graph_projection",
                started=graph_started,
                details={
                    "entity_count": graph_projection.get("entity_count"),
                    "relation_count": graph_projection.get("relation_count"),
                    "graph_source": graph_projection.get("graph_source"),
                },
            )
            index_quality = self._build_index_quality_report(
                preprocess_result=preprocess_result,
                parsed=parsed,
                status=status,
                graph_projection=graph_projection,
            )
            task.extra_data = {
                **(task.extra_data or {}),
                "graph_projection": graph_projection,
                "index_quality": index_quality,
            }

            completed_tasks = db.query(FileParseTask).filter(
                FileParseTask.kb_space_id == kb_space.id,
                FileParseTask.status == "completed",
            ).all()
            kb_space.status = "ready" if task.status == "completed" else "failed"
            kb_space.document_count = len({row.material_id for row in completed_tasks})
            kb_space.chunk_count = sum(len(row.chunks or []) for row in completed_tasks)
            kb_space.last_built_at = datetime.now(timezone.utc)
            kb_space.extra_data = {
                **(kb_space.extra_data or {}),
                "backend": "raganything",
                "last_status": status,
                "last_quality": quality,
                "last_graph_projection": graph_projection,
                "last_index_quality": index_quality,
            }
            db.commit()
            return task.status == "completed"

    async def query(
        self,
        question: str,
        class_id: str,
        history=None,
        attachments=None,
        role: str = "student",
        progress_callback: ProgressCallback | None = None,
    ) -> RAGResult:
        query_started = perf_counter()
        outer_stage_timings_ms: dict[str, float] = {}

        def mark(stage: str, started: float) -> None:
            outer_stage_timings_ms[stage] = round((perf_counter() - started) * 1000, 2)

        query_mode = settings.RAGANYTHING_QUERY_MODE or "mix"
        routing_snapshot = self._load_runtime_routing_snapshot()
        routing_meta = model_routing_service.flatten_routing_snapshot(routing_snapshot)
        stage_started = perf_counter()
        await self._emit_progress(
            progress_callback,
            stage="query_rewrite",
            status="running",
            label="正在生成检索问题与关键词",
            started_at=query_started,
        )
        rewrite_bundle = build_query_rewrite_bundle(
            question=question,
            enabled=bool(settings.RAG_QUERY_REWRITE_ENABLED),
            mode=settings.RAG_QUERY_REWRITE_MODE,
            max_variants=settings.RAG_QUERY_REWRITE_MAX_VARIANTS,
        )
        mark("query_rewrite", stage_started)
        await self._emit_progress(
            progress_callback,
            stage="query_rewrite",
            status="done",
            label="检索问题与关键词生成完成",
            started_at=query_started,
            details={
                "enabled": bool(rewrite_bundle.get("enabled")),
                "intent": rewrite_bundle.get("intent"),
                "variant_count": rewrite_bundle.get("variant_count"),
            },
        )
        stage_started = perf_counter()
        effective_question = self._build_effective_query_text(
            question=question,
            rewrite_bundle=rewrite_bundle,
        )
        mark("effective_query_build", stage_started)
        await self._emit_progress(
            progress_callback,
            stage="effective_query",
            status="done",
            label="已整理提交给检索引擎的问题",
            started_at=query_started,
        )

        image_contexts = []
        stage_started = perf_counter()
        if attachments:
            await self._emit_progress(
                progress_callback,
                stage="attachments",
                status="running",
                label="正在处理本轮附件",
                started_at=query_started,
            )
        for attachment in attachments or []:
            if attachment.get("file_type") == "image":
                description = await self._describe_image_attachment(attachment, question)
                if description:
                    image_contexts.append(description)
        mark("image_attachment_description", stage_started)
        if attachments:
            await self._emit_progress(
                progress_callback,
                stage="attachments",
                status="done",
                label="附件处理完成",
                started_at=query_started,
                details={"image_context_count": len(image_contexts)},
            )

        stage_started = perf_counter()
        raganything_result, fallback_reason, query_method, query_error_detail = await self._query_with_raganything(
            question=effective_question,
            original_question=question,
            class_id=class_id,
            history=history,
            attachments=attachments,
            image_contexts=image_contexts,
            query_mode=query_mode,
            role=role,
            progress_callback=progress_callback,
            progress_started=query_started,
        )
        mark("raganything_main_chain", stage_started)
        if raganything_result is not None:
            query_trace = dict((raganything_result.meta or {}).get("query_trace") or {})
            existing_stage_timings = dict(query_trace.get("stage_timings_ms") or {})
            query_trace.update({
                "class_id": class_id,
                "role": role,
                "query_mode": query_mode,
                "original_question_preview": self._trace_preview(question),
                "effective_query_preview": self._trace_preview(effective_question),
                "query_rewrite": self._build_query_rewrite_trace(
                    question=question,
                    effective_question=effective_question,
                    rewrite_bundle=rewrite_bundle,
                ),
                "attachment_count": len(attachments or []),
                "image_context_count": len(image_contexts),
                "image_context_chars": sum(len(item) for item in image_contexts),
                "history_message_count": len(history or []),
                "outer_stage_timings_ms": outer_stage_timings_ms,
                "adapter_total_latency_ms": round((perf_counter() - query_started) * 1000, 2),
            })
            if existing_stage_timings:
                query_trace["stage_timings_ms"] = existing_stage_timings
            logger.info(
                "raganything_query_trace",
                class_id=class_id,
                query_mode=query_mode,
                query_method=query_method,
                trace=query_trace,
            )
            raganything_result.meta = {
                **(raganything_result.meta or {}),
                "engine": "raganything",
                "query_mode": query_mode,
                "query_method": query_method,
                "used_multimodal": query_method == "aquery_with_multimodal",
                "used_fallback": False,
                "fallback_reason": None,
                "retrieval_strategy": "main_chain",
                "reranker_provider": (raganything_result.meta or {}).get("reranker_provider") or "main_chain_native",
                "reranker_model": (raganything_result.meta or {}).get("reranker_model"),
                "reranked_main_chain_sources": bool((raganything_result.meta or {}).get("reranked_main_chain_sources")),
                "candidate_count": (raganything_result.meta or {}).get(
                    "source_candidate_count",
                    len(raganything_result.sources or []),
                ),
                "selected_count": (raganything_result.meta or {}).get(
                    "source_selected_count",
                    len(raganything_result.sources or []),
                ),
                "query_rewrite_enabled": bool(rewrite_bundle["enabled"]),
                "query_rewrite_mode": rewrite_bundle["mode"],
                "query_variant_count": rewrite_bundle["variant_count"],
                "query_rewrite_queries": rewrite_bundle["queries"],
                "question_intent": rewrite_bundle.get("intent"),
                "question_intent_confidence": rewrite_bundle.get("intent_confidence"),
                "question_intent_signals": rewrite_bundle.get("intent_signals"),
                "retrieval_focus_terms": rewrite_bundle.get("retrieval_focus_terms"),
                "answer_focus": rewrite_bundle.get("answer_focus"),
                "query_trace": query_trace,
                "llm_backend": routing_meta.get("llm_backend"),
                "embedding_backend": routing_meta.get("embedding_backend"),
                "vlm_backend": routing_meta.get("vlm_backend"),
                "reranker_backend": routing_meta.get("reranker_backend"),
                "education_prompts_enabled": bool(settings.RAG_EDUCATION_PROMPTS_ENABLED),
                "education_query_prompt_enabled": bool(settings.RAG_EDUCATION_QUERY_PROMPT_ENABLED),
                "education_prompt_role": role,
            }
            return raganything_result

        return RAGResult(
            answer=(
                "我暂时没有从当前课程资料中检索到足够依据来回答这个问题。"
                "你可以换一种问法，或请教师先上传/补充相关课程资料后再提问。"
            ),
            sources=[],
            confidence=0.0,
            suggestions=self._suggestions(question),
            meta={
                "engine": "raganything",
                "query_mode": query_mode,
                "query_method": query_method,
                "used_multimodal": bool(image_contexts),
                "used_fallback": False,
                "fallback_disabled": True,
                "fallback_reason": fallback_reason or "main_chain_unavailable",
                "query_error_detail": query_error_detail,
                "retrieval_strategy": "raganything_main_chain",
                "query_rewrite_enabled": bool(rewrite_bundle["enabled"]),
                "query_rewrite_mode": rewrite_bundle["mode"],
                "query_variant_count": rewrite_bundle["variant_count"],
                "query_rewrite_queries": rewrite_bundle["queries"],
                "question_intent": rewrite_bundle.get("intent"),
                "question_intent_confidence": rewrite_bundle.get("intent_confidence"),
                "question_intent_signals": rewrite_bundle.get("intent_signals"),
                "retrieval_focus_terms": rewrite_bundle.get("retrieval_focus_terms"),
                "answer_focus": rewrite_bundle.get("answer_focus"),
                "query_trace": {
                    "trace_version": 2,
                    "class_id": class_id,
                    "role": role,
                    "query_mode": query_mode,
                    "query_method": query_method,
                    "fallback_reason": fallback_reason or "main_chain_unavailable",
                    "query_error_detail": query_error_detail,
                    "original_question_preview": self._trace_preview(question),
                    "effective_query_preview": self._trace_preview(effective_question),
                    "query_rewrite": self._build_query_rewrite_trace(
                        question=question,
                        effective_question=effective_question,
                        rewrite_bundle=rewrite_bundle,
                    ),
                    "attachment_count": len(attachments or []),
                    "image_context_count": len(image_contexts),
                    "image_context_chars": sum(len(item) for item in image_contexts),
                    "history_message_count": len(history or []),
                    "outer_stage_timings_ms": outer_stage_timings_ms,
                    "adapter_total_latency_ms": round((perf_counter() - query_started) * 1000, 2),
                },
                "llm_backend": routing_meta.get("llm_backend"),
                "embedding_backend": routing_meta.get("embedding_backend"),
                "vlm_backend": routing_meta.get("vlm_backend"),
                "reranker_backend": routing_meta.get("reranker_backend"),
                "education_prompts_enabled": bool(settings.RAG_EDUCATION_PROMPTS_ENABLED),
                "education_query_prompt_enabled": bool(settings.RAG_EDUCATION_QUERY_PROMPT_ENABLED),
                "education_prompt_role": role,
            },
        )

    async def _query_with_raganything(
        self,
        *,
        question: str,
        original_question: str | None = None,
        class_id: str,
        history: list[dict] | None,
        attachments: list[dict] | None,
        image_contexts: list[str],
        query_mode: str,
        role: str = "student",
        progress_callback: ProgressCallback | None = None,
        progress_started: float | None = None,
    ) -> tuple[RAGResult | None, str | None, str | None, str | None]:
        query_started = perf_counter()
        progress_base = progress_started or query_started
        stage_timings_ms: dict[str, float] = {}
        live_trace: dict[str, Any] = {
            "trace_version": 2,
            "class_id": class_id,
            "role": role,
            "requested_query_mode": query_mode,
            "llm_calls": [],
        }
        trace_token = _QUERY_TRACE_CONTEXT.set(live_trace) if bool(getattr(settings, "RAG_QUERY_TRACE_ENABLED", True)) else None

        def mark(stage: str, started: float) -> None:
            stage_timings_ms[stage] = round((perf_counter() - started) * 1000, 2)

        try:
            retrieval_question = original_question or question
            query_parts = [question]
            attachment_contexts = [
                (attachment or {}).get("attachment_context")
                for attachment in (attachments or [])
                if (attachment or {}).get("attachment_context")
            ]
            if image_contexts:
                query_parts.append(
                    "Image-derived context:\n"
                    + "\n".join(f"- {content}" for content in image_contexts[:2])
                )
            if attachment_contexts:
                query_parts.append(
                    "Attachment-derived context:\n"
                    + "\n\n".join(str(content) for content in attachment_contexts[:3])
                )
            query_text = "\n\n".join(query_parts)
            live_trace.update({
                "retrieval_question_chars": len(str(retrieval_question or "")),
                "rag_query_text_chars": len(query_text),
                "rag_query_text_preview": self._trace_preview(query_text),
                "attachment_context_count": len(attachment_contexts),
                "attachment_context_chars": sum(len(str(item)) for item in attachment_contexts),
            })
            aquery_history, aquery_history_meta = self._build_aquery_history(
                history=history or [],
                query_text=query_text,
            )
            live_trace["aquery_history"] = aquery_history_meta
            await self._emit_progress(
                progress_callback,
                stage="aquery_history",
                status="done",
                label="相关对话上下文筛选完成",
                started_at=progress_base,
                details=aquery_history_meta,
            )

            stage_started = perf_counter()
            await self._emit_progress(
                progress_callback,
                stage="knowledge_base",
                status="running",
                label="正在连接课程知识库",
                started_at=progress_base,
            )
            try:
                rag = self._get_instance(class_id)
            except Exception as exc:
                logger.warning(
                    "raganything_instance_fallback",
                    class_id=class_id,
                    reason=str(exc),
                )
                return None, "instance_init_failed", None, self._safe_error_detail(exc)
            mark("get_instance", stage_started)
            await self._emit_progress(
                progress_callback,
                stage="knowledge_base",
                status="done",
                label="课程知识库连接完成",
                started_at=progress_base,
            )

            stage_started = perf_counter()
            await self._emit_progress(
                progress_callback,
                stage="query_engine_ready",
                status="running",
                label="正在检查检索引擎状态",
                started_at=progress_base,
            )
            try:
                await self._ensure_rag_query_ready(rag)
            except Exception as exc:
                logger.warning(
                    "raganything_query_init_failed",
                    class_id=class_id,
                    mode=query_mode,
                    reason=str(exc),
                )
                return None, "query_init_failed", None, self._safe_error_detail(exc)
            mark("ensure_query_ready", stage_started)
            await self._emit_progress(
                progress_callback,
                stage="query_engine_ready",
                status="done",
                label="检索引擎已就绪",
                started_at=progress_base,
            )

            has_image = any((attachment or {}).get("file_type") == "image" for attachment in (attachments or []))
            logger.info(
                "raganything_query_attempt",
                class_id=class_id,
                mode=query_mode,
                has_image=has_image,
            )
            stage_started = perf_counter()
            await self._emit_progress(
                progress_callback,
                stage="official_retrieval",
                status="running",
                label="正在进行关键词抽取、图谱检索、向量召回与回答生成",
                started_at=progress_base,
                details={"query_mode": query_mode, "has_image": has_image},
            )
            try:
                raw, query_method = await self._invoke_rag_query(
                    rag=rag,
                    query_text=query_text,
                    query_mode=query_mode,
                    history=aquery_history,
                    attachments=attachments or [],
                    prefer_multimodal=has_image,
                    class_id=class_id,
                    role=role,
                )
            except Exception as exc:
                logger.warning(
                    "raganything_query_fallback",
                    class_id=class_id,
                    mode=query_mode,
                    reason=str(exc),
                )
                return None, "query_exception", None, self._safe_error_detail(exc)
            mark("invoke_rag_query", stage_started)
            await self._emit_progress(
                progress_callback,
                stage="official_retrieval",
                status="done",
                label="课程资料检索与初版回答完成",
                started_at=progress_base,
                details={"query_method": query_method, "latency_ms": stage_timings_ms.get("invoke_rag_query")},
            )

            stage_started = perf_counter()
            answer, sources, confidence = self._normalize_rag_query_output(raw)
            mark("normalize_output", stage_started)
            await self._emit_progress(
                progress_callback,
                stage="evidence_prepare",
                status="done",
                label="检索证据整理完成",
                started_at=progress_base,
                details={"source_count": len(sources or [])},
            )
            query_trace = self._build_query_trace(
                raw=raw,
                query_method=query_method,
                requested_mode=query_mode,
                has_image=has_image,
                live_trace=live_trace,
            )
            query_trace["stage_timings_ms"] = dict(stage_timings_ms)
            query_trace["source_count_initial"] = len(sources or [])
            query_trace["sources_initial"] = self._source_trace_summary(sources)
            if not answer:
                logger.warning(
                    "raganything_query_empty_answer",
                    class_id=class_id,
                    mode=query_mode,
                )
                return None, "empty_answer", query_method, None

            stage_started = perf_counter()
            sources, structured_match_meta = self._augment_sources_with_structured_table_matches(
                question=retrieval_question,
                sources=sources,
                class_id=class_id,
            )
            mark("structured_table_match", stage_started)
            query_trace["stage_timings_ms"] = dict(stage_timings_ms)
            query_trace["structured_table_match"] = structured_match_meta
            query_trace["source_count_after_structured_table_match"] = len(sources or [])
            query_trace["sources_after_structured_table_match"] = self._source_trace_summary(sources)

            stage_started = perf_counter()
            sources, kg_backtrace_meta = self._augment_sources_with_kg_material_backtrace(
                raw=raw,
                question=retrieval_question,
                answer=answer,
                sources=sources,
                class_id=class_id,
            )
            mark("kg_material_backtrace", stage_started)
            query_trace["stage_timings_ms"] = dict(stage_timings_ms)
            query_trace["kg_material_backtrace"] = kg_backtrace_meta
            query_trace["source_count_after_kg_material_backtrace"] = len(sources or [])
            query_trace["sources_after_kg_material_backtrace"] = self._source_trace_summary(sources)

            stage_started = perf_counter()
            await self._emit_progress(
                progress_callback,
                stage="rerank",
                status="running",
                label="正在重排候选资料",
                started_at=progress_base,
                details={"source_count": len(sources or [])},
            )
            sources, rerank_meta = await self._rerank_main_chain_sources(
                question=retrieval_question,
                sources=sources,
            )
            mark("rerank_sources", stage_started)
            sources, relevance_filter_meta = self._filter_low_relevance_sources(sources)
            rerank_meta = {
                **rerank_meta,
                "source_selected_count": len(sources or []),
                "relevance_filter": relevance_filter_meta,
            }
            await self._emit_progress(
                progress_callback,
                stage="rerank",
                status="done",
                label="候选资料重排完成",
                started_at=progress_base,
                details={"source_count": len(sources or [])},
            )
            query_trace["stage_timings_ms"] = dict(stage_timings_ms)
            query_trace["source_count_after_rerank"] = len(sources or [])
            query_trace["rerank"] = rerank_meta.get("rerank_trace")
            query_trace["relevance_filter"] = relevance_filter_meta
            stage_started = perf_counter()
            sources = self._enrich_sources_with_material_metadata(sources, class_id)
            mark("metadata_enrichment", stage_started)
            query_trace["stage_timings_ms"] = dict(stage_timings_ms)
            query_trace["source_count_after_metadata_enrichment"] = len(sources or [])
            query_trace["sources_after_metadata_enrichment"] = self._source_trace_summary(sources)
            source_count_before_active_filter = len(sources or [])
            stage_started = perf_counter()
            sources = self._filter_sources_to_active_materials(sources, class_id)
            mark("active_material_filter", stage_started)
            query_trace["stage_timings_ms"] = dict(stage_timings_ms)
            query_trace["source_count_after_active_filter"] = len(sources or [])
            stage_started = perf_counter()
            sources, answer_source_alignment = self._prioritize_sources_by_answer_evidence(
                sources=sources,
                raw=raw,
                answer=answer,
                question=retrieval_question,
            )
            sources, answer_reference_mapping = self._annotate_sources_with_answer_references(
                sources=sources,
                raw=raw,
                answer=answer,
            )
            mark("answer_source_alignment", stage_started)
            query_trace["stage_timings_ms"] = dict(stage_timings_ms)
            query_trace["answer_source_alignment"] = answer_source_alignment
            query_trace["answer_reference_mapping"] = answer_reference_mapping
            query_trace["sources_final"] = self._source_trace_summary(sources)
            if source_count_before_active_filter and not sources:
                logger.info(
                    "raganything_query_sources_filtered_to_inactive_materials",
                    class_id=class_id,
                    mode=query_mode,
                )
                return None, "inactive_sources_filtered", query_method, None
            if source_count_before_active_filter != len(sources or []):
                rerank_meta = {
                    **rerank_meta,
                    "source_selected_count": len(sources or []),
                }
            force_structured_table_answer = bool(
                (structured_match_meta or {}).get("matched_count")
                and (structured_match_meta or {}).get("enabled")
            )
            answer_repair_reason = (
                "structured_table_grounding"
                if force_structured_table_answer
                else self._answer_repair_reason(answer)
            )
            query_trace["answer_repair_checked"] = True
            query_trace["answer_repair_policy"] = getattr(settings, "RAG_ANSWER_REPAIR_POLICY", "severe_only")
            query_trace["answer_repair_would_trigger_reason"] = answer_repair_reason
            should_repair_answer = bool(settings.RAG_ANSWER_REPAIR_ENABLED) and sources and bool(answer_repair_reason)
            if not should_repair_answer:
                query_trace["answer_repair_triggered"] = False
                if not bool(settings.RAG_ANSWER_REPAIR_ENABLED):
                    query_trace["answer_repair_skipped_reason"] = "disabled"
                elif not sources:
                    query_trace["answer_repair_skipped_reason"] = "no_sources"
                else:
                    query_trace["answer_repair_skipped_reason"] = "raw_answer_accepted"
            if should_repair_answer:
                stage_started = perf_counter()
                await self._emit_progress(
                    progress_callback,
                    stage="answer_repair",
                    status="running",
                    label="正在优化回答可读性",
                    started_at=progress_base,
                    details={"reason": answer_repair_reason},
                )
                repaired_answer = await self._repair_answer_from_sources(
                    question=retrieval_question,
                    answer=answer,
                    sources=sources,
                    role=role,
                )
                mark("answer_repair", stage_started)
                query_trace["stage_timings_ms"] = dict(stage_timings_ms)
                if repaired_answer:
                    answer = repaired_answer
                    rerank_meta = {
                        **rerank_meta,
                        "answer_repaired": True,
                        "answer_repair_reason": answer_repair_reason,
                    }
                    query_trace["answer_repaired"] = True
                    query_trace["answer_repair_triggered"] = True
                    query_trace["answer_repair_reason"] = rerank_meta["answer_repair_reason"]
                    await self._emit_progress(
                        progress_callback,
                        stage="answer_repair",
                        status="done",
                        label="回答可读性优化完成",
                        started_at=progress_base,
                        details={"latency_ms": stage_timings_ms.get("answer_repair")},
                    )
                else:
                    query_trace["answer_repair_triggered"] = True
                    query_trace["answer_repaired"] = False
                    query_trace["answer_repair_reason"] = answer_repair_reason
                    query_trace["answer_repair_skipped_reason"] = "repair_generation_failed_or_still_unreadable"
                    await self._emit_progress(
                        progress_callback,
                        stage="answer_repair",
                        status="done",
                        label="回答可读性检查完成",
                        started_at=progress_base,
                        details={"repaired": False, "latency_ms": stage_timings_ms.get("answer_repair")},
                    )
            if confidence <= 0:
                top_score = next((source.get("score") for source in sources if source.get("score") is not None), None)
                confidence = min(0.95, max(0.55, float(top_score))) if top_score is not None else 0.6
            query_trace["answer_chars"] = len(str(answer or ""))
            query_trace["answer_preview"] = self._trace_preview(answer, limit=700)
            query_trace["stage_timings_ms"] = dict(stage_timings_ms)
            query_trace["total_latency_ms"] = round((perf_counter() - query_started) * 1000, 2)
            invoke_ms = float(stage_timings_ms.get("invoke_rag_query") or 0.0)
            llm_total_ms = float(query_trace.get("llm_total_latency_ms") or 0.0)
            if invoke_ms > 0 and llm_total_ms >= 0:
                query_trace["retrieval_context_latency_estimated_ms"] = round(
                    max(0.0, invoke_ms - llm_total_ms),
                    2,
                )
                query_trace["retrieval_context_latency_estimation_note"] = (
                    "invoke_rag_query minus traced LightRAG/RAG-Anything LLM calls; "
                    "covers graph retrieval, vector retrieval, context assembly, and framework overhead."
                )

            return (
                RAGResult(
                    answer=answer,
                    sources=sources,
                    confidence=confidence,
                    suggestions=self._suggestions(retrieval_question),
                    meta={**rerank_meta, "query_trace": query_trace},
                ),
                None,
                query_method,
                None,
            )
        finally:
            if trace_token is not None:
                _QUERY_TRACE_CONTEXT.reset(trace_token)

    def _build_effective_query_text(self, *, question: str, rewrite_bundle: dict[str, Any]) -> str:
        queries = [
            re.sub(r"\s+", " ", str(item or "").strip())
            for item in (rewrite_bundle.get("queries") or [])
            if str(item or "").strip()
        ]
        if len(queries) <= 1:
            return question

        extra_queries = [item for item in queries[1:] if item.lower() != queries[0].lower()]
        if not extra_queries:
            return question

        retrieval_terms = self._compact_retrieval_terms(
            question=question,
            rewrite_bundle=rewrite_bundle,
            max_terms=8,
        )
        if not retrieval_terms:
            return question

        # Keep the submitted query clean for LightRAG keyword extraction:
        # original standalone question + terse terms only, no instructional prose.
        return (question.strip() + "\n" + "；".join(retrieval_terms)).strip()

    def _compact_retrieval_terms(
        self,
        *,
        question: str,
        rewrite_bundle: dict[str, Any],
        max_terms: int = 8,
    ) -> list[str]:
        original = re.sub(r"\s+", " ", str(question or "")).strip()
        original_key = self._term_key(original)
        candidates: list[str] = []
        rejected: list[str] = []

        queries = [
            re.sub(r"\s+", " ", str(item or "").strip())
            for item in (rewrite_bundle.get("queries") or [])
            if str(item or "").strip()
        ]
        for query in queries[1:]:
            candidates.extend(self._split_retrieval_query_terms(query))
        for term in rewrite_bundle.get("retrieval_focus_terms", []) or []:
            candidates.append(str(term or "").strip())

        terms: list[str] = []
        seen: set[str] = {original_key} if original_key else set()
        for candidate in candidates:
            normalized = self._normalize_retrieval_term(candidate)
            key = self._term_key(normalized)
            if not normalized or not key or key in seen:
                continue
            if self._is_broad_course_term(normalized) and key not in original_key:
                rejected.append(f"{normalized}:broad_course_term_not_in_question")
                continue
            if self._is_noisy_retrieval_term(normalized):
                rejected.append(f"{normalized}:noisy")
                continue
            seen.add(key)
            terms.append(normalized)
            if len(terms) >= max(1, int(max_terms)):
                break

        if bool(getattr(settings, "RAG_QUERY_TRACE_ENABLED", True)):
            trace = _QUERY_TRACE_CONTEXT.get()
            if trace is not None:
                trace["compact_retrieval_terms"] = terms
                trace["compact_retrieval_terms_rejected"] = rejected[:12]
        return terms

    def _is_broad_course_term(self, term: str) -> bool:
        broad_terms = {
            "udp",
            "ip",
            "http",
            "https",
            "dns",
        }
        return self._term_key(term) in {self._term_key(item) for item in broad_terms}

    def _split_retrieval_query_terms(self, value: str) -> list[str]:
        text = re.sub(r"\s+", " ", str(value or "")).strip()
        if not text:
            return []
        if len(text) <= 24 and not re.search(r"[;；,，、\n]", text):
            return [text]
        parts = re.split(r"[;；,，、\n]+|\s{1,}", text)
        return [part.strip() for part in parts if part.strip()]

    def _normalize_retrieval_term(self, value: str) -> str:
        term = re.sub(r"\s+", " ", str(value or "")).strip(" \t\r\n-:：;；,，、。")
        if len(term) > 48:
            term = term[:48].rstrip()
        return term

    def _term_key(self, value: str) -> str:
        return re.sub(r"[\s\-_：:；;,，、。]+", "", str(value or "").strip().lower())

    def _is_noisy_retrieval_term(self, term: str) -> bool:
        normalized = self._term_key(term)
        if not normalized:
            return True
        if len(normalized) <= 1:
            return True
        if len(normalized) > 40 and not re.search(r"[A-Za-z]", normalized):
            return True
        noisy_terms = {
            "检索",
            "检索词",
            "检索焦点",
            "检索辅助信息",
            "扩展词",
            "问题",
            "问题意图",
            "回答",
            "资料",
            "课程资料",
            "查找",
            "课程",
            "内容",
            "证据",
            "原始问题",
            "仅用于召回课程资料",
            "回答时必须以原始问题为准",
            "userquery",
            "query",
            "context",
            "providedcontext",
            "documentchunks",
        }
        if normalized in {self._term_key(item) for item in noisy_terms}:
            return True
        if re.fullmatch(r"\d+", normalized):
            return True
        return False

    def _trace_preview(self, value: Any, *, limit: int | None = None) -> str:
        if not bool(getattr(settings, "RAG_QUERY_TRACE_ENABLED", True)):
            return ""
        max_chars = int(limit if limit is not None else getattr(settings, "RAG_QUERY_TRACE_PREVIEW_CHARS", 1200) or 1200)
        if max_chars <= 0:
            return ""
        text = re.sub(r"\s+", " ", str(value or "")).strip()
        if len(text) <= max_chars:
            return text
        return text[:max_chars].rstrip() + "..."

    def _full_raw_answer_trace(self, value: Any) -> dict[str, Any]:
        if not bool(getattr(settings, "RAG_QUERY_TRACE_FULL_RAW_ANSWER_ENABLED", False)):
            return {}
        max_chars = int(getattr(settings, "RAG_QUERY_TRACE_FULL_RAW_ANSWER_MAX_CHARS", 20000) or 0)
        if max_chars <= 0:
            return {}
        text = str(value or "")
        truncated = len(text) > max_chars
        return {
            "answer_full": text[:max_chars],
            "answer_full_chars": len(text),
            "answer_full_truncated": truncated,
        }

    def _build_query_rewrite_trace(
        self,
        *,
        question: str,
        effective_question: str,
        rewrite_bundle: dict[str, Any],
    ) -> dict[str, Any]:
        queries = [
            str(item).strip()
            for item in (rewrite_bundle.get("queries") or [])
            if str(item).strip()
        ]
        compact_terms = self._compact_retrieval_terms(
            question=question,
            rewrite_bundle=rewrite_bundle,
            max_terms=8,
        )
        return {
            "enabled": bool(rewrite_bundle.get("enabled")),
            "mode": rewrite_bundle.get("mode"),
            "variant_count": rewrite_bundle.get("variant_count", len(queries)),
            "queries": queries[: int(getattr(settings, "RAG_QUERY_REWRITE_MAX_VARIANTS", 3) or 3)],
            "submitted_query_policy": "original_question_plus_compact_terms",
            "submitted_compact_terms": compact_terms,
            "intent": rewrite_bundle.get("intent"),
            "intent_confidence": rewrite_bundle.get("intent_confidence"),
            "intent_signals": rewrite_bundle.get("intent_signals"),
            "retrieval_focus_terms": rewrite_bundle.get("retrieval_focus_terms"),
            "answer_focus": rewrite_bundle.get("answer_focus"),
            "original_question_chars": len(str(question or "")),
            "effective_question_chars": len(str(effective_question or "")),
            "effective_question_preview": self._trace_preview(effective_question),
        }

    def _source_trace_item(self, source: dict[str, Any], index: int) -> dict[str, Any]:
        metadata = source.get("metadata") if isinstance(source.get("metadata"), dict) else {}
        evidence_text = self._source_evidence_text(source)
        return {
            "index": index,
            "chunk_id": source.get("chunk_id") or source.get("id") or source.get("reference_id"),
            "source_name": source.get("source_name") or source.get("name") or source.get("file_name"),
            "material_id": source.get("material_id") or metadata.get("material_id"),
            "atomic_id": source.get("atomic_id") or metadata.get("atomic_id"),
            "modality": source.get("modality") or metadata.get("modality"),
            "page": source.get("page") or metadata.get("page") or metadata.get("page_idx"),
            "score": source.get("score"),
            "retrieval_score": source.get("retrieval_score"),
            "rerank_score": source.get("rerank_score"),
            "citation_index": source.get("citation_index"),
            "citation_label": source.get("citation_label"),
            "answer_reference_match": source.get("answer_reference_match"),
            "answer_alignment_score": source.get("answer_alignment_score"),
            "text_chars": len(evidence_text),
            "text_preview": self._trace_preview(evidence_text, limit=500),
        }

    def _source_trace_summary(self, sources: list[dict] | None, *, limit: int = 8) -> dict[str, Any]:
        normalized_sources = [source for source in (sources or []) if isinstance(source, dict)]
        return {
            "count": len(normalized_sources),
            "items": [
                self._source_trace_item(source, index)
                for index, source in enumerate(normalized_sources[:limit], start=1)
            ],
        }

    def _augment_sources_with_kg_material_backtrace(
        self,
        *,
        raw: Any,
        question: str,
        answer: str,
        sources: list[dict],
        class_id: str,
    ) -> tuple[list[dict], dict[str, Any]]:
        kg_terms = self._kg_terms_used_in_answer(raw=raw, question=question, answer=answer)
        if not kg_terms:
            return sources, {"applied": False, "reason": "no_answer_aligned_kg_terms"}

        try:
            db = SessionLocal()
        except Exception as exc:
            logger.warning("rag_kg_backtrace_session_failed", class_id=class_id, error=str(exc))
            return sources, {"applied": False, "reason": "session_failed", "error": str(exc)[:300]}

        try:
            entities = db.query(KnowledgeEntity).filter(
                KnowledgeEntity.class_id == class_id,
            ).all()
            matched_entities = [
                entity for entity in entities
                if str(entity.status or "").lower() != "rejected"
                and self._term_key(entity.name) in kg_terms
            ]

            material_ids: list[str] = []
            hit_terms: list[str] = []
            for entity in matched_entities:
                if entity.name and entity.name not in hit_terms:
                    hit_terms.append(entity.name)
                if entity.source_material_id:
                    material_ids.append(str(entity.source_material_id))
                material_ids.extend(self._source_material_ids_from_provenance(entity.provenance))

            material_ids = self._unique_strings(material_ids)
            if not material_ids:
                return sources, {
                    "applied": False,
                    "reason": "matched_kg_terms_without_material_ids",
                    "matched_terms": hit_terms[:12],
                }

            materials = db.query(Material).filter(
                Material.class_id == class_id,
                Material.id.in_(material_ids),
                Material.is_active == True,
            ).all()
            tasks = db.query(FileParseTask).filter(
                FileParseTask.class_id == class_id,
                FileParseTask.material_id.in_([material.id for material in materials]),
                FileParseTask.status == "completed",
            ).all()
        except Exception as exc:
            logger.warning("rag_kg_backtrace_lookup_failed", class_id=class_id, error=str(exc))
            return sources, {"applied": False, "reason": "lookup_failed", "error": str(exc)[:300]}
        finally:
            try:
                db.close()
            except Exception:
                pass

        material_by_id = {str(material.id): material for material in materials}
        terms_by_key = {self._term_key(term): term for term in hit_terms if self._term_key(term)}
        existing_keys = self._source_dedupe_keys(sources)
        backfilled: list[dict[str, Any]] = []
        selected_chunk_count = 0
        duplicate_source_count = 0
        for task in tasks:
            material = material_by_id.get(str(task.material_id))
            if material is None:
                continue
            selected_chunks = self._select_kg_backtrace_chunks(task, set(terms_by_key), limit=3)
            selected_chunk_count += len(selected_chunks)
            for chunk in selected_chunks:
                source = self._source_from_parse_task_chunk(
                    material=material,
                    task=task,
                    chunk=chunk,
                    hit_terms=[
                        label for key, label in terms_by_key.items()
                        if key and key in self._term_key(chunk.get("text") or chunk.get("content") or "")
                    ] or hit_terms[:8],
                )
                source_keys = self._source_dedupe_key_variants(source)
                if source_keys & existing_keys:
                    duplicate_source_count += 1
                    continue
                existing_keys.update(source_keys)
                backfilled.append(source)

        if not backfilled:
            if selected_chunk_count:
                return sources, {
                    "applied": True,
                    "reason": "matched_material_chunks_already_present",
                    "matched_terms": hit_terms[:12],
                    "material_ids": material_ids[:12],
                    "added_source_count": 0,
                    "matched_chunk_count": selected_chunk_count,
                    "duplicate_source_count": duplicate_source_count,
                }
            return sources, {
                "applied": False,
                "reason": "no_completed_chunks_for_matched_materials",
                "matched_terms": hit_terms[:12],
                "material_ids": material_ids[:12],
            }

        return [*backfilled, *(sources or [])], {
            "applied": True,
            "matched_terms": hit_terms[:12],
            "material_ids": material_ids[:12],
            "added_source_count": len(backfilled),
            "matched_chunk_count": selected_chunk_count,
            "duplicate_source_count": duplicate_source_count,
            "added_sources": self._source_trace_summary(backfilled, limit=6),
        }

    def _kg_terms_used_in_answer(self, *, raw: Any, question: str, answer: str) -> set[str]:
        raw_terms = self._kg_terms_from_raw_payload(raw)
        if not raw_terms:
            return set()
        qa_key = self._term_key(f"{question}\n{answer}")
        if not qa_key:
            return set()
        used: set[str] = set()
        for term in raw_terms:
            key = self._term_key(term)
            if not key or len(key) <= 1:
                continue
            if self._is_noisy_kg_backtrace_term(term):
                continue
            if key in qa_key:
                used.add(key)
        return used

    def _kg_terms_from_raw_payload(self, raw: Any) -> set[str]:
        if not isinstance(raw, dict):
            return set()
        data = raw.get("data") if isinstance(raw.get("data"), dict) else {}
        terms: set[str] = set()

        def add_value(value: Any) -> None:
            text = re.sub(r"\s+", " ", str(value or "").strip())
            if text:
                terms.add(text)

        for entity in data.get("entities") or []:
            if not isinstance(entity, dict):
                add_value(entity)
                continue
            for key in ("entity_name", "name", "entity", "id", "label"):
                add_value(entity.get(key))

        for relation in data.get("relationships") or []:
            if not isinstance(relation, dict):
                continue
            for key in ("src_id", "tgt_id", "source", "target", "source_name", "target_name"):
                add_value(relation.get(key))
            src_tgt = relation.get("src_tgt")
            if isinstance(src_tgt, (list, tuple)):
                for item in src_tgt:
                    add_value(item)
        return terms

    def _is_noisy_kg_backtrace_term(self, term: str) -> bool:
        key = self._term_key(term)
        if not key:
            return True
        noisy = {
            "表",
            "表格",
            "文件",
            "资料",
            "课程",
            "课程资料",
            "内容",
            "步骤",
            "事件描述",
            "细节说明",
            "学习建议",
            "详细解释",
            "简明结论",
            "身份",
            "故事类型",
            "核心事件",
            "教学建议",
        }
        noisy_keys = {self._term_key(value) for value in noisy | PROJECTION_COURSE_ARTIFACT_TERMS}
        return key in noisy_keys

    def _unique_strings(self, values: list[Any]) -> list[str]:
        unique: list[str] = []
        seen: set[str] = set()
        for value in values:
            text = str(value or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            unique.append(text)
        return unique

    def _source_dedupe_keys(self, sources: list[dict] | None) -> set[str]:
        keys: set[str] = set()
        for source in sources or []:
            if not isinstance(source, dict):
                continue
            keys.update(self._source_dedupe_key_variants(source))
        return {key for key in keys if key}

    def _source_dedupe_key(self, source: dict[str, Any]) -> str:
        variants = self._source_dedupe_key_variants(source)
        return next(iter(variants), "")

    def _source_dedupe_key_variants(self, source: dict[str, Any]) -> set[str]:
        metadata = source.get("metadata") if isinstance(source.get("metadata"), dict) else {}
        chunk_id = source.get("chunk_id") or metadata.get("chunk_id")
        material_id = source.get("material_id") or metadata.get("material_id")
        variants: set[str] = set()
        if chunk_id or material_id:
            variants.add(f"{material_id or ''}:{chunk_id or ''}")
        if chunk_id:
            variants.add(f"chunk:{chunk_id}")
        text = self._source_evidence_text(source)
        text_key = self._term_key(text[:500])
        if text_key:
            variants.add(f"text:{text_key}")
        return variants

    def _select_kg_backtrace_chunks(
        self,
        task: FileParseTask,
        term_keys: set[str],
        *,
        limit: int,
    ) -> list[dict[str, Any]]:
        chunks = [chunk for chunk in (task.chunks or []) if isinstance(chunk, dict)]
        if not chunks:
            text = re.sub(r"\s+", " ", str(task.extracted_text or "").strip())
            if not text:
                return []
            return [{
                "chunk_id": f"{task.material_id}-extracted-text",
                "text": text,
                "page": 0,
                "metadata": {"source": "file_parse_task_extracted_text"},
            }]

        scored: list[tuple[int, int, dict[str, Any]]] = []
        for index, chunk in enumerate(chunks):
            text_key = self._term_key(chunk.get("text") or chunk.get("content") or "")
            hit_count = sum(1 for term_key in term_keys if term_key and term_key in text_key)
            scored.append((hit_count, -index, chunk))

        matched = [chunk for hit_count, _, chunk in sorted(scored, reverse=True) if hit_count > 0]
        if matched:
            return matched[: max(1, int(limit))]
        return chunks[: max(1, int(limit))]

    def _source_from_parse_task_chunk(
        self,
        *,
        material: Material,
        task: FileParseTask,
        chunk: dict[str, Any],
        hit_terms: list[str],
    ) -> dict[str, Any]:
        chunk_metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {}
        text = self._clean_lightrag_chunk_text(chunk.get("text") or chunk.get("content") or "")
        display_name = material.file_name or material.title or "unknown"
        source_metadata = {
            **chunk_metadata,
            "source": "kg_material_backtrace",
            "material_id": material.id,
            "task_id": task.id,
            "kg_hit_terms": hit_terms[:12],
            "kg_backtrace": True,
        }
        return {
            "name": display_name,
            "source_name": display_name,
            "file_name": display_name,
            "type": material.mime_type,
            "page": chunk.get("page") or chunk.get("page_idx") or chunk_metadata.get("page") or chunk_metadata.get("page_idx"),
            "score": 1.0,
            "retrieval_score": 1.0,
            "chunk_id": chunk.get("chunk_id") or chunk.get("id") or chunk_metadata.get("chunk_id"),
            "snippet": text,
            "raw_text": text,
            "material_id": material.id,
            "metadata": source_metadata,
        }

    def _raw_context_trace(self, raw: Any) -> dict[str, Any]:
        if not isinstance(raw, dict):
            text = str(raw or "")
            return {
                "raw_text_chars": len(text),
                "raw_text_preview": self._trace_preview(text, limit=500),
                **self._full_raw_answer_trace(text),
            }

        def text_from_item(item: Any) -> str:
            if isinstance(item, str):
                return item
            if not isinstance(item, dict):
                return ""
            return str(
                item.get("content")
                or item.get("text")
                or item.get("snippet")
                or item.get("description")
                or item.get("name")
                or item.get("entity_name")
                or ""
            )

        def list_stats(value: Any) -> dict[str, Any]:
            if not isinstance(value, list):
                return {"count": 0, "text_chars": 0}
            texts = [text_from_item(item) for item in value]
            return {
                "count": len(value),
                "text_chars": sum(len(text) for text in texts),
                "first_preview": self._trace_preview(next((text for text in texts if text.strip()), ""), limit=350),
            }

        data = raw.get("data") if isinstance(raw.get("data"), dict) else {}
        context = raw.get("context") if isinstance(raw.get("context"), dict) else {}
        llm_response = raw.get("llm_response") if isinstance(raw.get("llm_response"), dict) else {}
        answer = (
            llm_response.get("content")
            or raw.get("answer")
            or raw.get("response")
            or raw.get("output")
            or raw.get("text")
            or ""
        )
        return {
            "answer_chars": len(str(answer or "")),
            "answer_preview": self._trace_preview(answer, limit=500),
            **self._full_raw_answer_trace(answer),
            "sources": list_stats(raw.get("sources")),
            "citations": list_stats(raw.get("citations")),
            "references": list_stats(raw.get("references")),
            "chunks": list_stats(raw.get("chunks")),
            "evidence": list_stats(raw.get("evidence")),
            "data_chunks": list_stats(data.get("chunks")),
            "data_references": list_stats(data.get("references")),
            "data_entities": list_stats(data.get("entities")),
            "data_relationships": list_stats(data.get("relationships")),
            "context_sources": list_stats(context.get("sources")),
            "context_chunks": list_stats(context.get("chunks")),
        }

    def _build_query_trace(
        self,
        *,
        raw: Any,
        query_method: str | None,
        requested_mode: str,
        has_image: bool,
        live_trace: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        trace: dict[str, Any] = {
            "trace_version": 2,
            "query_method": query_method,
            "requested_mode": requested_mode,
            "used_multimodal_input": bool(has_image),
            "raw_type": type(raw).__name__,
            "lightrag_internal_rerank_requested": self._lightrag_internal_rerank_enabled(),
        }
        if live_trace:
            trace.update({
                key: value
                for key, value in live_trace.items()
                if key not in {"stage_timings_ms"}
            })
        trace["raw_context"] = self._raw_context_trace(raw)
        if not isinstance(raw, dict):
            trace["raw_has_content"] = bool(str(raw or "").strip()) if raw is not None else False
            return trace

        metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
        data = raw.get("data") if isinstance(raw.get("data"), dict) else {}
        context = raw.get("context") if isinstance(raw.get("context"), dict) else {}

        trace.update({
            "effective_mode": metadata.get("adapter_effective_mode"),
            "attempted_modes": metadata.get("adapter_attempted_modes"),
            "mode_attempts": metadata.get("adapter_mode_attempts"),
            "include_references_requested": metadata.get("adapter_include_references_requested"),
            "lightrag_rerank_requested": metadata.get("adapter_lightrag_rerank_requested"),
            "metadata_keys": sorted(str(key) for key in metadata.keys())[:24],
            "top_level_keys": sorted(str(key) for key in raw.keys())[:24],
        })

        count_sources = lambda value: len(value) if isinstance(value, list) else 0
        trace["raw_source_counts"] = {
            "sources": count_sources(raw.get("sources")),
            "citations": count_sources(raw.get("citations")),
            "references": count_sources(raw.get("references")),
            "chunks": count_sources(raw.get("chunks")),
            "evidence": count_sources(raw.get("evidence")),
            "data_chunks": count_sources(data.get("chunks")),
            "data_references": count_sources(data.get("references")),
            "data_entities": count_sources(data.get("entities")),
            "data_relationships": count_sources(data.get("relationships")),
            "context_sources": count_sources(context.get("sources")),
            "context_chunks": count_sources(context.get("chunks")),
        }
        answer_key = next(
            (
                key for key in ("llm_response", "answer", "response", "output", "text")
                if raw.get(key)
            ),
            None,
        )
        trace["answer_key"] = answer_key
        return trace

    def _lightrag_internal_rerank_enabled(self) -> bool:
        provider = str(getattr(settings, "RERANKER_PROVIDER", "") or "").strip().lower()
        return provider not in {"", "none", "mock"}

    def _augment_sources_with_structured_table_matches(
        self,
        *,
        question: str,
        sources: list[dict],
        class_id: str,
    ) -> tuple[list[dict], dict[str, Any]]:
        if not self._is_structured_table_lookup_question(question):
            return sources, {"enabled": False, "reason": "not_table_lookup"}

        matched_sources = self._lookup_structured_table_sources(
            question=question,
            class_id=class_id,
            limit=5,
        )
        if not matched_sources:
            return sources, {"enabled": True, "matched_count": 0}

        merged: list[dict] = []
        seen: set[str] = set()

        def source_key(source: dict[str, Any]) -> str:
            metadata = source.get("metadata") if isinstance(source.get("metadata"), dict) else {}
            explicit = source.get("chunk_id") or source.get("id") or metadata.get("chunk_id")
            if explicit:
                return str(explicit)
            return self._source_evidence_text(source)[:500].lower()

        for source in list(matched_sources) + list(sources or []):
            if not isinstance(source, dict):
                continue
            key = source_key(source)
            if key in seen:
                continue
            seen.add(key)
            merged.append(source)

        return merged, {
            "enabled": True,
            "matched_count": len(matched_sources),
            "matched": self._source_trace_summary(matched_sources),
        }

    def _is_structured_table_lookup_question(self, question: str) -> bool:
        text = str(question or "").strip().lower()
        if not text:
            return False
        table_markers = ("表格", "表中", "中英对照", "markdown 表", "markdown table", "table")
        lookup_markers = ("是什么", "什么意思", "含义", "定义", "解释", "对应", "哪一行", "在哪")
        return any(marker in text for marker in table_markers) and any(marker in text for marker in lookup_markers)

    def _lookup_structured_table_sources(
        self,
        *,
        question: str,
        class_id: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        query_terms = self._structured_table_query_terms(question)
        if not query_terms:
            return []

        try:
            db = SessionLocal()
            tasks = (
                db.query(FileParseTask, Material)
                .join(Material, Material.id == FileParseTask.material_id)
                .filter(
                    FileParseTask.class_id == class_id,
                    FileParseTask.status == "completed",
                    Material.class_id == class_id,
                    Material.is_active == True,
                    Material.kb_status == "indexed",
                )
                .all()
            )
        except Exception as exc:
            logger.warning("structured_table_source_lookup_failed", class_id=class_id, error=str(exc))
            try:
                db.close()
            except Exception:
                pass
            return []
        finally:
            if "db" in locals():
                try:
                    db.close()
                except Exception:
                    pass

        context_terms = ["中英对照", "表格", "markdown 表格", "结构化信息"]
        scored: list[tuple[float, dict[str, Any]]] = []
        for task, material in tasks:
            for index, chunk in enumerate(task.chunks or [], start=1):
                if not isinstance(chunk, dict):
                    continue
                metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {}
                text = str(chunk.get("text") or chunk.get("content") or metadata.get("table_text") or "")
                if not text.strip():
                    continue
                metadata_text = json.dumps(metadata, ensure_ascii=False).lower()
                is_structured_table = (
                    metadata.get("origin") == "markdown_table"
                    or str(metadata.get("source_type") or "").lower() == "table"
                    or "markdown 表格" in text.lower()
                    or "结构化信息" in text
                    or "markdown_table" in metadata_text
                )
                if not is_structured_table:
                    continue

                normalized_text = text.lower()
                score = 0.0
                exact_term_hits = 0
                for term in query_terms:
                    if term and term.lower() in normalized_text:
                        exact_term_hits += 1
                        score += 3.0 + min(2.0, len(term) / 4)
                if exact_term_hits <= 0:
                    continue
                for term in context_terms:
                    if term.lower() in normalized_text or term.lower() in metadata_text:
                        score += 0.5
                if metadata.get("origin") == "markdown_table":
                    score += 1.0
                if "第 " in text and " 行" in text:
                    score += 0.5

                chunk_id = str(
                    chunk.get("chunk_id")
                    or metadata.get("chunk_id")
                    or metadata.get("atomic_id")
                    or f"{task.material_id}-structured-table-{index}"
                )
                scored.append((
                    score,
                    {
                        "chunk_id": chunk_id,
                        "name": material.file_name or material.title,
                        "source_name": material.file_name or material.title,
                        "file_name": material.file_name or material.title,
                        "source_type": "structured_table",
                        "type": "table",
                        "page": chunk.get("page") or metadata.get("page") or metadata.get("page_idx"),
                        "material_id": material.id,
                        "snippet": text[:1200],
                        "raw_text": text,
                        "retrieval_score": round(min(1.0, score / 10), 4),
                        "metadata": {
                            **metadata,
                            "material_id": material.id,
                            "source_name": material.file_name or material.title,
                            "structured_table_match": True,
                            "structured_table_score": round(score, 4),
                            "structured_table_query_terms": query_terms,
                        },
                    },
                ))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [source for _, source in scored[:limit]]

    def _structured_table_query_terms(self, question: str) -> list[str]:
        text = re.sub(r"\s+", " ", str(question or "")).strip()
        if not text:
            return []

        terms: list[str] = []
        for pattern in (
            r"[“\"']([^“”\"']{2,30})[”\"']",
            r"[，,、\s]([^，,、\s？?]{2,30})(?:是什么意思|是什么|的含义|含义|定义)",
            r"([^，,、\s？?]{2,30})(?:是什么意思|是什么|的含义|含义|定义)",
        ):
            for match in re.findall(pattern, text):
                cleaned = self._clean_structured_table_query_term(match)
                if cleaned:
                    terms.append(cleaned)

        reduced = text
        for phrase in (
            "中英对照表格",
            "中英对照表",
            "中英对照",
            "markdown表格",
            "markdown 表格",
            "表格",
            "表中",
            "里面",
            "在",
            "中",
            "请问",
            "是什么",
            "是什么意思",
            "什么意思",
            "的含义",
            "含义",
            "定义",
            "解释",
        ):
            reduced = reduced.replace(phrase, " ")
        for token in re.split(r"[\s，,。！？?、；;：:（）()\[\]【】]+", reduced):
            cleaned = self._clean_structured_table_query_term(token)
            if cleaned:
                terms.append(cleaned)

        deduped: list[str] = []
        seen: set[str] = set()
        for term in terms:
            key = term.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(term)
        return deduped[:6]

    def _clean_structured_table_query_term(self, value: Any) -> str:
        term = re.sub(r"\s+", " ", str(value or "")).strip(" ：:，,。！？?、；;\"'“”")
        if len(term) < 2 or len(term) > 30:
            return ""
        if term in {"表格", "中英对照", "含义", "定义", "概念", "什么", "意思", "里面", "资料"}:
            return ""
        return term

    def _filter_sources_to_active_materials(self, sources: list[dict], class_id: str) -> list[dict]:
        if not sources:
            return sources
        try:
            db = SessionLocal()
            active_materials = db.query(Material).filter(
                Material.class_id == class_id,
                Material.is_active == True,
            ).all()
            inactive_materials = db.query(Material).filter(
                Material.class_id == class_id,
                Material.is_active == False,
            ).all()
        except Exception as exc:
            logger.warning("rag_source_active_material_filter_failed", class_id=class_id, error=str(exc))
            try:
                db.close()
            except Exception:
                pass
            return sources
        finally:
            if "db" in locals():
                try:
                    db.close()
                except Exception:
                    pass

        active_tokens: set[str] = set()
        active_ids: set[str] = set()
        inactive_tokens: set[str] = set()
        inactive_ids: set[str] = set()

        def collect_material_tokens(material: Material) -> set[str]:
            tokens = {
                str(material.id or ""),
                str(material.file_name or ""),
                Path(str(material.file_name or "")).name,
                Path(str(material.file_name or "")).stem,
                str(material.file_path or ""),
                Path(str(material.file_path or "")).name,
                Path(str(material.file_path or "")).stem,
                str(material.title or ""),
            }
            return {token.strip() for token in tokens if token and token.strip()}

        for material in active_materials:
            if material.id:
                active_ids.add(str(material.id))
            active_tokens.update(collect_material_tokens(material))

        for material in inactive_materials:
            if material.id:
                inactive_ids.add(str(material.id))
            inactive_tokens.update(collect_material_tokens(material))

        if not active_tokens and not inactive_tokens:
            return sources
        if not active_tokens:
            return []

        filtered: list[dict] = []
        for source in sources:
            if not isinstance(source, dict):
                continue
            metadata = source.get("metadata") if isinstance(source.get("metadata"), dict) else {}
            candidates = [
                (source.get("material_id"), True),
                (source.get("doc_id"), True),
                (source.get("full_doc_id"), True),
                (source.get("file_path"), True),
                (source.get("name"), False),
                (source.get("source_name"), False),
                (source.get("file_name"), False),
                (metadata.get("material_id"), True),
                (metadata.get("doc_id"), True),
                (metadata.get("full_doc_id"), True),
                (metadata.get("source_path"), True),
                (metadata.get("file_path"), True),
                (metadata.get("source_name"), False),
            ]
            matched = False
            matched_inactive = False
            saw_material_token = False
            for candidate, is_strong_identifier in candidates:
                if candidate is None:
                    continue
                text = str(candidate).strip()
                if not text:
                    continue
                tokens = {text, Path(text).name, Path(text).stem}
                if tokens & active_tokens:
                    matched = True
                    break
                if is_strong_identifier and (tokens & inactive_tokens or text in inactive_ids):
                    matched_inactive = True
                    continue
                if text in active_ids:
                    matched = True
                    break
            if matched:
                filtered.append(source)
            elif matched_inactive:
                continue
            elif not saw_material_token:
                filtered.append(source)
        return filtered

    def _prioritize_sources_by_answer_evidence(
        self,
        *,
        sources: list[dict],
        raw: Any,
        answer: str,
        question: str,
    ) -> tuple[list[dict], dict[str, Any]]:
        if not sources:
            return sources, {"applied": False, "reason": "no_sources"}

        reference_tokens = self._answer_reference_tokens(raw=raw, answer=answer)
        support_terms = self._answer_support_terms(question=question, answer=answer)
        scored: list[tuple[float, int, dict[str, Any]]] = []
        for index, source in enumerate(sources):
            source_tokens = self._source_identity_tokens(source)
            evidence_text = self._source_evidence_text(source)
            evidence_key = self._term_key(evidence_text)
            reference_match = bool(reference_tokens and (reference_tokens & source_tokens))
            term_hits = [
                term for term in support_terms
                if self._term_key(term) and self._term_key(term) in evidence_key
            ]
            try:
                base_score = float(source.get("score") or source.get("rerank_score") or source.get("retrieval_score") or 0.0)
            except (TypeError, ValueError):
                base_score = 0.0
            alignment_score = base_score
            if reference_match:
                alignment_score += 2.0
            alignment_score += min(len(term_hits), 8) * 0.08
            aligned = dict(source)
            aligned["answer_alignment_score"] = round(alignment_score, 4)
            aligned["answer_reference_match"] = reference_match
            aligned["answer_support_term_hits"] = term_hits[:8]
            scored.append((alignment_score, -index, aligned))

        ordered = [item for _, _, item in sorted(scored, key=lambda value: (value[0], value[1]), reverse=True)]
        return ordered, {
            "applied": True,
            "reference_token_count": len(reference_tokens),
            "support_terms": support_terms,
            "top": [
                {
                    "source_name": item.get("source_name") or item.get("name") or item.get("file_name"),
                    "answer_alignment_score": item.get("answer_alignment_score"),
                    "answer_reference_match": item.get("answer_reference_match"),
                    "answer_support_term_hits": item.get("answer_support_term_hits"),
                }
                for item in ordered[:5]
            ],
        }

    def _answer_reference_tokens(self, *, raw: Any, answer: str) -> set[str]:
        candidates: list[Any] = []
        if isinstance(raw, dict):
            data = raw.get("data") if isinstance(raw.get("data"), dict) else {}
            for value in (raw.get("references"), data.get("references")):
                if isinstance(value, list):
                    candidates.extend(value)
        candidates.extend(re.findall(r"/app/(?:uploads|rag_storage|rag_output|runtime_tmp)/[^\s\]\)\r\n]+", str(answer or "")))

        tokens: set[str] = set()
        for candidate in candidates:
            values: list[Any] = []
            if isinstance(candidate, dict):
                values.extend(candidate.values())
            else:
                values.append(candidate)
            for value in values:
                text = str(value or "").strip()
                if not text:
                    continue
                path = Path(text)
                for part in (text, path.name, path.stem):
                    key = self._term_key(part)
                    if key:
                        tokens.add(key)
        return tokens

    def _source_identity_tokens(self, source: dict[str, Any]) -> set[str]:
        metadata = source.get("metadata") if isinstance(source.get("metadata"), dict) else {}
        values = [
            source.get("name"),
            source.get("source_name"),
            source.get("file_name"),
            source.get("material_id"),
            metadata.get("storage_name"),
            metadata.get("material_title"),
            metadata.get("material_id"),
        ]
        tokens: set[str] = set()
        for value in values:
            text = str(value or "").strip()
            if not text:
                continue
            path = Path(text)
            for part in (text, path.name, path.stem):
                key = self._term_key(part)
                if key:
                    tokens.add(key)
        return tokens

    def _answer_support_terms(self, *, question: str, answer: str) -> list[str]:
        text = f"{question}\n{answer}"
        candidates = [
            "慢启动",
            "拥塞避免",
            "丢包",
            "窗口变化",
            "拥塞窗口",
            "CongWin",
            "1MSS",
            "1 MSS",
            "CongWin/2",
            "RTT",
            "ACK",
            "重复 ACK",
            "超时",
            "可靠传输",
            "流量控制",
            "确认应答",
            "序列号",
        ]
        terms: list[str] = []
        seen: set[str] = set()
        text_key = self._term_key(text)
        for term in candidates:
            key = self._term_key(term)
            if key and key in text_key and key not in seen:
                seen.add(key)
                terms.append(term)
        return terms

    def _annotate_sources_with_answer_references(
        self,
        *,
        sources: list[dict],
        raw: Any,
        answer: str,
    ) -> tuple[list[dict], dict[str, Any]]:
        reference_map = self._answer_reference_map(raw=raw, answer=answer)
        if not reference_map or not sources:
            return sources, {
                "applied": False,
                "reference_count": len(reference_map),
                "reason": "no_references_or_sources",
            }

        annotated: list[dict] = []
        matched_indexes: set[int] = set()
        for source in sources:
            source_tokens = self._source_identity_tokens(source)
            matched_reference = next(
                (
                    ref
                    for ref in reference_map
                    if ref["tokens"] & source_tokens
                ),
                None,
            )
            updated = dict(source)
            if matched_reference:
                matched_indexes.add(int(matched_reference["index"]))
                updated["citation_index"] = int(matched_reference["index"])
                updated["citation_label"] = f"[{matched_reference['index']}]"
                updated["citation_path"] = matched_reference["path"]
                updated["answer_reference_match"] = True
                current_score = self._safe_float(updated.get("answer_alignment_score")) or 0.0
                updated["answer_alignment_score"] = round(current_score + 2.0, 4)
            annotated.append(updated)

        annotated.sort(
            key=lambda item: (
                int(item.get("citation_index") or 9999),
                -(self._safe_float(item.get("answer_alignment_score")) or 0.0),
            )
        )
        return annotated, {
            "applied": True,
            "reference_count": len(reference_map),
            "matched_reference_indexes": sorted(matched_indexes),
            "unmatched_reference_indexes": [
                int(ref["index"])
                for ref in reference_map
                if int(ref["index"]) not in matched_indexes
            ],
            "references": [
                {"index": int(ref["index"]), "path": ref["path"]}
                for ref in reference_map
            ],
        }

    def _answer_reference_map(self, *, raw: Any, answer: str) -> list[dict[str, Any]]:
        refs: dict[int, str] = {}
        for match in re.finditer(r"(?m)^\s*[-*]?\s*\[(\d+)\]\s+(.+?)\s*$", str(answer or "")):
            try:
                index = int(match.group(1))
            except ValueError:
                continue
            refs[index] = match.group(2).strip()

        if isinstance(raw, dict):
            data = raw.get("data") if isinstance(raw.get("data"), dict) else {}
            raw_refs = data.get("references") or raw.get("references") or []
            if isinstance(raw_refs, list):
                for offset, item in enumerate(raw_refs, start=1):
                    if offset in refs:
                        continue
                    text = ""
                    if isinstance(item, dict):
                        text = str(
                            item.get("file_path")
                            or item.get("path")
                            or item.get("source")
                            or item.get("file")
                            or item.get("name")
                            or item.get("id")
                            or ""
                        )
                    else:
                        text = str(item or "")
                    if text.strip():
                        refs[offset] = text.strip()

        mapped: list[dict[str, Any]] = []
        for index, path_text in sorted(refs.items()):
            path = Path(path_text)
            tokens = {
                self._term_key(value)
                for value in (path_text, path.name, path.stem)
                if self._term_key(value)
            }
            mapped.append({"index": index, "path": path_text, "tokens": tokens})
        return mapped

    def _answer_needs_repair(self, answer: str) -> bool:
        return self._answer_repair_reason(answer) is not None

    def _answer_repair_reason(self, answer: str) -> str | None:
        text = str(answer or "")
        if not text.strip():
            return None
        garbled_reason = self._garbled_answer_reason(text)
        if garbled_reason:
            return garbled_reason
        if "�" in text:
            return "replacement_character"

        normalized = re.sub(r"\s+", " ", text)
        if len(re.findall(r"\\{2,}", text)) >= 3:
            return "excessive_backslashes"
        if re.search(r"\b(?:Analysis|Structure|Image Path|Caption|Footnotes)\s*:", text, flags=re.I):
            return "multimodal_metadata_leak"
        if re.search(r"([\u4e00-\u9fff]{1,4})\1{2,}", text):
            return "repeated_chinese_sequence"

        policy = str(getattr(settings, "RAG_ANSWER_REPAIR_POLICY", "severe_only") or "severe_only").strip().lower()
        if policy != "legacy":
            return None

        if re.search(r"[A-Za-z]+[\u4e00-\u9fff]+[A-Za-z]+|[\u4e00-\u9fff]+[A-Za-z]{3,}[\u4e00-\u9fff]+", normalized):
            return "awkward_mixed_language"

        chinese_chars = re.findall(r"[\u4e00-\u9fff]", text)
        if chinese_chars:
            quote_count = len(re.findall(r'["“”]', text))
            if quote_count / max(len(chinese_chars), 1) > 0.08:
                return "excessive_quotes"
            repeated_chinese = re.findall(r"([\u4e00-\u9fff]{1,2})\1{2,}", text)
            if len(repeated_chinese) >= 2:
                return "repeated_chinese_noise"
            awkward_patterns = (
                r"的的",
                r"地地",
                r"会会",
                r"指指",
                r"###\s*###",
                r"RTTT",
            )
            if any(re.search(pattern, text) for pattern in awkward_patterns):
                return "awkward_repeated_pattern"
        return None

    def _looks_like_garbled_answer(self, answer: Any) -> bool:
        return self._garbled_answer_reason(answer) is not None

    def _garbled_answer_reason(self, answer: Any) -> str | None:
        text = str(answer or "")
        if not text.strip():
            return None

        normalized = re.sub(r"\s+", " ", text).strip()
        if not normalized:
            return None

        lightrag_intermediate_markers = (
            "关键词 词汇表",
            "关键词查看代码",
            "关键词解释",
            "内容提由文字",
            "内容提取中文字",
            "在维修词语",
            "parseInt",
            "stdClass",
        )
        if any(marker in normalized for marker in lightrag_intermediate_markers):
            return "lightrag_intermediate_marker"

        if len(re.findall(r"\\", text)) >= 8:
            return "excessive_backslash_noise"
        if len(re.findall(r"(?<![A-Za-z])(?:IP|TCP|UDP|ACK|SYN|FIN)(?![A-Za-z])", text)) >= 30:
            return "repeated_protocol_tokens"

        repeated_backslash_words = re.findall(r"\\\s*[\u4e00-\u9fffA-Za-z]{1,6}", text)
        if len(repeated_backslash_words) >= 8:
            return "repeated_backslash_words"

        repeated_noise_tokens = re.findall(r"(?<![\u4e00-\u9fffA-Za-z])(?:信|修|模型)\s*[.。]?", text)
        if len(repeated_noise_tokens) >= 30:
            return "repeated_noise_tokens"

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if len(lines) >= 12:
            very_short_lines = [
                line for line in lines
                if len(line) <= 4 and re.fullmatch(r"[\u4e00-\u9fffA-Za-z0-9 .。,:：\"'\\]+", line)
            ]
            if len(very_short_lines) / len(lines) >= 0.55:
                return "fragmented_short_lines"

        punctuation_text = self._strip_markdown_table_lines(text)
        punctuation_noise = len(re.findall(r"[\\`|]", punctuation_text))
        if punctuation_noise >= 20 and punctuation_noise / max(len(punctuation_text), 1) > 0.025:
            return "punctuation_noise"

        return None

    def _strip_markdown_table_lines(self, text: str) -> str:
        kept_lines: list[str] = []
        for line in str(text or "").splitlines():
            stripped = line.strip()
            if stripped.count("|") >= 2:
                cells = [cell.strip() for cell in stripped.strip("|").split("|")]
                if len(cells) >= 2 and any(cell for cell in cells):
                    continue
            kept_lines.append(line)
        return "\n".join(kept_lines)

    async def _repair_answer_from_sources(
        self,
        *,
        question: str,
        answer: str,
        sources: list[dict],
        role: str,
    ) -> str:
        generation_base = settings.EFFECTIVE_LLM_API_BASE
        generation_api_key = settings.EFFECTIVE_LLM_API_KEY
        generation_model = settings.LLM_MODEL
        if not generation_base or not generation_api_key or not generation_model:
            return ""

        evidence_lines = []
        for index, source in enumerate(sources[:5], start=1):
            snippet = (
                source.get("snippet")
                or source.get("raw_text")
                or source.get("content")
                or source.get("text")
                or ""
            )
            snippet = re.sub(r"\s+", " ", str(snippet)).strip()
            if not snippet:
                continue
            name = source.get("source_name") or source.get("name") or f"source-{index}"
            evidence_lines.append(f"[资料{index}] {name}: {snippet[:900]}")
        if not evidence_lines:
            return ""

        role_guidance = (
            "当前用户是教师，请额外给出教学提示。"
            if str(role or "").lower() in {"teacher", "admin", "instructor"}
            else "当前用户是学生，请用循序渐进的方式解释，避免过度扩展。"
        )
        prompt = (
            "请根据下面的课程资料，重新生成一段自然、准确、适合中国教育场景的中文回答。\n"
            "要求：\n"
            "1. 只能依据资料内容回答，不要编造资料外事实。\n"
            "2. 先给简明结论，再用 2-4 个要点解释。\n"
            "3. 中文必须通顺，不要输出乱码、重复字词、异常引号或无意义标题。\n"
            "4. 如果资料不足，请明确说明资料不足。\n"
            f"5. {role_guidance}\n\n"
            f"学生问题：{question}\n\n"
            "课程资料：\n"
            + "\n".join(evidence_lines)
            + "\n\n原始回答存在可读性问题，仅用于判断不要照抄：\n"
            + str(answer)[:1200]
        )
        system_prompt = "你是面向中国高校课程的 AI 助教，请输出清晰、严谨、自然的简体中文。"
        call_trace = self._record_llm_trace(
            prompt=prompt,
            system_prompt=system_prompt,
            history_messages=[],
            keyword_extraction=False,
            use_generation_model=True,
            model=generation_model,
            wire_api=settings.LLM_WIRE_API,
        )
        started_at = perf_counter()
        try:
            llm_result = await self._call_llm_api(
                prompt=prompt,
                system_prompt=system_prompt,
                history_messages=[],
                model=generation_model,
                base_url=generation_base,
                api_key=generation_api_key,
                wire_api=settings.LLM_WIRE_API,
            )
            if isinstance(llm_result, tuple):
                repaired, usage = llm_result
            else:
                repaired, usage = llm_result, {}
        except Exception as exc:
            self._finish_llm_trace(
                call_trace,
                started_at=started_at,
                success=False,
                error=str(exc),
            )
            logger.warning("raganything_answer_repair_failed", error=str(exc))
            return ""
        self._finish_llm_trace(
            call_trace,
            started_at=started_at,
            success=True,
            response_text=repaired,
            usage=usage,
        )

        repaired = self._sanitize_answer_text(repaired)
        if not repaired or self._answer_needs_repair(repaired):
            return ""
        logger.info("raganything_answer_repaired", source_count=len(sources))
        return repaired

    async def _ensure_rag_query_ready(self, rag: object) -> None:
        ensure_method = getattr(rag, "_ensure_lightrag_initialized", None)
        if ensure_method is None:
            return

        result = ensure_method()
        if inspect.isawaitable(result):
            result = await result

        if isinstance(result, dict) and result.get("success") is False:
            raise RuntimeError(str(result.get("error") or "Failed to initialize LightRAG"))

    async def _rerank_main_chain_sources(
        self,
        *,
        question: str,
        sources: list[dict],
    ) -> tuple[list[dict], dict[str, Any]]:
        candidates = []
        for index, source in enumerate(sources or []):
            evidence_text = (
                source.get("raw_text")
                or source.get("snippet")
                or source.get("text")
                or source.get("content")
                or source.get("description")
                or ""
            )
            evidence_text = self._clean_lightrag_chunk_text(evidence_text)
            if not evidence_text:
                continue
            candidates.append({
                **source,
                "chunk_id": source.get("chunk_id") or f"raganything-source-{index}",
                "source_name": source.get("name") or source.get("source_name") or "unknown",
                "source_type": source.get("type") or source.get("source_type"),
                "page": source.get("page"),
                "snippet": str(evidence_text)[:800],
                "raw_text": str(evidence_text),
                "retrieval_score": source.get("score") or source.get("retrieval_score") or 0.0,
                "_source_index": index,
            })

        if not candidates:
            candidate_count = len(sources or [])
            top_k = max(0, int(getattr(settings, "RAG_ANSWER_TOP_K", 0) or 0))
            selected_sources = list(sources or [])
            if top_k > 0:
                selected_sources = selected_sources[:top_k]
            return selected_sources, {
                "reranker_provider": "main_chain_native",
                "reranker_model": None,
                "reranked_main_chain_sources": False,
                "source_candidate_count": candidate_count,
                "source_selected_count": len(selected_sources),
                "source_top_k": top_k or None,
                "rerank_trace": {
                    "provider": "main_chain_native",
                    "model": None,
                    "applied": False,
                    "candidate_count": candidate_count,
                    "selected_count": len(selected_sources),
                    "top_k": top_k or None,
                    "before": self._source_trace_summary(sources),
                    "after": self._source_trace_summary(selected_sources),
                },
            }

        reranker = get_reranker()
        reranked = await reranker.rerank(
            query=question,
            candidates=candidates,
            context={"retrieval_strategy": "raganything_main_chain"},
        )
        by_index = {item.get("_source_index"): item for item in reranked}
        untouched = [
            {**source, "_source_index": index}
            for index, source in enumerate(sources or [])
            if index not in by_index
        ]
        candidate_count = len(sources or [])
        top_k = max(0, int(getattr(settings, "RAG_ANSWER_TOP_K", 0) or 0))
        ordered = reranked + untouched
        if top_k > 0:
            ordered = ordered[:top_k]
        normalized = []
        for item in ordered:
            source = dict(item)
            source.pop("_source_index", None)
            if "name" not in source and source.get("source_name"):
                source["name"] = source["source_name"]
            if "type" not in source and source.get("source_type"):
                source["type"] = source["source_type"]
            source["score"] = source.get("rerank_score", source.get("score"))
            normalized.append(source)

        return normalized, {
            "reranker_provider": getattr(reranker, "provider_name", "unknown"),
            "reranker_model": getattr(reranker, "model_name", "unknown"),
            "reranked_main_chain_sources": True,
            "source_candidate_count": candidate_count,
            "source_selected_count": len(normalized),
            "source_top_k": top_k or None,
            "rerank_trace": {
                "provider": getattr(reranker, "provider_name", "unknown"),
                "model": getattr(reranker, "model_name", "unknown"),
                "applied": True,
                "candidate_count": candidate_count,
                "candidate_with_text_count": len(candidates),
                "selected_count": len(normalized),
                "top_k": top_k or None,
                "before": self._source_trace_summary(candidates),
                "after": self._source_trace_summary(normalized),
            },
        }

    def _filter_low_relevance_sources(self, sources: list[dict]) -> tuple[list[dict], dict[str, Any]]:
        if not sources:
            return sources, {"applied": False, "reason": "no_sources"}

        scored: list[tuple[float, dict[str, Any]]] = []
        for source in sources:
            if not isinstance(source, dict):
                continue
            score = (
                self._safe_float(source.get("rerank_score"))
                or self._safe_float(source.get("score"))
                or self._safe_float(source.get("retrieval_score"))
                or 0.0
            )
            scored.append((score, source))
        if not scored:
            return sources, {"applied": False, "reason": "no_scored_sources"}

        best_score = max(score for score, _ in scored)
        if best_score < 0.5:
            return sources, {
                "applied": False,
                "reason": "best_score_below_filter_floor",
                "best_score": round(best_score, 4),
            }

        threshold = max(0.25, best_score * 0.5)
        kept = [source for score, source in scored if score >= threshold]
        if not kept:
            return sources, {
                "applied": False,
                "reason": "filter_would_drop_all",
                "best_score": round(best_score, 4),
                "threshold": round(threshold, 4),
            }

        return kept, {
            "applied": len(kept) != len(sources),
            "best_score": round(best_score, 4),
            "threshold": round(threshold, 4),
            "before_count": len(sources),
            "after_count": len(kept),
            "after": self._source_trace_summary(kept),
        }

    def _enrich_sources_with_material_metadata(self, sources: list[dict], class_id: str) -> list[dict]:
        if not sources:
            return sources

        try:
            db = SessionLocal()
        except Exception as exc:
            logger.warning("rag_source_material_session_failed", class_id=class_id, error=str(exc))
            return sources

        try:
            materials = db.query(Material).filter(
                Material.class_id == class_id,
                Material.is_active == True,
            ).all()
            parse_tasks = db.query(FileParseTask).filter(
                FileParseTask.class_id == class_id,
                FileParseTask.status == "completed",
            ).all()
        except Exception as exc:
            logger.warning("rag_source_material_lookup_failed", class_id=class_id, error=str(exc))
            db.close()
            return sources
        finally:
            try:
                db.close()
            except Exception:
                pass

        if not materials:
            return sources

        material_by_token: dict[str, Material] = {}
        for material in materials:
            tokens = {
                str(material.id or ""),
                str(material.file_name or ""),
                Path(str(material.file_name or "")).name,
                str(material.file_path or ""),
                Path(str(material.file_path or "")).name,
                Path(str(material.file_path or "")).stem,
                str(material.title or ""),
            }
            for token in tokens:
                token = token.strip()
                if token:
                    material_by_token[token] = material
        task_by_material_id = {
            str(task.material_id): task
            for task in parse_tasks
            if getattr(task, "material_id", None)
        }

        enriched: list[dict] = []
        for source in sources:
            if not isinstance(source, dict):
                enriched.append(source)
                continue

            metadata = source.get("metadata") if isinstance(source.get("metadata"), dict) else {}
            candidate_tokens = [
                source.get("material_id"),
                source.get("doc_id"),
                source.get("full_doc_id"),
                source.get("file_path"),
                source.get("name"),
                source.get("source_name"),
                source.get("file_name"),
                metadata.get("material_id"),
                metadata.get("doc_id"),
                metadata.get("full_doc_id"),
                metadata.get("source_path"),
                metadata.get("file_path"),
                metadata.get("source_name"),
            ]
            matched = None
            for token in candidate_tokens:
                if token is None:
                    continue
                text = str(token).strip()
                possible_tokens = [text, Path(text).name, Path(text).stem]
                matched = next((material_by_token[item] for item in possible_tokens if item in material_by_token), None)
                if matched is not None:
                    break

            if matched is None:
                enriched.append(source)
                continue

            display_name = matched.file_name or matched.title or source.get("name") or source.get("source_name")
            storage_name = Path(str(matched.file_path or "")).name
            next_metadata = dict(metadata)
            if storage_name and storage_name != display_name:
                next_metadata.setdefault("storage_name", storage_name)
            next_metadata.setdefault("material_title", matched.title)
            next_metadata.setdefault("material_id", matched.id)
            atomic_payload = self._source_atomic_metadata(source, task_by_material_id.get(str(matched.id)))
            if atomic_payload:
                for key, value in atomic_payload.items():
                    if value is not None:
                        next_metadata.setdefault(key, value)

            enriched_source = {
                **source,
                "name": display_name,
                "source_name": display_name,
                "file_name": display_name,
                "material_id": matched.id,
                "metadata": next_metadata,
            }
            enriched.append(enriched_source)

        return enriched

    def _source_atomic_metadata(self, source: dict[str, Any], task: FileParseTask | None) -> dict[str, Any]:
        if task is None:
            return {}
        metadata = source.get("metadata") if isinstance(source.get("metadata"), dict) else {}
        chunk_ids = {
            str(value).strip()
            for value in (
                source.get("chunk_id"),
                source.get("id"),
                source.get("reference_id"),
                metadata.get("chunk_id"),
                metadata.get("atomic_id"),
                metadata.get("item_id"),
            )
            if value
        }
        text = self._source_evidence_text(source)

        for chunk in task.chunks or []:
            if not isinstance(chunk, dict):
                continue
            chunk_metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {}
            chunk_id_values = {
                str(value).strip()
                for value in (
                    chunk.get("chunk_id"),
                    chunk.get("id"),
                    chunk_metadata.get("chunk_id"),
                    chunk_metadata.get("atomic_id"),
                    chunk_metadata.get("item_id"),
                )
                if value
            }
            if chunk_ids and chunk_ids & chunk_id_values:
                return self._atomic_payload_from_record(chunk, chunk_metadata)
            if text and self._source_text_matches_record(text, chunk.get("text") or chunk.get("content")):
                return self._atomic_payload_from_record(chunk, chunk_metadata)

        extra = task.extra_data or {}
        for item in extra.get("content_items") or []:
            if not isinstance(item, dict):
                continue
            item_metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
            item_id_values = {
                str(value).strip()
                for value in (
                    item.get("atomic_id"),
                    item.get("item_id"),
                    item.get("id"),
                    item.get("chunk_id"),
                    item_metadata.get("atomic_id"),
                    item_metadata.get("item_id"),
                    item_metadata.get("chunk_id"),
                )
                if value
            }
            if chunk_ids and chunk_ids & item_id_values:
                return self._atomic_payload_from_record(item, item_metadata)
            item_text = (
                item.get("text")
                or item.get("caption")
                or item.get("ocr_text")
                or item.get("table_markdown")
                or item.get("equation")
                or item.get("formula_latex")
            )
            if text and self._source_text_matches_record(text, item_text):
                return self._atomic_payload_from_record(item, item_metadata)
        return {}

    def _source_evidence_text(self, source: dict[str, Any]) -> str:
        return re.sub(
            r"\s+",
            " ",
            str(
                source.get("raw_text")
                or source.get("snippet")
                or source.get("content")
                or source.get("text")
                or source.get("description")
                or ""
            ),
        ).strip()

    def _source_text_matches_record(self, source_text: str, record_text: Any) -> bool:
        source_norm = re.sub(r"\s+", " ", str(source_text or "")).strip().lower()
        record_norm = re.sub(r"\s+", " ", str(record_text or "")).strip().lower()
        if not source_norm or not record_norm:
            return False
        source_probe = source_norm[:300]
        record_probe = record_norm[:1200]
        return source_probe in record_probe or record_probe[:300] in source_norm

    def _atomic_payload_from_record(self, record: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
        return {
            "atomic_id": record.get("atomic_id") or record.get("item_id") or metadata.get("atomic_id"),
            "item_id": record.get("item_id") or metadata.get("item_id"),
            "modality": record.get("modality") or metadata.get("modality") or self._normalize_content_modality(
                str(record.get("type") or metadata.get("source_type") or "")
            ),
            "content_index": metadata.get("content_index") or record.get("content_index"),
            "page": record.get("page") or record.get("page_idx") or metadata.get("page") or metadata.get("page_idx"),
            "bbox": record.get("bbox") or metadata.get("bbox"),
        }

    async def _invoke_rag_query(
        self,
        *,
        rag: object,
        query_text: str,
        query_mode: str,
        history: list[dict],
        attachments: list[dict],
        prefer_multimodal: bool,
        class_id: str,
        role: str = "student",
    ) -> tuple[Any, str]:
        if not prefer_multimodal and getattr(rag, "lightrag", None) is not None:
            raw, method_name = await self._invoke_lightrag_query_with_references(
                rag=rag,
                query_text=query_text,
                query_mode=query_mode,
                history=history,
                class_id=class_id,
                role=role,
            )
            if self._query_payload_has_content(raw):
                logger.info(
                    "raganything_query_method",
                    class_id=class_id,
                    method=method_name,
                    mode=query_mode,
                )
                return raw, method_name

        candidate_methods = []
        if prefer_multimodal:
            candidate_methods.append("aquery_with_multimodal")
        candidate_methods.extend(["aquery", "query"])

        for method_name in candidate_methods:
            method = getattr(rag, method_name, None)
            if method is None:
                continue

            kwargs = self._build_rag_query_kwargs(
                method=method,
                query_text=query_text,
                query_mode=query_mode,
                history=history,
                attachments=attachments,
                role=role,
            )
            signature = inspect.signature(method)
            accepts_kwargs = any(param.kind == inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values())
            if (
                kwargs is not None
                and method_name == "aquery"
                and not prefer_multimodal
                and (accepts_kwargs or "vlm_enhanced" in signature.parameters)
            ):
                kwargs["vlm_enhanced"] = False
            try:
                call_result = method(**kwargs) if kwargs is not None else method(query_text)
            except TypeError:
                call_result = method(query_text)

            if inspect.isawaitable(call_result):
                call_result = await call_result
            logger.info(
                "raganything_query_method",
                class_id=class_id,
                method=method_name,
                mode=query_mode,
            )
            return call_result, method_name

        raise RuntimeError("No compatible query method found on RAG-Anything instance")

    async def _invoke_lightrag_query_with_references(
        self,
        *,
        rag: object,
        query_text: str,
        query_mode: str,
        history: list[dict],
        class_id: str,
        role: str = "student",
    ) -> tuple[dict[str, Any], str]:
        lightrag = getattr(rag, "lightrag", None)
        if lightrag is None or not hasattr(lightrag, "aquery_llm"):
            return {}, "lightrag_aquery_llm"

        lightrag_module = importlib.import_module("lightrag")
        QueryParam = getattr(lightrag_module, "QueryParam")
        attempted_modes = self._lightrag_reference_query_modes(query_mode)

        last_raw: dict[str, Any] = {}
        mode_attempts: list[dict[str, Any]] = []
        for effective_mode in attempted_modes:
            query_param = self._build_lightrag_query_param(
                QueryParam=QueryParam,
                mode=effective_mode,
                history=history or [],
                role=role,
            )
            try:
                raw = await lightrag.aquery_llm(query_text, param=query_param)
            except Exception as exc:
                mode_attempts.append({
                    "mode": effective_mode,
                    "success": False,
                    "error": self._safe_error_detail(exc),
                })
                logger.warning(
                    "lightrag_query_mode_failed",
                    class_id=class_id,
                    requested_mode=query_mode,
                    effective_mode=effective_mode,
                    error=str(exc),
                )
                continue
            if isinstance(raw, dict):
                has_content = self._query_payload_has_content(raw)
                mode_attempts.append({
                    "mode": effective_mode,
                    "success": True,
                    "has_content": has_content,
                    **self._query_payload_stats(raw),
                })
                metadata = dict(raw.get("metadata") or {})
                metadata["adapter_requested_mode"] = query_mode
                metadata["adapter_effective_mode"] = effective_mode
                metadata["adapter_attempted_modes"] = attempted_modes
                metadata["adapter_mode_attempts"] = list(mode_attempts)
                metadata["adapter_include_references_requested"] = True
                metadata["adapter_lightrag_rerank_requested"] = self._lightrag_internal_rerank_enabled()
                raw["metadata"] = metadata
                last_raw = raw
                if has_content:
                    return raw, f"lightrag_aquery_llm:{effective_mode}"

        if last_raw:
            metadata = dict(last_raw.get("metadata") or {})
            metadata["adapter_mode_attempts"] = list(mode_attempts)
            last_raw["metadata"] = metadata
        return last_raw, f"lightrag_aquery_llm:{attempted_modes[-1]}"

    def _lightrag_reference_query_modes(self, query_mode: str) -> list[str]:
        requested = (query_mode or "hybrid").strip().lower()
        attempted_modes = [requested]
        attempted_modes.extend(
            mode for mode in ("mix", "hybrid", "global", "local", "naive")
            if mode not in attempted_modes
        )
        return attempted_modes

    def _build_lightrag_query_param(
        self,
        *,
        QueryParam: Any,
        mode: str,
        history: list[dict],
        role: str,
    ) -> Any:
        kwargs: dict[str, Any] = {
            "mode": mode,
            "include_references": True,
            "conversation_history": history or [],
        }
        user_prompt = build_query_user_prompt(settings, role=role)
        try:
            signature = inspect.signature(QueryParam)
            supports_user_prompt = "user_prompt" in signature.parameters
            supports_enable_rerank = "enable_rerank" in signature.parameters
        except Exception:  # pragma: no cover - optional dependency implementation detail
            supports_user_prompt = False
            supports_enable_rerank = False
        if user_prompt and supports_user_prompt:
            if bool(getattr(settings, "RAG_KG_CONTEXT_FILTER_ENABLED", True)):
                user_prompt = (
                    f"{user_prompt}\n\n"
                    f"Retrieval policy: {KG_CONTEXT_FILTER_CACHE_TAG}. "
                    "Ignore generic table-structure artifact nodes unless they directly answer the question."
                )
            kwargs["user_prompt"] = user_prompt
        if supports_enable_rerank:
            kwargs["enable_rerank"] = self._lightrag_internal_rerank_enabled()
        return QueryParam(**kwargs)

    def _query_payload_has_content(self, raw: Any) -> bool:
        if isinstance(raw, str):
            return bool(raw.strip())
        if not isinstance(raw, dict):
            return bool(raw)

        llm_response = raw.get("llm_response") or {}
        if str(llm_response.get("content") or "").strip():
            return True

        data = raw.get("data") or {}
        if data.get("chunks") or data.get("references") or data.get("entities") or data.get("relationships"):
            return True

        for key in ("answer", "response", "output", "text"):
            if str(raw.get(key) or "").strip():
                return True
        return False

    def _query_payload_stats(self, raw: Any) -> dict[str, Any]:
        if not isinstance(raw, dict):
            text = str(raw or "")
            return {
                "raw_type": type(raw).__name__,
                "answer_chars": len(text),
                "chunk_count": 0,
                "reference_count": 0,
                "entity_count": 0,
                "relationship_count": 0,
            }

        data = raw.get("data") if isinstance(raw.get("data"), dict) else {}
        llm_response = raw.get("llm_response") if isinstance(raw.get("llm_response"), dict) else {}
        answer = (
            llm_response.get("content")
            or raw.get("answer")
            or raw.get("response")
            or raw.get("output")
            or raw.get("text")
            or ""
        )

        def count(value: Any) -> int:
            return len(value) if isinstance(value, list) else 0

        return {
            "raw_type": type(raw).__name__,
            "top_level_keys": sorted(str(key) for key in raw.keys())[:12],
            "answer_chars": len(str(answer or "")),
            "chunk_count": count(raw.get("chunks")) + count(data.get("chunks")),
            "reference_count": count(raw.get("references")) + count(data.get("references")),
            "entity_count": count(data.get("entities")),
            "relationship_count": count(data.get("relationships")),
        }

    def _build_rag_query_kwargs(
        self,
        *,
        method: Any,
        query_text: str,
        query_mode: str,
        history: list[dict],
        attachments: list[dict],
        role: str = "student",
    ) -> dict[str, Any] | None:
        signature = inspect.signature(method)
        params = signature.parameters
        accepts_kwargs = any(param.kind == inspect.Parameter.VAR_KEYWORD for param in params.values())

        question_param = next(
            (name for name in ("query", "question", "prompt") if accepts_kwargs or name in params),
            None,
        )
        mode_param = next((name for name in ("mode", "query_mode") if name in params), None)
        history_param = next(
            (name for name in ("history_messages", "history", "conversation_history") if accepts_kwargs or name in params),
            None,
        )
        attachments_param = next(
            (name for name in ("multimodal_content", "attachments", "images", "image_inputs") if name in params),
            None,
        )

        if question_param is None and not accepts_kwargs:
            return None

        kwargs: dict[str, Any] = {}
        if question_param:
            kwargs[question_param] = query_text
        elif accepts_kwargs:
            kwargs["query"] = query_text

        if mode_param:
            kwargs[mode_param] = query_mode
        elif accepts_kwargs:
            kwargs["mode"] = query_mode
        if history and history_param:
            kwargs[history_param] = history
        if attachments and attachments_param:
            kwargs[attachments_param] = attachments
        user_prompt = build_query_user_prompt(settings, role=role)
        if user_prompt and "user_prompt" in params:
            kwargs["user_prompt"] = user_prompt
        return kwargs

    def _normalize_rag_query_output(self, raw: Any) -> tuple[str, list[dict], float]:
        if raw is None:
            return "", [], 0.0

        if isinstance(raw, str):
            return self._sanitize_answer_text(raw), [], 0.0

        if isinstance(raw, dict):
            answer = (
                ((raw.get("llm_response") or {}).get("content") if isinstance(raw.get("llm_response"), dict) else None)
                or raw.get("answer")
                or raw.get("response")
                or raw.get("output")
                or raw.get("text")
                or ""
            )
            source_candidates = (
                raw.get("sources")
                or raw.get("citations")
                or raw.get("references")
                or raw.get("chunks")
                or raw.get("evidence")
                or []
            )
            if not source_candidates and isinstance(raw.get("data"), dict):
                data = raw["data"]
                source_candidates = (
                    data.get("chunks")
                    or data.get("references")
                    or data.get("entities")
                    or data.get("relationships")
                    or []
                )
            if not source_candidates and isinstance(raw.get("context"), dict):
                source_candidates = raw["context"].get("sources") or raw["context"].get("chunks") or []
            sources = self._normalize_sources(source_candidates)
            confidence = self._safe_float(raw.get("confidence")) or self._safe_float(raw.get("score")) or 0.0
            return self._sanitize_answer_text(answer), sources, confidence

        if isinstance(raw, (list, tuple)):
            if all(isinstance(item, str) for item in raw):
                return self._sanitize_answer_text("\n".join(item for item in raw if item)), [], 0.0
            sources = self._normalize_sources(list(raw))
            return "", sources, 0.0

        answer = getattr(raw, "answer", None) or getattr(raw, "response", None) or str(raw)
        sources = self._normalize_sources(getattr(raw, "sources", []))
        confidence = self._safe_float(getattr(raw, "confidence", 0.0)) or 0.0
        return self._sanitize_answer_text(answer), sources, confidence

    def _sanitize_answer_text(self, answer: Any) -> str:
        text = str(answer or "").strip()
        if not text:
            return ""

        if self._is_no_context_answer(text):
            return (
                "我暂时没有从当前课程资料中检索到足够依据来回答这个问题。"
                "你可以换一种问法，或请教师先上传/补充相关课程资料后再提问。"
            )

        text = text.replace("\x00", "")
        text = re.sub(r"[ \t]{3,}", " ", text)
        text = re.sub(r"\n{4,}", "\n\n", text)

        # Some provider/model combinations can emit a long tail of repeated
        # quote-like tokens after the useful answer. Trim that tail before it
        # reaches the UI, while leaving normal quoted text intact.
        repeated_tail = re.search(r'(?s)(["“”]\s*){24,}.*$', text)
        if repeated_tail:
            text = text[: repeated_tail.start()].rstrip()

        repeated_token_tail = re.search(r"(?s)(\b[\w\u4e00-\u9fff]{1,8}\b[\s，。,.、]*)\1{12,}.*$", text)
        if repeated_token_tail:
            text = text[: repeated_token_tail.start()].rstrip()

        text = text.replace("�", "")

        # Do not expose local workspace paths in student-facing answers. The
        # structured sources list still carries the citation metadata.
        text = re.sub(
            r"(?P<path>[A-Za-z]:\\[^\s\]\)\r\n]+)",
            lambda match: Path(match.group("path")).name,
            text,
        )
        text = re.sub(
            r"(?P<path>/app/(?:uploads|rag_storage|rag_output|runtime_tmp)/[^\s\]\)\r\n]+)",
            lambda match: Path(match.group("path")).name,
            text,
        )

        max_chars = 6000
        if len(text) > max_chars:
            text = text[:max_chars].rstrip() + "\n\n[答案过长，已截断。]"
        return text.strip()

    def _is_no_context_answer(self, text: str) -> bool:
        normalized = re.sub(r"\s+", " ", str(text or "").strip()).lower()
        if not normalized:
            return False
        markers = (
            "[no-context]",
            "no context",
            "not able to provide an answer",
            "cannot provide an answer",
            "unable to answer",
        )
        return any(marker in normalized for marker in markers)

    def _normalize_sources(self, source_candidates: Any) -> list[dict]:
        if not isinstance(source_candidates, list):
            return []

        normalized = []
        for item in source_candidates:
            if isinstance(item, str):
                normalized.append({
                    "name": item[:64],
                    "page": None,
                    "type": None,
                    "score": None,
                    "chunk_id": None,
                    "snippet": item,
                    "raw_text": item,
                })
                continue
            if not isinstance(item, dict):
                continue

            score = (
                self._safe_float(item.get("score"))
                or self._safe_float(item.get("similarity"))
                or self._safe_float(item.get("confidence"))
            )
            file_name = item.get("name") or item.get("source_name") or item.get("source") or item.get("file_name")
            file_path = item.get("file_path")
            if not file_name and file_path:
                file_name = Path(str(file_path)).name
            normalized.append({
                "name": file_name or "unknown",
                "page": item.get("page") or item.get("page_idx") or item.get("page_number"),
                "type": item.get("type") or item.get("source_type") or item.get("mime_type"),
                "score": score,
                "chunk_id": item.get("chunk_id") or item.get("id") or item.get("doc_id") or item.get("reference_id"),
                "snippet": item.get("snippet") or item.get("content") or item.get("text") or item.get("description"),
                "raw_text": item.get("raw_text") or item.get("content") or item.get("text") or item.get("snippet"),
                "metadata": item.get("metadata") or item.get("extra_data"),
                "retrieval_score": score,
            })
        return normalized

    def _safe_float(self, value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _safe_error_detail(self, exc: Exception, *, max_length: int = 500) -> str:
        detail = re.sub(r"\s+", " ", str(exc or "")).strip()
        if not detail:
            return exc.__class__.__name__
        detail = re.sub(r"(?i)(api[_-]?key|authorization|bearer)\s*[:=]\s*[^,'\"\\s}]+", r"\1=<redacted>", detail)
        return detail[:max(80, int(max_length))]

    async def add_qa_pair(self, class_id: str, question: str, answer: str) -> bool:
        rag = self._get_instance(class_id)
        now = datetime.now(timezone.utc)
        content_list = [{
            "type": "text",
            "text": f"Teacher-reviewed question: {question}\nTeacher-verified answer: {answer}",
            "page_idx": 0,
            "metadata": {
                "source": "teacher_review",
                "class_id": class_id,
                "created_at": now.isoformat(),
            },
        }]
        doc_id = "teacher-review-" + hashlib.sha256(
            f"{class_id}|{question}|{answer}".encode("utf-8")
        ).hexdigest()[:24]
        file_path = f"teacher_review_{class_id}.txt"
        method = getattr(rag, "insert_content_list", None)
        if method is None:
            raise RuntimeError("RAG-Anything instance does not expose insert_content_list for teacher feedback sync")

        kwargs = {
            "content_list": content_list,
            "file_path": file_path,
            "doc_id": doc_id,
        }
        try:
            result = method(**kwargs)
        except TypeError:
            result = method(content_list)
        if inspect.isawaitable(result):
            await result

        with SessionLocal() as db:
            cls = db.query(Class).filter(Class.id == class_id).first()
            if cls:
                kb_space = self._ensure_kb_space(db, course_id=cls.course_id, class_id=class_id)
                extra = kb_space.extra_data or {}
                sync_items = [
                    item for item in (extra.get("raganything_teacher_review_sync") or [])
                    if isinstance(item, dict) and item.get("doc_id") != doc_id
                ]
                sync_items.append({
                    "doc_id": doc_id,
                    "entrypoint": "insert_content_list",
                    "question": question,
                    "answer_preview": answer[:240],
                    "synced_at": now.isoformat(),
                })
                extra["raganything_teacher_review_sync"] = sync_items[-50:]
                extra["last_teacher_review_sync_at"] = now.isoformat()
                kb_space.extra_data = extra
                kb_space.updated_at = now
                db.add(kb_space)
                db.commit()
        return True

    def get_parse_task(self, task_id: str) -> dict[str, Any] | None:
        with SessionLocal() as db:
            task = db.query(FileParseTask).filter(FileParseTask.id == task_id).first()
            if not task:
                return None
            material = db.query(Material).filter(Material.id == task.material_id).first()
            extra = task.extra_data or {}
            ingest = extra.get("ingest", {}) if isinstance(extra.get("ingest"), dict) else {}
            alert = ingest.get("alert", {}) if isinstance(ingest.get("alert"), dict) else {}
            raw_items = extra.get("content_items")
            content_items = raw_items if isinstance(raw_items, list) else []
            return {
                "id": task.id,
                "kind": "file_parse",
                "course_id": task.course_id,
                "class_id": task.class_id,
                "material_id": task.material_id,
                "material_name": material.file_name if material else None,
                "status": task.status,
                "parser_name": task.parser_name,
                "summary": task.summary,
                "extracted_text": task.extracted_text,
                "chunks": task.chunks or [],
                "chunk_count": len(task.chunks or []),
                "content_items": content_items,
                "content_items_schema": extra.get("content_items_schema") or ("v1" if content_items else None),
                "preprocess": extra.get("preprocess"),
                "raganything_status": extra.get("raganything_status"),
                "raganything_quality": extra.get("raganything_quality"),
                "graph_projection": extra.get("graph_projection"),
                "error_message": task.error_message,
                "attempt_count": int(ingest.get("attempt_count", 0) or 0),
                "max_attempts": int(ingest.get("max_attempts", settings.KB_PARSE_MAX_RETRIES) or settings.KB_PARSE_MAX_RETRIES),
                "retry_available": bool(ingest.get("retry_available", task.status == "failed")),
                "last_error_category": (
                    getattr(task, "last_error_category", None)
                    or ingest.get("last_error_category")
                    or (extra.get("raganything_error") or {}).get("category")
                ),
                "queue_task_id": ingest.get("queue_task_id"),
                "queue_status": ingest.get("queue_status"),
                "auto_retry_round": int(ingest.get("auto_retry_round", 0) or 0),
                "next_retry_after": ingest.get("next_retry_after"),
                "alert_count": int(alert.get("count", 0) or 0),
                "last_alert_reason": alert.get("last_reason"),
                "last_alert_at": alert.get("last_alert_at"),
                "created_at": task.created_at,
                "updated_at": task.updated_at,
            }

    def get_kb_status(self, course_id: str) -> dict[str, Any]:
        with SessionLocal() as db:
            classes = db.query(Class).filter(Class.course_id == course_id).all()
            class_ids = [row.id for row in classes]
            materials_query = db.query(Material).join(Class, Class.id == Material.class_id).filter(
                Class.course_id == course_id,
                Material.is_active == True,
            )
            tasks_query = db.query(FileParseTask).filter(FileParseTask.course_id == course_id)
            kb_query = db.query(KBSpace).filter(KBSpace.course_id == course_id)
            entity_query = db.query(KnowledgeEntity)
            relation_query = db.query(KnowledgeRelation)
            if class_ids:
                entity_query = entity_query.filter(KnowledgeEntity.class_id.in_(class_ids))
                relation_query = relation_query.filter(KnowledgeRelation.class_id.in_(class_ids))
            else:
                entity_query = entity_query.filter(KnowledgeEntity.class_id == "__missing__")
                relation_query = relation_query.filter(KnowledgeRelation.class_id == "__missing__")

            materials = materials_query.all()
            tasks = tasks_query.all()
            kb_spaces = kb_query.all()

            materials_total = len(materials)
            materials_indexed = sum(1 for item in materials if str(item.kb_status) == "indexed")
            materials_failed = sum(1 for item in materials if str(item.kb_status) == "failed")
            materials_pending = sum(1 for item in materials if str(item.kb_status) in {"pending", "processing"})
            tasks_completed = sum(1 for item in tasks if str(item.status) == "completed")
            tasks_failed = sum(1 for item in tasks if str(item.status) == "failed")
            tasks_processing = sum(1 for item in tasks if str(item.status) in {"pending", "processing"})
            latest_built_at = max(
                (space.last_built_at for space in kb_spaces if space.last_built_at is not None),
                default=None,
            )

            if materials_total == 0 and not kb_spaces:
                health = "empty"
            elif tasks_processing > 0 and tasks_completed == 0:
                health = "building"
            elif tasks_failed > 0 and tasks_completed == 0:
                health = "failed"
            elif materials_failed > 0 or tasks_failed > 0:
                health = "degraded"
            elif materials_indexed > 0 or tasks_completed > 0:
                health = "healthy"
            else:
                health = "building"

            teacher_review_sync_count = 0
            for space in kb_spaces:
                extra = space.extra_data or {}
                sync_items = extra.get("raganything_teacher_review_sync") or []
                if isinstance(sync_items, list):
                    teacher_review_sync_count += len(sync_items)
            storage_summary = self._build_kb_storage_summary(
                tasks=tasks,
                materials=materials,
            )

            return {
                "course_id": course_id,
                "backend": "raganything",
                "strict_mode": settings.RAGANYTHING_STRICT_MODE,
                "status": health,
                "class_count": len(class_ids),
                "materials_total": materials_total,
                "materials_indexed": materials_indexed,
                "materials_failed": materials_failed,
                "materials_pending": materials_pending,
                "parse_tasks": {
                    "total": len(tasks),
                    "completed": tasks_completed,
                    "failed": tasks_failed,
                    "processing": tasks_processing,
                },
                "kb_spaces": {
                    "total": len(kb_spaces),
                    "ready": sum(1 for item in kb_spaces if str(item.status) == "ready"),
                    "failed": sum(1 for item in kb_spaces if str(item.status) == "failed"),
                },
                "knowledge_graph": {
                    "entity_count": entity_query.count(),
                    "relation_count": relation_query.count(),
                },
                "teacher_review_sync_count": teacher_review_sync_count,
                "last_rebuild_at": latest_built_at,
                "storage": storage_summary,
            }

    def _build_kb_storage_summary(
        self,
        *,
        tasks: list[FileParseTask],
        materials: list[Material],
    ) -> dict[str, Any]:
        current_storage = build_runtime_rag_storage_config_snapshot()
        current_requested = current_storage.get("requested_backend")
        current_effective = current_storage.get("effective_backend")
        target_backend = current_effective if current_effective != "unavailable" else current_requested

        latest_task_by_material: dict[str, FileParseTask] = {}
        backend_distribution: dict[str, int] = {}
        latest_completed_backend = None
        latest_completed_at = None

        completed_tasks = [
            task for task in tasks
            if str(task.status) == "completed"
        ]
        for task in sorted(completed_tasks, key=lambda item: item.updated_at or item.created_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True):
            if task.material_id not in latest_task_by_material:
                latest_task_by_material[task.material_id] = task
            storage_meta = self._extract_task_storage_meta(task)
            backend = storage_meta.get("effective_backend") or storage_meta.get("requested_backend") or "unknown"
            backend_distribution[backend] = backend_distribution.get(backend, 0) + 1
            if latest_completed_backend is None:
                latest_completed_backend = backend
                latest_completed_at = task.updated_at or task.created_at

        reindex_candidates = []
        for material in materials:
            if str(material.kb_status) != "indexed":
                continue
            latest_task = latest_task_by_material.get(material.id)
            storage_meta = self._extract_task_storage_meta(latest_task) if latest_task else {}
            indexed_backend = storage_meta.get("effective_backend") or storage_meta.get("requested_backend")
            if not indexed_backend and target_backend == "lightrag-default":
                indexed_backend = "lightrag-default"
            if not indexed_backend:
                reindex_candidates.append({
                    "material_id": material.id,
                    "title": material.title,
                    "file_name": material.file_name,
                    "class_id": material.class_id,
                    "current_kb_status": material.kb_status,
                    "indexed_backend": None,
                    "reason": "missing_storage_metadata",
                })
            elif target_backend and indexed_backend != target_backend:
                reindex_candidates.append({
                    "material_id": material.id,
                    "title": material.title,
                    "file_name": material.file_name,
                    "class_id": material.class_id,
                    "current_kb_status": material.kb_status,
                    "indexed_backend": indexed_backend,
                    "reason": "backend_mismatch",
                })

        return {
            "current_requested_backend": current_requested,
            "current_effective_backend": current_effective,
            "indexed_backend_distribution": dict(sorted(backend_distribution.items(), key=lambda item: (-item[1], item[0]))),
            "latest_completed_backend": latest_completed_backend,
            "latest_completed_at": latest_completed_at.isoformat() if latest_completed_at else None,
            "reindex_required": bool(reindex_candidates),
            "reindex_required_count": len(reindex_candidates),
            "reindex_target_backend": target_backend,
            "reindex_candidates": reindex_candidates[:20],
        }

    def _extract_task_storage_meta(self, task: FileParseTask | None) -> dict[str, Any]:
        if not task:
            return {}
        extra = task.extra_data or {}
        storage = extra.get("raganything_storage") or {}
        active = storage.get("active_lightrag_storage") or {}
        return {
            "requested_backend": active.get("requested_backend") or storage.get("requested_backend"),
            "effective_backend": active.get("effective_backend") or storage.get("effective_backend"),
            "workspace": active.get("workspace"),
            "vector_storage": active.get("vector_storage"),
            "graph_storage": active.get("graph_storage"),
        }

    def get_graph(
        self,
        course_id: str,
        *,
        class_id: str | None = None,
        entity_type: str | None = None,
        min_confidence: float = 0.0,
        limit: int = 1000,
    ) -> dict[str, Any]:
        with SessionLocal() as db:
            classes = db.query(Class).filter(Class.course_id == course_id).all()
            class_ids = [row.id for row in classes]
            requested_class_id = str(class_id or "").strip() or None
            if requested_class_id:
                class_ids = [item for item in class_ids if item == requested_class_id]
            normalized_entity_type = str(entity_type or "").strip().lower() or None
            normalized_min_confidence = max(0.0, min(1.0, float(min_confidence or 0.0)))
            node_limit = max(1, min(int(limit or 1000), 2000))
            if not class_ids:
                return {
                    "course_id": course_id,
                    "backend": "raganything",
                    "nodes": [],
                    "edges": [],
                    "stats": {"node_count": 0, "edge_count": 0, "class_count": 0},
                    "summary": {
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                        "entity_type_distribution": {},
                        "relation_type_distribution": {},
                        "source_material_count": 0,
                        "material_type_distribution": {},
                        "average_node_confidence": 0.0,
                        "average_edge_confidence": 0.0,
                    },
                    "legend": {"entity_types": [], "relation_types": []},
                    "materials": [],
                    "filters": {
                        "class_id": requested_class_id,
                        "entity_type": normalized_entity_type,
                        "min_confidence": normalized_min_confidence,
                        "limit": node_limit,
                        "available_class_ids": [],
                        "available_entity_types": [],
                    },
                }

            entity_query = db.query(KnowledgeEntity).filter(
                KnowledgeEntity.class_id.in_(class_ids),
                KnowledgeEntity.confidence >= normalized_min_confidence,
            )
            if normalized_entity_type:
                entity_query = entity_query.filter(KnowledgeEntity.entity_type == normalized_entity_type)
            entities = entity_query.all()
            if not normalized_entity_type:
                entities = [
                    entity for entity in entities
                    if self._is_course_graph_display_entity(entity)
                ]

            relation_query = db.query(KnowledgeRelation).filter(
                KnowledgeRelation.class_id.in_(class_ids),
                KnowledgeRelation.confidence >= normalized_min_confidence,
            )
            relations = relation_query.all()

            entity_by_id = {entity.id: entity for entity in entities}
            nodes = []
            sorted_entities = sorted(
                entities,
                key=lambda item: (float(item.confidence or 0.0), str(item.updated_at or item.created_at or "")),
                reverse=True,
            )
            for entity in sorted_entities[:node_limit]:
                nodes.append({
                    "id": entity.id,
                    "label": entity.name,
                    "name": entity.name,
                    "class_id": entity.class_id,
                    "group": entity.entity_type or "concept",
                    "entity_type": entity.entity_type,
                    "description": entity.description,
                    "source_material_id": entity.source_material_id,
                    "confidence": float(entity.confidence or 0.0),
                    "source_span": entity.source_span or {},
                    "provenance": entity.provenance or {},
                    "status": entity.status,
                })
            visible_node_ids = {node["id"] for node in nodes}

            edges = []
            sorted_relations = sorted(
                relations,
                key=lambda item: (float(item.confidence or 0.0), float(item.weight or 0.0)),
                reverse=True,
            )
            for relation in sorted_relations:
                if relation.source_id not in visible_node_ids or relation.target_id not in visible_node_ids:
                    continue
                source = entity_by_id.get(relation.source_id)
                target = entity_by_id.get(relation.target_id)
                source_label = source.name if source else relation.source_id
                target_label = target.name if target else relation.target_id
                relation_label = relation.relation_type or "related_to"
                relation_description = self._relation_description(
                    source_label=source_label,
                    target_label=target_label,
                    relation_type=relation_label,
                    source_span=relation.source_span or {},
                    provenance=relation.provenance or {},
                )
                edges.append({
                    "id": relation.id,
                    "source": relation.source_id,
                    "target": relation.target_id,
                    "source_label": source_label,
                    "target_label": target_label,
                    "label": relation_label,
                    "relation_type": relation.relation_type,
                    "description": relation_description,
                    "summary": relation_description,
                    "weight": float(relation.weight or 0.0),
                    "confidence": float(relation.confidence or 0.0),
                    "source_span": relation.source_span or {},
                    "provenance": relation.provenance or {},
                    "class_id": relation.class_id,
                })

            entity_type_distribution = self._count_labels(
                node.get("entity_type") or node.get("group") or "concept"
                for node in nodes
            )
            relation_type_distribution = self._count_labels(
                edge.get("relation_type") or edge.get("label") or "related_to"
                for edge in edges
            )
            material_ids = sorted({
                str(node.get("source_material_id"))
                for node in nodes
                if node.get("source_material_id")
            })
            materials_by_id = {
                row.id: row
                for row in (
                    db.query(Material).filter(Material.id.in_(material_ids)).all()
                    if material_ids
                    else []
                )
            }
            material_type_distribution = self._count_labels(
                str(materials_by_id[item].file_type or "unknown")
                for item in material_ids
                if item in materials_by_id
            )
            material_summaries = []
            for material_id in material_ids:
                material = materials_by_id.get(material_id)
                if not material:
                    continue
                material_summaries.append({
                    "material_id": material.id,
                    "title": material.title,
                    "file_name": material.file_name,
                    "file_type": material.file_type,
                    "kb_status": material.kb_status,
                    "class_id": material.class_id,
                    "created_at": material.created_at.isoformat() if material.created_at else None,
                })

            return {
                "course_id": course_id,
                "backend": "raganything",
                "nodes": nodes,
                "edges": edges,
                "stats": {
                    "node_count": len(nodes),
                    "edge_count": len(edges),
                    "class_count": len(class_ids),
                },
                "summary": {
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "entity_type_distribution": entity_type_distribution,
                    "relation_type_distribution": relation_type_distribution,
                    "source_material_count": len(material_summaries),
                    "material_type_distribution": material_type_distribution,
                    "average_node_confidence": self._average_numeric(node.get("confidence") for node in nodes),
                    "average_edge_confidence": self._average_numeric(edge.get("confidence") for edge in edges),
                },
                "legend": {
                    "entity_types": [
                        {"name": key, "count": value}
                        for key, value in entity_type_distribution.items()
                    ],
                    "relation_types": [
                        {"name": key, "count": value}
                        for key, value in relation_type_distribution.items()
                    ],
                },
                "materials": material_summaries,
                "filters": {
                    "class_id": requested_class_id,
                    "entity_type": normalized_entity_type,
                    "min_confidence": normalized_min_confidence,
                    "limit": node_limit,
                    "available_class_ids": sorted({str(item.id) for item in classes}),
                    "available_entity_types": sorted({
                        str(item.entity_type or "concept")
                        for item in entities
                        if (item.entity_type or "concept")
                    }),
                },
            }

    def _is_course_graph_display_entity(self, entity: KnowledgeEntity) -> bool:
        kind = str(((entity.source_span or {}) if isinstance(entity.source_span, dict) else {}).get("kind") or "").lower()
        entity_type = str(entity.entity_type or "").strip().lower()
        if kind in {"material", "content_item", "candidate_concept_identifier"}:
            return False
        if entity_type in {"material", "document", "file", "page", "chunk"}:
            return False
        if self._is_low_quality_projection_keyword(entity.name):
            return False
        if self._is_projection_artifact_label(entity.name):
            return False
        if kind.startswith("candidate_") and float(entity.confidence or 0.0) < 0.7:
            return False
        return True

    @staticmethod
    def _relation_description(
        *,
        source_label: str,
        target_label: str,
        relation_type: str,
        source_span: dict[str, Any],
        provenance: dict[str, Any],
    ) -> str:
        evidence = source_span.get("evidence")
        if evidence:
            return str(evidence)[:500]

        relation_payload = provenance.get("raganything_relation")
        if isinstance(relation_payload, dict):
            for key in ("description", "summary", "evidence"):
                value = relation_payload.get(key)
                if value:
                    return str(value)[:500]

        return f"{source_label} --{relation_type}--> {target_label}"

    def _count_labels(self, values: Any) -> dict[str, int]:
        counts: dict[str, int] = {}
        for value in values:
            label = str(value or "unknown").strip() or "unknown"
            counts[label] = counts.get(label, 0) + 1
        return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))

    def _average_numeric(self, values: Any) -> float:
        normalized = [
            float(item)
            for item in values
            if item is not None
        ]
        if not normalized:
            return 0.0
        return round(sum(normalized) / len(normalized), 4)

    async def rebuild_course(self, course_id: str, *, storage_migration_only: bool = False) -> dict:
        with SessionLocal() as db:
            materials = db.query(Material).join(
                Class, Class.id == Material.class_id
            ).filter(
                Class.course_id == course_id,
                Material.is_active == True,
            ).all()
            tasks = db.query(FileParseTask).filter(FileParseTask.course_id == course_id).all()
            storage_summary = self._build_kb_storage_summary(
                tasks=tasks,
                materials=materials,
            )

        selected_material_ids = None
        if storage_migration_only:
            selected_material_ids = {
                str(item.get("material_id"))
                for item in (storage_summary.get("reindex_candidates") or [])
                if item.get("material_id")
            }

        requested = 0
        processed = 0
        for material in materials:
            if not material.file_path:
                continue
            if selected_material_ids is not None and material.id not in selected_material_ids:
                continue
            requested += 1
            if material.file_path:
                ok = await self.ingest_material(material.class_id, material.id, material.file_path, material.mime_type or "application/octet-stream")
                if ok:
                    processed += 1

        status = self.get_kb_status(course_id)
        status["rebuild_scope"] = "storage_migration_only" if storage_migration_only else "full"
        status["requested_reindex_count"] = requested
        status["reprocessed_count"] = processed
        if storage_migration_only:
            status["storage_migration_target_backend"] = (storage_summary.get("reindex_target_backend"))
        return status

    def _terms(self, text: str) -> set[str]:
        latin = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text.lower())
        cjk = re.findall(r"[\u4e00-\u9fff]{2,8}", text)
        return {token for token in [*latin, *cjk] if token}

    def _ensure_kb_space(self, db, course_id: str, class_id: str | None = None) -> KBSpace:
        kb_space = db.query(KBSpace).filter(
            KBSpace.course_id == course_id,
            KBSpace.class_id == class_id,
        ).first()
        if not kb_space:
            kb_space = KBSpace(
                course_id=course_id,
                class_id=class_id,
                status="building",
                extra_data={},
            )
            db.add(kb_space)
            db.flush()
        return kb_space

    def _blended_confidence(self, current: float | None, incoming: float) -> float:
        baseline = float(current) if current is not None else 0.55
        blended = baseline * 0.8 + float(incoming) * 0.2
        return round(min(0.99, max(0.4, blended)), 4)

    def _suggestions(self, question: str) -> list[str]:
        topic = question.strip().replace("\n", " ")[:30] or "这个问题"
        return [
            "可以结合一个例子再解释一遍吗？",
            "我接下来应该优先阅读哪份课程资料？",
            f"关于“{topic}”，最核心的知识点是什么？",
        ]

    def _build_processing_quality(self, status: dict[str, Any]) -> dict[str, Any]:
        text_processed = bool(status.get("text_processed"))
        multimodal_processed = bool(status.get("multimodal_processed"))
        fully_processed = bool(status.get("fully_processed"))

        if fully_processed and text_processed and multimodal_processed:
            quality_level = "complete"
        elif text_processed and multimodal_processed:
            quality_level = "partial"
        elif text_processed:
            quality_level = "text_only"
        elif multimodal_processed:
            quality_level = "multimodal_only"
        else:
            quality_level = "failed"

        warnings: list[str] = []
        if not text_processed:
            warnings.append("text_not_ready")
        if not multimodal_processed:
            warnings.append("multimodal_not_ready")
        if not fully_processed:
            warnings.append("pipeline_not_fully_processed")

        return {
            "quality_level": quality_level,
            "text_processed": text_processed,
            "multimodal_processed": multimodal_processed,
            "fully_processed": fully_processed,
            "warnings": warnings,
            "raw_status_keys": sorted(status.keys()),
        }

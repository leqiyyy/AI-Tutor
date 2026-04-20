import importlib
import inspect
import os
import re
import asyncio
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from app.ai.base import RAGResult
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.logging import get_logger
from app.integrations.parser.simple import SimpleParserProvider
from app.integrations.rag.query_rewrite import build_query_rewrite_bundle
from app.integrations.reranker import get_reranker
from app.integrations.rag.simple_engine import SimpleRAGEngine
from app.models.chat import ReviewSyncRecord
from app.models.course import Class, Course, Material
from app.models.knowledge import FileParseTask, KBSpace, KnowledgeEntity, KnowledgeRelation
from app.services import model_routing_service

logger = get_logger(__name__)


class RAGAnythingAdapter(SimpleRAGEngine):
    """Official RAG-Anything-backed adapter with local DB metadata support."""

    def __init__(self) -> None:
        super().__init__()
        self._instances: dict[str, object] = {}
        self._instance_route_signatures: dict[str, str] = {}

    def _prepare_environment(self) -> None:
        if settings.LIBREOFFICE_PATH:
            soffice_path = Path(settings.LIBREOFFICE_PATH)
            if soffice_path.exists():
                os.environ["SOFFICE_PATH"] = str(soffice_path)
                soffice_dir = str(soffice_path.parent)
                path_parts = os.environ.get("PATH", "").split(os.pathsep)
                if soffice_dir not in path_parts:
                    os.environ["PATH"] = soffice_dir + os.pathsep + os.environ.get("PATH", "")

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
    ) -> str:
        if wire_api == "responses":
            input_items = []
            if system_prompt:
                input_items.append({
                    "role": "system",
                    "content": [{"type": "input_text", "text": system_prompt}],
                })
            for message in history_messages or []:
                input_items.append({
                    "role": message.get("role", "user"),
                    "content": [{"type": "input_text", "text": message.get("content", "")}],
                })
            input_items.append({
                "role": "user",
                "content": [{"type": "input_text", "text": prompt}],
            })

            endpoint = base_url.rstrip("/") + "/responses"
            headers = {
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

            if data.get("output_text"):
                return data["output_text"]

            texts = []
            for item in data.get("output", []) or []:
                for content in item.get("content", []) or []:
                    text = content.get("text")
                    if text:
                        texts.append(text)
            return "\n".join(texts)

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
            chat_messages.extend(history_messages or [])
            chat_messages.append({"role": "user", "content": prompt})
            response = await client.chat.completions.create(
                model=model,
                messages=chat_messages,
            )
            return response.choices[0].message.content or ""
        finally:
            await client.close()

    def _build_llm_func(self, routing_snapshot: dict[str, Any]):
        generation = routing_snapshot.get("generation") or {}
        extract_model = generation.get("model") or settings.EFFECTIVE_EXTRACT_MODEL
        extract_base = generation.get("api_base") or settings.EFFECTIVE_EXTRACT_API_BASE
        extract_api_key = settings.EFFECTIVE_EXTRACT_API_KEY

        async def _llm(prompt, system_prompt=None, history_messages=None, keyword_extraction=False, **kwargs):
            return await self._call_llm_api(
                prompt=prompt,
                system_prompt=system_prompt,
                history_messages=history_messages,
                model=extract_model,
                base_url=extract_base,
                api_key=extract_api_key,
                wire_api=settings.EXTRACT_WIRE_API,
            )

        return _llm

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
            return await openai_embed.func(
                texts,
                model=embedding_model,
                base_url=embedding_base or None,
                api_key=embedding_api_key,
                embedding_dim=settings.EMBEDDING_DIM,
                **kwargs,
            )

        return _embedding

    def _build_vision_func(self, routing_snapshot: dict[str, Any]):
        vlm = routing_snapshot.get("vlm") or {}
        vlm_base = vlm.get("api_base") or settings.EFFECTIVE_VLM_API_BASE
        vlm_model = vlm.get("model") or settings.EFFECTIVE_VLM_MODEL
        vlm_api_key = settings.EFFECTIVE_VLM_API_KEY

        async def _vision(prompt, image_data=None, system_prompt=None, messages=None, **kwargs):
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
                return response.choices[0].message.content or ""
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

    def _get_instance(self, class_id: str):
        routing_snapshot = self._load_runtime_routing_snapshot()
        routing_signature = self._routing_signature(routing_snapshot)
        if class_id in self._instances and self._instance_route_signatures.get(class_id) == routing_signature:
            return self._instances[class_id]

        self._prepare_environment()
        self._require_model_config(routing_snapshot)

        raganything_module = importlib.import_module("raganything")
        config_module = importlib.import_module("raganything.config")
        RAGAnything = getattr(raganything_module, "RAGAnything")
        RAGAnythingConfig = getattr(config_module, "RAGAnythingConfig")

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
        llm_model_name = generation.get("model") or settings.LLM_MODEL
        embedding_func = self._build_embedding_func(routing_snapshot)

        instance = RAGAnything(
            llm_model_func=self._build_llm_func(routing_snapshot),
            vision_model_func=self._build_vision_func(routing_snapshot) if vlm.get("effective_backend") != "mock" else None,
            embedding_func=embedding_func,
            config=config,
            lightrag_kwargs={
                "llm_model_name": llm_model_name,
                "embedding_func": embedding_func,
                "working_dir": str(working_dir),
                "llm_model_max_async": 1,
            },
        )
        if not instance.check_parser_installation():
            raise RuntimeError("RAG-Anything parser installation check failed")

        self._instances[class_id] = instance
        self._instance_route_signatures[class_id] = routing_signature
        return instance

    def _load_runtime_routing_snapshot(self) -> dict[str, Any]:
        snapshot = model_routing_service.build_runtime_model_routing_snapshot()
        if snapshot:
            return snapshot
        return model_routing_service.build_model_routing_snapshot()

    def _routing_signature(self, snapshot: dict[str, Any]) -> str:
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
        return "|".join(parts)

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

            task.status = "processing"
            material.kb_status = "processing"
            db.commit()

            rag = self._get_instance(class_id)
            await rag.process_document_complete(
                file_path=file_path,
                output_dir=str((Path(settings.RAGANYTHING_OUTPUT_DIR) / class_id).resolve()),
                parse_method=settings.RAGANYTHING_PARSE_METHOD,
                doc_id=material_id,
                file_name=material.file_name,
            )

            status = rag.get_document_processing_status(material_id)
            if inspect.isawaitable(status):
                status = await status
            parsed = self.parser.parse(file_path, mime_type, material.file_name)

            text_processed = bool(status.get("text_processed"))
            multimodal_processed = bool(status.get("multimodal_processed"))
            fully_processed = bool(status.get("fully_processed"))
            quality = self._build_processing_quality(status)

            task.status = "completed" if text_processed else "failed"
            task.parser_name = "raganything"
            task.summary = parsed["summary"]
            task.extracted_text = parsed["text"]
            task.chunks = parsed["chunks"]
            task.extra_data = {
                "keywords": parsed["keywords"],
                "content_items": parsed["content_items"],
                "raganything_status": status,
                "raganything_quality": quality,
            }
            material.kb_status = "indexed" if task.status == "completed" else "failed"
            if task.status == "completed" and not fully_processed:
                if text_processed and not multimodal_processed:
                    material.kb_error = "RAG-Anything text indexing succeeded, but multimodal/KG extraction only partially completed"
                else:
                    material.kb_error = "RAG-Anything indexed text successfully, but some advanced extraction steps failed"
            else:
                material.kb_error = None if task.status == "completed" else "RAG-Anything processing incomplete"

            self._sync_entities(
                db,
                class_id,
                material_id,
                parsed["keywords"],
                chunks=parsed.get("chunks"),
                content_items=parsed.get("content_items"),
            )

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
    ) -> RAGResult:
        query_mode = settings.RAGANYTHING_QUERY_MODE or "mix"
        routing_snapshot = self._load_runtime_routing_snapshot()
        routing_meta = model_routing_service.flatten_routing_snapshot(routing_snapshot)
        rewrite_bundle = build_query_rewrite_bundle(
            question=question,
            enabled=bool(settings.RAG_QUERY_REWRITE_ENABLED),
            mode=settings.RAG_QUERY_REWRITE_MODE,
            max_variants=settings.RAG_QUERY_REWRITE_MAX_VARIANTS,
        )
        query_variants = rewrite_bundle["queries"]
        with SessionLocal() as db:
            review_matches = self._review_answer_candidates(db, class_id, question)
            search_results = self._search_chunks_for_queries(
                db,
                class_id=class_id,
                queries=query_variants,
            )

        image_contexts = []
        for attachment in attachments or []:
            if attachment.get("file_type") == "image":
                description = await self._describe_image_attachment(attachment, question)
                if description:
                    image_contexts.append(description)

        raganything_result, fallback_reason, query_method = await self._query_with_raganything(
            question=question,
            class_id=class_id,
            history=history,
            attachments=attachments,
            image_contexts=image_contexts,
            query_mode=query_mode,
        )
        if raganything_result is not None:
            raganything_result.meta = {
                **(raganything_result.meta or {}),
                "engine": "raganything",
                "query_mode": query_mode,
                "query_method": query_method,
                "used_multimodal": query_method == "aquery_with_multimodal",
                "used_fallback": False,
                "fallback_reason": None,
                "retrieval_strategy": "main_chain",
                "reranker_provider": "main_chain_native",
                "reranker_model": None,
                "candidate_count": len(raganything_result.sources or []),
                "selected_count": len(raganything_result.sources or []),
                "query_rewrite_enabled": bool(rewrite_bundle["enabled"]),
                "query_rewrite_mode": rewrite_bundle["mode"],
                "query_variant_count": rewrite_bundle["variant_count"],
                "llm_backend": routing_meta.get("llm_backend"),
                "embedding_backend": routing_meta.get("embedding_backend"),
                "vlm_backend": routing_meta.get("vlm_backend"),
                "reranker_backend": routing_meta.get("reranker_backend"),
            }
            return raganything_result

        fallback_result = await self._query_with_local_fallback(
            question=question,
            class_id=class_id,
            history=history,
            role=role,
            review_matches=review_matches,
            search_results=search_results,
            image_contexts=image_contexts,
            query_variants=query_variants,
            rewrite_bundle=rewrite_bundle,
            routing_snapshot=routing_snapshot,
        )
        fallback_result.meta = {
            **(fallback_result.meta or {}),
            "engine": "raganything",
            "query_mode": query_mode,
            "query_method": query_method,
            "used_multimodal": bool(image_contexts),
            "used_fallback": True,
            "fallback_reason": fallback_reason or "main_chain_unavailable",
        }
        return fallback_result

    async def _query_with_raganything(
        self,
        *,
        question: str,
        class_id: str,
        history: list[dict] | None,
        attachments: list[dict] | None,
        image_contexts: list[str],
        query_mode: str,
    ) -> tuple[RAGResult | None, str | None, str | None]:
        query_parts = [question]
        if image_contexts:
            query_parts.append(
                "Image-derived context:\n"
                + "\n".join(f"- {content}" for content in image_contexts[:2])
            )
        query_text = "\n\n".join(query_parts)

        try:
            rag = self._get_instance(class_id)
        except Exception as exc:
            logger.warning(
                "raganything_instance_fallback",
                class_id=class_id,
                reason=str(exc),
            )
            return None, "instance_init_failed", None

        has_image = any((attachment or {}).get("file_type") == "image" for attachment in (attachments or []))
        logger.info(
            "raganything_query_attempt",
            class_id=class_id,
            mode=query_mode,
            has_image=has_image,
        )
        try:
            raw, query_method = await self._invoke_rag_query(
                rag=rag,
                query_text=query_text,
                query_mode=query_mode,
                history=history or [],
                attachments=attachments or [],
                prefer_multimodal=has_image,
                class_id=class_id,
            )
        except Exception as exc:
            logger.warning(
                "raganything_query_fallback",
                class_id=class_id,
                mode=query_mode,
                reason=str(exc),
            )
            return None, "query_exception", None

        answer, sources, confidence = self._normalize_rag_query_output(raw)
        if not answer:
            logger.warning(
                "raganything_query_empty_answer",
                class_id=class_id,
                mode=query_mode,
            )
            return None, "empty_answer", query_method

        if confidence <= 0:
            top_score = next((source.get("score") for source in sources if source.get("score") is not None), None)
            confidence = min(0.95, max(0.55, float(top_score))) if top_score is not None else 0.6

        return (
            RAGResult(
                answer=answer,
                sources=sources,
                confidence=confidence,
                suggestions=self._suggestions(question),
            ),
            None,
            query_method,
        )

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
    ) -> tuple[Any, str]:
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
            )
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

    def _build_rag_query_kwargs(
        self,
        *,
        method: Any,
        query_text: str,
        query_mode: str,
        history: list[dict],
        attachments: list[dict],
    ) -> dict[str, Any] | None:
        signature = inspect.signature(method)
        params = signature.parameters
        accepts_kwargs = any(param.kind == inspect.Parameter.VAR_KEYWORD for param in params.values())

        question_param = next(
            (name for name in ("query", "question", "prompt") if accepts_kwargs or name in params),
            None,
        )
        mode_param = next(
            (name for name in ("query_mode", "mode") if accepts_kwargs or name in params),
            None,
        )
        history_param = next(
            (name for name in ("history_messages", "history", "conversation_history") if accepts_kwargs or name in params),
            None,
        )
        attachments_param = next(
            (name for name in ("attachments", "images", "image_inputs") if accepts_kwargs or name in params),
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
        if history and history_param:
            kwargs[history_param] = history
        if attachments and attachments_param:
            kwargs[attachments_param] = attachments
        return kwargs

    def _normalize_rag_query_output(self, raw: Any) -> tuple[str, list[dict], float]:
        if raw is None:
            return "", [], 0.0

        if isinstance(raw, str):
            return raw.strip(), [], 0.0

        if isinstance(raw, dict):
            answer = (
                raw.get("answer")
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
            if not source_candidates and isinstance(raw.get("context"), dict):
                source_candidates = raw["context"].get("sources") or raw["context"].get("chunks") or []
            sources = self._normalize_sources(source_candidates)
            confidence = self._safe_float(raw.get("confidence")) or self._safe_float(raw.get("score")) or 0.0
            return str(answer).strip(), sources, confidence

        if isinstance(raw, (list, tuple)):
            if all(isinstance(item, str) for item in raw):
                return "\n".join(item for item in raw if item).strip(), [], 0.0
            sources = self._normalize_sources(list(raw))
            return "", sources, 0.0

        answer = getattr(raw, "answer", None) or getattr(raw, "response", None) or str(raw)
        sources = self._normalize_sources(getattr(raw, "sources", []))
        confidence = self._safe_float(getattr(raw, "confidence", 0.0)) or 0.0
        return str(answer).strip(), sources, confidence

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
                })
                continue
            if not isinstance(item, dict):
                continue

            score = (
                self._safe_float(item.get("score"))
                or self._safe_float(item.get("similarity"))
                or self._safe_float(item.get("confidence"))
            )
            normalized.append({
                "name": item.get("name") or item.get("source_name") or item.get("source") or item.get("file_name") or "unknown",
                "page": item.get("page") or item.get("page_idx") or item.get("page_number"),
                "type": item.get("type") or item.get("source_type") or item.get("mime_type"),
                "score": score,
                "chunk_id": item.get("chunk_id") or item.get("id") or item.get("doc_id"),
            })
        return normalized

    def _safe_float(self, value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    async def _query_with_local_fallback(
        self,
        *,
        question: str,
        class_id: str,
        history: list[dict] | None,
        role: str,
        review_matches: list[dict],
        search_results: list[dict],
        image_contexts: list[str],
        query_variants: list[str],
        rewrite_bundle: dict[str, Any],
        routing_snapshot: dict[str, Any],
    ) -> RAGResult:
        logger.info("raganything_local_fallback_used", class_id=class_id)
        routing_meta = model_routing_service.flatten_routing_snapshot(routing_snapshot)

        retrieval_bundle = self._apply_retrieval_strategy(
            question=question,
            class_id=class_id,
            search_results=search_results,
            query_variants=query_variants,
        )
        candidates = retrieval_bundle["candidates"]
        reranker = get_reranker()
        reranked_results = await reranker.rerank(
            query=question,
            candidates=candidates,
            context={
                "review_matches": review_matches,
                "image_contexts": image_contexts,
                "retrieval_strategy": retrieval_bundle["strategy"],
                "query_variants": query_variants,
            },
        )
        top_k = max(1, int(settings.RAG_ANSWER_TOP_K))
        top_results = reranked_results[:top_k]

        sources = [{
            "name": item["source_name"],
            "page": item["page"],
            "type": item["source_type"],
            "score": item.get("rerank_score", item.get("retrieval_score", item.get("score"))),
            "chunk_id": item["chunk_id"],
            "retrieval_score": item.get("retrieval_score"),
            "rerank_score": item.get("rerank_score"),
        } for item in top_results]
        context_text = "\n\n".join(
            f"Source {idx + 1} ({source['name']} p.{source['page']} | score={source['score']}): {item['snippet']}"
            for idx, (source, item) in enumerate(zip(sources, top_results))
        )
        review_context = "\n\n".join(
            f"Teacher-reviewed answer {idx + 1}: {item['final_answer']}"
            for idx, item in enumerate(review_matches[:2])
        )
        image_context = "\n\n".join(
            f"Image context {idx + 1}: {content}"
            for idx, content in enumerate(image_contexts[:2])
        )

        if sources or review_context or image_context:
            role_instruction = (
                "Answer like a patient course tutor for a student. Use simple teaching language, definitions, and a short example when helpful."
                if role == "student"
                else "Answer like a teaching copilot for an instructor. Be concise, structured, and classroom-oriented."
            )
            sections = []
            if review_context:
                sections.append("Teacher-reviewed corrections:\n" + review_context)
            if context_text:
                sections.append("Retrieved course context:\n" + context_text)
            if image_context:
                sections.append("User-provided image context:\n" + image_context)
            generation = routing_snapshot.get("generation") or {}
            if generation.get("effective_backend") in {"api", "local"}:
                answer = await self._call_llm_api(
                    prompt=(
                        "Answer the user question using the supplied course evidence. "
                        "Prefer teacher-reviewed answers when they are relevant. "
                        "Do not invent facts outside the provided evidence. "
                        "If evidence is limited, say what is supported and what is uncertain.\n\n"
                        f"{role_instruction}\n\n"
                        f"Question: {question}\n\n"
                        + "\n\n".join(sections)
                    ),
                    system_prompt=(
                        "You are the AI tutor for a course. "
                        "Produce grounded answers, mention the core concept first, then a brief explanation, then a practical example when possible."
                    ),
                    history_messages=history or [],
                    model=generation.get("model") or settings.LLM_MODEL,
                    base_url=generation.get("api_base") or settings.EFFECTIVE_LLM_API_BASE,
                    api_key=settings.EFFECTIVE_LLM_API_KEY,
                    wire_api=settings.LLM_WIRE_API,
                )
            else:
                answer = self._build_rule_based_fallback_answer(
                    question=question,
                    top_results=top_results,
                    role_instruction=role_instruction,
                )
            top_score = float(top_results[0].get("rerank_score", 0.0)) if top_results else 0.0
            confidence = min(0.96, max(0.4, top_score + 0.35))
        else:
            answer = (
                "I could not find grounded evidence in the current course knowledge base. "
                "Please upload more course materials or ask a more specific question."
            )
            confidence = 0.4
        return RAGResult(
            answer=answer,
            sources=sources,
            confidence=confidence,
            suggestions=self._suggestions(question),
            meta={
                "retrieval_strategy": retrieval_bundle["strategy"],
                "candidate_count": retrieval_bundle["candidate_count"],
                "selected_count": len(top_results),
                "graph_term_count": retrieval_bundle["graph_term_count"],
                "reranker_provider": getattr(reranker, "provider_name", "unknown"),
                "reranker_model": getattr(reranker, "model_name", "unknown"),
                "query_rewrite_enabled": bool(rewrite_bundle["enabled"]),
                "query_rewrite_mode": rewrite_bundle["mode"],
                "query_variant_count": rewrite_bundle["variant_count"],
                "llm_backend": routing_meta.get("llm_backend"),
                "embedding_backend": routing_meta.get("embedding_backend"),
                "vlm_backend": routing_meta.get("vlm_backend"),
                "reranker_backend": routing_meta.get("reranker_backend"),
            },
        )

    def _build_rule_based_fallback_answer(
        self,
        *,
        question: str,
        top_results: list[dict[str, Any]],
        role_instruction: str,
    ) -> str:
        if not top_results:
            return (
                "I could not find grounded evidence in the current course knowledge base. "
                "Please upload more course materials or ask a more specific question."
            )

        snippets = []
        for idx, item in enumerate(top_results[:3]):
            snippets.append(f"{idx + 1}. {(item.get('snippet') or '').strip()}")
        return (
            f"{role_instruction}\n\n"
            f"Question: {question}\n\n"
            "Based on the retrieved course evidence, here are the most relevant points:\n"
            + "\n".join(snippets)
        )

    async def add_qa_pair(self, class_id: str, question: str, answer: str) -> bool:
        rag = self._get_instance(class_id)
        await rag.insert_content_list(
            content_list=[{
                "type": "text",
                "text": f"Question: {question}\nAnswer: {answer}",
                "page_idx": 0,
            }],
            file_path=f"manual_review_{class_id}.txt",
            doc_id=f"manual-{abs(hash(question + answer))}",
        )
        return await super().add_qa_pair(class_id, question, answer)

    async def rebuild_course(self, course_id: str) -> dict:
        with SessionLocal() as db:
            materials = db.query(Material).join(
                Class, Class.id == Material.class_id
            ).filter(
                Class.course_id == course_id,
                Material.is_active == True,
            ).all()

        processed = 0
        for material in materials:
            if material.file_path:
                ok = await self.ingest_material(material.class_id, material.id, material.file_path, material.mime_type or "application/octet-stream")
                if ok:
                    processed += 1

        status = self.get_kb_status(course_id)
        status["reprocessed_count"] = processed
        return status

    def _search_class_chunks(self, db, class_id: str, query: str) -> list[dict]:
        tasks = db.query(FileParseTask).filter(
            FileParseTask.class_id == class_id,
            FileParseTask.status == "completed",
        ).all()
        query_terms = self._terms(query)
        results = []
        for task in tasks:
            for chunk in task.chunks or []:
                chunk_text = chunk.get("text", "")
                overlap = len(query_terms & self._terms(chunk_text))
                if overlap <= 0:
                    continue
                results.append({
                    "source_name": chunk.get("source_name"),
                    "source_type": chunk.get("source_type"),
                    "page": chunk.get("page"),
                    "chunk_id": chunk.get("chunk_id"),
                    "score": round(overlap / max(len(query_terms), 1), 4),
                    "snippet": chunk_text[:280],
                    "raw_text": chunk_text,
                })
        results.sort(key=lambda item: item["score"], reverse=True)
        limit = max(8, int(settings.RAG_RETRIEVAL_CANDIDATE_K) * 2)
        return results[:limit]

    def _search_chunks_for_queries(self, db, class_id: str, queries: list[str]) -> list[dict]:
        ordered_queries: list[str] = []
        seen_queries = set()
        for query in queries or []:
            normalized = (query or "").strip()
            if not normalized:
                continue
            lowered = normalized.lower()
            if lowered in seen_queries:
                continue
            seen_queries.add(lowered)
            ordered_queries.append(normalized)

        if not ordered_queries:
            return []

        merged: dict[str, dict] = {}
        for query in ordered_queries:
            query_results = self._search_class_chunks(db, class_id, query)
            for item in query_results:
                key = item.get("chunk_id") or hashlib.md5(
                    f"{item.get('source_name')}|{item.get('page')}|{item.get('snippet')}".encode()
                ).hexdigest()
                current_score = float(item.get("score") or 0.0)
                existing = merged.get(key)
                if not existing:
                    merged[key] = {
                        **item,
                        "score": current_score,
                        "matched_queries": [query],
                        "query_hits": 1,
                    }
                    continue

                existing_score = float(existing.get("score") or 0.0)
                if current_score > existing_score:
                    existing.update({
                        **item,
                        "score": current_score,
                    })
                    existing["matched_queries"] = existing.get("matched_queries", [])

                matched_queries = existing.get("matched_queries") or []
                if query not in matched_queries:
                    matched_queries.append(query)
                existing["matched_queries"] = matched_queries
                existing["query_hits"] = len(matched_queries)

        results = list(merged.values())
        results.sort(
            key=lambda item: (
                float(item.get("score") or 0.0),
                int(item.get("query_hits") or 0),
            ),
            reverse=True,
        )
        limit = max(10, int(settings.RAG_RETRIEVAL_CANDIDATE_K) * 4)
        return results[:limit]

    def _deduplicate_results(self, results: list[dict]) -> list[dict]:
        deduped = []
        seen = set()
        for item in results:
            key = (
                item.get("chunk_id")
                or hashlib.md5(f"{item.get('source_name')}|{item.get('page')}|{item.get('snippet')}".encode()).hexdigest()
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    def _rerank_results(
        self,
        question: str,
        results: list[dict],
        review_matches: list[dict],
        image_contexts: list[str],
    ) -> list[dict]:
        question_terms = self._terms(question)
        image_terms = self._terms(" ".join(image_contexts))
        reranked = []
        for item in results:
            snippet_terms = self._terms(item.get("raw_text", ""))
            lexical = len(question_terms & snippet_terms)
            image_boost = 0.2 if image_terms and (image_terms & snippet_terms) else 0.0
            review_boost = 0.1 if review_matches else 0.0
            score = float(item["score"]) + lexical * 0.05 + image_boost + review_boost
            reranked.append({**item, "score": round(score, 3)})
        reranked.sort(key=lambda item: item["score"], reverse=True)
        return reranked

    def _apply_retrieval_strategy(
        self,
        *,
        question: str,
        class_id: str,
        search_results: list[dict],
        query_variants: list[str] | None = None,
    ) -> dict[str, Any]:
        strategy = self._normalized_retrieval_strategy()
        deduped = self._deduplicate_results(search_results)
        normalized_queries = self._normalize_query_variants(query_variants, fallback=question)
        variant_term_sets = []
        for query_text in normalized_queries:
            term_set = self._terms(query_text)
            if term_set:
                variant_term_sets.append(term_set)
        graph_seed = " ".join(normalized_queries) if normalized_queries else question
        graph_terms = self._collect_graph_terms(class_id, graph_seed) if strategy in {"hybrid", "graph"} else set()
        candidate_limit = max(5, int(settings.RAG_RETRIEVAL_CANDIDATE_K))

        candidates: list[dict[str, Any]] = []
        for item in deduped:
            lexical_score = float(item.get("score") or 0.0)
            snippet_terms = self._terms(item.get("raw_text") or item.get("snippet") or "")
            matched_variants = sum(
                1 for term_set in variant_term_sets if term_set and (term_set & snippet_terms)
            )
            query_coverage = (
                matched_variants / len(variant_term_sets)
                if variant_term_sets
                else 0.0
            )
            coverage_boost = 0.0
            if len(variant_term_sets) > 1:
                coverage_boost = min(0.16, max(0, matched_variants - 1) * 0.04)
            graph_overlap = len(graph_terms & snippet_terms)
            graph_boost = min(0.5, graph_overlap * 0.07)

            if strategy == "lexical":
                retrieval_score = lexical_score + coverage_boost
            elif strategy == "graph":
                retrieval_score = graph_boost + lexical_score * 0.1 + coverage_boost
            else:  # hybrid
                retrieval_score = lexical_score + graph_boost + coverage_boost

            candidates.append({
                **item,
                "lexical_score": round(lexical_score, 4),
                "graph_boost": round(graph_boost, 4),
                "query_coverage": round(query_coverage, 4),
                "query_coverage_boost": round(coverage_boost, 4),
                "matched_query_count": matched_variants,
                "retrieval_score": round(retrieval_score, 4),
                "retrieval_strategy": strategy,
            })

        candidates.sort(key=lambda item: item.get("retrieval_score", 0.0), reverse=True)
        return {
            "strategy": strategy,
            "candidate_count": len(candidates),
            "graph_term_count": len(graph_terms),
            "query_variant_count": len(normalized_queries),
            "candidates": candidates[:candidate_limit],
        }

    def _normalize_query_variants(self, query_variants: list[str] | None, *, fallback: str) -> list[str]:
        variants: list[str] = []
        seen = set()
        for query in query_variants or []:
            normalized = (query or "").strip()
            if not normalized:
                continue
            lowered = normalized.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            variants.append(normalized)
        if not variants:
            fallback_query = (fallback or "").strip()
            if fallback_query:
                variants.append(fallback_query)
        return variants

    def _normalized_retrieval_strategy(self) -> str:
        strategy = (settings.RAG_RETRIEVAL_STRATEGY or "hybrid").lower().strip()
        if strategy not in {"lexical", "hybrid", "graph"}:
            logger.warning("retrieval_strategy_fallback", requested=strategy, fallback="hybrid")
            return "hybrid"
        return strategy

    def _collect_graph_terms(self, class_id: str, question: str) -> set[str]:
        question_terms = self._terms(question)
        if not question_terms:
            return set()

        with SessionLocal() as db:
            entities = db.query(KnowledgeEntity).filter(KnowledgeEntity.class_id == class_id).all()

        terms: set[str] = set()
        for entity in entities:
            name = (entity.name or "").strip().lower()
            if not name:
                continue
            entity_terms = self._terms(name)
            if not entity_terms:
                continue
            if entity_terms & question_terms:
                terms.update(entity_terms)
        return terms

    def _review_answer_candidates(self, db, class_id: str, question: str) -> list[dict]:
        question_terms = self._terms(question)
        matches = []
        for record in db.query(ReviewSyncRecord).filter(
            ReviewSyncRecord.class_id == class_id,
            ReviewSyncRecord.sync_status == "synced",
        ).all():
            overlap = len(question_terms & self._terms(record.question_content))
            if overlap <= 0:
                continue
            matches.append({
                "review_id": record.review_id,
                "question_content": record.question_content,
                "final_answer": record.final_answer,
                "score": round(overlap / max(len(question_terms), 1), 3),
            })
        matches.sort(key=lambda item: item["score"], reverse=True)
        return matches

    def _terms(self, text: str) -> set[str]:
        latin = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text.lower())
        cjk = re.findall(r"[\u4e00-\u9fff]{2,8}", text)
        return {token for token in [*latin, *cjk] if token}

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

import importlib
import inspect
import os
import re
import asyncio
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import httpx
from app.ai.base import RAGResult
from app.core.config import settings
from app.core.database import SessionLocal
from app.integrations.parser.simple import SimpleParserProvider
from app.integrations.rag.simple_engine import SimpleRAGEngine
from app.models.chat import ReviewSyncRecord
from app.models.course import Class, Course, Material
from app.models.knowledge import FileParseTask, KBSpace, KnowledgeEntity, KnowledgeRelation


class RAGAnythingAdapter(SimpleRAGEngine):
    """Official RAG-Anything-backed adapter with local DB metadata support."""

    def __init__(self) -> None:
        super().__init__()
        self._instances: dict[str, object] = {}

    def _prepare_environment(self) -> None:
        if settings.LIBREOFFICE_PATH:
            soffice_path = Path(settings.LIBREOFFICE_PATH)
            if soffice_path.exists():
                os.environ["SOFFICE_PATH"] = str(soffice_path)
                soffice_dir = str(soffice_path.parent)
                path_parts = os.environ.get("PATH", "").split(os.pathsep)
                if soffice_dir not in path_parts:
                    os.environ["PATH"] = soffice_dir + os.pathsep + os.environ.get("PATH", "")

    def _require_model_config(self) -> None:
        if not settings.EFFECTIVE_LLM_API_KEY:
            raise RuntimeError("RAG-Anything requires OPENAI_API_KEY for llm/embedding initialization")
        if not settings.LLM_MODEL:
            raise RuntimeError("RAG-Anything requires LLM_MODEL to be configured")
        if not settings.EMBEDDING_MODEL:
            raise RuntimeError("RAG-Anything requires EMBEDDING_MODEL to be configured")

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

    def _build_llm_func(self):
        async def _llm(prompt, system_prompt=None, history_messages=None, keyword_extraction=False, **kwargs):
            return await self._call_llm_api(
                prompt=prompt,
                system_prompt=system_prompt,
                history_messages=history_messages,
                model=settings.EFFECTIVE_EXTRACT_MODEL,
                base_url=settings.EFFECTIVE_EXTRACT_API_BASE,
                api_key=settings.EFFECTIVE_EXTRACT_API_KEY,
                wire_api=settings.EXTRACT_WIRE_API,
            )

        return _llm

    def _build_embedding_func(self):
        openai_module = importlib.import_module("lightrag.llm.openai")
        utils_module = importlib.import_module("lightrag.utils")
        openai_embed = getattr(openai_module, "openai_embed")
        wrap_embedding_func_with_attrs = getattr(utils_module, "wrap_embedding_func_with_attrs")

        @wrap_embedding_func_with_attrs(
            embedding_dim=settings.EMBEDDING_DIM,
            max_token_size=8192,
            model_name=settings.EMBEDDING_MODEL,
        )
        async def _embedding(texts: list[str], **kwargs):
            return await openai_embed.func(
                texts,
                model=settings.EMBEDDING_MODEL,
                base_url=settings.EFFECTIVE_EMBEDDING_API_BASE or None,
                api_key=settings.EFFECTIVE_EMBEDDING_API_KEY,
                embedding_dim=settings.EMBEDDING_DIM,
                **kwargs,
            )

        return _embedding

    def _build_vision_func(self):
        async def _vision(prompt, image_data=None, system_prompt=None, messages=None, **kwargs):
            openai_module = importlib.import_module("openai")
            AsyncOpenAI = getattr(openai_module, "AsyncOpenAI")
            client = AsyncOpenAI(
                base_url=settings.EFFECTIVE_VLM_API_BASE or None,
                api_key=settings.EFFECTIVE_VLM_API_KEY,
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
                    model=settings.EFFECTIVE_VLM_MODEL,
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
        if not image_data or not settings.EFFECTIVE_VLM_MODEL:
            return None

        vision = self._build_vision_func()
        description = await vision(
            prompt=f"Describe the educational content in this image to help answer the question: {question}",
            image_data=image_data,
            system_prompt="You are assisting a course AI tutor. Extract the question content, visible text, diagrams, and any problem-solving cues from the image.",
        )
        return description.strip() if description else None

    def _get_instance(self, class_id: str):
        if class_id in self._instances:
            return self._instances[class_id]

        self._prepare_environment()
        self._require_model_config()

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

        instance = RAGAnything(
            llm_model_func=self._build_llm_func(),
            vision_model_func=self._build_vision_func() if settings.EFFECTIVE_VLM_MODEL else None,
            embedding_func=self._build_embedding_func(),
            config=config,
            lightrag_kwargs={
                "llm_model_name": settings.LLM_MODEL,
                "embedding_func": self._build_embedding_func(),
                "working_dir": str(working_dir),
                "llm_model_max_async": 1,
            },
        )
        if not instance.check_parser_installation():
            raise RuntimeError("RAG-Anything parser installation check failed")

        self._instances[class_id] = instance
        return instance

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

            task.status = "completed" if text_processed else "failed"
            task.parser_name = "raganything"
            task.summary = parsed["summary"]
            task.extracted_text = parsed["text"]
            task.chunks = parsed["chunks"]
            task.extra_data = {
                "keywords": parsed["keywords"],
                "content_items": parsed["content_items"],
                "raganything_status": status,
            }
            material.kb_status = "indexed" if task.status == "completed" else "failed"
            if task.status == "completed" and not fully_processed:
                if text_processed and not multimodal_processed:
                    material.kb_error = "RAG-Anything text indexing succeeded, but multimodal/KG extraction only partially completed"
                else:
                    material.kb_error = "RAG-Anything indexed text successfully, but some advanced extraction steps failed"
            else:
                material.kb_error = None if task.status == "completed" else "RAG-Anything processing incomplete"

            self._sync_entities(db, class_id, material_id, parsed["keywords"])

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
        with SessionLocal() as db:
            review_matches = self._review_answer_candidates(db, class_id, question)
            search_results = self._search_class_chunks(db, class_id, question)

        image_contexts = []
        for attachment in attachments or []:
            if attachment.get("file_type") == "image":
                description = await self._describe_image_attachment(attachment, question)
                if description:
                    image_contexts.append(description)

        deduped_results = self._deduplicate_results(search_results)
        top_results = self._rerank_results(question, deduped_results, review_matches, image_contexts)[:3]

        sources = [{
            "name": item["source_name"],
            "page": item["page"],
            "type": item["source_type"],
            "score": item["score"],
            "chunk_id": item["chunk_id"],
        } for item in top_results]
        context_text = "\n\n".join(
            f"Source {idx + 1} ({source['name']} p.{source['page']}): {item['snippet']}"
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
                model=settings.LLM_MODEL,
                base_url=settings.EFFECTIVE_LLM_API_BASE,
                api_key=settings.EFFECTIVE_LLM_API_KEY,
                wire_api=settings.LLM_WIRE_API,
            )
            confidence = min(0.96, max([0.55, *(item["score"] for item in top_results[:1])]))
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
                    "score": round(overlap / max(len(query_terms), 1), 3),
                    "snippet": chunk_text[:280],
                    "raw_text": chunk_text,
                })
        results.sort(key=lambda item: item["score"], reverse=True)
        return results[:10]

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

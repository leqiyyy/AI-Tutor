import re
from collections import Counter
from datetime import datetime, timezone

from app.ai.base import RAGResult
from app.core.config import settings
from app.core.database import SessionLocal
from app.integrations.parser.simple import SimpleParserProvider
from app.integrations.rag.query_rewrite import build_query_rewrite_bundle
from app.integrations.reranker import get_reranker
from app.models.course import Class, Course, Material
from app.models.knowledge import FileParseTask, KBSpace, KnowledgeEntity, KnowledgeRelation


class SimpleRAGEngine:
    def __init__(self) -> None:
        self.parser = SimpleParserProvider()

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
                    parser_name="simple",
                    status="pending",
                )
                db.add(task)
                db.flush()

            task.status = "processing"
            material.kb_status = "processing"
            db.commit()

            parsed = self.parser.parse(file_path, mime_type, material.file_name)

            task.status = "completed"
            task.parser_name = "simple"
            task.summary = parsed["summary"]
            task.extracted_text = parsed["text"]
            task.chunks = parsed["chunks"]
            task.extra_data = {
                "keywords": parsed["keywords"],
                "content_items": parsed["content_items"],
            }
            material.kb_status = "indexed"
            material.kb_error = None

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
            kb_space.status = "ready"
            kb_space.document_count = len({row.material_id for row in completed_tasks})
            kb_space.chunk_count = sum(len(row.chunks or []) for row in completed_tasks)
            kb_space.last_built_at = datetime.now(timezone.utc)
            db.commit()
            return True

    async def query(
        self,
        question: str,
        class_id: str,
        history=None,
        attachments=None,
        role: str = "student",
    ) -> RAGResult:
        rewrite_bundle = build_query_rewrite_bundle(
            question=question,
            enabled=bool(settings.RAG_QUERY_REWRITE_ENABLED),
            mode=settings.RAG_QUERY_REWRITE_MODE,
            max_variants=settings.RAG_QUERY_REWRITE_MAX_VARIANTS,
        )
        with SessionLocal() as db:
            tasks = db.query(FileParseTask).filter(
                FileParseTask.class_id == class_id,
                FileParseTask.status == "completed",
            ).all()
            review_matches: list[dict] = []
            image_contexts: list[str] = []
            candidates_bundle = self._collect_retrieval_candidates(
                class_id=class_id,
                question=question,
                tasks=tasks,
                review_matches=review_matches,
                image_contexts=image_contexts,
                query_variants=rewrite_bundle["queries"],
            )
            reranker = get_reranker()
            reranked = []
            if candidates_bundle["candidates"]:
                reranked = await reranker.rerank(
                    query=question,
                    candidates=candidates_bundle["candidates"],
                    context={
                        "review_matches": review_matches,
                        "image_contexts": image_contexts,
                        "retrieval_strategy": candidates_bundle["strategy"],
                    },
                )

            top_k = max(1, int(settings.RAG_ANSWER_TOP_K))
            top = reranked[:top_k]

            if top:
                sources = []
                snippets = []
                for item in top:
                    sources.append({
                        "name": item.get("source_name"),
                        "page": item.get("page"),
                        "type": item.get("source_type"),
                        "score": item.get("rerank_score", item.get("retrieval_score", item.get("score"))),
                        "chunk_id": item.get("chunk_id"),
                    })
                    snippets.append((item.get("snippet") or "")[:280])

                top_score = float(top[0].get("rerank_score", 0.0))
                confidence = min(0.95, max(0.4, top_score + 0.35))
                answer = (
                    "Based on the course knowledge base, here is the most relevant material I found:\n\n"
                    + "\n\n".join(f"{idx + 1}. {snippet}" for idx, snippet in enumerate(snippets))
                )
                suggestions = self._suggestions(question)
                return RAGResult(
                    answer=answer,
                    sources=sources,
                    confidence=confidence,
                    suggestions=suggestions,
                    meta={
                        "engine": "simple",
                        "query_mode": settings.RAGANYTHING_QUERY_MODE,
                        "query_method": "simple_query",
                        "used_multimodal": False,
                        "used_fallback": False,
                        "fallback_reason": None,
                        "retrieval_strategy": candidates_bundle["strategy"],
                        "candidate_count": candidates_bundle["candidate_count"],
                        "selected_count": len(top),
                        "graph_term_count": candidates_bundle["graph_term_count"],
                        "reranker_provider": getattr(reranker, "provider_name", "unknown"),
                        "reranker_model": getattr(reranker, "model_name", "unknown"),
                        "query_rewrite_enabled": bool(rewrite_bundle["enabled"]),
                        "query_rewrite_mode": rewrite_bundle["mode"],
                        "query_variant_count": rewrite_bundle["variant_count"],
                    },
                )

            materials = db.query(Material).filter(
                Material.class_id == class_id,
                Material.is_active == True,
            ).all()
            material_titles = ", ".join(material.file_name for material in materials[:3]) or "no indexed materials yet"
            return RAGResult(
                answer=(
                    "I could not find a strong grounded answer in the current class knowledge base. "
                    f"Indexed materials available: {material_titles}."
                ),
                sources=[],
                confidence=0.35,
                suggestions=self._suggestions(question),
                meta={
                    "engine": "simple",
                    "query_mode": settings.RAGANYTHING_QUERY_MODE,
                    "query_method": "simple_query",
                    "used_multimodal": False,
                    "used_fallback": False,
                    "fallback_reason": "no_retrieval_candidates",
                    "retrieval_strategy": candidates_bundle["strategy"],
                    "candidate_count": candidates_bundle["candidate_count"],
                    "selected_count": 0,
                    "graph_term_count": candidates_bundle["graph_term_count"],
                    "reranker_provider": getattr(reranker, "provider_name", "unknown"),
                    "reranker_model": getattr(reranker, "model_name", "unknown"),
                    "query_rewrite_enabled": bool(rewrite_bundle["enabled"]),
                    "query_rewrite_mode": rewrite_bundle["mode"],
                    "query_variant_count": rewrite_bundle["variant_count"],
                },
            )

    async def add_qa_pair(self, class_id: str, question: str, answer: str) -> bool:
        with SessionLocal() as db:
            cls = db.query(Class).filter(Class.id == class_id).first()
            if not cls:
                return False
            kb_space = self._ensure_kb_space(db, course_id=cls.course_id, class_id=class_id)
            extra = kb_space.extra_data or {}
            manual_qa = extra.get("manual_qa", [])
            manual_qa.append({
                "question": question,
                "answer": answer,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            extra["manual_qa"] = manual_qa[-20:]
            kb_space.extra_data = extra
            kb_space.updated_at = datetime.now(timezone.utc)
            db.commit()
            return True

    def get_kb_status(self, course_id: str) -> dict:
        with SessionLocal() as db:
            course = db.query(Course).filter(Course.id == course_id).first()
            kb_space = db.query(KBSpace).filter(KBSpace.course_id == course_id).first()
            tasks = db.query(FileParseTask).filter(FileParseTask.course_id == course_id).all()
            status_counts = Counter(task.status for task in tasks)
            return {
                "course_id": course_id,
                "course_name": course.name if course else None,
                "kb_space_id": kb_space.id if kb_space else None,
                "status": kb_space.status if kb_space else "empty",
                "document_count": kb_space.document_count if kb_space else 0,
                "chunk_count": kb_space.chunk_count if kb_space else 0,
                "last_built_at": kb_space.last_built_at if kb_space else None,
                "task_summary": dict(status_counts),
                "latest_task_id": tasks[-1].id if tasks else None,
            }

    async def rebuild_course(self, course_id: str) -> dict:
        with SessionLocal() as db:
            classes = db.query(Class).filter(Class.course_id == course_id, Class.is_active == True).all()
            materials = db.query(Material).join(
                Class, Class.id == Material.class_id
            ).filter(
                Class.course_id == course_id,
                Material.is_active == True,
            ).all()

        processed = 0
        for material in materials:
            if material.file_path:
                await self.ingest_material(material.class_id, material.id, material.file_path, material.mime_type or "application/octet-stream")
                processed += 1

        status = self.get_kb_status(course_id)
        status["reprocessed_count"] = processed
        return status

    def get_graph(self, course_id: str) -> dict:
        with SessionLocal() as db:
            class_ids = [cls.id for cls in db.query(Class).filter(Class.course_id == course_id).all()]
            entities = db.query(KnowledgeEntity).filter(KnowledgeEntity.class_id.in_(class_ids)).all() if class_ids else []
            relations = db.query(KnowledgeRelation).filter(KnowledgeRelation.class_id.in_(class_ids)).all() if class_ids else []

            nodes = [{
                "id": entity.id,
                "label": entity.name,
                "type": entity.entity_type or "concept",
                "status": entity.status,
                "confidence": float(entity.confidence or 0.0),
                "source_material_id": entity.source_material_id,
                "source_span": entity.source_span or {},
                "provenance": entity.provenance or {},
            } for entity in entities]
            edges = [{
                "id": relation.id,
                "source": relation.source_id,
                "target": relation.target_id,
                "type": relation.relation_type or "related",
                "weight": relation.weight,
                "confidence": float(relation.confidence or 0.0),
                "source_span": relation.source_span or {},
                "provenance": relation.provenance or {},
            } for relation in relations]
            return {"nodes": nodes, "edges": edges}

    def get_parse_task(self, task_id: str) -> dict | None:
        with SessionLocal() as db:
            task = db.query(FileParseTask).filter(FileParseTask.id == task_id).first()
            if not task:
                return None
            extra = task.extra_data or {}
            ingest = extra.get("ingest", {})
            return {
                "id": task.id,
                "kind": "file_parse",
                "kb_space_id": task.kb_space_id,
                "course_id": task.course_id,
                "class_id": task.class_id,
                "material_id": task.material_id,
                "status": task.status,
                "parser_name": task.parser_name,
                "summary": task.summary,
                "error_message": task.error_message,
                "attempt_count": int(ingest.get("attempt_count", 0) or 0),
                "max_attempts": int(ingest.get("max_attempts", 0) or 0),
                "retry_available": bool(ingest.get("retry_available", task.status == "failed")),
                "last_error_category": ingest.get("last_error_category"),
                "queue_task_id": ingest.get("queue_task_id"),
                "queue_status": ingest.get("queue_status"),
                "created_at": task.created_at,
                "updated_at": task.updated_at,
            }

    def _ensure_kb_space(self, db, course_id: str, class_id: str | None = None) -> KBSpace:
        kb_space = db.query(KBSpace).filter(KBSpace.course_id == course_id, KBSpace.class_id == class_id).first()
        if not kb_space:
            kb_space = KBSpace(course_id=course_id, class_id=class_id, status="building", extra_data={})
            db.add(kb_space)
            db.flush()
        return kb_space

    def _sync_entities(
        self,
        db,
        class_id: str,
        material_id: str,
        keywords: list[str],
        chunks: list[dict] | None = None,
        content_items: list[dict] | None = None,
    ) -> None:
        normalized = self._normalize_keywords(keywords)
        if not normalized:
            return

        now_iso = datetime.now(timezone.utc).isoformat()
        source_span_seed = self._build_source_span_seed(
            material_id=material_id,
            chunks=chunks or [],
            content_items=content_items or [],
        )
        entities = []
        for index, keyword in enumerate(normalized[:6]):
            base_confidence = max(0.55, 0.9 - index * 0.06)
            entity_source_span = {
                **source_span_seed,
                "keyword": keyword,
            }
            entity = db.query(KnowledgeEntity).filter(
                KnowledgeEntity.class_id == class_id,
                KnowledgeEntity.name == keyword,
            ).first()
            if not entity:
                entity = KnowledgeEntity(
                    class_id=class_id,
                    name=keyword,
                    entity_type="keyword",
                    description=f"Extracted from material {material_id}",
                    source_material_id=material_id,
                    confidence=round(base_confidence, 4),
                    source_span=entity_source_span,
                    provenance={
                        "source_material_ids": [material_id],
                        "first_seen_at": now_iso,
                        "last_seen_at": now_iso,
                        "occurrence_count": 1,
                    },
                    status="approved",
                )
                db.add(entity)
                db.flush()
            else:
                entity.source_material_id = material_id
                entity.confidence = self._blended_confidence(entity.confidence, base_confidence)
                entity.source_span = self._merge_source_span(entity.source_span, entity_source_span)
                entity.provenance = self._merge_provenance(entity.provenance, material_id, now_iso)
                db.add(entity)
            entities.append(entity)

        for pair_index, (left, right) in enumerate(zip(entities, entities[1:])):
            relation_confidence = max(0.5, min(left.confidence or 0.6, right.confidence or 0.6) - 0.05)
            relation_source_span = {
                **source_span_seed,
                "pair_index": pair_index,
                "keywords": [left.name, right.name],
            }
            exists = db.query(KnowledgeRelation).filter(
                KnowledgeRelation.class_id == class_id,
                KnowledgeRelation.source_id == left.id,
                KnowledgeRelation.target_id == right.id,
            ).first()
            if not exists:
                db.add(KnowledgeRelation(
                    class_id=class_id,
                    source_id=left.id,
                    target_id=right.id,
                    relation_type="co_occurs_with",
                    weight=1.0,
                    confidence=round(relation_confidence, 4),
                    source_span=relation_source_span,
                    provenance={
                        "source_material_ids": [material_id],
                        "first_seen_at": now_iso,
                        "last_seen_at": now_iso,
                        "occurrence_count": 1,
                    },
                ))
            else:
                exists.weight = round(min(5.0, float(exists.weight or 1.0) + 0.2), 4)
                exists.confidence = self._blended_confidence(exists.confidence, relation_confidence)
                exists.source_span = self._merge_source_span(exists.source_span, relation_source_span)
                exists.provenance = self._merge_provenance(exists.provenance, material_id, now_iso)
                db.add(exists)

    def _normalize_keywords(self, keywords: list[str]) -> list[str]:
        seen = set()
        ordered: list[str] = []
        for keyword in keywords or []:
            token = (keyword or "").strip()
            if len(token) < 2:
                continue
            lowered = token.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            ordered.append(lowered)
        return ordered

    def _build_source_span_seed(
        self,
        *,
        material_id: str,
        chunks: list[dict],
        content_items: list[dict],
    ) -> dict:
        pages: list[int] = []
        chunk_ids: list[str] = []
        source_names: list[str] = []
        modalities: list[str] = []

        for chunk in chunks[:8]:
            if not isinstance(chunk, dict):
                continue
            page = chunk.get("page")
            if isinstance(page, int):
                pages.append(page)
            chunk_id = chunk.get("chunk_id")
            if chunk_id:
                chunk_ids.append(str(chunk_id))
            source_name = chunk.get("source_name")
            if source_name:
                source_names.append(str(source_name))

        for item in content_items[:8]:
            if not isinstance(item, dict):
                continue
            modality = item.get("modality") or item.get("type")
            if modality:
                modalities.append(str(modality))

        return {
            "material_id": material_id,
            "pages": self._compact_unique(pages),
            "chunk_ids": self._compact_unique(chunk_ids),
            "source_names": self._compact_unique(source_names),
            "modalities": self._compact_unique(modalities),
        }

    def _compact_unique(self, values: list, limit: int = 8) -> list:
        seen = []
        for value in values:
            if value in seen:
                continue
            seen.append(value)
            if len(seen) >= limit:
                break
        return seen

    def _merge_source_span(self, old_span, new_span: dict) -> dict:
        old_span = old_span if isinstance(old_span, dict) else {}
        result = {
            "material_id": new_span.get("material_id") or old_span.get("material_id"),
            "keyword": new_span.get("keyword") or old_span.get("keyword"),
            "pair_index": new_span.get("pair_index") if new_span.get("pair_index") is not None else old_span.get("pair_index"),
            "keywords": self._compact_unique([*(old_span.get("keywords") or []), *(new_span.get("keywords") or [])]),
            "pages": self._compact_unique([*(old_span.get("pages") or []), *(new_span.get("pages") or [])]),
            "chunk_ids": self._compact_unique([*(old_span.get("chunk_ids") or []), *(new_span.get("chunk_ids") or [])]),
            "source_names": self._compact_unique([*(old_span.get("source_names") or []), *(new_span.get("source_names") or [])]),
            "modalities": self._compact_unique([*(old_span.get("modalities") or []), *(new_span.get("modalities") or [])]),
        }
        return result

    def _merge_provenance(self, old_provenance, material_id: str, now_iso: str) -> dict:
        old = old_provenance if isinstance(old_provenance, dict) else {}
        source_material_ids = self._compact_unique([*(old.get("source_material_ids") or []), material_id], limit=20)
        return {
            "source_material_ids": source_material_ids,
            "first_seen_at": old.get("first_seen_at") or now_iso,
            "last_seen_at": now_iso,
            "occurrence_count": int(old.get("occurrence_count", 0) or 0) + 1,
        }

    def _blended_confidence(self, current: float | None, incoming: float) -> float:
        baseline = float(current) if current is not None else 0.55
        blended = baseline * 0.8 + float(incoming) * 0.2
        return round(min(0.99, max(0.4, blended)), 4)

    def _terms(self, text: str) -> set[str]:
        latin_tokens = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text.lower())
        cjk_tokens = re.findall(r"[\u4e00-\u9fff]{2,8}", text)
        return {token for token in [*latin_tokens, *cjk_tokens] if token}

    def _collect_retrieval_candidates(
        self,
        *,
        class_id: str,
        question: str,
        tasks: list[FileParseTask],
        review_matches: list[dict],
        image_contexts: list[str],
        query_variants: list[str] | None = None,
    ) -> dict:
        _ = (review_matches, image_contexts)
        normalized_queries = self._normalize_query_variants(query_variants, fallback=question)
        variant_term_sets = []
        for query_text in normalized_queries:
            term_set = self._terms(query_text)
            if term_set:
                variant_term_sets.append(term_set)
        if not variant_term_sets:
            fallback_terms = self._terms(question)
            if fallback_terms:
                variant_term_sets.append(fallback_terms)

        query_terms_for_graph = set().union(*variant_term_sets) if variant_term_sets else self._terms(question)
        strategy = self._normalized_retrieval_strategy()
        graph_terms = self._graph_terms_for_question(class_id, query_terms_for_graph) if strategy in {"hybrid", "graph"} else set()

        candidates = []
        for task in tasks:
            for chunk in task.chunks or []:
                chunk_text = chunk.get("text", "")
                chunk_terms = self._terms(chunk_text)
                overlaps = [len(term_set & chunk_terms) for term_set in variant_term_sets] if variant_term_sets else [0]
                lexical_overlap = max(overlaps) if overlaps else 0
                if lexical_overlap <= 0:
                    continue
                denominator = max((len(term_set) for term_set in variant_term_sets), default=1)
                lexical_score = lexical_overlap / max(denominator, 1)
                matched_variants = sum(1 for overlap in overlaps if overlap > 0)
                query_coverage = (
                    matched_variants / len(variant_term_sets)
                    if variant_term_sets
                    else 0.0
                )
                coverage_boost = 0.0
                if len(variant_term_sets) > 1:
                    coverage_boost = min(0.16, max(0, matched_variants - 1) * 0.04)
                graph_overlap = len(graph_terms & chunk_terms)
                graph_boost = min(0.5, graph_overlap * 0.07)
                if strategy == "lexical":
                    retrieval_score = lexical_score + coverage_boost
                elif strategy == "graph":
                    retrieval_score = graph_boost + lexical_score * 0.1 + coverage_boost
                else:
                    retrieval_score = lexical_score + graph_boost + coverage_boost
                candidates.append({
                    "source_name": chunk.get("source_name"),
                    "source_type": chunk.get("source_type"),
                    "page": chunk.get("page"),
                    "chunk_id": chunk.get("chunk_id"),
                    "score": round(lexical_score, 4),
                    "lexical_score": round(lexical_score, 4),
                    "graph_boost": round(graph_boost, 4),
                    "query_coverage": round(query_coverage, 4),
                    "query_coverage_boost": round(coverage_boost, 4),
                    "matched_query_count": matched_variants,
                    "retrieval_score": round(retrieval_score, 4),
                    "retrieval_strategy": strategy,
                    "snippet": chunk_text[:280],
                    "raw_text": chunk_text,
                })

        candidates = self._deduplicate_candidates(candidates)
        candidates.sort(key=lambda item: item.get("retrieval_score", 0.0), reverse=True)
        candidate_limit = max(5, int(settings.RAG_RETRIEVAL_CANDIDATE_K))
        return {
            "strategy": strategy,
            "candidate_count": len(candidates),
            "graph_term_count": len(graph_terms),
            "query_variant_count": len(normalized_queries),
            "candidates": candidates[:candidate_limit],
        }

    def _normalized_retrieval_strategy(self) -> str:
        strategy = (settings.RAG_RETRIEVAL_STRATEGY or "hybrid").lower().strip()
        return strategy if strategy in {"lexical", "hybrid", "graph"} else "hybrid"

    def _graph_terms_for_question(self, class_id: str, question_terms: set[str]) -> set[str]:
        if not question_terms:
            return set()
        with SessionLocal() as db:
            entities = db.query(KnowledgeEntity).filter(KnowledgeEntity.class_id == class_id).all()
        terms = set()
        for entity in entities:
            entity_terms = self._terms((entity.name or "").lower())
            if entity_terms & question_terms:
                terms.update(entity_terms)
        return terms

    def _deduplicate_candidates(self, candidates: list[dict]) -> list[dict]:
        deduped = []
        seen = set()
        for item in candidates:
            key = item.get("chunk_id") or f"{item.get('source_name')}|{item.get('page')}|{item.get('snippet')}"
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

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

    def _suggestions(self, question: str) -> list[str]:
        return [
            "Can you explain this with an example?",
            "Which source should I read next?",
            f"What is the key concept behind: {question[:30]}?",
        ]

import math
import re
from collections import Counter
from datetime import datetime, timezone

from app.ai.base import RAGResult
from app.core.database import SessionLocal
from app.integrations.parser.simple import SimpleParserProvider
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

            self._sync_entities(db, class_id, material_id, parsed["keywords"])

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
        with SessionLocal() as db:
            tasks = db.query(FileParseTask).filter(
                FileParseTask.class_id == class_id,
                FileParseTask.status == "completed",
            ).all()

            question_terms = self._terms(question)
            ranked = []
            for task in tasks:
                for chunk in task.chunks or []:
                    chunk_terms = self._terms(chunk.get("text", ""))
                    overlap = len(question_terms & chunk_terms)
                    if overlap == 0:
                        continue
                    score = overlap / max(len(question_terms), 1)
                    ranked.append((score, task, chunk))

            ranked.sort(key=lambda item: item[0], reverse=True)
            top = ranked[:3]

            if top:
                sources = []
                snippets = []
                for score, _task, chunk in top:
                    sources.append({
                        "name": chunk.get("source_name"),
                        "page": chunk.get("page"),
                        "type": chunk.get("source_type"),
                        "score": round(score, 3),
                        "chunk_id": chunk.get("chunk_id"),
                    })
                    snippets.append(chunk.get("text", "")[:280])

                confidence = min(0.95, max(0.45, top[0][0] + 0.45))
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
            } for entity in entities]
            edges = [{
                "id": relation.id,
                "source": relation.source_id,
                "target": relation.target_id,
                "type": relation.relation_type or "related",
                "weight": relation.weight,
            } for relation in relations]
            return {"nodes": nodes, "edges": edges}

    def get_parse_task(self, task_id: str) -> dict | None:
        with SessionLocal() as db:
            task = db.query(FileParseTask).filter(FileParseTask.id == task_id).first()
            if not task:
                return None
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

    def _sync_entities(self, db, class_id: str, material_id: str, keywords: list[str]) -> None:
        normalized = [keyword for keyword in keywords if keyword]
        entities = []
        for keyword in normalized[:6]:
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
                    status="approved",
                )
                db.add(entity)
                db.flush()
            entities.append(entity)

        for left, right in zip(entities, entities[1:]):
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
                ))

    def _terms(self, text: str) -> set[str]:
        latin_tokens = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text.lower())
        cjk_tokens = re.findall(r"[\u4e00-\u9fff]{2,8}", text)
        return {token for token in [*latin_tokens, *cjk_tokens] if token}

    def _suggestions(self, question: str) -> list[str]:
        return [
            "Can you explain this with an example?",
            "Which source should I read next?",
            f"What is the key concept behind: {question[:30]}?",
        ]

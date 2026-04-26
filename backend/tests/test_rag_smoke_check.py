from types import SimpleNamespace

from app.ai.base import RAGResult
from app.integrations.rag.smoke_check import (
    arun_raganything_smoke_check,
    write_raganything_smoke_report,
)


def test_smoke_check_blocks_when_runtime_not_ready(monkeypatch, tmp_path):
    sample = tmp_path / "smoke.txt"
    sample.write_text("strict rag smoke sample", encoding="utf-8")

    monkeypatch.setattr(
        "app.integrations.rag.smoke_check.build_raganything_runtime_report",
        lambda: {"status": "blocked", "blockers": [{"key": "raganything_package"}]},
    )

    report = __import__("asyncio").run(
        arun_raganything_smoke_check(file_path=str(sample))
    )

    assert report["status"] == "blocked"
    assert report["steps"][0]["name"] == "runtime_check"
    assert report["steps"][0]["status"] == "fail"


def test_smoke_check_verifies_teacher_review_query(monkeypatch, tmp_path):
    sample = tmp_path / "smoke.txt"
    sample.write_text("strict rag smoke sample", encoding="utf-8")

    monkeypatch.setattr(
        "app.integrations.rag.smoke_check.build_raganything_runtime_report",
        lambda: {"status": "ready", "blockers": []},
    )
    monkeypatch.setattr(
        "app.integrations.rag.smoke_check._resolve_target_class",
        lambda class_id: SimpleNamespace(id="class-1", course_id="course-1", teacher_id="teacher-1"),
    )
    monkeypatch.setattr(
        "app.integrations.rag.smoke_check._create_smoke_material",
        lambda **kwargs: SimpleNamespace(id="material-1", file_name="smoke.txt"),
    )
    monkeypatch.setattr(
        "app.integrations.rag.smoke_check._latest_parse_task_for_material",
        lambda material_id: SimpleNamespace(id="task-1"),
    )

    class FakeEngine:
        def get_parse_task(self, task_id):
            return {"id": task_id, "kind": "file_parse", "status": "completed"}

        async def ingest_material(self, class_id, material_id, file_path, mime_type):
            return True

        async def add_qa_pair(self, class_id, question, answer):
            self.synced_answer = answer
            return True

        async def query(self, question, class_id, history=None, attachments=None, role="teacher"):
            if question.startswith("Please summarize"):
                return RAGResult(
                    answer="Main chain summary answer",
                    sources=[{"name": "smoke.txt", "chunk_id": "chunk-1", "snippet": "strict rag smoke sample"}],
                    confidence=0.88,
                    meta={"engine": "raganything"},
                )
            return RAGResult(
                answer="I found the synced token in the teacher-reviewed evidence.",
                sources=[{
                    "name": "teacher_review_class-1.txt",
                    "chunk_id": "teacher-review-chunk",
                    "snippet": self.synced_answer,
                    "score": 0.92,
                }],
                confidence=0.91,
                meta={"engine": "raganything"},
            )

    fake_engine = FakeEngine()
    monkeypatch.setattr(
        "app.integrations.rag.smoke_check.get_rag_engine",
        lambda requested_engine=None: fake_engine,
    )

    report = __import__("asyncio").run(
        arun_raganything_smoke_check(file_path=str(sample))
    )

    assert report["status"] == "passed"
    step_names = [step["name"] for step in report["steps"]]
    assert step_names == [
        "runtime_check",
        "register_material",
        "ingest_material",
        "query",
        "teacher_review_sync",
        "teacher_review_query",
    ]
    review_sync_step = next(step for step in report["steps"] if step["name"] == "teacher_review_sync")
    review_query_step = next(step for step in report["steps"] if step["name"] == "teacher_review_query")
    token = review_sync_step["review_token"]
    assert token.startswith("SMOKE_SYNC_")
    assert review_query_step["verification"]["expected_token"] == token
    assert review_query_step["verification"]["verified"] is True
    assert review_query_step["verification"]["matched_source_count"] >= 1


def test_smoke_check_can_create_isolated_class(monkeypatch, tmp_path):
    sample = tmp_path / "smoke.txt"
    sample.write_text("strict rag smoke sample", encoding="utf-8")
    base_class = SimpleNamespace(id="base-class", course_id="course-1", teacher_id="teacher-1")
    isolated_class = SimpleNamespace(id="isolated-class", course_id="course-1", teacher_id="teacher-1")
    seen = {}

    monkeypatch.setattr(
        "app.integrations.rag.smoke_check.build_raganything_runtime_report",
        lambda: {"status": "ready", "blockers": []},
    )
    monkeypatch.setattr(
        "app.integrations.rag.smoke_check._resolve_target_class",
        lambda class_id: base_class,
    )

    def fake_create_isolated(cls):
        seen["base_id"] = cls.id
        return isolated_class

    monkeypatch.setattr(
        "app.integrations.rag.smoke_check._create_isolated_smoke_class",
        fake_create_isolated,
    )
    monkeypatch.setattr(
        "app.integrations.rag.smoke_check._create_smoke_material",
        lambda **kwargs: SimpleNamespace(id="material-1", file_name="smoke.txt"),
    )
    monkeypatch.setattr(
        "app.integrations.rag.smoke_check._latest_parse_task_for_material",
        lambda material_id: SimpleNamespace(id="task-1"),
    )

    class FakeEngine:
        def get_parse_task(self, task_id):
            return {"id": task_id, "kind": "file_parse", "status": "completed"}

        async def ingest_material(self, class_id, material_id, file_path, mime_type):
            seen["ingest_class_id"] = class_id
            return True

        async def query(self, question, class_id, history=None, attachments=None, role="teacher"):
            return RAGResult(answer="ok", sources=[], confidence=0.7, meta={"engine": "raganything"})

    monkeypatch.setattr(
        "app.integrations.rag.smoke_check.get_rag_engine",
        lambda requested_engine=None: FakeEngine(),
    )

    report = __import__("asyncio").run(
        arun_raganything_smoke_check(
            file_path=str(sample),
            create_isolated_class=True,
            include_review_sync=False,
        )
    )

    assert report["status"] == "passed"
    assert seen["base_id"] == "base-class"
    assert seen["ingest_class_id"] == "isolated-class"
    assert report["artifacts"]["base_class_id"] == "base-class"
    assert report["artifacts"]["isolated_class_created"] is True


def test_smoke_check_fails_when_review_writeback_cannot_be_verified(monkeypatch, tmp_path):
    sample = tmp_path / "smoke.txt"
    sample.write_text("strict rag smoke sample", encoding="utf-8")

    monkeypatch.setattr(
        "app.integrations.rag.smoke_check.build_raganything_runtime_report",
        lambda: {"status": "ready", "blockers": []},
    )
    monkeypatch.setattr(
        "app.integrations.rag.smoke_check._resolve_target_class",
        lambda class_id: SimpleNamespace(id="class-1", course_id="course-1", teacher_id="teacher-1"),
    )
    monkeypatch.setattr(
        "app.integrations.rag.smoke_check._create_smoke_material",
        lambda **kwargs: SimpleNamespace(id="material-1", file_name="smoke.txt"),
    )
    monkeypatch.setattr(
        "app.integrations.rag.smoke_check._latest_parse_task_for_material",
        lambda material_id: SimpleNamespace(id="task-1"),
    )

    class FakeEngine:
        def get_parse_task(self, task_id):
            return {"id": task_id, "kind": "file_parse", "status": "completed"}

        async def ingest_material(self, class_id, material_id, file_path, mime_type):
            return True

        async def add_qa_pair(self, class_id, question, answer):
            return True

        async def query(self, question, class_id, history=None, attachments=None, role="teacher"):
            return RAGResult(
                answer="No token here.",
                sources=[{"name": "smoke.txt", "chunk_id": "chunk-1", "snippet": "regular material evidence"}],
                confidence=0.5,
                meta={"engine": "raganything"},
            )

    monkeypatch.setattr(
        "app.integrations.rag.smoke_check.get_rag_engine",
        lambda requested_engine=None: FakeEngine(),
    )

    report = __import__("asyncio").run(
        arun_raganything_smoke_check(file_path=str(sample))
    )

    assert report["status"] == "failed"
    review_query_step = next(step for step in report["steps"] if step["name"] == "teacher_review_query")
    assert review_query_step["status"] == "fail"
    assert review_query_step["verification"]["verified"] is False


def test_smoke_check_fails_when_main_chain_query_is_unavailable(monkeypatch, tmp_path):
    sample = tmp_path / "smoke.txt"
    sample.write_text("strict rag smoke sample", encoding="utf-8")

    monkeypatch.setattr(
        "app.integrations.rag.smoke_check.build_raganything_runtime_report",
        lambda: {"status": "ready", "blockers": []},
    )
    monkeypatch.setattr(
        "app.integrations.rag.smoke_check._resolve_target_class",
        lambda class_id: SimpleNamespace(id="class-1", course_id="course-1", teacher_id="teacher-1"),
    )
    monkeypatch.setattr(
        "app.integrations.rag.smoke_check._create_smoke_material",
        lambda **kwargs: SimpleNamespace(id="material-1", file_name="smoke.txt"),
    )
    monkeypatch.setattr(
        "app.integrations.rag.smoke_check._latest_parse_task_for_material",
        lambda material_id: SimpleNamespace(id="task-1"),
    )

    class FakeEngine:
        def get_parse_task(self, task_id):
            return {"id": task_id, "kind": "file_parse", "status": "completed"}

        async def ingest_material(self, class_id, material_id, file_path, mime_type):
            return True

        async def query(self, question, class_id, history=None, attachments=None, role="teacher"):
            return RAGResult(
                answer="RAG-Anything main-chain retrieval is currently unavailable.",
                sources=[],
                confidence=0.0,
                meta={"fallback_disabled": True},
            )

    monkeypatch.setattr(
        "app.integrations.rag.smoke_check.get_rag_engine",
        lambda requested_engine=None: FakeEngine(),
    )

    report = __import__("asyncio").run(
        arun_raganything_smoke_check(file_path=str(sample), include_review_sync=False)
    )

    assert report["status"] == "failed"
    query_step = next(step for step in report["steps"] if step["name"] == "query")
    assert query_step["status"] == "fail"


def test_smoke_report_writer_persists_json_and_markdown(tmp_path):
    report = {
        "status": "passed",
        "started_at": "2026-04-23T03:00:00+00:00",
        "finished_at": "2026-04-23T03:01:00+00:00",
        "engine": "raganything",
        "strict_mode": True,
        "runtime": {"status": "ready", "blocker_count": 0},
        "input": {
            "file_path": "E:/tmp/sample.txt",
            "file_name": "sample.txt",
            "mime_type": "text/plain",
            "file_type": "txt",
            "requested_class_id": "class-1",
        },
        "artifacts": {
            "course_id": "course-1",
            "class_id": "class-1",
            "material_id": "material-1",
            "parse_task_id": "task-1",
        },
        "steps": [
            {"name": "runtime_check", "status": "pass", "message": "ready"},
            {"name": "teacher_review_query", "status": "pass", "message": "verified"},
        ],
    }

    paths = write_raganything_smoke_report(report, output_dir=tmp_path)

    json_path = tmp_path / "raganything_smoke_20260423_030000Z.json"
    md_path = tmp_path / "raganything_smoke_20260423_030000Z.md"
    assert paths["json_path"] == str(json_path)
    assert paths["md_path"] == str(md_path)
    assert json_path.exists()
    assert md_path.exists()
    assert '"status": "passed"' in json_path.read_text(encoding="utf-8")
    markdown = md_path.read_text(encoding="utf-8")
    assert "# RAG-Anything Smoke Report" in markdown
    assert "`teacher_review_query`: `pass`" in markdown

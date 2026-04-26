from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.database import SessionLocal  # noqa: E402
from app.integrations.rag.raganything_adapter import RAGAnythingAdapter  # noqa: E402
from app.models.course import Course  # noqa: E402


async def _run(course_id: str | None, apply_changes: bool) -> int:
    adapter = RAGAnythingAdapter()
    with SessionLocal() as db:
        query = db.query(Course).order_by(Course.created_at.asc())
        if course_id:
            query = query.filter(Course.id == course_id)
        courses = query.all()

    selected = []
    for course in courses:
        status = adapter.get_kb_status(course.id)
        storage = status.get("storage") or {}
        if storage.get("reindex_required"):
            selected.append((course, storage))

    if not selected:
        print("No courses currently require storage-driven reindex.")
        return 0

    if not apply_changes:
        for course, storage in selected:
            print(f"{course.name} ({course.id}) -> {storage.get('reindex_required_count')} materials need reindex")
        print("Dry run only. Re-run with `--apply` to execute selective rebuild.")
        return 0

    for course, storage in selected:
        print(f"Rebuilding storage targets for {course.name} ({course.id}) ...")
        result = await adapter.rebuild_course(course.id, storage_migration_only=True)
        print(
            f"  requested={result.get('requested_reindex_count')} "
            f"processed={result.get('reprocessed_count')} "
            f"target={result.get('storage_migration_target_backend')}"
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Selective reindex for materials that mismatch the current external RAG storage backend.")
    parser.add_argument("--course-id", help="Optional course id to limit the rebuild target.")
    parser.add_argument("--apply", action="store_true", help="Execute selective rebuild instead of dry-run listing.")
    args = parser.parse_args()
    return asyncio.run(_run(args.course_id, args.apply))


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.database import SessionLocal  # noqa: E402
from app.integrations.rag.raganything_adapter import RAGAnythingAdapter  # noqa: E402
from app.models.course import Course  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="List courses/materials that should be reindexed after external RAG storage changes.")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args()

    adapter = RAGAnythingAdapter()
    items: list[dict] = []
    with SessionLocal() as db:
        courses = db.query(Course).order_by(Course.created_at.asc()).all()
        for course in courses:
            status = adapter.get_kb_status(course.id)
            storage = status.get("storage") or {}
            if not storage.get("reindex_required"):
                continue
            items.append({
                "course_id": course.id,
                "course_name": course.name,
                "reindex_target_backend": storage.get("reindex_target_backend"),
                "reindex_required_count": storage.get("reindex_required_count", 0),
                "current_effective_backend": storage.get("current_effective_backend"),
                "indexed_backend_distribution": storage.get("indexed_backend_distribution") or {},
                "reindex_candidates": storage.get("reindex_candidates") or [],
            })

    if args.format == "json":
        print(json.dumps(items, ensure_ascii=False, indent=2, default=str))
        return 0

    if not items:
        print("No courses currently require storage-driven reindex.")
        return 0

    for item in items:
        print(f"Course: {item['course_name']} ({item['course_id']})")
        print(f"  target backend: {item['reindex_target_backend']}")
        print(f"  current effective backend: {item['current_effective_backend']}")
        print(f"  reindex required count: {item['reindex_required_count']}")
        print(f"  indexed backend distribution: {item['indexed_backend_distribution']}")
        for candidate in item["reindex_candidates"][:5]:
            print(
                "  - "
                f"{candidate.get('title') or candidate.get('file_name') or candidate.get('material_id')} "
                f"[reason={candidate.get('reason')}, indexed_backend={candidate.get('indexed_backend')}]"
            )
        if len(item["reindex_candidates"]) > 5:
            print(f"  ... and {len(item['reindex_candidates']) - 5} more")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

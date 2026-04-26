from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.integrations.rag.smoke_check import (  # noqa: E402
    DEFAULT_SMOKE_REPORT_DIR,
    DEFAULT_REVIEW_ANSWER,
    DEFAULT_REVIEW_QUESTION,
    DEFAULT_REVIEW_VERIFICATION_QUESTION,
    DEFAULT_SMOKE_QUESTION,
    run_raganything_smoke_check,
    write_raganything_smoke_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a strict RAG-Anything smoke check against one local material.")
    parser.add_argument("--file", required=True, type=str, help="Local file path to ingest through the RAG-Anything main chain.")
    parser.add_argument("--class-id", default=None, type=str, help="Optional class id. Defaults to the first active class in the database.")
    parser.add_argument(
        "--isolated-class",
        action="store_true",
        help=(
            "Create a temporary active class cloned from --class-id or the first active class, "
            "so the smoke run uses a clean RAG-Anything working directory."
        ),
    )
    parser.add_argument("--question", default=DEFAULT_SMOKE_QUESTION, type=str, help="Question used for the smoke-test query stage.")
    parser.add_argument("--review-question", default=DEFAULT_REVIEW_QUESTION, type=str, help="Teacher-review question written back into the KB.")
    parser.add_argument("--review-answer", default=DEFAULT_REVIEW_ANSWER, type=str, help="Teacher-review answer written back into the KB.")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_SMOKE_REPORT_DIR),
        type=str,
        help="Directory used to persist the smoke report as JSON and Markdown.",
    )
    parser.add_argument(
        "--skip-review-query",
        action="store_true",
        help=(
            "Skip the follow-up query that verifies the teacher-reviewed QA write-back "
            f"using: {DEFAULT_REVIEW_VERIFICATION_QUESTION}"
        ),
    )
    parser.add_argument(
        "--skip-review-sync",
        action="store_true",
        help="Skip the teacher-reviewed QA write-back stage.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run_raganything_smoke_check(
        file_path=args.file,
        class_id=args.class_id,
        create_isolated_class=bool(args.isolated_class),
        question=args.question,
        review_question=args.review_question,
        review_answer=args.review_answer,
        include_review_sync=not bool(args.skip_review_sync),
        verify_review_query=not bool(args.skip_review_query),
    )
    paths = write_raganything_smoke_report(report, output_dir=args.output_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"JSON report: {paths['json_path']}")
    print(f"Markdown report: {paths['md_path']}")
    return 0 if report.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

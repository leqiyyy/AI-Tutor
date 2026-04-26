from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.integrations.rag.storage_config import build_external_storage_bootstrap_plan  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare env/bootstrap guidance for external RAG storage.")
    parser.add_argument(
        "--backend",
        default="qdrant-neo4j",
        choices=["qdrant", "neo4j", "qdrant-neo4j"],
        help="Target external LightRAG storage topology.",
    )
    parser.add_argument(
        "--format",
        default="text",
        choices=["text", "json"],
        help="Output format.",
    )
    args = parser.parse_args()

    plan = build_external_storage_bootstrap_plan(args.backend)
    if args.format == "json":
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0

    print(f"Target backend: {plan['target_backend']}")
    print(f"Docker compose file: {plan['docker_compose_file']}")
    print()
    if plan["install_packages"]:
        print("Missing optional packages:")
        for item in plan["install_packages"]:
            print(f"- {item}")
        print()
    print("Suggested .env patch:")
    print(plan["env_block"])
    print()
    print("Next steps:")
    for item in plan["next_steps"]:
        print(f"- {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

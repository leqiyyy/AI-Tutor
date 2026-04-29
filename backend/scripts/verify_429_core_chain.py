"""Verify the 2026-04-29 core AI tutor chain through public API routes."""

from __future__ import annotations

import base64
import io
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.seed import seed_data  # noqa: E402
from app.main import app  # noqa: E402


REPORT_DIR = ROOT / "runtime_tmp" / "429_core_chain_reports"
ONE_PIXEL_PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7+4xkAAAAASUVORK5CYII="
)


class ChainVerifier:
    def __init__(self) -> None:
        self.marker = uuid.uuid4().hex[:8]
        self.report: dict[str, Any] = {
            "marker": self.marker,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "checks": [],
            "artifacts": {},
        }

    def check(self, name: str, passed: bool, **details: Any) -> None:
        self.report["checks"].append({
            "name": name,
            "passed": bool(passed),
            **details,
        })
        if not passed:
            raise AssertionError(f"{name} failed: {details}")

    def login(self, client: TestClient, account: str, password: str, role: str) -> dict[str, str]:
        response = client.post(
            "/api/v1/auth/login",
            json={"account": account, "password": password, "role": role},
        )
        self.check(f"login_{role}", response.status_code == 200, status_code=response.status_code)
        token = response.json()["data"]["access_token"]
        return {"Authorization": f"Bearer {token}"}

    def upload_fixture(
        self,
        client: TestClient,
        *,
        teacher_headers: dict[str, str],
        course_id: str,
        class_id: str,
        file_name: str,
        file_bytes: bytes,
        mime_type: str,
        title: str,
        expected_modalities: set[str],
    ) -> dict[str, Any]:
        upload = client.post(
            f"/api/v1/courses/{course_id}/files/upload",
            headers=teacher_headers,
            files={"file": (file_name, io.BytesIO(file_bytes), mime_type)},
            data={"title": title, "class_id": class_id},
        )
        upload_payload = upload.json() if upload.headers.get("content-type", "").startswith("application/json") else {}
        self.check(
            f"upload_{title}",
            upload.status_code == 200 and upload_payload.get("data", {}).get("action") in {
                "indexed",
                "reindexed",
                "already_indexed",
                "reuse_existing",
            },
            status_code=upload.status_code,
            payload=upload_payload,
        )
        material_id = upload_payload["data"]["id"]
        analysis = client.get(
            f"/api/v1/courses/{course_id}/files/{material_id}/analysis",
            headers=teacher_headers,
        )
        analysis_payload = analysis.json() if analysis.headers.get("content-type", "").startswith("application/json") else {}
        analysis_data = analysis_payload.get("data") or {}
        modalities = {
            str(item.get("modality") or "").lower()
            for item in analysis_data.get("content_items") or []
        }
        self.check(
            f"analysis_{title}",
            analysis.status_code == 200
            and analysis_data.get("content_items_schema") == "v1"
            and expected_modalities.issubset(modalities),
            status_code=analysis.status_code,
            material_id=material_id,
            expected_modalities=sorted(expected_modalities),
            actual_modalities=sorted(modalities),
            chunk_count=analysis_data.get("chunk_count"),
            raganything_quality=analysis_data.get("raganything_quality"),
        )
        return {
            "material_id": material_id,
            "upload": upload_payload["data"],
            "modalities": sorted(modalities),
            "chunk_count": analysis_data.get("chunk_count"),
        }

    def run(self) -> dict[str, Any]:
        seed_data()
        with TestClient(app) as client:
            teacher_headers = self.login(client, "teacher@aitutor.local", "Teacher123!", "teacher")
            student_headers = self.login(client, "student@aitutor.local", "Student123!", "student")

            courses = client.get("/api/v1/courses", headers=teacher_headers)
            course_data = courses.json()["data"]
            self.check("teacher_course_available", courses.status_code == 200 and bool(course_data))
            course_id = course_data[0]["id"]

            create_class = client.post(
                "/api/v1/classes",
                headers=teacher_headers,
                json={
                    "course_id": course_id,
                    "name": f"429 Core Chain {self.marker}",
                    "semester": "2026 Spring",
                    "description": "End-to-end chain verification sandbox.",
                },
            )
            class_payload = create_class.json()
            self.check("teacher_create_class", create_class.status_code == 200, payload=class_payload)
            class_id = class_payload["data"]["id"]
            invite_code = class_payload["data"]["invite_code"]

            join = client.post(
                "/api/v1/classes/join",
                headers=student_headers,
                json={"invite_code": invite_code},
            )
            self.check("student_join_class", join.status_code == 200, payload=join.json())
            self.report["artifacts"].update({"course_id": course_id, "class_id": class_id})

            md = f"""# 429 Core Fixture {self.marker}

Adaptive congestion control marker {self.marker} lowers packet loss during burst traffic.

| metric | value | unit |
| --- | --- | --- |
| throughput_{self.marker} | 125 | Mbps |
| rtt_{self.marker} | 28 | ms |
| loss_{self.marker} | 0.8 | % |

Formula anchor: $v_{self.marker} = d / t$.

The queue tuning observation {self.marker} links throughput, RTT, loss, and fairness.
""".encode("utf-8")
            md_result = self.upload_fixture(
                client,
                teacher_headers=teacher_headers,
                course_id=course_id,
                class_id=class_id,
                file_name=f"429_core_table_formula_{self.marker}.md",
                file_bytes=md,
                mime_type="text/markdown",
                title=f"429 Markdown {self.marker}",
                expected_modalities={"text", "table", "formula"},
            )

            image_result = self.upload_fixture(
                client,
                teacher_headers=teacher_headers,
                course_id=course_id,
                class_id=class_id,
                file_name=f"429_core_diagram_{self.marker}.png",
                file_bytes=base64.b64decode(ONE_PIXEL_PNG),
                mime_type="image/png",
                title=f"429 Image {self.marker}",
                expected_modalities={"text", "image"},
            )
            material_ids = [md_result["material_id"], image_result["material_id"]]
            self.report["artifacts"]["materials"] = [md_result, image_result]

            kb_status = client.get(f"/api/v1/courses/{course_id}/kb/status", headers=teacher_headers)
            self.check("kb_status_available", kb_status.status_code == 200, data=kb_status.json().get("data"))

            search = client.get(
                f"/api/v1/courses/{course_id}/search",
                headers=student_headers,
                params={"q": f"throughput_{self.marker} loss_{self.marker}"},
            )
            search_data = search.json().get("data") or []
            self.check(
                "student_search_retrieves_uploaded_chunks",
                search.status_code == 200 and bool(search_data),
                result_count=len(search_data),
                top_result=search_data[0] if search_data else None,
            )

            graph = client.get(
                f"/api/v1/courses/{course_id}/graph",
                headers=teacher_headers,
                params={"class_id": class_id, "limit": 500},
            )
            graph_data = graph.json().get("data") or {}
            nodes = graph_data.get("nodes") or []
            edges = graph_data.get("edges") or []
            relevant_nodes = [
                node for node in nodes
                if set((node.get("provenance") or {}).get("source_material_ids") or []).intersection(material_ids)
            ]
            nodes_with_description = [node for node in relevant_nodes if node.get("description")]
            edges_with_summary = [edge for edge in edges if edge.get("summary") or edge.get("description")]
            self.check(
                "graph_constructed_with_provenance_and_summaries",
                graph.status_code == 200
                and bool(relevant_nodes)
                and len(nodes_with_description) == len(relevant_nodes)
                and len(edges_with_summary) == len(edges),
                node_count=len(nodes),
                edge_count=len(edges),
                relevant_node_count=len(relevant_nodes),
                nodes_with_description=len(nodes_with_description),
                edges_with_summary=len(edges_with_summary),
                summary=graph_data.get("summary"),
            )

            student_query = client.post(
                "/api/v1/chat/query",
                headers=student_headers,
                json={
                    "class_id": class_id,
                    "message": f"What does marker {self.marker} say about throughput and packet loss?",
                    "attachments": [],
                },
            )
            student_answer = student_query.json().get("data") or {}
            self.check(
                "student_ai_chat_with_citations",
                student_query.status_code == 200
                and bool(student_answer.get("content"))
                and bool(student_answer.get("sources")),
                confidence=student_answer.get("confidence"),
                source_count=len(student_answer.get("sources") or []),
                quality=student_answer.get("quality"),
                review_context=student_answer.get("review_context"),
            )

            teacher_query = client.post(
                "/api/v1/chat/query",
                headers=teacher_headers,
                json={
                    "class_id": class_id,
                    "message": f"Summarize the uploaded marker {self.marker} material for teaching.",
                    "attachments": [],
                },
            )
            teacher_answer = teacher_query.json().get("data") or {}
            self.check(
                "teacher_ai_chat_with_citations",
                teacher_query.status_code == 200
                and bool(teacher_answer.get("content"))
                and bool(teacher_answer.get("sources")),
                confidence=teacher_answer.get("confidence"),
                source_count=len(teacher_answer.get("sources") or []),
            )

            feedback = client.post(
                f"/api/v1/chat/messages/{student_answer['message_id']}/feedback",
                headers=student_headers,
                json={"feedback": "dislike", "reason": f"Need teacher review for marker {self.marker}."},
            )
            self.check("student_feedback_created_review_signal", feedback.status_code == 200, data=feedback.json().get("data"))

            pending = client.get(
                "/api/v1/reviews/pending",
                headers=teacher_headers,
                params={"class_id": class_id},
            )
            pending_items = pending.json().get("data") or []
            review_item = next(
                (
                    item for item in pending_items
                    if item.get("message_id") == student_answer["message_id"]
                ),
                pending_items[0] if pending_items else None,
            )
            self.check(
                "teacher_pending_review_visible",
                pending.status_code == 200 and review_item is not None,
                pending_count=len(pending_items),
                review_item=review_item,
            )

            teacher_answer_text = (
                f"Teacher-reviewed marker {self.marker}: throughput remains 125 Mbps, RTT is 28 ms, "
                "and loss is 0.8 percent after queue tuning."
            )
            resolve = client.post(
                f"/api/v1/reviews/{review_item['id']}/submit",
                headers=teacher_headers,
                json={"teacher_answer": teacher_answer_text, "add_to_kb": True},
            )
            resolve_data = resolve.json().get("data") or {}
            self.check(
                "teacher_review_resolved_and_synced",
                resolve.status_code == 200 and resolve_data.get("status") == "resolved",
                data=resolve_data,
            )

            follow_up = client.post(
                "/api/v1/chat/query",
                headers=student_headers,
                json={
                    "class_id": class_id,
                    "message": f"Use the teacher-reviewed answer for marker {self.marker}. What are the three numbers?",
                    "attachments": [],
                },
            )
            follow_up_data = follow_up.json().get("data") or {}
            self.check(
                "student_followup_after_review",
                follow_up.status_code == 200 and bool(follow_up_data.get("content")),
                confidence=follow_up_data.get("confidence"),
                source_count=len(follow_up_data.get("sources") or []),
                needs_review=follow_up_data.get("needs_review"),
            )

        self.report["passed"] = all(item["passed"] for item in self.report["checks"])
        return self.report


def main() -> int:
    verifier = ChainVerifier()
    try:
        report = verifier.run()
    finally:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        report = verifier.report
        report["passed"] = all(item["passed"] for item in report["checks"])
        output = REPORT_DIR / f"verify_429_core_chain_{verifier.marker}.json"
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"report_path={output}")
        print(json.dumps({
            "passed": report.get("passed"),
            "marker": report.get("marker"),
            "check_count": len(report.get("checks") or []),
            "report_path": str(output),
        }, ensure_ascii=False))
    return 0 if verifier.report.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import binascii
import json
import re
import struct
import subprocess
import sys
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.integrations.rag.smoke_check import DEFAULT_SMOKE_REPORT_DIR  # noqa: E402


DEFAULT_SUITE_DIR = Path("runtime_tmp") / "multimodal_smoke_inputs"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run strict RAG-Anything smoke checks for audio/video content-list preprocessing."
    )
    parser.add_argument("--class-id", default=None, type=str, help="Optional class id used by all smoke runs.")
    parser.add_argument(
        "--isolated-class",
        action="store_true",
        help="Create a fresh isolated class for each modality smoke run.",
    )
    parser.add_argument(
        "--fixture-dir",
        default=str(DEFAULT_SUITE_DIR),
        type=str,
        help="Directory where deterministic audio/video smoke inputs are prepared.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_SMOKE_REPORT_DIR),
        type=str,
        help="Directory used to persist per-file smoke reports and the suite summary.",
    )
    parser.add_argument("--skip-audio", action="store_true", help="Skip the audio sidecar transcript smoke run.")
    parser.add_argument("--skip-video", action="store_true", help="Skip the video transcript/keyframe smoke run.")
    parser.add_argument("--skip-review-sync", action="store_true", help="Skip teacher QA write-back checks.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    fixture_paths = prepare_multimodal_smoke_fixtures(Path(args.fixture_dir))
    targets: list[tuple[str, Path]] = []
    if not args.skip_audio:
        targets.append(("audio", fixture_paths["audio"]))
    if not args.skip_video:
        targets.append(("video", fixture_paths["video"]))

    suite: dict[str, Any] = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "running",
        "engine": "raganything",
        "strict_mode": True,
        "fixture_dir": str(Path(args.fixture_dir).resolve()),
        "class_id": args.class_id,
        "isolated_class": bool(args.isolated_class),
        "runs": [],
    }

    for modality, file_path in targets:
        report, paths, process = run_single_smoke_subprocess(
            file_path=str(file_path),
            class_id=args.class_id,
            output_dir=args.output_dir,
            isolated_class=bool(args.isolated_class),
            question=f"Summarize the key teaching points from this {modality} material.",
            include_review_sync=not bool(args.skip_review_sync),
        )
        suite["runs"].append({
            "modality": modality,
            "file_path": str(file_path),
            "status": report.get("status"),
            "steps": [
                {"name": step.get("name"), "status": step.get("status")}
                for step in report.get("steps", [])
            ],
            "report_json_path": paths["json_path"],
            "report_md_path": paths["md_path"],
            "process_returncode": process.returncode,
        })

    suite["status"] = "passed" if suite["runs"] and all(item["status"] == "passed" for item in suite["runs"]) else "failed"
    suite["finished_at"] = datetime.now(timezone.utc).isoformat()
    suite_paths = write_suite_report(suite, Path(args.output_dir))
    print(json.dumps(suite, ensure_ascii=False, indent=2, default=str))
    print(f"Suite JSON report: {suite_paths['json_path']}")
    print(f"Suite Markdown report: {suite_paths['md_path']}")
    return 0 if suite["status"] == "passed" else 1


def prepare_multimodal_smoke_fixtures(base_dir: Path) -> dict[str, Path]:
    base_dir = base_dir.resolve()
    base_dir.mkdir(parents=True, exist_ok=True)

    audio_path = base_dir / "fixture_audio.mp3"
    audio_path.write_bytes(b"deterministic fake audio bytes for sidecar transcript smoke test")
    audio_path.with_suffix(".txt").write_text(
        "Audio lesson transcript: TCP slow start increases the congestion window, "
        "while queue delay and packet loss are used to evaluate congestion control.",
        encoding="utf-8",
    )

    video_path = base_dir / "fixture_video.mp4"
    video_path.write_bytes(b"deterministic fake video bytes for sidecar transcript smoke test")
    video_path.with_suffix(".vtt").write_text(
        "WEBVTT\n\n"
        "00:00:01 --> 00:00:04\n"
        "The video explains adaptive congestion control and queue stability.\n\n"
        "00:00:05 --> 00:00:08\n"
        "A key frame shows the relationship between throughput, fairness, and packet loss.\n",
        encoding="utf-8",
    )
    keyframe_dir = base_dir / "fixture_video_keyframes"
    keyframe_dir.mkdir(parents=True, exist_ok=True)
    (keyframe_dir / "frame001.png").write_bytes(_build_fixture_png())

    return {"audio": audio_path, "video": video_path}


def _build_fixture_png(width: int = 64, height: int = 64) -> bytes:
    """Build a tiny valid RGB PNG without relying on optional imaging packages."""

    def chunk(chunk_type: bytes, data: bytes) -> bytes:
        payload = chunk_type + data
        return (
            struct.pack(">I", len(data))
            + payload
            + struct.pack(">I", binascii.crc32(payload) & 0xFFFFFFFF)
        )

    raw_rows = []
    for y in range(height):
        row = bytearray()
        for x in range(width):
            row.extend((
                40 + (x * 5) % 180,
                80 + (y * 7) % 140,
                180 - (x + y) % 90,
            ))
        raw_rows.append(b"\x00" + bytes(row))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(b"".join(raw_rows)))
        + chunk(b"IEND", b"")
    )


def run_single_smoke_subprocess(
    *,
    file_path: str,
    class_id: str | None,
    output_dir: str,
    isolated_class: bool,
    question: str,
    include_review_sync: bool,
) -> tuple[dict[str, Any], dict[str, str], subprocess.CompletedProcess[str]]:
    command = [
        sys.executable,
        str(ROOT / "scripts" / "smoke_raganything_pipeline.py"),
        "--file",
        file_path,
        "--question",
        question,
        "--output-dir",
        output_dir,
    ]
    if class_id:
        command.extend(["--class-id", class_id])
    if isolated_class:
        command.append("--isolated-class")
    if not include_review_sync:
        command.append("--skip-review-sync")

    process = subprocess.run(
        command,
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        timeout=900,
        check=False,
    )
    json_path = _extract_report_path(process.stdout, "JSON report")
    md_path = _extract_report_path(process.stdout, "Markdown report")
    if not json_path:
        raise RuntimeError(
            "Unable to locate child smoke JSON report path. "
            f"returncode={process.returncode}; stderr={process.stderr[-1000:]}"
        )
    report = json.loads(Path(json_path).read_text(encoding="utf-8"))
    return report, {"json_path": json_path, "md_path": md_path or ""}, process


def _extract_report_path(stdout: str, label: str) -> str:
    match = re.search(rf"{re.escape(label)}:\s*(.+)", stdout or "")
    return match.group(1).strip() if match else ""


def write_suite_report(suite: dict[str, Any], output_dir: Path) -> dict[str, str]:
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    run_id = str(suite.get("started_at") or datetime.now(timezone.utc).isoformat())
    run_id = (
        run_id.replace("+00:00", "Z")
        .replace("-", "")
        .replace(":", "")
        .replace(".", "")
        .replace("T", "_")
    )[:32]
    json_path = output_dir / f"raganything_multimodal_suite_{run_id}.json"
    md_path = output_dir / f"raganything_multimodal_suite_{run_id}.md"
    json_path.write_text(json.dumps(suite, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    md_path.write_text(build_suite_markdown(suite), encoding="utf-8")
    return {"json_path": str(json_path), "md_path": str(md_path)}


def build_suite_markdown(suite: dict[str, Any]) -> str:
    lines = [
        "# RAG-Anything Multimodal Smoke Suite",
        "",
        f"- Status: `{suite.get('status')}`",
        f"- Started At: `{suite.get('started_at')}`",
        f"- Finished At: `{suite.get('finished_at')}`",
        f"- Fixture Dir: `{suite.get('fixture_dir')}`",
        "",
        "## Runs",
    ]
    for run in suite.get("runs", []):
        steps = ", ".join(f"{step['name']}:{step['status']}" for step in run.get("steps", []))
        lines.append(f"- `{run.get('modality')}`: `{run.get('status')}` - {steps}")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())

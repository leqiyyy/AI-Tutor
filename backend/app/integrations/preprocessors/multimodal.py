from __future__ import annotations

import hashlib
import importlib
import re
import shutil
import subprocess
from dataclasses import dataclass, field
import mimetypes
from pathlib import Path
from typing import Any

import httpx

from app.core.config import BASE_DIR, settings


DOCUMENT_EXTENSIONS = {
    ".pdf": "pdf",
    ".doc": "docx",
    ".docx": "docx",
    ".ppt": "ppt",
    ".pptx": "ppt",
    ".md": "md",
    ".txt": "txt",
}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv", ".wmv", ".m4v"}
TRANSCRIPT_EXTENSIONS = (".md", ".txt", ".vtt", ".srt")
KEYFRAME_EXTENSIONS = IMAGE_EXTENSIONS


@dataclass
class PreprocessResult:
    """Normalized input handed to RAG-Anything.

    Documents and images can be processed directly by RAG-Anything. Audio and
    video are converted into text/image content items first so the downstream
    indexing, embedding and graph construction still stay inside RAG-Anything.
    """

    mode: str
    modality: str
    source_file: str
    file_name: str
    content_list: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def use_content_list(self) -> bool:
        return self.mode == "content_list"


def detect_material_file_type(file_name: str, mime_type: str | None = None) -> str:
    suffix = Path(file_name or "").suffix.lower()
    mime = (mime_type or "").lower()

    if suffix in DOCUMENT_EXTENSIONS:
        return DOCUMENT_EXTENSIONS[suffix]
    if suffix in IMAGE_EXTENSIONS or mime.startswith("image/"):
        return "image"
    if suffix in AUDIO_EXTENSIONS or mime.startswith("audio/"):
        return "audio"
    if suffix in VIDEO_EXTENSIONS or mime.startswith("video/"):
        return "video"
    return "other"


def preprocess_for_raganything(file_path: str, mime_type: str, file_name: str) -> PreprocessResult:
    file_type = detect_material_file_type(file_name, mime_type)
    path = Path(file_path)

    if file_type in {"md", "txt"}:
        return _preprocess_text_document(path=path, mime_type=mime_type, file_name=file_name, file_type=file_type)

    if file_type == "image":
        return _preprocess_image(path=path, mime_type=mime_type, file_name=file_name)

    if file_type in {"pdf", "docx", "ppt"}:
        return PreprocessResult(
            mode="direct_document",
            modality="document",
            source_file=str(path),
            file_name=file_name,
            metadata={
                "file_type": file_type,
                "mime_type": mime_type,
                "raganything_entrypoint": "process_document_complete",
            },
        )

    if file_type == "audio":
        return _preprocess_audio(path=path, mime_type=mime_type, file_name=file_name)

    if file_type == "video":
        return _preprocess_video(path=path, mime_type=mime_type, file_name=file_name)

    return PreprocessResult(
        mode="direct_document",
        modality="other",
        source_file=str(path),
        file_name=file_name,
        metadata={
            "file_type": "other",
            "mime_type": mime_type,
            "raganything_entrypoint": "process_document_complete",
        },
        warnings=["unsupported_file_type_direct_attempt"],
    )


def _preprocess_image(*, path: Path, mime_type: str, file_name: str) -> PreprocessResult:
    caption = (
        f"Image material: {file_name}. "
        "The original image is attached as a multimodal content item for visual analysis."
    )
    content_list = [
        {
            "type": "text",
            "text": caption,
            "page_idx": 0,
            "metadata": {
                "source_name": file_name,
                "source_path": str(path),
                "source_type": "image_anchor",
                "mime_type": mime_type,
                "preprocess_quality": "image_content_list",
            },
        },
        {
            "type": "image",
            "img_path": str(path),
            "image_path": str(path),
            "caption": caption,
            "page_idx": 0,
            "metadata": {
                "source_name": file_name,
                "source_path": str(path),
                "source_type": "image",
                "mime_type": mime_type,
                "preprocess_quality": "image_content_list",
            },
        },
    ]
    return PreprocessResult(
        mode="content_list",
        modality="image",
        source_file=str(path),
        file_name=file_name,
        content_list=content_list,
        metadata={
            "file_type": "image",
            "mime_type": mime_type,
            "raganything_entrypoint": "insert_content_list",
            "preprocess_quality": "image_content_list",
        },
    )


def _preprocess_text_document(
    *,
    path: Path,
    mime_type: str,
    file_name: str,
    file_type: str,
) -> PreprocessResult:
    warnings: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="ignore")
        warnings.append("text_decoded_with_ignored_errors")

    if not text.strip():
        warnings.append("empty_text_document")

    content_list = [{
        "type": "text",
        "text": text,
        "page_idx": 0,
        "metadata": {
            "source_name": file_name,
            "source_path": str(path),
            "source_type": file_type,
            "mime_type": mime_type,
            "preprocess_quality": "native_text",
        },
    }]
    content_list.extend(_extract_structured_markdown_items(text, path=path, file_name=file_name, file_type=file_type))

    return PreprocessResult(
        mode="content_list",
        modality="document",
        source_file=str(path),
        file_name=file_name,
        content_list=content_list,
        metadata={
            "file_type": file_type,
            "mime_type": mime_type,
            "raganything_entrypoint": "insert_content_list",
            "preprocess_quality": "native_text",
        },
        warnings=warnings,
    )


def _extract_structured_markdown_items(
    text: str,
    *,
    path: Path,
    file_name: str,
    file_type: str,
) -> list[dict[str, Any]]:
    if file_type not in {"md", "txt"}:
        return []

    items: list[dict[str, Any]] = []
    for index, table_markdown in enumerate(_extract_markdown_tables(text), start=1):
        items.append({
            "type": "table",
            "text": f"Markdown table extracted from {file_name}:\n{table_markdown}",
            "table_markdown": table_markdown,
            "page_idx": 0,
            "metadata": {
                "source_name": file_name,
                "source_path": str(path),
                "source_type": "table",
                "origin": "markdown_table",
                "content_index": index,
            },
        })

    for index, formula in enumerate(_extract_markdown_formulas(text), start=1):
        items.append({
            "type": "equation",
            "text": f"Formula extracted from {file_name}: {formula}",
            "equation": formula,
            "formula_latex": formula,
            "page_idx": 0,
            "metadata": {
                "source_name": file_name,
                "source_path": str(path),
                "source_type": "formula",
                "origin": "markdown_formula",
                "content_index": index,
            },
        })

    return items


def _extract_markdown_tables(text: str) -> list[str]:
    tables: list[str] = []
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        if not _looks_like_table_row(lines[index]):
            index += 1
            continue
        start = index
        block: list[str] = []
        while index < len(lines) and _looks_like_table_row(lines[index]):
            block.append(lines[index].rstrip())
            index += 1
        if len(block) >= 2 and any(_looks_like_table_separator(row) for row in block[1:3]):
            tables.append("\n".join(block).strip())
        if index == start:
            index += 1
    return tables


def _looks_like_table_row(line: str) -> bool:
    stripped = line.strip()
    return stripped.count("|") >= 2 and not stripped.startswith("```")


def _looks_like_table_separator(line: str) -> bool:
    stripped = line.strip().strip("|")
    if not stripped:
        return False
    cells = [cell.strip() for cell in stripped.split("|")]
    return all(re.fullmatch(r":?-{3,}:?", cell or "") for cell in cells)


def _extract_markdown_formulas(text: str) -> list[str]:
    formulas: list[str] = []
    patterns = [
        r"\$\$(.+?)\$\$",
        r"\\\[(.+?)\\\]",
        r"\\\((.+?)\\\)",
        r"(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.DOTALL):
            formula = re.sub(r"\s+", " ", match.group(1)).strip()
            if not formula or len(formula) > 500:
                continue
            if formula not in formulas:
                formulas.append(formula)
    return formulas


def _preprocess_audio(*, path: Path, mime_type: str, file_name: str) -> PreprocessResult:
    transcript_path = _find_sidecar_transcript(path)
    generated_transcript = False
    warnings: list[str] = []
    if not transcript_path and settings.MULTIMODAL_AUTO_PREPROCESS_ENABLED:
        transcript_path = _generate_transcript_for_audio(path, warnings)
        generated_transcript = bool(transcript_path)
    transcript_text = _read_transcript(transcript_path) if transcript_path else ""
    quality = "transcript"
    if not transcript_text:
        warnings.append("missing_audio_transcript")
        quality = "metadata_only"
        transcript_text = (
            f"Audio material: {file_name}. "
            "No ASR transcript sidecar was found yet. Configure an ASR provider "
            "or upload a same-name .txt/.md/.srt/.vtt transcript for full indexing."
        )

    content_list = [{
        "type": "text",
        "text": transcript_text,
        "page_idx": 0,
        "metadata": {
            "source_name": file_name,
            "source_path": str(path),
            "source_type": "audio",
            "mime_type": mime_type,
            "preprocess_quality": quality,
            "transcript_path": str(transcript_path) if transcript_path else None,
            "generated_transcript": generated_transcript,
        },
    }]

    return PreprocessResult(
        mode="content_list",
        modality="audio",
        source_file=str(path),
        file_name=file_name,
        content_list=content_list,
        metadata={
            "file_type": "audio",
            "mime_type": mime_type,
            "raganything_entrypoint": "insert_content_list",
            "preprocess_quality": quality,
            "transcript_path": str(transcript_path) if transcript_path else None,
            "generated_transcript": generated_transcript,
        },
        warnings=warnings,
    )


def _preprocess_video(*, path: Path, mime_type: str, file_name: str) -> PreprocessResult:
    transcript_path = _find_sidecar_transcript(path)
    generated_audio_path: Path | None = None
    generated_transcript = False
    warnings: list[str] = []
    if not transcript_path and settings.MULTIMODAL_AUTO_PREPROCESS_ENABLED:
        generated_audio_path = _extract_audio_from_video(path, warnings)
        if generated_audio_path:
            transcript_path = _generate_transcript_for_audio(generated_audio_path, warnings, source_path=path)
            generated_transcript = bool(transcript_path)
    transcript_text = _read_transcript(transcript_path) if transcript_path else ""
    keyframes = _find_keyframes(path)
    generated_keyframes = False
    if not keyframes and settings.MULTIMODAL_AUTO_PREPROCESS_ENABLED:
        generated = _extract_video_keyframes(path, warnings)
        generated_keyframes = bool(generated)
        keyframes = generated or keyframes
    quality_parts = []

    if transcript_text:
        quality_parts.append("transcript")
    else:
        warnings.append("missing_video_transcript")
        transcript_text = (
            f"Video material: {file_name}. "
            "No ASR transcript sidecar was found yet. Configure video preprocessing "
            "or upload a same-name transcript for full indexing."
        )

    if keyframes:
        quality_parts.append("keyframes")
    else:
        warnings.append("missing_video_keyframes")

    content_list: list[dict[str, Any]] = [{
        "type": "text",
        "text": transcript_text,
        "page_idx": 0,
        "metadata": {
            "source_name": file_name,
            "source_path": str(path),
            "source_type": "video_transcript",
            "mime_type": mime_type,
            "transcript_path": str(transcript_path) if transcript_path else None,
            "generated_transcript": generated_transcript,
            "generated_audio_path": str(generated_audio_path) if generated_audio_path else None,
        },
    }]
    max_keyframes = max(1, int(settings.MULTIMODAL_VIDEO_MAX_KEYFRAMES))
    for index, frame_path in enumerate(keyframes[:max_keyframes], start=1):
        content_list.append({
            "type": "image",
            "img_path": str(frame_path),
            "image_path": str(frame_path),
            "caption": f"Key frame {index} extracted from {file_name}.",
            "page_idx": index,
            "metadata": {
                "source_name": file_name,
                "source_path": str(path),
                "source_type": "video_keyframe",
                "keyframe_path": str(frame_path),
            },
        })

    preprocess_quality = "+".join(quality_parts) if quality_parts else "metadata_only"
    return PreprocessResult(
        mode="content_list",
        modality="video",
        source_file=str(path),
        file_name=file_name,
        content_list=content_list,
        metadata={
            "file_type": "video",
            "mime_type": mime_type,
            "raganything_entrypoint": "insert_content_list",
            "preprocess_quality": preprocess_quality,
            "transcript_path": str(transcript_path) if transcript_path else None,
            "generated_transcript": generated_transcript,
            "generated_audio_path": str(generated_audio_path) if generated_audio_path else None,
            "generated_keyframes": generated_keyframes,
            "keyframe_count": len(keyframes),
        },
        warnings=warnings,
    )


def _find_sidecar_transcript(path: Path) -> Path | None:
    for suffix in TRANSCRIPT_EXTENSIONS:
        candidate = path.with_suffix(suffix)
        if candidate.exists() and candidate.is_file():
            return candidate

    transcript_dir = path.parent / f"{path.stem}_transcript"
    if transcript_dir.exists() and transcript_dir.is_dir():
        for suffix in TRANSCRIPT_EXTENSIONS:
            matches = sorted(transcript_dir.glob(f"*{suffix}"))
            if matches:
                return matches[0]

    artifact_dir = _artifact_dir(path, create=False)
    if artifact_dir.exists():
        for suffix in TRANSCRIPT_EXTENSIONS:
            matches = sorted(artifact_dir.glob(f"*{suffix}"))
            if matches:
                return matches[0]
    return None


def _read_transcript(path: Path | None) -> str:
    if not path:
        return ""
    text = path.read_text(encoding="utf-8", errors="ignore")
    if path.suffix.lower() in {".srt", ".vtt"}:
        text = _strip_subtitle_markup(text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _strip_subtitle_markup(text: str) -> str:
    cleaned_lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.upper() == "WEBVTT":
            continue
        if stripped.isdigit():
            continue
        if "-->" in stripped:
            cleaned_lines.append(f"[{stripped}]")
            continue
        cleaned_lines.append(stripped)
    return "\n".join(cleaned_lines)


def _find_keyframes(path: Path) -> list[Path]:
    candidates = [
        path.parent / f"{path.stem}_keyframes",
        path.parent / f"{path.stem}.keyframes",
        path.parent / path.stem,
        _artifact_dir(path, create=False) / "keyframes",
    ]
    frames: list[Path] = []
    for directory in candidates:
        if not directory.exists() or not directory.is_dir():
            continue
        for frame in sorted(directory.iterdir()):
            if frame.suffix.lower() in KEYFRAME_EXTENSIONS and frame.is_file():
                frames.append(frame)
    return frames


def _generate_transcript_for_audio(
    audio_path: Path,
    warnings: list[str],
    *,
    source_path: Path | None = None,
) -> Path | None:
    provider = (settings.ASR_PROVIDER or "none").strip().lower()
    if provider in {"", "none", "mock"}:
        warnings.append("asr_provider_not_configured")
        return None
    if provider == "faster_whisper":
        return _generate_transcript_with_faster_whisper(
            audio_path=audio_path,
            warnings=warnings,
            source_path=source_path,
        )
    if provider in {"api", "openai", "openai_compatible"}:
        return _generate_transcript_with_api(
            audio_path=audio_path,
            warnings=warnings,
            source_path=source_path,
        )
    warnings.append(f"unsupported_asr_provider:{provider}")
    return None


def _generate_transcript_with_faster_whisper(
    *,
    audio_path: Path,
    warnings: list[str],
    source_path: Path | None = None,
) -> Path | None:
    try:
        module = importlib.import_module("faster_whisper")
    except Exception:
        warnings.append("faster_whisper_not_installed")
        return None

    artifact_dir = _artifact_dir(source_path or audio_path)
    transcript_path = artifact_dir / f"{(source_path or audio_path).stem}.asr.md"
    try:
        WhisperModel = getattr(module, "WhisperModel")
        model = WhisperModel(
            settings.ASR_MODEL,
            device=settings.ASR_DEVICE,
            compute_type=settings.ASR_COMPUTE_TYPE,
        )
        language = settings.ASR_LANGUAGE or None
        segments, info = model.transcribe(str(audio_path), language=language, vad_filter=True)
        lines = [
            f"# ASR transcript for {(source_path or audio_path).name}",
            "",
            f"- provider: faster_whisper",
            f"- model: {settings.ASR_MODEL}",
            f"- language: {getattr(info, 'language', language or 'auto')}",
            "",
        ]
        for segment in segments:
            start = _format_seconds(float(getattr(segment, "start", 0.0) or 0.0))
            end = _format_seconds(float(getattr(segment, "end", 0.0) or 0.0))
            text = str(getattr(segment, "text", "") or "").strip()
            if text:
                lines.append(f"[{start} --> {end}] {text}")
        transcript_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
        return transcript_path
    except Exception as exc:
        warnings.append(f"asr_transcription_failed:{type(exc).__name__}")
        return None


def _generate_transcript_with_api(
    *,
    audio_path: Path,
    warnings: list[str],
    source_path: Path | None = None,
) -> Path | None:
    api_base = settings.EFFECTIVE_ASR_API_BASE
    api_key = settings.EFFECTIVE_ASR_API_KEY
    if not api_base:
        warnings.append("asr_api_base_missing")
        return None
    if not api_key:
        warnings.append("asr_api_key_missing")
        return None

    transcript_payload = _request_asr_api_transcript(audio_path, warnings)
    if transcript_payload is None:
        return None

    artifact_dir = _artifact_dir(source_path or audio_path)
    transcript_path = artifact_dir / f"{(source_path or audio_path).stem}.asr.md"
    source_name = (source_path or audio_path).name
    language = transcript_payload.get("language") or settings.ASR_LANGUAGE or "auto"
    segments = transcript_payload.get("segments") or []
    text = str(transcript_payload.get("text") or "").strip()

    lines = [
        f"# ASR transcript for {source_name}",
        "",
        f"- provider: {settings.ASR_PROVIDER}",
        f"- model: {settings.ASR_MODEL}",
        f"- language: {language}",
        "",
    ]
    if segments:
        for segment in segments:
            start = _format_seconds(float((segment.get("start") or 0.0)))
            end = _format_seconds(float((segment.get("end") or 0.0)))
            segment_text = str(segment.get("text") or "").strip()
            if segment_text:
                lines.append(f"[{start} --> {end}] {segment_text}")
    elif text:
        lines.append(text)
    else:
        warnings.append("asr_api_empty_transcript")
        return None

    transcript_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return transcript_path


def _request_asr_api_transcript(audio_path: Path, warnings: list[str]) -> dict[str, Any] | None:
    url = _join_base_and_path(settings.EFFECTIVE_ASR_API_BASE, settings.ASR_API_PATH)
    headers = _build_asr_headers(settings.EFFECTIVE_ASR_API_KEY)
    mime_type = mimetypes.guess_type(audio_path.name)[0] or "application/octet-stream"
    timeout = max(10.0, float(settings.ASR_API_TIMEOUT_SECONDS or 120.0))
    response_formats = ("verbose_json", "json", "text")

    for response_format in response_formats:
        try:
            with audio_path.open("rb") as fh:
                response = httpx.post(
                    url,
                    headers=headers,
                    data=_build_asr_form_data(response_format),
                    files={"file": (audio_path.name, fh, mime_type)},
                    timeout=timeout,
                )
            response.raise_for_status()
            return _normalize_asr_api_response(response, response_format)
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code if exc.response is not None else "unknown"
            if isinstance(status, int) and status in {400, 404, 415, 422} and response_format != response_formats[-1]:
                continue
            warnings.append(f"asr_api_failed:http_{status}")
            return None
        except Exception as exc:
            warnings.append(f"asr_api_failed:{type(exc).__name__}")
            return None
    return None


def _build_asr_form_data(response_format: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": settings.ASR_MODEL,
        "response_format": response_format,
    }
    if settings.ASR_LANGUAGE:
        payload["language"] = settings.ASR_LANGUAGE
    return payload


def _normalize_asr_api_response(response: httpx.Response, response_format: str) -> dict[str, Any]:
    if response_format == "text":
        return {"text": response.text.strip(), "segments": [], "language": settings.ASR_LANGUAGE or "auto"}

    payload = response.json()
    if isinstance(payload, str):
        return {"text": payload.strip(), "segments": [], "language": settings.ASR_LANGUAGE or "auto"}
    if not isinstance(payload, dict):
        return {"text": "", "segments": [], "language": settings.ASR_LANGUAGE or "auto"}

    segments = payload.get("segments")
    normalized_segments = []
    if isinstance(segments, list):
        for item in segments:
            if not isinstance(item, dict):
                continue
            normalized_segments.append({
                "start": float(item.get("start") or 0.0),
                "end": float(item.get("end") or 0.0),
                "text": str(item.get("text") or "").strip(),
            })
    return {
        "text": str(payload.get("text") or "").strip(),
        "segments": normalized_segments,
        "language": payload.get("language") or settings.ASR_LANGUAGE or "auto",
    }


def _join_base_and_path(base: str, path: str) -> str:
    normalized_base = str(base or "").rstrip("/")
    normalized_path = "/" + str(path or "").lstrip("/")
    return normalized_base + normalized_path


def _build_asr_headers(api_key: str) -> dict[str, str]:
    header_name = str(settings.ASR_API_AUTH_HEADER or "Authorization").strip() or "Authorization"
    scheme = str(settings.ASR_API_AUTH_SCHEME or "").strip()
    value = f"{scheme} {api_key}".strip() if scheme else api_key
    return {header_name: value}


def _extract_audio_from_video(video_path: Path, warnings: list[str]) -> Path | None:
    ffmpeg = _resolve_executable(settings.MULTIMODAL_FFMPEG_PATH)
    if not ffmpeg:
        warnings.append("ffmpeg_not_available")
        return None

    artifact_dir = _artifact_dir(video_path)
    audio_path = artifact_dir / f"{video_path.stem}.wav"
    if audio_path.exists() and audio_path.stat().st_size > 0:
        return audio_path

    command = [
        ffmpeg,
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        str(audio_path),
    ]
    if _run_command(command, warnings, "video_audio_extract"):
        return audio_path if audio_path.exists() else None
    return None


def _extract_video_keyframes(video_path: Path, warnings: list[str]) -> list[Path]:
    ffmpeg = _resolve_executable(settings.MULTIMODAL_FFMPEG_PATH)
    if not ffmpeg:
        warnings.append("ffmpeg_not_available")
        return []

    output_dir = _artifact_dir(video_path) / "keyframes"
    output_dir.mkdir(parents=True, exist_ok=True)
    interval = max(1, int(settings.MULTIMODAL_VIDEO_KEYFRAME_INTERVAL_SECONDS))
    max_frames = max(1, int(settings.MULTIMODAL_VIDEO_MAX_KEYFRAMES))
    pattern = output_dir / "frame_%03d.jpg"
    command = [
        ffmpeg,
        "-y",
        "-i",
        str(video_path),
        "-vf",
        f"fps=1/{interval}",
        "-frames:v",
        str(max_frames),
        str(pattern),
    ]
    if not _run_command(command, warnings, "video_keyframe_extract"):
        return []
    return [
        frame
        for frame in sorted(output_dir.glob("frame_*.jpg"))
        if frame.is_file()
    ]


def _artifact_dir(path: Path, *, create: bool = True) -> Path:
    root = Path(settings.MULTIMODAL_PREPROCESS_OUTPUT_DIR)
    if not root.is_absolute():
        root = (BASE_DIR / root).resolve()
    digest = hashlib.sha1(str(path.resolve()).encode("utf-8", errors="ignore")).hexdigest()[:10]
    directory = root / f"{path.stem}-{digest}"
    if create:
        directory.mkdir(parents=True, exist_ok=True)
    return directory


def _resolve_executable(value: str) -> str | None:
    candidate = (value or "").strip()
    if not candidate:
        return None
    path = Path(candidate)
    if path.exists():
        return str(path)
    return shutil.which(candidate)


def _run_command(command: list[str], warnings: list[str], label: str) -> bool:
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except FileNotFoundError:
        warnings.append(f"{label}_executable_not_found")
        return False
    except subprocess.TimeoutExpired:
        warnings.append(f"{label}_timeout")
        return False

    if result.returncode != 0:
        message = (result.stderr or result.stdout or "").strip().splitlines()
        detail = message[-1][:160] if message else "unknown_error"
        warnings.append(f"{label}_failed:{detail}")
        return False
    return True


def _format_seconds(value: float) -> str:
    total = max(0, int(value))
    hours = total // 3600
    minutes = (total % 3600) // 60
    seconds = total % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

from pathlib import Path
import shutil

import app.integrations.preprocessors.multimodal as multimodal
from app.integrations.preprocessors import detect_material_file_type, preprocess_for_raganything
from scripts.smoke_multimodal_raganything_suite import prepare_multimodal_smoke_fixtures


def test_detect_material_file_type_supports_multimodal_inputs():
    assert detect_material_file_type("lesson.pdf", "application/pdf") == "pdf"
    assert detect_material_file_type("slides.pptx", "") == "ppt"
    assert detect_material_file_type("diagram.webp", "image/webp") == "image"
    assert detect_material_file_type("lecture.mp3", "audio/mpeg") == "audio"
    assert detect_material_file_type("demo.mp4", "video/mp4") == "video"


def test_audio_preprocessor_uses_sidecar_transcript(tmp_path: Path):
    audio = tmp_path / "lecture.mp3"
    audio.write_bytes(b"fake-audio")
    transcript = tmp_path / "lecture.txt"
    transcript.write_text("TCP slow start doubles the congestion window each RTT.", encoding="utf-8")

    result = preprocess_for_raganything(str(audio), "audio/mpeg", "lecture.mp3")

    assert result.mode == "content_list"
    assert result.modality == "audio"
    assert result.warnings == []
    assert result.content_list[0]["text"].startswith("TCP slow start")
    assert result.metadata["preprocess_quality"] == "transcript"


def test_video_preprocessor_collects_transcript_and_keyframes(tmp_path: Path):
    video = tmp_path / "demo.mp4"
    video.write_bytes(b"fake-video")
    transcript = tmp_path / "demo.vtt"
    transcript.write_text("WEBVTT\n\n00:00:01 --> 00:00:03\nA router forwards packets.", encoding="utf-8")
    keyframe_dir = tmp_path / "demo_keyframes"
    keyframe_dir.mkdir()
    (keyframe_dir / "frame001.jpg").write_bytes(b"fake-image")

    result = preprocess_for_raganything(str(video), "video/mp4", "demo.mp4")

    assert result.mode == "content_list"
    assert result.modality == "video"
    assert "missing_video_transcript" not in result.warnings
    assert result.metadata["keyframe_count"] == 1
    assert any(item["type"] == "image" for item in result.content_list)


def test_audio_preprocessor_can_use_generated_transcript(tmp_path: Path, monkeypatch):
    audio = tmp_path / "lecture.mp3"
    audio.write_bytes(b"fake-audio")

    def fake_generate(audio_path, warnings, source_path=None):
        transcript = tmp_path / "generated.md"
        transcript.write_text("[00:00:01 --> 00:00:03] Generated TCP transcript.", encoding="utf-8")
        return transcript

    monkeypatch.setattr(multimodal.settings, "MULTIMODAL_AUTO_PREPROCESS_ENABLED", True)
    monkeypatch.setattr(multimodal, "_generate_transcript_for_audio", fake_generate)

    result = preprocess_for_raganything(str(audio), "audio/mpeg", "lecture.mp3")

    assert result.metadata["generated_transcript"] is True
    assert result.metadata["preprocess_quality"] == "transcript"
    assert result.content_list[0]["text"].startswith("[00:00:01")


def test_video_preprocessor_can_generate_audio_transcript_and_keyframes(tmp_path: Path, monkeypatch):
    video = tmp_path / "demo.mp4"
    video.write_bytes(b"fake-video")
    extracted_audio = tmp_path / "demo.wav"
    extracted_audio.write_bytes(b"fake-wav")
    frame = tmp_path / "frame001.jpg"
    frame.write_bytes(b"fake-image")

    def fake_extract_audio(video_path, warnings):
        return extracted_audio

    def fake_generate(audio_path, warnings, source_path=None):
        transcript = tmp_path / "demo.asr.md"
        transcript.write_text("[00:00:01 --> 00:00:04] Generated video transcript.", encoding="utf-8")
        return transcript

    def fake_extract_keyframes(video_path, warnings):
        return [frame]

    monkeypatch.setattr(multimodal.settings, "MULTIMODAL_AUTO_PREPROCESS_ENABLED", True)
    monkeypatch.setattr(multimodal, "_extract_audio_from_video", fake_extract_audio)
    monkeypatch.setattr(multimodal, "_generate_transcript_for_audio", fake_generate)
    monkeypatch.setattr(multimodal, "_extract_video_keyframes", fake_extract_keyframes)

    result = preprocess_for_raganything(str(video), "video/mp4", "demo.mp4")

    assert "missing_video_transcript" not in result.warnings
    assert "missing_video_keyframes" not in result.warnings
    assert result.metadata["generated_transcript"] is True
    assert result.metadata["generated_keyframes"] is True
    assert result.metadata["preprocess_quality"] == "transcript+keyframes"


def test_audio_preprocessor_can_use_api_asr_provider(tmp_path: Path, monkeypatch):
    audio = tmp_path / "lecture.mp3"
    audio.write_bytes(b"fake-audio")
    artifact_dir = multimodal._artifact_dir(audio, create=False)
    if artifact_dir.exists():
        shutil.rmtree(artifact_dir)

    class FakeResponse:
        status_code = 200
        text = ""

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "text": "TCP slow start gradually increases the congestion window.",
                "language": "en",
                "segments": [
                    {"start": 0.0, "end": 3.0, "text": "TCP slow start gradually increases the congestion window."}
                ],
            }

    def fake_post(url, headers=None, data=None, files=None, timeout=None):
        assert url == "https://asr.example/v1/audio/transcriptions"
        assert headers["Authorization"] == "Bearer asr-key"
        assert data["model"] == "whisper-test"
        assert files["file"][0] == "lecture.mp3"
        return FakeResponse()

    monkeypatch.setattr(multimodal.settings, "MULTIMODAL_AUTO_PREPROCESS_ENABLED", True)
    monkeypatch.setattr(multimodal.settings, "ASR_PROVIDER", "api")
    monkeypatch.setattr(multimodal.settings, "ASR_MODEL", "whisper-test")
    monkeypatch.setattr(multimodal.settings, "ASR_API_BASE", "https://asr.example/v1")
    monkeypatch.setattr(multimodal.settings, "ASR_API_KEY", "asr-key")
    monkeypatch.setattr(multimodal.settings, "VLM_API_BASE", "")
    monkeypatch.setattr(multimodal.settings, "VLM_API_KEY", "")
    monkeypatch.setattr(multimodal.settings, "LLM_API_BASE", "")
    monkeypatch.setattr(multimodal.settings, "LLM_API_KEY", "")
    monkeypatch.setattr(multimodal.httpx, "post", fake_post)

    result = preprocess_for_raganything(str(audio), "audio/mpeg", "lecture.mp3")

    assert result.metadata["generated_transcript"] is True
    assert result.metadata["preprocess_quality"] == "transcript"
    assert "TCP slow start" in result.content_list[0]["text"]
    assert result.warnings == []


def test_multimodal_smoke_fixture_builder_creates_audio_and_video_inputs(tmp_path: Path):
    paths = prepare_multimodal_smoke_fixtures(tmp_path)

    audio = preprocess_for_raganything(str(paths["audio"]), "audio/mpeg", paths["audio"].name)
    video = preprocess_for_raganything(str(paths["video"]), "video/mp4", paths["video"].name)

    assert audio.mode == "content_list"
    assert audio.modality == "audio"
    assert audio.metadata["preprocess_quality"] == "transcript"
    assert "TCP slow start" in audio.content_list[0]["text"]

    assert video.mode == "content_list"
    assert video.modality == "video"
    assert video.metadata["preprocess_quality"] == "transcript+keyframes"
    assert any(item["type"] == "image" for item in video.content_list)

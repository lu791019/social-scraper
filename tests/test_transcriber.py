import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from media.transcriber import extract_audio


def test_extract_audio_creates_mp3(tmp_path):
    """測試 ffmpeg 音軌擷取（需要真實 ffmpeg）"""
    import subprocess

    video_path = tmp_path / "test.mp4"
    # 產生 1 秒靜音影片
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
        "-t", "1", "-q:a", "9", "-acodec", "aac", str(video_path),
    ], capture_output=True)

    audio_path = extract_audio(video_path)
    assert audio_path.exists()
    assert audio_path.suffix == ".mp3"
    audio_path.unlink()
    video_path.unlink()


@patch("media.transcriber.mlx_whisper")
def test_transcribe_audio_returns_text(mock_whisper):
    mock_whisper.transcribe.return_value = {"text": "大家好"}
    from media.transcriber import transcribe_audio
    result = transcribe_audio(Path("/fake/audio.mp3"))
    assert result == "大家好"

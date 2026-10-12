import subprocess
from pathlib import Path

import httpx
import mlx_whisper

from config import WHISPER_MODEL, TEMP_DIR


async def download_video(video_url: str) -> Path:
    """下載影片到暫存目錄"""
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    video_path = TEMP_DIR / "video.mp4"

    async with httpx.AsyncClient(follow_redirects=True, timeout=120) as client:
        response = await client.get(video_url)
        response.raise_for_status()
        video_path.write_bytes(response.content)

    return video_path


def extract_audio(video_path: Path) -> Path:
    """用 ffmpeg 從影片擷取音軌為 MP3"""
    audio_path = video_path.with_suffix(".mp3")
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(video_path),
            "-vn", "-acodec", "libmp3lame", "-q:a", "4",
            str(audio_path),
        ],
        capture_output=True,
        check=True,
    )
    return audio_path


def transcribe_audio(audio_path: Path) -> str:
    """用 mlx-whisper 本地轉逐字稿（Apple Silicon 加速）"""
    result = mlx_whisper.transcribe(
        str(audio_path),
        path_or_hf_repo=WHISPER_MODEL,
        language="zh",
    )
    return result["text"].strip()


async def process_video(video_url: str) -> str:
    """完整影片處理管線：下載 → 抽音軌 → 本地轉逐字稿 → 清理"""
    video_path = await download_video(video_url)
    try:
        audio_path = extract_audio(video_path)
        try:
            transcript = transcribe_audio(audio_path)
            return transcript
        finally:
            audio_path.unlink(missing_ok=True)
    finally:
        video_path.unlink(missing_ok=True)

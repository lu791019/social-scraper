import asyncio
from pathlib import Path

import httpx

from config import CLAUDE_CLI, TEMP_DIR


async def run_claude_print(prompt: str, image_path: Path | None = None) -> str:
    """呼叫 claude --print，走 Max 額度不花 API"""
    cmd = [CLAUDE_CLI, "--print"]
    if image_path:
        cmd.extend(["--image", str(image_path)])
    cmd.append(prompt)

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError(f"claude --print 失敗: {stderr.decode().strip()}")

    return stdout.decode().strip()


async def download_image(image_url: str) -> Path:
    """下載圖片到暫存目錄"""
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"img_{hash(image_url) % 10**8}.jpg"
    image_path = TEMP_DIR / filename

    async with httpx.AsyncClient(follow_redirects=True, timeout=60) as client:
        response = await client.get(image_url)
        response.raise_for_status()
        image_path.write_bytes(response.content)

    return image_path


async def extract_image_text(image_path: Path) -> str:
    """用 claude --print 擷取圖片上的文字"""
    text = await run_claude_print(
        "請擷取這張圖片上的所有文字，保持原始排版。如果圖片上完全沒有文字，只回覆「無文字」。",
        image_path=image_path,
    )
    if text == "無文字":
        return ""
    return text


async def process_images(image_urls: list[str]) -> str:
    """處理多張圖片的 OCR：下載 → claude --print OCR → 合併結果"""
    results = []
    for url in image_urls:
        image_path = await download_image(url)
        try:
            text = await extract_image_text(image_path)
            results.append(text)
        finally:
            image_path.unlink(missing_ok=True)
    return format_ocr_results(results)


def format_ocr_results(results: list[str]) -> str:
    """合併 OCR 結果，過濾空值"""
    non_empty = [r for r in results if r.strip()]
    return "\n\n".join(non_empty)

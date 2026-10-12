import asyncio
from pathlib import Path

import httpx

from config import CLAUDE_CLI, TEMP_DIR


async def run_claude_print(prompt: str, image_path: Path | None = None) -> str:
    """呼叫 claude --print，走 Max 額度不花 API"""
    cmd = [CLAUDE_CLI, "--print"]
    if image_path:
        cmd.extend(["--allowed-tools", "Read"])

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate(input=prompt.encode())

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
    """用 claude --print + Read 工具擷取單張圖片上的文字"""
    text = await run_claude_print(
        f"請讀取圖片 {image_path.resolve()} 並擷取上面所有文字，保持原始排版。如果圖片上完全沒有文字，只回覆「無文字」。",
        image_path=image_path,
    )
    if text == "無文字":
        return ""
    return text


async def extract_images_text_batch(image_paths: list[Path]) -> str:
    """用一次 claude --print 批次擷取多張圖片的文字"""
    if len(image_paths) == 1:
        return await extract_image_text(image_paths[0])

    paths_list = "\n".join(
        f"{i+1}. {p.resolve()}" for i, p in enumerate(image_paths)
    )
    prompt = (
        f"請依序讀取以下 {len(image_paths)} 張圖片，擷取每張上面的所有文字，保持原始排版。\n"
        "如果某張圖片完全沒有文字，該張寫「無文字」。\n"
        "每張圖片的結果用「---圖片N---」分隔（N 為編號）。\n\n"
        f"{paths_list}"
    )
    text = await run_claude_print(prompt, image_path=image_paths[0])
    # 過濾「無文字」段落
    sections = []
    for section in text.split("---"):
        cleaned = section.strip()
        # 跳過分隔標記和「無文字」
        if not cleaned or cleaned.startswith("圖片") or cleaned == "無文字":
            continue
        # 移除開頭的「圖片N」標記行
        lines = cleaned.split("\n")
        if lines and lines[0].strip().startswith("圖片"):
            lines = lines[1:]
        content = "\n".join(lines).strip()
        if content and content != "無文字":
            sections.append(content)
    return "\n\n".join(sections)


async def process_images(image_urls: list[str]) -> str:
    """處理多張圖片的 OCR：下載全部 → 一次批次 OCR → 清理"""
    if not image_urls:
        return ""

    image_paths = []
    for url in image_urls:
        image_paths.append(await download_image(url))

    try:
        return await extract_images_text_batch(image_paths)
    finally:
        for p in image_paths:
            p.unlink(missing_ok=True)


def format_ocr_results(results: list[str]) -> str:
    """合併 OCR 結果，過濾空值"""
    non_empty = [r for r in results if r.strip()]
    return "\n\n".join(non_empty)

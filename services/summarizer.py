from media.ocr import run_claude_print


def format_raw_content(caption: str, ocr_text: str, transcript: str) -> str:
    """將各來源內容格式化為 B 欄格式"""
    sections = []
    if caption.strip():
        sections.append(f"【貼文文字】\n{caption.strip()}")
    if ocr_text.strip():
        sections.append(f"【圖片文字】\n{ocr_text.strip()}")
    if transcript.strip():
        sections.append(f"【影片逐字稿】\n{transcript.strip()}")
    return "\n\n".join(sections)


async def summarize(raw_content: str) -> str:
    """用 claude --print 產出摘要（走 Max 額度）"""
    prompt = (
        "請用繁體中文摘要以下社群貼文內容，"
        "包含重點觀點和關鍵資訊，控制在 2-3 句話：\n\n"
        f"{raw_content}"
    )
    return await run_claude_print(prompt)


async def extract_key_points(raw_content: str) -> str:
    """用 claude --print 提取 3~5 個關鍵點"""
    prompt = (
        "請從以下社群貼文內容中，用繁體中文提取 3~5 個關鍵點或重要語句。"
        "每個關鍵點用「• 」開頭，一行一個，不要額外說明：\n\n"
        f"{raw_content}"
    )
    return await run_claude_print(prompt)

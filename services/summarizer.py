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


async def summarize_and_extract(raw_content: str) -> tuple[str, str]:
    """用一次 claude --print 同時產出摘要和關鍵點（走 Max 額度）。

    回傳 (summary, key_points)。
    """
    prompt = (
        "請用繁體中文分析以下社群貼文內容，輸出格式嚴格如下：\n\n"
        "【摘要】\n"
        "（2-3 句話，包含重點觀點和關鍵資訊）\n\n"
        "【關鍵點】\n"
        "（3~5 個，每個用「• 」開頭，一行一個）\n\n"
        "---\n\n"
        f"{raw_content}"
    )
    result = await run_claude_print(prompt)
    return _parse_summary_and_key_points(result)


def _parse_summary_and_key_points(text: str) -> tuple[str, str]:
    """解析 LLM 回應，拆分為 (summary, key_points)"""
    summary = ""
    key_points = ""

    if "【關鍵點】" in text:
        parts = text.split("【關鍵點】", 1)
        summary_part = parts[0]
        key_points = parts[1].strip()
    elif "【摘要】" in text:
        summary_part = text
    else:
        # 格式不符時，全部當摘要
        return text.strip(), ""

    if "【摘要】" in summary_part:
        summary = summary_part.split("【摘要】", 1)[1].strip()
    else:
        summary = summary_part.strip()

    return summary, key_points

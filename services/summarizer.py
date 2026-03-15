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

    根據內容類型自動切換提取策略：
    - 工具/資源推薦 → 列出名稱、連結、描述
    - 教學/知識分享 → 提取步驟或核心知識點
    - 觀點/討論 → 摘要論點與正反觀點
    - 其他 → 3~5 個重點

    回傳 (summary, key_points)。
    """
    prompt = (
        "請用繁體中文分析以下社群貼文內容。\n\n"
        "先判斷內容類型，再依類型提取結構化資訊：\n"
        "■ 工具/資源推薦 → 關鍵點列出每個工具或資源的「名稱」「連結（如有）」「一句話描述」\n"
        "■ 教學/知識分享 → 關鍵點按順序列出核心步驟或知識點\n"
        "■ 觀點/討論 → 關鍵點摘要各方論點與正反觀點\n"
        "■ 其他 → 關鍵點列出 3~5 個重點\n\n"
        "輸出格式嚴格如下：\n\n"
        "【摘要】\n"
        "（1-2 句話概述貼文主題和核心價值）\n\n"
        "【關鍵點】\n"
        "（依內容類型提取的結構化資訊，每項用「• 」開頭，一行一個）\n\n"
        "重要規則：\n"
        "- 如果貼文提到具體工具、套件、GitHub repo、網站，務必列出名稱和連結\n"
        "- 如果有步驟流程，按順序編號列出\n"
        "- 保留原文中的關鍵數據和具體資訊，不要泛泛而談\n"
        "- 不要自己編造連結，只提取原文中出現的連結\n\n"
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

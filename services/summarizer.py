import re
from dataclasses import dataclass

from media.ocr import run_claude_print

SUMMARY_MARK = "【摘要】"
KEY_POINTS_MARK = "【關鍵點】"
TITLE_MARK = "【Discord標題】"
COMMENT_MARK = "【Discord點評】"
_DISCORD_MARKS = (TITLE_MARK, COMMENT_MARK)


@dataclass(frozen=True)
class PostSummary:
    """一次 claude --print 的完整輸出。summary/key_points 寫 Sheet，title/discord_comment 只給 Discord。"""
    summary: str
    key_points: str
    title: str = ""
    discord_comment: str = ""


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
    """Sheet 用的舊介面：回傳 (summary, key_points)。"""
    result = await summarize_post(raw_content)
    return result.summary, result.key_points


async def summarize_post(raw_content: str) -> PostSummary:
    """用一次 claude --print 產出摘要、關鍵點，以及 Discord 用的標題與蛇摸點評（走 Max 額度）。

    根據內容類型自動切換提取策略：
    - 工具/資源推薦 → 列出名稱、連結、描述
    - 教學/知識分享 → 提取步驟或核心知識點
    - 觀點/討論 → 摘要論點與正反觀點
    - 其他 → 3~5 個重點
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
        "【Discord標題】\n"
        "（一行 30 字以內的標題，直述這篇在講什麼，不加引號、不加 emoji）\n\n"
        "【Discord點評】\n"
        "（1-2 句，用「蛇摸影評」的口吻：部落長身邊一條慵懶、好奇、有點壞的蛇，"
        "以「嘶～」開頭，語氣懶洋洋但要點出這篇最值得看的一點或盲點，"
        "可用「欸？」「等等」，不要驚嘆號連發、不要 hashtag）\n\n"
        "重要規則：\n"
        "- 如果貼文提到具體工具、套件、GitHub repo、網站，務必列出名稱和連結\n"
        "- 如果有步驟流程，按順序編號列出\n"
        "- 保留原文中的關鍵數據和具體資訊，不要泛泛而談\n"
        "- 不要自己編造連結，只提取原文中出現的連結\n"
        "- 四個段落標記一字不改，依上面順序輸出\n\n"
        "---\n\n"
        f"{raw_content}"
    )
    result = await run_claude_print(prompt)
    return _parse_post_summary(result)


def _split_discord_sections(text: str) -> tuple[str, dict[str, str]]:
    """把 Discord 段落從尾端切出，回傳 (其餘文字, {標記: 內容})。"""
    pattern = "(" + "|".join(re.escape(m) for m in _DISCORD_MARKS) + ")"
    parts = re.split(pattern, text)
    head = parts[0]
    sections = {parts[i]: parts[i + 1].strip() for i in range(1, len(parts) - 1, 2)}
    return head, sections


def _parse_post_summary(text: str) -> PostSummary:
    head, sections = _split_discord_sections(text)
    summary, key_points = _parse_sheet_fields(head)
    return PostSummary(
        summary=summary,
        key_points=key_points,
        title=sections.get(TITLE_MARK, "").splitlines()[0].strip() if sections.get(TITLE_MARK) else "",
        discord_comment=sections.get(COMMENT_MARK, ""),
    )


def _parse_summary_and_key_points(text: str) -> tuple[str, str]:
    """解析 LLM 回應，拆分為 (summary, key_points)；Discord 段落會被排除。"""
    return _parse_sheet_fields(_split_discord_sections(text)[0])


def _parse_sheet_fields(text: str) -> tuple[str, str]:
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

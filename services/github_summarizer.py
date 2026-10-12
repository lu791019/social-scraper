from media.ocr import run_claude_print
from scraper.github import RepoData


async def summarize_readme(repo: RepoData) -> tuple[str, str]:
    """用 claude --print 翻譯/摘要 README + 提取使用情境。

    回傳 (chinese_summary, use_cases)。
    """
    if not repo.readme:
        return "（README 為空）", ""

    prompt = (
        "你是技術文件摘要專家。請用繁體中文分析以下 GitHub Repo 的 README。\n\n"
        f"Repo: {repo.full_name}\n"
        f"說明: {repo.description}\n"
        f"語言: {repo.language} | ⭐ {repo.stars}\n\n"
        "---README 開始---\n"
        f"{repo.readme}\n"
        "---README 結束---\n\n"
        "請嚴格按以下格式輸出：\n\n"
        "【中文摘要】\n"
        "（5~10 句話，涵蓋：這是什麼、解決什麼問題、核心功能、技術特色）\n\n"
        "【使用情境】\n"
        "（3~5 個 bullet，每項用「• 」開頭，描述誰在什麼場景下會用到這個工具）\n\n"
        "重要規則：\n"
        "- 使用繁體中文\n"
        "- 保留專有名詞原文（如 API、SDK、framework 名稱）\n"
        "- 不要編造功能，只根據 README 內容摘要"
    )
    result = await run_claude_print(prompt)
    return _parse_github_summary(result)


def _parse_github_summary(text: str) -> tuple[str, str]:
    """解析 LLM 回應，拆分為 (summary, use_cases)。"""
    summary = ""
    use_cases = ""

    if "【使用情境】" in text:
        parts = text.split("【使用情境】", 1)
        summary_part = parts[0]
        use_cases = parts[1].strip()
    elif "【中文摘要】" in text:
        summary_part = text
    else:
        return text.strip(), ""

    if "【中文摘要】" in summary_part:
        summary = summary_part.split("【中文摘要】", 1)[1].strip()
    else:
        summary = summary_part.strip()

    return summary, use_cases

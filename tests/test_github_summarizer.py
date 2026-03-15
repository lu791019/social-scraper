import pytest
from unittest.mock import AsyncMock, patch
from services.github_summarizer import summarize_readme, _parse_github_summary
from scraper.github import RepoData


def test_parse_github_summary_full():
    text = (
        "【中文摘要】\n"
        "Requests 是 Python 的 HTTP 庫，提供簡潔的 API。\n\n"
        "【使用情境】\n"
        "• 後端開發者需要呼叫外部 API\n"
        "• 爬蟲開發時使用"
    )
    summary, use_cases = _parse_github_summary(text)
    assert "Requests" in summary
    assert "HTTP" in summary
    assert "後端開發者" in use_cases
    assert "爬蟲" in use_cases


def test_parse_github_summary_only_summary():
    text = "【中文摘要】\n這是一個很棒的工具。"
    summary, use_cases = _parse_github_summary(text)
    assert "很棒的工具" in summary
    assert use_cases == ""


def test_parse_github_summary_no_markers():
    text = "這段回應沒有格式標記，純文字。"
    summary, use_cases = _parse_github_summary(text)
    assert summary == text
    assert use_cases == ""


def test_parse_github_summary_empty_sections():
    text = "【中文摘要】\n\n【使用情境】\n"
    summary, use_cases = _parse_github_summary(text)
    assert summary == ""
    assert use_cases == ""


@pytest.mark.asyncio
async def test_summarize_readme_empty():
    repo = RepoData(
        owner="user", repo="repo", full_name="user/repo",
        description="", stars=0, language="", readme="",
    )
    summary, use_cases = await summarize_readme(repo)
    assert "README 為空" in summary


@pytest.mark.asyncio
async def test_summarize_readme_calls_claude():
    repo = RepoData(
        owner="psf", repo="requests", full_name="psf/requests",
        description="HTTP for Humans", stars=52000, language="Python",
        readme="# Requests\n\nSimple HTTP library.",
    )
    mock_response = (
        "【中文摘要】\n"
        "Requests 是一個簡潔的 Python HTTP 庫。\n\n"
        "【使用情境】\n"
        "• 開發者呼叫 REST API"
    )
    with patch("services.github_summarizer.run_claude_print", new_callable=AsyncMock, return_value=mock_response):
        summary, use_cases = await summarize_readme(repo)

    assert "Requests" in summary
    assert "REST API" in use_cases

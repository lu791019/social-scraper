import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from scraper.github import parse_github_url, fetch_repo, RepoData


def test_parse_github_url_basic():
    owner, repo = parse_github_url("https://github.com/psf/requests")
    assert owner == "psf"
    assert repo == "requests"


def test_parse_github_url_with_path():
    owner, repo = parse_github_url("https://github.com/langchain-ai/langchain/tree/main/docs")
    assert owner == "langchain-ai"
    assert repo == "langchain"


def test_parse_github_url_with_git_suffix():
    owner, repo = parse_github_url("https://github.com/psf/requests.git")
    assert owner == "psf"
    assert repo == "requests"


def test_parse_github_url_www():
    owner, repo = parse_github_url("https://github.com/fastapi/fastapi")
    assert owner == "fastapi"
    assert repo == "fastapi"


def test_parse_github_url_invalid():
    with pytest.raises(ValueError, match="無法解析"):
        parse_github_url("https://gitlab.com/user/repo")


def test_parse_github_url_in_text():
    owner, repo = parse_github_url("看看這個 https://github.com/psf/requests 很棒")
    assert owner == "psf"
    assert repo == "requests"


@pytest.mark.asyncio
async def test_fetch_repo_success():
    mock_repo_response = MagicMock()
    mock_repo_response.status_code = 200
    mock_repo_response.json.return_value = {
        "full_name": "psf/requests",
        "description": "A simple HTTP library",
        "stargazers_count": 52000,
        "language": "Python",
    }
    mock_repo_response.raise_for_status = MagicMock()

    mock_readme_response = MagicMock()
    mock_readme_response.status_code = 200
    mock_readme_response.text = "# Requests\n\nA simple HTTP library."

    async def mock_get(url, **kwargs):
        if "/readme" in url:
            return mock_readme_response
        return mock_repo_response

    mock_client = AsyncMock()
    mock_client.get = mock_get
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("scraper.github.httpx.AsyncClient", return_value=mock_client):
        repo = await fetch_repo("https://github.com/psf/requests")

    assert repo.full_name == "psf/requests"
    assert repo.description == "A simple HTTP library"
    assert repo.stars == 52000
    assert repo.language == "Python"
    assert "Requests" in repo.readme


@pytest.mark.asyncio
async def test_fetch_repo_no_readme():
    mock_repo_response = MagicMock()
    mock_repo_response.status_code = 200
    mock_repo_response.json.return_value = {
        "full_name": "user/repo",
        "description": None,
        "stargazers_count": 0,
        "language": None,
    }
    mock_repo_response.raise_for_status = MagicMock()

    mock_readme_response = MagicMock()
    mock_readme_response.status_code = 404

    async def mock_get(url, **kwargs):
        if "/readme" in url:
            return mock_readme_response
        return mock_repo_response

    mock_client = AsyncMock()
    mock_client.get = mock_get
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("scraper.github.httpx.AsyncClient", return_value=mock_client):
        repo = await fetch_repo("https://github.com/user/repo")

    assert repo.full_name == "user/repo"
    assert repo.description == ""
    assert repo.readme == ""

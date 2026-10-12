import re
from dataclasses import dataclass

import httpx

from config import GITHUB_TOKEN

GITHUB_URL_PATTERN = re.compile(
    r"https?://github\.com/([^/\s]+)/([^/\s#?]+)"
)

README_MAX_CHARS = 12_000


@dataclass
class RepoData:
    owner: str
    repo: str
    full_name: str  # owner/repo
    description: str
    stars: int
    language: str
    readme: str  # raw markdown, truncated


def parse_github_url(url: str) -> tuple[str, str]:
    """從 GitHub URL 解析 owner 和 repo 名稱。"""
    m = GITHUB_URL_PATTERN.search(url)
    if not m:
        raise ValueError(f"無法解析 GitHub URL: {url}")
    owner, repo = m.group(1), m.group(2)
    # 移除 .git 後綴
    if repo.endswith(".git"):
        repo = repo[:-4]
    return owner, repo


async def fetch_repo(url: str) -> RepoData:
    """透過 GitHub REST API 取得 repo 資訊與 README。"""
    owner, repo = parse_github_url(url)

    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    async with httpx.AsyncClient(timeout=30) as client:
        # 取得 repo metadata
        resp = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}",
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()

        # 取得 README（raw markdown）
        readme = ""
        try:
            readme_resp = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/readme",
                headers={**headers, "Accept": "application/vnd.github.raw+json"},
            )
            if readme_resp.status_code == 200:
                readme = readme_resp.text[:README_MAX_CHARS]
        except httpx.HTTPError:
            pass

    return RepoData(
        owner=owner,
        repo=repo,
        full_name=data.get("full_name", f"{owner}/{repo}"),
        description=data.get("description") or "",
        stars=data.get("stargazers_count", 0),
        language=data.get("language") or "",
        readme=readme,
    )

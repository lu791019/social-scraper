import re
import logging

logger = logging.getLogger(__name__)

# 支援的平台 URL pattern
SUPPORTED_URL_PATTERN = re.compile(
    r"https?://(?:www\.)?"
    r"(?:instagram\.com|threads\.net|threads\.com)"
    r"/\S+"
)

GITHUB_URL_PATTERN = re.compile(
    r"https?://github\.com/[^/\s]+/[^/\s#?]+"
)

GENERAL_URL_PATTERN = re.compile(r"https?://\S+")


def extract_urls(text: str) -> list[str]:
    """從訊息文字中提取所有支援平台的 URL"""
    return SUPPORTED_URL_PATTERN.findall(text)


def extract_github_urls(text: str) -> list[str]:
    """從訊息文字中提取所有 GitHub repo URL"""
    return GITHUB_URL_PATTERN.findall(text)


def is_supported_url(url: str) -> bool:
    """檢查 URL 是否為支援的平台"""
    return bool(SUPPORTED_URL_PATTERN.match(url))


def is_github_url(url: str) -> bool:
    """檢查 URL 是否為 GitHub repo"""
    return bool(GITHUB_URL_PATTERN.match(url))


def extract_general_urls(text: str) -> list[str]:
    """提取非 IG/Threads/GitHub 的一般 URL"""
    all_urls = GENERAL_URL_PATTERN.findall(text)
    return [
        url for url in all_urls
        if not SUPPORTED_URL_PATTERN.match(url)
        and not GITHUB_URL_PATTERN.match(url)
    ]

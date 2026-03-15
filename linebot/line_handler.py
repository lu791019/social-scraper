import re
import logging

logger = logging.getLogger(__name__)

# 支援的平台 URL pattern
SUPPORTED_URL_PATTERN = re.compile(
    r"https?://(?:www\.)?"
    r"(?:instagram\.com|threads\.net|threads\.com)"
    r"/\S+"
)


def extract_urls(text: str) -> list[str]:
    """從訊息文字中提取所有支援平台的 URL"""
    return SUPPORTED_URL_PATTERN.findall(text)


def is_supported_url(url: str) -> bool:
    """檢查 URL 是否為支援的平台"""
    return bool(SUPPORTED_URL_PATTERN.match(url))

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Google Sheet
GOOGLE_SHEET_URL = os.environ["GOOGLE_SHEET_URL"]
GOOGLE_CREDENTIALS_PATH = Path(os.environ.get(
    "GOOGLE_CREDENTIALS_PATH", "credentials.json"
))

# Claude CLI path
CLAUDE_CLI = os.environ.get("CLAUDE_CLI", "claude")

# Whisper model (mlx-whisper)
WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "mlx-community/whisper-large-v3-turbo")

# Scraper settings
DAILY_LIMIT = 30
REQUEST_DELAY_MIN = 3.0
REQUEST_DELAY_MAX = 8.0
PAGE_TIMEOUT_MS = 30_000
MAX_RETRIES = 1

# Proxy (None for MVP)
PROXY_URL: str | None = os.environ.get("PROXY_URL")

# LINE Bot
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "")
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")

# GitHub (optional, unauthenticated = 60 req/hr)
GITHUB_TOKEN: str | None = os.environ.get("GITHUB_TOKEN")

# Temp directory for video downloads
TEMP_DIR = Path("/tmp/social-scraper")

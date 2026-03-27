import textwrap
from datetime import date

import gspread
from config import GOOGLE_SHEET_URL, GOOGLE_CREDENTIALS_PATH

_worksheet: gspread.Worksheet | None = None
_github_worksheet: gspread.Worksheet | None = None

GITHUB_HEADERS = ["Repo URL", "Repo 名稱", "官方說明", "README 中文摘要",
                  "使用情境", "星數/語言", "日期"]


def get_worksheet() -> gspread.Worksheet:
    global _worksheet
    if _worksheet is None:
        gc = gspread.service_account(filename=str(GOOGLE_CREDENTIALS_PATH))
        spreadsheet = gc.open_by_url(GOOGLE_SHEET_URL)
        _worksheet = spreadsheet.sheet1
    return _worksheet


def get_pending_rows() -> list[tuple[int, str]]:
    """找出 A 欄有值但 B 欄為空的列，回傳 (row_number, url) 列表"""
    ws = get_worksheet()
    rows = ws.get_all_values()

    pending = []
    for i, row in enumerate(rows[1:], start=2):
        url = row[0].strip() if len(row) > 0 else ""
        summary = row[1].strip() if len(row) > 1 else ""
        if url and not summary:
            pending.append((i, url))
    return pending


def wrap_text(text: str, width: int = 40) -> str:
    """在固定字數處換行，保留原有換行"""
    lines = text.split("\n")
    wrapped = []
    for line in lines:
        if len(line) <= width:
            wrapped.append(line)
        else:
            wrapped.extend(textwrap.fill(line, width=width).split("\n"))
    return "\n".join(wrapped)


def write_result(row_num: int, summary: str, key_points: str) -> None:
    """將摘要寫入 B 欄、關鍵點寫入 C 欄、日期寫入 D 欄"""
    ws = get_worksheet()
    ws.update_cell(row_num, 2, wrap_text(summary))
    ws.update_cell(row_num, 3, wrap_text(key_points))
    ws.update_cell(row_num, 4, date.today().isoformat())


def write_error(row_num: int, error_msg: str) -> None:
    """將錯誤訊息寫入 B 欄"""
    ws = get_worksheet()
    ws.update_cell(row_num, 2, f"[ERROR] {error_msg}")


def _get_spreadsheet() -> gspread.Spreadsheet:
    gc = gspread.service_account(filename=str(GOOGLE_CREDENTIALS_PATH))
    return gc.open_by_url(GOOGLE_SHEET_URL)


def get_github_worksheet() -> gspread.Worksheet:
    """取得或自動建立 GitHub 工作表"""
    global _github_worksheet
    if _github_worksheet is None:
        spreadsheet = _get_spreadsheet()
        try:
            _github_worksheet = spreadsheet.worksheet("GitHub")
        except gspread.exceptions.WorksheetNotFound:
            _github_worksheet = spreadsheet.add_worksheet(
                title="GitHub", rows=1000, cols=7
            )
            _github_worksheet.append_row(GITHUB_HEADERS)
    return _github_worksheet


def get_github_pending_rows() -> list[tuple[int, str]]:
    """GitHub 工作表：A 欄有 URL 但 B 欄為空的列"""
    ws = get_github_worksheet()
    rows = ws.get_all_values()
    pending = []
    for i, row in enumerate(rows[1:], start=2):
        url = row[0].strip() if len(row) > 0 else ""
        name = row[1].strip() if len(row) > 1 else ""
        if url and not name:
            pending.append((i, url))
    return pending


def append_github_repo(url: str) -> int:
    """將 GitHub URL 寫入 GitHub 工作表 A 欄的下一個空行"""
    ws = get_github_worksheet()
    rows = ws.get_all_values()
    next_row = len(rows) + 1
    ws.update_cell(next_row, 1, url)
    return next_row


def write_github_result(
    row_num: int,
    full_name: str,
    description: str,
    summary: str,
    use_cases: str,
    stars_language: str,
) -> None:
    """將 GitHub repo 結果寫入 B~G 欄"""
    ws = get_github_worksheet()
    ws.update_cell(row_num, 2, full_name)
    ws.update_cell(row_num, 3, wrap_text(description))
    ws.update_cell(row_num, 4, wrap_text(summary))
    ws.update_cell(row_num, 5, wrap_text(use_cases))
    ws.update_cell(row_num, 6, stars_language)
    ws.update_cell(row_num, 7, date.today().isoformat())


def write_github_error(row_num: int, error_msg: str) -> None:
    """將錯誤訊息寫入 GitHub 工作表 B 欄"""
    ws = get_github_worksheet()
    ws.update_cell(row_num, 2, f"[ERROR] {error_msg}")


def append_url(url: str) -> int:
    """將 URL 寫入 Sheet A 欄的下一個空行，回傳寫入的列號"""
    ws = get_worksheet()
    rows = ws.get_all_values()
    next_row = len(rows) + 1
    ws.update_cell(next_row, 1, url)
    return next_row

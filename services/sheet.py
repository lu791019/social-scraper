import gspread
from config import GOOGLE_SHEET_URL, GOOGLE_CREDENTIALS_PATH

_worksheet: gspread.Worksheet | None = None


def get_worksheet() -> gspread.Worksheet:
    global _worksheet
    if _worksheet is None:
        gc = gspread.service_account(filename=str(GOOGLE_CREDENTIALS_PATH))
        spreadsheet = gc.open_by_url(GOOGLE_SHEET_URL)
        _worksheet = spreadsheet.sheet1
    return _worksheet


def get_pending_rows() -> list[tuple[int, str]]:
    """找出 A 欄有值但 C 欄為空的列，回傳 (row_number, url) 列表"""
    ws = get_worksheet()
    rows = ws.get_all_values()

    pending = []
    for i, row in enumerate(rows[1:], start=2):
        url = row[0].strip() if len(row) > 0 else ""
        summary = row[2].strip() if len(row) > 2 else ""
        if url and not summary:
            pending.append((i, url))
    return pending


def write_result(row_num: int, raw_content: str, summary: str) -> None:
    """將原始內容寫入 B 欄、摘要寫入 C 欄"""
    ws = get_worksheet()
    ws.update_cell(row_num, 2, raw_content)
    ws.update_cell(row_num, 3, summary)


def write_error(row_num: int, error_msg: str) -> None:
    """將錯誤訊息寫入 C 欄"""
    ws = get_worksheet()
    ws.update_cell(row_num, 3, f"[ERROR] {error_msg}")

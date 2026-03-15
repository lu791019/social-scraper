import pytest
from unittest.mock import MagicMock, patch
from services.sheet import get_pending_rows, write_result, write_error, wrap_text, append_url


@patch("services.sheet.get_worksheet")
def test_get_pending_rows_finds_empty_b_column(mock_ws):
    """Scenario: A 欄有值但 B 欄為空 → 待處理"""
    mock_ws.return_value.get_all_values.return_value = [
        ["社群連結", "AI 摘要"],
        ["https://instagram.com/p/abc", ""],
        ["https://threads.net/@user/post/xyz", "已有摘要"],
        ["https://instagram.com/p/def", ""],
        ["", ""],
    ]
    pending = get_pending_rows()
    assert len(pending) == 2
    assert pending[0] == (2, "https://instagram.com/p/abc")
    assert pending[1] == (4, "https://instagram.com/p/def")


@patch("services.sheet.get_worksheet")
def test_get_pending_rows_returns_empty_for_all_processed(mock_ws):
    """Scenario: 所有列都已處理 → 空列表"""
    mock_ws.return_value.get_all_values.return_value = [
        ["社群連結", "AI 摘要"],
        ["https://instagram.com/p/abc", "摘要"],
    ]
    pending = get_pending_rows()
    assert len(pending) == 0


@patch("services.sheet.date")
@patch("services.sheet.get_worksheet")
def test_write_result_updates_b_c_d_columns(mock_ws, mock_date):
    """Scenario: 摘要寫入 B 欄、關鍵點寫入 C 欄、日期寫入 D 欄"""
    mock_date.today.return_value.isoformat.return_value = "2026-02-20"
    mock_worksheet = MagicMock()
    mock_ws.return_value = mock_worksheet
    write_result(2, summary="短摘要", key_points="• 重點一")
    mock_worksheet.update_cell.assert_any_call(2, 2, "短摘要")
    mock_worksheet.update_cell.assert_any_call(2, 3, "• 重點一")
    mock_worksheet.update_cell.assert_any_call(2, 4, "2026-02-20")


@patch("services.sheet.get_worksheet")
def test_write_error_marks_b_column(mock_ws):
    """Scenario: 錯誤訊息寫入 B 欄"""
    mock_worksheet = MagicMock()
    mock_ws.return_value = mock_worksheet
    write_error(2, "載入逾時")
    mock_worksheet.update_cell.assert_called_once_with(2, 2, "[ERROR] 載入逾時")


def test_wrap_text_short_text_unchanged():
    assert wrap_text("短文字", width=40) == "短文字"


def test_wrap_text_long_text_wraps():
    text = "這是一段超過四十個字的長文字，需要在適當的位置換行以確保在試算表中的可讀性良好"
    result = wrap_text(text, width=40)
    for line in result.split("\n"):
        assert len(line) <= 40


def test_wrap_text_preserves_existing_newlines():
    text = "第一行\n第二行"
    result = wrap_text(text, width=40)
    assert "第一行" in result
    assert "第二行" in result
    assert result.count("\n") >= 1


@patch("services.sheet.get_worksheet")
def test_append_url_writes_to_next_empty_row(mock_ws):
    """Scenario: URL 寫入 A 欄下一個空行"""
    mock_worksheet = MagicMock()
    mock_worksheet.get_all_values.return_value = [
        ["社群連結", "AI 摘要"],
        ["https://instagram.com/p/abc", "摘要"],
    ]
    mock_ws.return_value = mock_worksheet
    row_num = append_url("https://instagram.com/p/new")
    assert row_num == 3
    mock_worksheet.update_cell.assert_called_once_with(3, 1, "https://instagram.com/p/new")

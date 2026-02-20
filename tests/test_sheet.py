import pytest
from unittest.mock import MagicMock, patch
from services.sheet import get_pending_rows, write_result, write_error


@patch("services.sheet.get_worksheet")
def test_get_pending_rows_finds_empty_c_column(mock_ws):
    """Scenario: A 欄有值但 C 欄為空 → 待處理"""
    mock_ws.return_value.get_all_values.return_value = [
        ["社群連結", "原始內容", "AI 摘要"],
        ["https://instagram.com/p/abc", "", ""],
        ["https://threads.net/@user/post/xyz", "已有內容", "已有摘要"],
        ["https://instagram.com/p/def", "", ""],
        ["", "", ""],
    ]
    pending = get_pending_rows()
    assert len(pending) == 2
    assert pending[0] == (2, "https://instagram.com/p/abc")
    assert pending[1] == (4, "https://instagram.com/p/def")


@patch("services.sheet.get_worksheet")
def test_get_pending_rows_returns_empty_for_all_processed(mock_ws):
    """Scenario: 所有列都已處理 → 空列表"""
    mock_ws.return_value.get_all_values.return_value = [
        ["社群連結", "原始內容", "AI 摘要"],
        ["https://instagram.com/p/abc", "內容", "摘要"],
    ]
    pending = get_pending_rows()
    assert len(pending) == 0


@patch("services.sheet.get_worksheet")
def test_write_result_updates_b_and_c_columns(mock_ws):
    """Scenario: 寫入結果到 B 欄和 C 欄"""
    mock_worksheet = MagicMock()
    mock_ws.return_value = mock_worksheet
    write_result(2, raw_content="原始文字", summary="AI 摘要")
    mock_worksheet.update_cell.assert_any_call(2, 2, "原始文字")
    mock_worksheet.update_cell.assert_any_call(2, 3, "AI 摘要")


@patch("services.sheet.get_worksheet")
def test_write_error_marks_c_column(mock_ws):
    """Scenario: 錯誤訊息寫入 C 欄"""
    mock_worksheet = MagicMock()
    mock_ws.return_value = mock_worksheet
    write_error(2, "載入逾時")
    mock_worksheet.update_cell.assert_called_once_with(2, 3, "[ERROR] 載入逾時")

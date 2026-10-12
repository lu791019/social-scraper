import pytest
from scraper.browser import random_ua, random_viewport, VIEWPORTS, USER_AGENTS


def test_random_ua_returns_string_from_pool():
    ua = random_ua()
    assert ua in USER_AGENTS
    assert "Mozilla" in ua


def test_random_viewport_returns_valid_dict():
    vp = random_viewport()
    assert "width" in vp and "height" in vp
    assert vp in VIEWPORTS


def test_ua_pool_has_multiple_entries():
    assert len(USER_AGENTS) >= 5


def test_viewport_pool_has_multiple_entries():
    assert len(VIEWPORTS) >= 3


from scraper.browser import explain_navigation_error  # noqa: E402


def test_explain_cert_error_as_network_block():
    msg = explain_navigation_error(Exception("Page.goto: net::ERR_CERT_AUTHORITY_INVALID at https://www.instagram.com/p/x/"))
    assert "網路" in msg and "攔截" in msg


def test_explain_other_errors_passthrough():
    assert explain_navigation_error(Exception("Timeout 30000ms exceeded")) is None

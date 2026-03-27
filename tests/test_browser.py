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

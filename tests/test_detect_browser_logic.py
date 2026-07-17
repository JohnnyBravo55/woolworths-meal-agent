"""Mirror of apps/mobile/lib/detect-browser.ts — keep UA rules in sync manually."""

import re


def detect_browser(ua: str) -> str:
    if re.search(r"firefox|fxios", ua, re.I):
        return "firefox"
    if re.search(r"edg/", ua, re.I):
        return "edge"
    if re.search(r"chrome|chromium|crios", ua, re.I) and not re.search(r"edg/", ua, re.I):
        return "chrome"
    if re.search(r"safari", ua, re.I) and not re.search(
        r"chrome|chromium|crios|android", ua, re.I
    ):
        return "safari"
    return "other"


def test_detect_chrome():
    assert (
        detect_browser(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        )
        == "chrome"
    )


def test_detect_edge():
    assert (
        detect_browser(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0"
        )
        == "edge"
    )


def test_detect_firefox():
    assert (
        detect_browser("Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0")
        == "firefox"
    )


def test_detect_safari():
    assert (
        detect_browser(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/17.5 Safari/605.1.15"
        )
        == "safari"
    )

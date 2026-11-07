"""Unit tests for protocol registration and Moodle token extraction."""

from canvas_track.protocol import build_moodle_sso_url, extract_moodle_token


def test_extract_moodle_token_from_full_url() -> None:
    # Full moodlemobile URL with base64 encoded payload
    url = (
        "moodlemobile://token="
        "YThhNzA2YTk3ZWVjNjkzMzkyNjY5MzZhNGQxZjc0N2E6Ojo2YWI3MmQyNDkyMmQwYTUwNzU4MmY2NWZkM2JlYWZkZA=="
    )
    token = extract_moodle_token(url)
    assert token == "6ab72d24922d0a507582f65fd3beafdd"


def test_extract_moodle_token_from_canvastrack_scheme() -> None:
    # canvastrack:// URL
    url = (
        "canvastrack://token="
        "YThhNzA2YTk3ZWVjNjkzMzkyNjY5MzZhNGQxZjc0N2E6Ojo2YWI3MmQyNDkyMmQwYTUwNzU4MmY2NWZkM2JlYWZkZA=="
    )
    token = extract_moodle_token(url)
    assert token == "6ab72d24922d0a507582f65fd3beafdd"


def test_extract_moodle_token_from_delimited_string() -> None:
    raw = "a8a706a97eec69339266936a4d1f747a:::6ab72d24922d0a507582f65fd3beafdd"
    token = extract_moodle_token(raw)
    assert token == "6ab72d24922d0a507582f65fd3beafdd"


def test_extract_moodle_token_from_three_part_delimited() -> None:
    raw = "https://moodle.lnu.se:::6ab72d24922d0a507582f65fd3beafdd:::private12345"
    token = extract_moodle_token(raw)
    assert token == "6ab72d24922d0a507582f65fd3beafdd"


def test_extract_moodle_token_from_plain_hex() -> None:
    raw = "6ab72d24922d0a507582f65fd3beafdd"
    token = extract_moodle_token(raw)
    assert token == "6ab72d24922d0a507582f65fd3beafdd"


def test_build_moodle_sso_url() -> None:
    url = build_moodle_sso_url("moodle.lnu.se")
    assert "https://moodle.lnu.se/admin/tool/mobile/launch.php" in url
    assert "urlscheme=canvastrack" in url
    assert "service=moodle_mobile_app" in url

"""Unit tests for protocol registration and Moodle token extraction."""

from canvas_track.protocol import build_moodle_sso_url, extract_moodle_token


def test_extract_moodle_token_from_full_url() -> None:
    # Full moodlemobile URL with base64 encoded payload
    url = (
        "moodlemobile://token="
        "ZHVtbXlfcHJpdmF0ZV90b2tlbjo6OjAxMjM0NTY3ODlhYmNkZWYwMTIzNDU2Nzg5YWJjZGVm"
    )
    token = extract_moodle_token(url)
    assert token == "0123456789abcdef0123456789abcdef"


def test_extract_moodle_token_from_canvastrack_scheme() -> None:
    # canvastrack:// URL
    url = (
        "canvastrack://token="
        "ZHVtbXlfcHJpdmF0ZV90b2tlbjo6OjAxMjM0NTY3ODlhYmNkZWYwMTIzNDU2Nzg5YWJjZGVm"
    )
    token = extract_moodle_token(url)
    assert token == "0123456789abcdef0123456789abcdef"


def test_extract_moodle_token_from_delimited_string() -> None:
    raw = "dummy_private_token:::0123456789abcdef0123456789abcdef"
    token = extract_moodle_token(raw)
    assert token == "0123456789abcdef0123456789abcdef"


def test_extract_moodle_token_from_three_part_delimited() -> None:
    raw = "https://moodle.example.edu:::0123456789abcdef0123456789abcdef:::private12345"
    token = extract_moodle_token(raw)
    assert token == "0123456789abcdef0123456789abcdef"


def test_extract_moodle_token_from_plain_hex() -> None:
    raw = "0123456789abcdef0123456789abcdef"
    token = extract_moodle_token(raw)
    assert token == "0123456789abcdef0123456789abcdef"


def test_build_moodle_sso_url() -> None:
    url = build_moodle_sso_url("moodle.example.edu")
    assert "https://moodle.example.edu/admin/tool/mobile/launch.php" in url
    assert "urlscheme=canvastrack" in url
    assert "service=moodle_mobile_app" in url

"""Unit tests for CanvasClient URL parsing and header handling."""

import pytest
from canvas_track.client import CanvasClient, parse_link_header
from canvas_track.rewriter import CanvasLinkRewriter


def test_parse_link_header() -> None:
    header = (
        '<https://canvas.ltu.se/api/v1/courses?page=1&per_page=10>; rel="current", '
        '<https://canvas.ltu.se/api/v1/courses?page=2&per_page=10>; rel="next", '
        '<https://canvas.ltu.se/api/v1/courses?page=1&per_page=10>; rel="first", '
        '<https://canvas.ltu.se/api/v1/courses?page=5&per_page=10>; rel="last"'
    )
    links = parse_link_header(header)
    assert links.get("next") == "https://canvas.ltu.se/api/v1/courses?page=2&per_page=10"
    assert links.get("first") == "https://canvas.ltu.se/api/v1/courses?page=1&per_page=10"
    assert links.get("last") == "https://canvas.ltu.se/api/v1/courses?page=5&per_page=10"


def test_canvas_client_url_normalization() -> None:
    client = CanvasClient("canvas.ltu.se", "test-token")
    assert client.base_url == "https://canvas.ltu.se"
    assert client.api_url == "https://canvas.ltu.se/api/v1"

    client2 = CanvasClient("https://canvas.instructure.com/", "test-token")
    assert client2.base_url == "https://canvas.instructure.com"
    assert client2.api_url == "https://canvas.instructure.com/api/v1"


def test_canvas_link_rewriter() -> None:
    rewriter = CanvasLinkRewriter(site_id="ltu", course_id=29010, base_domain="canvas.ltu.se")
    raw_html = (
        '<p>Check out <a href="/courses/29010/pages/week-1-introduction">Week 1</a> and '
        '<a href="https://canvas.ltu.se/courses/29010/assignments/55443">Assignment 1</a>.</p>'
        '<p>Also file: <a href="/courses/29010/files/88776/download">Slides</a></p>'
    )
    rewritten = rewriter.rewrite_html(raw_html)
    assert "#/site/ltu/course/29010/pages/week-1-introduction" in rewritten
    assert "#/site/ltu/course/29010/assignments/55443" in rewritten
    assert "/api/vault/files/ltu/29010/88776" in rewritten

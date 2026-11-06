"""Unit tests for FastAPI endpoints in Canvas Track."""

from pathlib import Path

from fastapi.testclient import TestClient

from canvas_track.models import CourseMeta, SiteConfig
from canvas_track.server import create_app
from canvas_track.vault import VaultManager


def test_api_sites_and_vault(tmp_path: Path) -> None:
    vault = VaultManager(tmp_path)
    site = SiteConfig(
        id="ltu",
        domain="canvas.ltu.se",
        base_url="https://canvas.ltu.se",
        user_name="Student Test",
        user_id=12345,
        token="mock_token",
    )
    vault.save_site(site)

    # Save a course with a front page and a normal page
    meta = CourseMeta(
        course_id=29010,
        course_name="Advanced Data Mining",
        default_view="wiki",
        front_page_url="home-slug",
        front_page_title="Course Home",
        total_pages=2,
    )
    vault.save_course_meta("ltu", 29010, meta)

    vault.save_front_page(
        "ltu",
        29010,
        {
            "url": "home-slug",
            "title": "Course Home",
            "body": '<p>Welcome! See <a href="/courses/29010/pages/week-1">Week 1</a>.</p>',
            "front_page": True,
        },
    )

    vault.save_page(
        "ltu",
        29010,
        "week-1",
        {
            "url": "week-1",
            "title": "Week 1",
            "body": (
                '<p>Content of week 1 with file: '
                '<a href="/courses/29010/files/999/download">Lecture</a></p>'
            ),
            "front_page": False,
        },
    )

    app = create_app(tmp_path)
    client = TestClient(app)

    # Test list sites
    resp = client.get("/api/sites")
    assert resp.status_code == 200
    sites = resp.json()
    assert len(sites) == 1
    assert sites[0]["id"] == "ltu"
    assert sites[0]["user_name"] == "Student Test"

    # Test list vault courses
    resp = client.get("/api/vault/sites/ltu/courses")
    assert resp.status_code == 200
    courses = resp.json()
    assert len(courses) == 1
    assert courses[0]["course_name"] == "Advanced Data Mining"

    # Test get front page with rewritten HTML
    resp = client.get("/api/vault/courses/ltu/29010/front_page")
    assert resp.status_code == 200
    fp_data = resp.json()
    assert fp_data["title"] == "Course Home"
    assert "#/site/ltu/course/29010/pages/week-1" in fp_data["body_rewritten"]

    # Test get page with rewritten file link
    resp = client.get("/api/vault/courses/ltu/29010/pages/week-1")
    assert resp.status_code == 200
    page_data = resp.json()
    assert page_data["title"] == "Week 1"
    assert "/api/vault/files/ltu/29010/999" in page_data["body_rewritten"]

"""Unit tests for VaultManager storage operations."""

from pathlib import Path

from canvas_track.models import CourseMeta, SiteConfig
from canvas_track.vault import VaultManager


def test_vault_site_management(tmp_path: Path) -> None:
    vault = VaultManager(tmp_path)
    site = SiteConfig(
        id="test_site",
        domain="canvas.example.edu",
        base_url="https://canvas.example.edu",
        user_name="Test Student",
        user_id=123,
        token="test_token_123",
    )
    vault.save_site(site)

    sites = vault.list_sites()
    assert len(sites) == 1
    assert sites[0].id == "test_site"
    assert sites[0].user_name == "Test Student"

    retrieved = vault.get_site("test_site")
    assert retrieved is not None
    assert retrieved.domain == "canvas.example.edu"


def test_vault_course_and_pages_storage(tmp_path: Path) -> None:
    vault = VaultManager(tmp_path)
    site_id = "test_site"
    course_id = 9999

    meta = CourseMeta(
        course_id=course_id,
        course_name="Machine Learning 101",
        default_view="wiki",
        front_page_url="welcome-to-ml",
        front_page_title="Welcome to ML",
        total_pages=2,
    )
    vault.save_course_meta(site_id, course_id, meta)

    # Verify CourseMeta retrieval
    loaded_meta = vault.get_course_meta(site_id, course_id)
    assert loaded_meta is not None
    assert loaded_meta.course_name == "Machine Learning 101"
    assert loaded_meta.default_view == "wiki"

    # Save front page
    front_page_data = {
        "url": "welcome-to-ml",
        "title": "Welcome to ML",
        "body": "<h1>Welcome</h1><p>Course overview here.</p>",
        "front_page": True,
    }
    vault.save_front_page(site_id, course_id, front_page_data)

    # Save second page
    page2_data = {
        "url": "week-1-linear-regression",
        "title": "Week 1: Linear Regression",
        "body": "<p>Math details...</p>",
        "front_page": False,
    }
    vault.save_page(site_id, course_id, "week-1-linear-regression", page2_data)

    # Retrieve front page
    fp = vault.get_front_page(site_id, course_id)
    assert fp is not None
    assert fp["url"] == "welcome-to-ml"
    assert "Course overview here" in fp["body"]

    # Retrieve individual page
    p2 = vault.get_page(site_id, course_id, "week-1-linear-regression")
    assert p2 is not None
    assert p2["title"] == "Week 1: Linear Regression"

    # List archived courses
    archived = vault.list_archived_courses(site_id)
    assert len(archived) == 1
    assert archived[0].course_id == course_id

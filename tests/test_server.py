"""Unit tests for FastAPI endpoints in Canvas Track."""

from pathlib import Path

import pytest
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
        user_id=225205,
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
                "<p>Content of week 1 with file: "
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

    # Test list sync jobs endpoint
    resp = client.get("/api/sync/jobs")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

    # Test delete vault course endpoint
    resp = client.delete("/api/vault/courses/ltu/29010")
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    # Course should now be gone from vault
    resp = client.get("/api/vault/courses/ltu/29010")
    assert resp.status_code == 404

    # Second delete returns 404
    resp = client.delete("/api/vault/courses/ltu/29010")
    assert resp.status_code == 404


def test_api_vault_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vault = VaultManager(tmp_path)
    site = SiteConfig(
        id="ltu",
        domain="canvas.ltu.se",
        base_url="https://canvas.ltu.se",
        user_name="Student Test",
        user_id=225205,
        token="mock_token",
    )
    vault.save_site(site)

    # Save folders and files
    vault.save_folders_metadata(
        "ltu",
        29010,
        [{"id": 1, "full_name": "course files/Lectures"}],
    )
    vault.save_files_metadata(
        "ltu",
        29010,
        [
            {
                "id": 999,
                "display_name": "lecture.pdf",
                "folder_id": 1,
                "content_type": "application/pdf",
                "size": 12,
            }
        ],
    )

    # Create dummy file on disk
    files_dir = vault.get_files_dir("ltu", 29010)
    pdf_path = files_dir / "Lectures" / "lecture.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_text("dummy pdf", encoding="utf-8")

    app = create_app(tmp_path)
    client = TestClient(app)

    # Test list files
    resp = client.get("/api/vault/courses/ltu/29010/files")
    assert resp.status_code == 200
    files_list = resp.json()
    assert len(files_list) == 1
    assert files_list[0]["id"] == 999
    assert files_list[0]["is_downloaded"] is True

    # Test serve file
    resp = client.get("/api/vault/files/ltu/29010/999")
    assert resp.status_code == 200
    assert resp.content == b"dummy pdf"
    assert resp.headers.get("content-type") == "application/pdf"

    # Test open file with system viewer
    opened_paths: list[str] = []
    import os

    if hasattr(os, "startfile"):
        monkeypatch.setattr(os, "startfile", lambda p: opened_paths.append(str(p)))
    else:
        import subprocess

        monkeypatch.setattr(
            subprocess,
            "Popen",
            lambda cmd: opened_paths.append(cmd[1]),
        )

    resp = client.post("/api/vault/files/ltu/29010/999/open")
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    assert len(opened_paths) == 1
    assert "lecture.pdf" in opened_paths[0]

    # Test open non-existent file
    resp = client.post("/api/vault/files/ltu/29010/99999/open")
    assert resp.status_code == 404

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

    # Verify backup size
    size = vault.get_course_backup_size(site_id, course_id)
    assert size > 0

    # Delete local backup
    deleted = vault.delete_course_archive(site_id, course_id)
    assert deleted is True
    assert vault.get_course_meta(site_id, course_id) is None
    assert len(vault.list_archived_courses(site_id)) == 0

    # Second delete returns False (not found)
    assert vault.delete_course_archive(site_id, course_id) is False


def test_vault_site_deduplication_and_update(tmp_path: Path) -> None:
    vault = VaultManager(tmp_path)
    site1 = SiteConfig(
        id="ltu",
        domain="canvas.ltu.se",
        base_url="https://canvas.ltu.se",
        user_name="Student",
        user_id=225,
        token="tok1",
    )
    vault.save_site(site1)

    # Detect duplicate by domain + user_id
    dup = vault.find_duplicate_site("canvas.ltu.se", user_id=225, token="different_tok")
    assert dup is not None
    assert dup.id == "ltu"

    # Detect duplicate by token
    dup_tok = vault.find_duplicate_site("other.domain.com", user_id=999, token="tok1")
    assert dup_tok is not None
    assert dup_tok.id == "ltu"

    # Update site
    updated = vault.update_site("ltu", "ltu_new", "canvas.ltu.se", "tok_updated")
    assert updated.id == "ltu_new"
    assert updated.token == "tok_updated"
    assert vault.get_site("ltu_new") is not None

    # Test deduplication cleanup
    raw_config = {
        "sites": [
            {
                "id": "s1",
                "domain": "canvas.test",
                "base_url": "https://canvas.test",
                "user_id": 10,
                "token": "t1",
            },
            {
                "id": "s2",
                "domain": "canvas.test",
                "base_url": "https://canvas.test",
                "user_id": 10,
                "token": "t2",
            },  # dup user_id
            {
                "id": "s3",
                "domain": "canvas.other",
                "base_url": "https://canvas.other",
                "user_id": 20,
                "token": "t1",
            },  # dup token
        ]
    }
    vault._save_raw_json(vault.config_file, raw_config)
    removed = vault.deduplicate_sites()
    assert len(removed) == 2
    sites = vault.list_sites()
    assert len(sites) == 1
    assert sites[0].id == "s1"


def test_vault_page_comments(tmp_path: Path) -> None:
    vault = VaultManager(tmp_path)
    site_id = "test_site"
    course_id = 101
    page_url = "intro-page"

    # Initially empty
    comments = vault.get_page_comments(site_id, course_id, page_url)
    assert comments == []

    # Add comment
    c1 = vault.add_page_comment(site_id, course_id, page_url, "Remember to read chapter 1.")
    assert c1["text"] == "Remember to read chapter 1."
    assert "id" in c1
    assert "created_at" in c1

    # Add second comment
    c2 = vault.add_page_comment(site_id, course_id, page_url, "Exam date changed.")
    comments = vault.get_page_comments(site_id, course_id, page_url)
    assert len(comments) == 2

    # Delete first comment
    deleted = vault.delete_page_comment(site_id, course_id, page_url, c1["id"])
    assert deleted is True

    comments = vault.get_page_comments(site_id, course_id, page_url)
    assert len(comments) == 1
    assert comments[0]["id"] == c2["id"]

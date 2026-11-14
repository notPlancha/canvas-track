"""Unit tests for FastAPI Moodle site endpoints and SSO callback handling."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from canvas_track.server import create_app
from canvas_track.vault import VaultManager


def test_add_and_list_moodle_site(tmp_path: Path) -> None:
    app = create_app(tmp_path)
    client = TestClient(app)

    mock_info = {
        "sitename": "Example Moodle",
        "username": "student_user",
        "firstname": "Student",
        "lastname": "User",
        "fullname": "Student User",
        "userid": 12345,
    }

    with patch("canvas_track.server.MoodleClient") as mock_client_cls:
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        mock_instance.base_url = "https://moodle.example.edu"
        mock_instance.get_site_info.return_value = mock_info
        mock_client_cls.return_value = mock_instance

        # Test adding Moodle site using a moodlemobile:// URL with base64 token
        payload = {
            "domain": "moodle.example.edu",
            "token": "moodlemobile://token=ZHVtbXlfcHJpdmF0ZV90b2tlbjo6OjAxMjM0NTY3ODlhYmNkZWYwMTIzNDU2Nzg5YWJjZGVm",
            "site_id": "example_moodle",
            "platform": "moodle",
        }
        res = client.post("/api/sites", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["site"]["id"] == "example_moodle"
        assert data["site"]["platform"] == "moodle"
        assert data["site"]["user_name"] == "Student User"
        assert data["site"]["token"] == "0123456789abcdef0123456789abcdef"

        # List sites and verify platform is moodle
        res_list = client.get("/api/sites")
        assert res_list.status_code == 200
        sites = res_list.json()
        assert len(sites) == 1
        assert sites[0]["platform"] == "moodle"


def test_list_remote_moodle_courses(tmp_path: Path) -> None:
    app = create_app(tmp_path)
    client = TestClient(app)
    vault = VaultManager(tmp_path)

    from canvas_track.models import SiteConfig

    vault.save_site(
        SiteConfig(
            id="example_moodle",
            domain="moodle.example.edu",
            base_url="https://moodle.example.edu",
            platform="moodle",
            user_name="Student User",
            user_id=12345,
            token="0123456789abcdef0123456789abcdef",
        )
    )

    with patch("canvas_track.server.MoodleClient") as mock_client_cls:
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        mock_instance.list_courses.return_value = [
            {
                "id": 73674,
                "fullname": "Advanced Data Visualization",
                "shortname": "4NA035",
            }
        ]
        mock_client_cls.return_value = mock_instance

        res = client.get("/api/sites/example_moodle/courses")
        assert res.status_code == 200
        courses = res.json()
        assert len(courses) == 1
        assert courses[0]["id"] == 73674
        assert courses[0]["name"] == "Advanced Data Visualization"
        assert courses[0]["default_view"] == "modules"


def test_moodle_sso_url_and_callback(tmp_path: Path) -> None:
    app = create_app(tmp_path)
    client = TestClient(app)

    # 1. Get SSO launch URL
    res_url = client.get("/api/auth/moodle-sso-url?domain=moodle.example.edu")
    assert res_url.status_code == 200
    assert "https://moodle.example.edu/admin/tool/mobile/launch.php" in res_url.json()["url"]
    assert "urlscheme=canvastrack" in res_url.json()["url"]

    # 2. Post callback from OS protocol handler
    mock_info = {
        "sitename": "Example Moodle",
        "username": "student_user",
        "fullname": "Student User",
        "userid": 12345,
    }

    with patch("canvas_track.server.MoodleClient") as mock_client_cls:
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        mock_instance.get_site_info.return_value = mock_info
        mock_client_cls.return_value = mock_instance

        cb_payload = {
            "url": "canvastrack://token=ZHVtbXlfcHJpdmF0ZV90b2tlbjo6OjAxMjM0NTY3ODlhYmNkZWYwMTIzNDU2Nzg5YWJjZGVm",
            "domain": "moodle.example.edu",
        }
        res_cb = client.post("/api/auth/moodle-callback", json=cb_payload)
        assert res_cb.status_code == 200
        assert res_cb.json()["success"] is True
        assert res_cb.json()["site"]["platform"] == "moodle"
        assert res_cb.json()["site"]["token"] == "0123456789abcdef0123456789abcdef"

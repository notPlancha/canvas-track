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
        "sitename": "Linnaeus Moodle",
        "username": "mp224ug",
        "firstname": "Mónica André",
        "lastname": "Plancha Fernandes",
        "fullname": "Mónica André Plancha Fernandes",
        "userid": 639977,
    }

    with patch("canvas_track.server.MoodleClient") as mock_client_cls:
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        mock_instance.base_url = "https://moodle.lnu.se"
        mock_instance.get_site_info.return_value = mock_info
        mock_client_cls.return_value = mock_instance

        # Test adding Moodle site using a moodlemobile:// URL with base64 token
        payload = {
            "domain": "moodle.lnu.se",
            "token": "moodlemobile://token=YThhNzA2YTk3ZWVjNjkzMzkyNjY5MzZhNGQxZjc0N2E6Ojo2YWI3MmQyNDkyMmQwYTUwNzU4MmY2NWZkM2JlYWZkZA==",
            "site_id": "lnu",
            "platform": "moodle",
        }
        res = client.post("/api/sites", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["site"]["id"] == "lnu"
        assert data["site"]["platform"] == "moodle"
        assert data["site"]["user_name"] == "Mónica André Plancha Fernandes"
        assert data["site"]["token"] == "6ab72d24922d0a507582f65fd3beafdd"

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
            id="lnu",
            domain="moodle.lnu.se",
            base_url="https://moodle.lnu.se",
            platform="moodle",
            user_name="Mónica",
            user_id=639977,
            token="6ab72d24922d0a507582f65fd3beafdd",
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

        res = client.get("/api/sites/lnu/courses")
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
    res_url = client.get("/api/auth/moodle-sso-url?domain=moodle.lnu.se")
    assert res_url.status_code == 200
    assert "https://moodle.lnu.se/admin/tool/mobile/launch.php" in res_url.json()["url"]
    assert "urlscheme=canvastrack" in res_url.json()["url"]

    # 2. Post callback from OS protocol handler
    mock_info = {
        "sitename": "Linnaeus Moodle",
        "username": "mp224ug",
        "fullname": "Mónica André Plancha Fernandes",
        "userid": 639977,
    }

    with patch("canvas_track.server.MoodleClient") as mock_client_cls:
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        mock_instance.get_site_info.return_value = mock_info
        mock_client_cls.return_value = mock_instance

        cb_payload = {
            "url": "canvastrack://token=YThhNzA2YTk3ZWVjNjkzMzkyNjY5MzZhNGQxZjc0N2E6Ojo2YWI3MmQyNDkyMmQwYTUwNzU4MmY2NWZkM2JlYWZkZA==",
            "domain": "moodle.lnu.se",
        }
        res_cb = client.post("/api/auth/moodle-callback", json=cb_payload)
        assert res_cb.status_code == 200
        assert res_cb.json()["success"] is True
        assert res_cb.json()["site"]["platform"] == "moodle"
        assert res_cb.json()["site"]["token"] == "6ab72d24922d0a507582f65fd3beafdd"

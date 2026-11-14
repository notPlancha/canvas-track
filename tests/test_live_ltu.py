"""Live read-only verification test for Canvas LMS course.

Tests read-only course synchronization, front page & wiki page retrieval,
link rewriting, and FastAPI server response.
"""

import asyncio
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from canvas_track.client import CanvasClient
from canvas_track.models import SiteConfig
from canvas_track.server import create_app
from canvas_track.sync import SyncEngine
from canvas_track.vault import VaultManager

CANVAS_DOMAIN = os.environ.get("CANVAS_DOMAIN", "canvas.example.edu")
CANVAS_TOKEN = os.environ.get("CANVAS_TOKEN")
COURSE_ID = int(os.environ.get("CANVAS_COURSE_ID", "12345"))
SITE_ID = os.environ.get("CANVAS_SITE_ID", "canvas_live")
EXPECTED_USER_ID = os.environ.get("CANVAS_EXPECTED_USER_ID")
EXPECTED_USER_NAME = os.environ.get("CANVAS_EXPECTED_USER_NAME")

if not CANVAS_TOKEN:
    pytest.skip(
        "CANVAS_TOKEN environment variable not set; skipping live Canvas test",
        allow_module_level=True,
    )


def test_live_canvas_read_only_sync_and_pages(tmp_path: Path) -> None:
    async def _test() -> None:
        vault = VaultManager(tmp_path)
        client = CanvasClient(CANVAS_DOMAIN, CANVAS_TOKEN)

        # 1. Verify read-only authentication
        user = await client.get_user_profile()
        assert user.id is not None
        assert user.name
        if EXPECTED_USER_ID:
            assert str(user.id) == str(EXPECTED_USER_ID)
        if EXPECTED_USER_NAME:
            assert EXPECTED_USER_NAME.lower() in user.name.lower()

        site = SiteConfig(
            id=SITE_ID,
            domain=CANVAS_DOMAIN,
            base_url=f"https://{CANVAS_DOMAIN}",
            user_name=user.name,
            user_id=user.id,
            token=CANVAS_TOKEN,
        )
        vault.save_site(site)

        # 2. Run read-only sync on target course
        sync_engine = SyncEngine(client, vault, SITE_ID)
        events = []

        async def on_event(evt: dict) -> None:
            events.append(evt)

        meta = await sync_engine.sync_course(
            course_id=COURSE_ID,
            progress_cb=on_event,
            download_files=False,  # Keep test swift, no binary file downloads
        )

        assert meta.course_id == COURSE_ID
        assert meta.default_view == "wiki"
        assert meta.front_page_url is not None
        assert meta.total_pages >= 1

        # 3. Verify front page stored in vault
        fp = vault.get_front_page(SITE_ID, COURSE_ID)
        assert fp is not None
        assert fp["url"] == meta.front_page_url
        assert bool(fp.get("body")) is True

        # 4. Verify wiki pages in vault
        pages = vault.get_pages_list(SITE_ID, COURSE_ID)
        assert len(pages) >= 1
        first_page = vault.get_page(SITE_ID, COURSE_ID, pages[0]["url"])
        assert first_page is not None
        assert "title" in first_page

        # 5. Verify FastAPI endpoints
        app = create_app(tmp_path)
        test_client = TestClient(app)

        # Test SPA index
        spa_resp = test_client.get("/")
        assert spa_resp.status_code == 200
        assert "html" in spa_resp.headers.get("content-type", "")

        # Test front page API
        fp_resp = test_client.get(f"/api/vault/courses/{SITE_ID}/{COURSE_ID}/front_page")
        assert fp_resp.status_code == 200
        fp_json = fp_resp.json()
        assert fp_json["url"] == meta.front_page_url
        assert "body_rewritten" in fp_json
        assert fp_json["body_rewritten"] is not None

        # Test pages list API
        pages_resp = test_client.get(f"/api/vault/courses/{SITE_ID}/{COURSE_ID}/pages")
        assert pages_resp.status_code == 200
        pages_json = pages_resp.json()
        assert len(pages_json) >= 1

    asyncio.run(_test())

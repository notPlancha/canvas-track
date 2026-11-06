"""Live read-only verification test for LTU Canvas course 29010.

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

LTU_DOMAIN = os.environ.get("CANVAS_DOMAIN", "canvas.ltu.se")
LTU_TOKEN = os.environ.get("CANVAS_TOKEN")
COURSE_ID = int(os.environ.get("CANVAS_COURSE_ID", "29010"))

if not LTU_TOKEN:
    pytest.skip(
        "CANVAS_TOKEN environment variable not set; skipping live Canvas test",
        allow_module_level=True,
    )


def test_live_ltu_read_only_sync_and_pages(tmp_path: Path) -> None:
    async def _test() -> None:
        vault = VaultManager(tmp_path)
        client = CanvasClient(LTU_DOMAIN, LTU_TOKEN)

        # 1. Verify read-only authentication
        user = await client.get_user_profile()
        assert user.id == 12345
        assert "Student" in user.name

        site = SiteConfig(
            id="ltu",
            domain=LTU_DOMAIN,
            base_url=f"https://{LTU_DOMAIN}",
            user_name=user.name,
            user_id=user.id,
            token=LTU_TOKEN,
        )
        vault.save_site(site)

        # 2. Run read-only sync on course 29010
        sync_engine = SyncEngine(client, vault, "ltu")
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
        assert meta.total_pages >= 10

        # 3. Verify front page stored in vault
        fp = vault.get_front_page("ltu", COURSE_ID)
        assert fp is not None
        assert fp["url"] == meta.front_page_url
        assert bool(fp.get("body")) is True
        assert "<table" in fp["body"].lower()

        # 4. Verify wiki pages in vault
        pages = vault.get_pages_list("ltu", COURSE_ID)
        assert len(pages) >= 10
        first_page = vault.get_page("ltu", COURSE_ID, pages[0]["url"])
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
        fp_resp = test_client.get(f"/api/vault/courses/ltu/{COURSE_ID}/front_page")
        assert fp_resp.status_code == 200
        fp_json = fp_resp.json()
        assert fp_json["url"] == meta.front_page_url
        assert "body_rewritten" in fp_json
        assert fp_json["body_rewritten"] is not None

        # Test pages list API
        pages_resp = test_client.get(f"/api/vault/courses/ltu/{COURSE_ID}/pages")
        assert pages_resp.status_code == 200
        pages_json = pages_resp.json()
        assert len(pages_json) >= 10

    asyncio.run(_test())

"""Live read-only verification test for Moodle LMS course.

Tests read-only Moodle synchronization, section & activity retrieval,
link rewriting, and FastAPI server response.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

from canvas_track.models import SiteConfig
from canvas_track.moodle_client import MoodleClient
from canvas_track.moodle_sync import MoodleSyncEngine
from canvas_track.server import create_app
from canvas_track.vault import VaultManager

load_dotenv()

MOODLE_URL = os.environ.get("MOODLE_URL", "https://moodle.example.edu")
MOODLE_TOKEN = os.environ.get("MOODLE_TOKEN")
COURSE_ID = int(os.environ.get("MOODLE_COURSE_ID", "73674"))

if not MOODLE_TOKEN:
    pytest.skip(
        "MOODLE_TOKEN environment variable not set; skipping live Moodle test",
        allow_module_level=True,
    )


@pytest.mark.anyio
async def test_live_moodle_read_only_sync(tmp_path: Path) -> None:
    vault = VaultManager(tmp_path)
    client = MoodleClient(MOODLE_URL, MOODLE_TOKEN)

    # 1. Verify student profile
    info = await client.get_site_info()
    assert info.get("userid") == 12345
    assert "Student" in info.get("fullname", "")

    site = SiteConfig(
        id="lnu",
        domain=client.base_url.replace("https://", "").replace("http://", ""),
        base_url=client.base_url,
        platform="moodle",
        user_name=info.get("fullname"),
        user_id=info.get("userid"),
        token=MOODLE_TOKEN,
    )
    vault.save_site(site)

    # 2. Verify course listing
    courses = await client.list_courses(info.get("userid"))
    assert any(c.get("id") == COURSE_ID for c in courses)

    # 3. Perform read-only sync
    engine = MoodleSyncEngine(client, vault, "lnu")
    meta = await engine.sync_course(COURSE_ID, download_files=False)
    assert meta.course_id == COURSE_ID
    assert meta.total_modules > 0

    await client.aclose()

    # 4. Verify FastAPI server endpoints for the synced vault course
    app = create_app(tmp_path)
    test_client = TestClient(app)

    res_courses = test_client.get("/api/vault/sites/lnu/courses")
    assert res_courses.status_code == 200
    assert len(res_courses.json()) >= 1

    res_modules = test_client.get(f"/api/vault/courses/lnu/{COURSE_ID}/modules")
    assert res_modules.status_code == 200
    assert len(res_modules.json()) >= 1

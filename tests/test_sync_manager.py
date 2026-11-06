"""Unit tests for background sync job manager and SSE subscriptions."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from canvas_track.models import CourseMeta, SiteConfig
from canvas_track.sync_manager import SyncJobManager
from canvas_track.vault import VaultManager


@pytest.mark.anyio
async def test_sync_job_manager_deduplication_and_replay(tmp_path: Path) -> None:
    vault = VaultManager(tmp_path)
    site = SiteConfig(
        id="mock_site",
        domain="canvas.example.edu",
        base_url="https://canvas.example.edu",
        user_name="Test User",
        user_id=123,
        token="token_abc",
    )
    vault.save_site(site)

    manager = SyncJobManager()

    meta = CourseMeta(
        course_id=101,
        course_name="Machine Learning",
        default_view="wiki",
        total_pages=5,
    )

    with patch("canvas_track.sync_manager.SyncEngine") as mock_engine_cls:
        mock_engine = AsyncMock()
        mock_engine_cls.return_value = mock_engine

        # Mock sync_course to emit progress then return meta
        async def fake_sync(course_id: int, progress_cb=None, download_files=True):
            if progress_cb:
                payload = {
                    "stage": "pages",
                    "message": "Fetching page 1/5",
                    "current": 1,
                    "total": 5,
                }
                res = progress_cb(payload)
                if res:
                    await res
            return meta

        mock_engine.sync_course = AsyncMock(side_effect=fake_sync)

        # 1. Start job
        job1 = manager.start_job(vault, "mock_site", 101, "Machine Learning")
        assert job1.status.status in ("running", "completed")

        # 2. Try starting again while registered -> must return same job
        job2 = manager.start_job(vault, "mock_site", 101, "Machine Learning")
        assert job1 is job2

        # 3. Add subscriber and verify replay of initial status
        sub_queue = job1.add_subscriber()
        first_evt = await sub_queue.get()
        assert first_evt is not None
        assert "stage" in first_evt

        # Wait for task to finish
        if job1._task:
            await job1._task

        assert job1.status.status == "completed"
        assert job1.status.percent == 100

        # Verify job is listed
        jobs = manager.list_jobs("mock_site")
        assert len(jobs) == 1
        assert jobs[0].course_id == 101

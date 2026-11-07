"""Unit tests for MoodleSyncEngine."""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from canvas_track.moodle_sync import MoodleSyncEngine
from canvas_track.vault import VaultManager


@pytest.mark.anyio
async def test_moodle_sync_engine(tmp_path: Path) -> None:
    vault = VaultManager(tmp_path)
    client = AsyncMock()

    # Mock courses
    client.list_courses.return_value = [
        {
            "id": 101,
            "fullname": "Advanced Data Visualization",
            "shortname": "4NA035",
            "summary": "Course Syllabus HTML",
        }
    ]

    # Mock sections
    client.get_course_contents.return_value = [
        {
            "id": 1,
            "name": "General",
            "modules": [
                {
                    "id": 501,
                    "name": "Course Guide",
                    "modname": "resource",
                    "contents": [
                        {
                            "filename": "guide.pdf",
                            "fileurl": "https://moodle.example.edu/file.pdf",
                            "filesize": 1024,
                        }
                    ],
                },
                {
                    "id": 502,
                    "name": "Important Info",
                    "modname": "page",
                    "description": "<p>Important Information</p>",
                },
            ],
        }
    ]

    # Mock pages, assignments, forums
    client.list_pages.return_value = []
    client.list_assignments.return_value = [
        {
            "id": 701,
            "name": "Assignment 1",
            "intro": "<p>Submit code</p>",
            "duedate": 1700000000,
            "grade": 100,
        }
    ]
    client.get_submission_status.return_value = {}
    client.list_forums.return_value = []
    client.download_file.return_value = True

    engine = MoodleSyncEngine(client, vault, "test_moodle")

    progress_events = []

    async def on_progress(evt):
        progress_events.append(evt)

    meta = await engine.sync_course(101, progress_cb=on_progress, download_files=False)

    assert meta.course_id == 101
    assert meta.course_name == "Advanced Data Visualization"
    assert meta.total_modules == 1
    assert meta.total_files == 1
    assert meta.total_assignments == 1
    assert len(progress_events) > 0

    # Verify vault saved contents
    modules = vault.get_modules("test_moodle", 101)
    assert len(modules) == 1
    assert modules[0]["name"] == "General"
    assert len(modules[0]["items"]) == 2

    assigns = vault.get_assignments("test_moodle", 101)
    assert len(assigns) == 1
    assert assigns[0]["name"] == "Assignment 1"

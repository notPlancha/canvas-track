"""Sync Job Manager for background synchronization.

Tracks active and completed sync jobs, manages multiple SSE subscribers,
replays logs on reconnect, and ensures only one sync task runs per course.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from canvas_track.client import CanvasClient
from canvas_track.models import CourseMeta
from canvas_track.sync import SyncEngine
from canvas_track.vault import VaultManager

logger = logging.getLogger(__name__)


class SyncJobStatus(BaseModel):
    """Serializable status information for a sync job."""

    job_id: str
    site_id: str
    course_id: int
    course_name: str = ""
    status: str = "pending"  # "pending", "running", "completed", "error"
    stage: str = "init"
    message: str = "Preparing synchronization..."
    current: int = 0
    total: int = 0
    percent: int = 0
    started_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    completed_at: str | None = None
    error: str | None = None
    logs: list[str] = Field(default_factory=list)


class SyncJob:
    """Represents an active or recent sync execution for a course."""

    def __init__(
        self,
        job_id: str,
        site_id: str,
        course_id: int,
        course_name: str = "",
    ) -> None:
        self.job_id = job_id
        self.site_id = site_id
        self.course_id = course_id
        self.course_name = course_name
        self.status = SyncJobStatus(
            job_id=job_id,
            site_id=site_id,
            course_id=course_id,
            course_name=course_name,
            status="running",
            stage="init",
            message=f"Starting sync for {course_name or course_id}...",
        )
        self._subscribers: set[asyncio.Queue[dict[str, Any] | None]] = set()
        self._task: asyncio.Task[Any] | None = None

    def add_subscriber(self) -> asyncio.Queue[dict[str, Any] | None]:
        """Register a new SSE subscriber and queue initial replay events."""
        q: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        # Initial status event
        q.put_nowait(
            {
                "stage": self.status.stage,
                "message": self.status.message,
                "current": self.status.current,
                "total": self.status.total,
                "percent": self.status.percent,
                "status": self.status.status,
                "logs": list(self.status.logs),
            }
        )
        # If job is already complete or errored, send sentinel
        if self.status.status in ("completed", "error"):
            q.put_nowait(None)
        self._subscribers.add(q)
        return q

    def remove_subscriber(self, q: asyncio.Queue[dict[str, Any] | None]) -> None:
        """Unregister an SSE subscriber."""
        self._subscribers.discard(q)

    def emit_progress(self, evt: dict[str, Any]) -> None:
        """Update job state and broadcast progress to all subscribers."""
        stage = evt.get("stage", self.status.stage)
        msg = evt.get("message", self.status.message)
        current = evt.get("current", self.status.current)
        total = evt.get("total", self.status.total)

        self.status.stage = stage
        self.status.message = msg
        self.status.current = current
        self.status.total = total

        if total > 0:
            self.status.percent = min(100, max(0, int(round((current / total) * 100))))
        elif stage == "done":
            self.status.percent = 100

        # Maintain last 120 log lines
        log_entry = f"[{stage.upper()}] {msg}"
        self.status.logs.append(log_entry)
        if len(self.status.logs) > 120:
            self.status.logs.pop(0)

        payload = {
            "stage": stage,
            "message": msg,
            "current": current,
            "total": total,
            "percent": self.status.percent,
            "status": self.status.status,
        }

        for q in list(self._subscribers):
            with contextlib.suppress(Exception):
                q.put_nowait(payload)

    def finish(self, meta: CourseMeta) -> None:
        """Mark job as successfully completed."""
        self.status.status = "completed"
        self.status.stage = "done"
        self.status.percent = 100
        self.status.completed_at = datetime.now().isoformat()
        self.status.message = f"Sync completed successfully for {meta.course_name}!"
        self.status.logs.append(f"[DONE] {self.status.message}")

        payload = {
            "stage": "done",
            "message": self.status.message,
            "status": "completed",
            "percent": 100,
        }

        for q in list(self._subscribers):
            with contextlib.suppress(Exception):
                q.put_nowait(payload)
                q.put_nowait(None)  # Sentinel to end stream

    def fail(self, error_msg: str) -> None:
        """Mark job as failed."""
        self.status.status = "error"
        self.status.stage = "error"
        self.status.error = error_msg
        self.status.completed_at = datetime.now().isoformat()
        self.status.message = f"Sync failed: {error_msg}"
        self.status.logs.append(f"[ERROR] {error_msg}")

        payload = {
            "stage": "error",
            "message": self.status.message,
            "status": "error",
            "error": error_msg,
        }

        for q in list(self._subscribers):
            with contextlib.suppress(Exception):
                q.put_nowait(payload)
                q.put_nowait(None)  # Sentinel to end stream


class SyncJobManager:
    """Singleton manager controlling active and recent sync tasks."""

    def __init__(self) -> None:
        self._jobs: dict[str, SyncJob] = {}

    def _job_key(self, site_id: str, course_id: int) -> str:
        return f"{site_id}:{course_id}"

    def get_job(self, site_id: str, course_id: int) -> SyncJob | None:
        """Get an existing job for a course."""
        return self._jobs.get(self._job_key(site_id, course_id))

    def list_jobs(self, site_id: str | None = None) -> list[SyncJobStatus]:
        """Return statuses of all jobs, optionally filtered by site."""
        jobs = list(self._jobs.values())
        if site_id:
            jobs = [j for j in jobs if j.site_id == site_id]
        return [j.status for j in jobs]

    def start_job(
        self,
        vault: VaultManager,
        site_id: str,
        course_id: int,
        course_name: str = "",
        download_files: bool = True,
    ) -> SyncJob:
        """Start a sync job if not already running, or return existing active job."""
        key = self._job_key(site_id, course_id)
        existing = self._jobs.get(key)
        if existing and existing.status.status == "running":
            logger.info("Sync job for %s already running.", key)
            return existing

        job = SyncJob(
            job_id=key,
            site_id=site_id,
            course_id=course_id,
            course_name=course_name,
        )
        self._jobs[key] = job

        site = vault.get_site(site_id)
        if not site:
            job.fail(f"Site '{site_id}' not found in vault configuration.")
            return job

        client = CanvasClient(site.domain, site.token)
        sync_engine = SyncEngine(client, vault, site_id)

        async def _run() -> None:
            try:
                logger.info("Beginning sync for %s (course %d)", site_id, course_id)
                meta = await sync_engine.sync_course(
                    course_id=course_id,
                    progress_cb=lambda evt: job.emit_progress(evt),
                    download_files=download_files,
                )
                job.finish(meta)
                logger.info("Completed sync for %s (course %d)", site_id, course_id)
            except Exception as e:
                logger.exception("Failed sync for %s (course %d): %s", site_id, course_id, e)
                job.fail(str(e))
            finally:
                await client.aclose()

        job._task = asyncio.create_task(_run())
        return job

    def remove_job(self, site_id: str, course_id: int) -> bool:
        """Remove a cached or completed sync job for a course."""
        key = self._job_key(site_id, course_id)
        if key in self._jobs:
            job = self._jobs[key]
            if job.status.status == "running" and job._task and not job._task.done():
                job._task.cancel()
            del self._jobs[key]
            return True
        return False


# Global singleton instance for the app
sync_manager = SyncJobManager()

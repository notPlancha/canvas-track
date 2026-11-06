"""Vault Storage Manager for Canvas Track.

Manages storing raw API JSON dumps and downloaded course assets in a local folder
structure, with atomic JSON writes and SHA-256 hash tracking.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import os
import re
import shutil
import stat
from pathlib import Path
from typing import Any

from canvas_track.models import CourseMeta, SiteConfig

logger = logging.getLogger(__name__)


def sanitize_filename(name: str) -> str:
    """Sanitize a string for safe use in file/folder names across operating systems."""
    cleaned = re.sub(r'[\\/*?:"<>|]', "_", name).strip()
    return cleaned or "unnamed"


def compute_sha256(file_path: Path) -> str:
    """Compute the SHA-256 hash of a file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


class VaultManager:
    """Manages the local archive of Canvas sites and courses."""

    def __init__(self, vault_dir: Path | str | None = None) -> None:
        if vault_dir is None:
            default_dir = os.environ.get("CANVAS_TRACK_VAULT", Path.home() / ".canvas-vault")
            self.root = Path(default_dir).resolve()
        else:
            self.root = Path(vault_dir).resolve()

        self.root.mkdir(parents=True, exist_ok=True)
        self.config_file = self.root / "config.json"
        self._ensure_config()

    def _ensure_config(self) -> None:
        if not self.config_file.exists():
            self._save_raw_json(self.config_file, {"sites": []})

    def _save_raw_json(self, path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        temp_path.replace(path)

    def _read_raw_json(self, path: Path) -> Any | None:
        if not path.exists():
            return None
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error("Failed to read JSON at %s: %s", path, e)
            return None

    # Sites configuration
    def list_sites(self) -> list[SiteConfig]:
        config = self._read_raw_json(self.config_file) or {}
        raw_sites = config.get("sites", [])
        return [SiteConfig.model_validate(s) for s in raw_sites]

    def get_site(self, site_id: str) -> SiteConfig | None:
        for s in self.list_sites():
            if s.id == site_id:
                return s
        return None

    def save_site(self, site: SiteConfig) -> None:
        config = self._read_raw_json(self.config_file) or {"sites": []}
        existing = [s for s in config.get("sites", []) if s.get("id") != site.id]
        existing.append(site.model_dump())
        config["sites"] = existing
        self._save_raw_json(self.config_file, config)

    def delete_site(self, site_id: str, delete_files: bool = False) -> None:
        config = self._read_raw_json(self.config_file) or {"sites": []}
        config["sites"] = [s for s in config.get("sites", []) if s.get("id") != site_id]
        self._save_raw_json(self.config_file, config)

        if delete_files:
            site_dir = self.root / "sites" / sanitize_filename(site_id)
            if site_dir.exists():
                def _on_rm_error(func: Any, path: str, exc_info: Any) -> None:
                    try:
                        os.chmod(path, stat.S_IWRITE)
                        func(path)
                    except Exception as e:
                        logger.error("Failed to remove path %s: %s", path, e)

                shutil.rmtree(site_dir, onexc=_on_rm_error)

    # Course paths
    def get_site_dir(self, site_id: str) -> Path:
        return self.root / "sites" / sanitize_filename(site_id)

    def get_course_dir(self, site_id: str, course_id: int) -> Path:
        return self.get_site_dir(site_id) / "courses" / str(course_id)

    def get_api_raw_dir(self, site_id: str, course_id: int) -> Path:
        return self.get_course_dir(site_id, course_id) / "api_raw"

    def get_files_dir(self, site_id: str, course_id: int) -> Path:
        return self.get_course_dir(site_id, course_id) / "files"

    # Course Metadata & Dumps
    def save_course_meta(self, site_id: str, course_id: int, meta: CourseMeta) -> None:
        path = self.get_course_dir(site_id, course_id) / "meta.json"
        self._save_raw_json(path, meta.model_dump())

    def get_course_meta(self, site_id: str, course_id: int) -> CourseMeta | None:
        path = self.get_course_dir(site_id, course_id) / "meta.json"
        data = self._read_raw_json(path)
        return CourseMeta.model_validate(data) if data else None

    def list_archived_courses(self, site_id: str) -> list[CourseMeta]:
        site_courses_dir = self.get_site_dir(site_id) / "courses"
        if not site_courses_dir.exists():
            return []
        courses: list[CourseMeta] = []
        for d in site_courses_dir.iterdir():
            if d.is_dir() and (d / "meta.json").exists():
                meta = self.get_course_meta(site_id, int(d.name))
                if meta:
                    courses.append(meta)
        return courses

    def get_course_backup_size(self, site_id: str, course_id: int) -> int:
        """Calculate total disk usage in bytes for a course's local vault archive."""
        course_dir = self.root / "sites" / sanitize_filename(site_id) / "courses" / str(course_id)
        if not course_dir.exists():
            return 0
        total_size = 0
        for p in course_dir.rglob("*"):
            if p.is_file():
                with contextlib.suppress(OSError):
                    total_size += p.stat().st_size
        return total_size

    def delete_course_archive(self, site_id: str, course_id: int) -> bool:
        """Permanently delete a course's local vault directory."""
        course_dir = self.root / "sites" / sanitize_filename(site_id) / "courses" / str(course_id)
        if not course_dir.exists():
            return False

        def _on_rm_error(func: Any, path: str, exc_info: Any) -> None:
            try:
                os.chmod(path, stat.S_IWRITE)
                func(path)
            except Exception as e:
                logger.error("Failed to remove path %s during deletion: %s", path, e)

        shutil.rmtree(course_dir, onexc=_on_rm_error)
        logger.info("Deleted local vault backup for course %s in site %s", course_id, site_id)
        return True

    # Pages
    def save_pages_list(self, site_id: str, course_id: int, pages: list[dict[str, Any]]) -> None:
        path = self.get_api_raw_dir(site_id, course_id) / "pages.json"
        self._save_raw_json(path, pages)

    def save_page(
        self, site_id: str, course_id: int, page_url: str, page_data: dict[str, Any]
    ) -> None:
        pages_dir = self.get_api_raw_dir(site_id, course_id) / "pages"
        pages_dir.mkdir(parents=True, exist_ok=True)
        path = pages_dir / f"{sanitize_filename(page_url)}.json"
        self._save_raw_json(path, page_data)

    def get_pages_list(self, site_id: str, course_id: int) -> list[dict[str, Any]]:
        path = self.get_api_raw_dir(site_id, course_id) / "pages.json"
        return self._read_raw_json(path) or []

    def get_page(self, site_id: str, course_id: int, page_url: str) -> dict[str, Any] | None:
        pages_dir = self.get_api_raw_dir(site_id, course_id) / "pages"
        path = pages_dir / f"{sanitize_filename(page_url)}.json"
        return self._read_raw_json(path)

    def save_front_page(self, site_id: str, course_id: int, page_data: dict[str, Any]) -> None:
        path = self.get_api_raw_dir(site_id, course_id) / "front_page.json"
        self._save_raw_json(path, page_data)
        if "url" in page_data:
            self.save_page(site_id, course_id, page_data["url"], page_data)

    def get_front_page(self, site_id: str, course_id: int) -> dict[str, Any] | None:
        path = self.get_api_raw_dir(site_id, course_id) / "front_page.json"
        return self._read_raw_json(path)

    # Modules
    def save_modules(self, site_id: str, course_id: int, modules: list[dict[str, Any]]) -> None:
        path = self.get_api_raw_dir(site_id, course_id) / "modules.json"
        self._save_raw_json(path, modules)

    def get_modules(self, site_id: str, course_id: int) -> list[dict[str, Any]]:
        path = self.get_api_raw_dir(site_id, course_id) / "modules.json"
        return self._read_raw_json(path) or []

    # Files & Folders
    def save_files_metadata(
        self, site_id: str, course_id: int, files: list[dict[str, Any]]
    ) -> None:
        path = self.get_api_raw_dir(site_id, course_id) / "files.json"
        self._save_raw_json(path, files)

    def get_files_metadata(self, site_id: str, course_id: int) -> list[dict[str, Any]]:
        path = self.get_api_raw_dir(site_id, course_id) / "files.json"
        return self._read_raw_json(path) or []

    def save_folders_metadata(
        self, site_id: str, course_id: int, folders: list[dict[str, Any]]
    ) -> None:
        path = self.get_api_raw_dir(site_id, course_id) / "folders.json"
        self._save_raw_json(path, folders)

    def get_folders_metadata(self, site_id: str, course_id: int) -> list[dict[str, Any]]:
        path = self.get_api_raw_dir(site_id, course_id) / "folders.json"
        return self._read_raw_json(path) or []

    # Assignments & Submissions
    def save_assignments(
        self, site_id: str, course_id: int, assignments: list[dict[str, Any]]
    ) -> None:
        path = self.get_api_raw_dir(site_id, course_id) / "assignments.json"
        self._save_raw_json(path, assignments)

    def get_assignments(self, site_id: str, course_id: int) -> list[dict[str, Any]]:
        path = self.get_api_raw_dir(site_id, course_id) / "assignments.json"
        return self._read_raw_json(path) or []

    def save_submissions(
        self, site_id: str, course_id: int, submissions: list[dict[str, Any]]
    ) -> None:
        path = self.get_api_raw_dir(site_id, course_id) / "submissions.json"
        self._save_raw_json(path, submissions)

    def get_submissions(self, site_id: str, course_id: int) -> list[dict[str, Any]]:
        path = self.get_api_raw_dir(site_id, course_id) / "submissions.json"
        return self._read_raw_json(path) or []

    # Announcements
    def save_announcements(
        self, site_id: str, course_id: int, announcements: list[dict[str, Any]]
    ) -> None:
        path = self.get_api_raw_dir(site_id, course_id) / "announcements.json"
        self._save_raw_json(path, announcements)

    def get_announcements(self, site_id: str, course_id: int) -> list[dict[str, Any]]:
        path = self.get_api_raw_dir(site_id, course_id) / "announcements.json"
        return self._read_raw_json(path) or []

    # Discussions
    def save_discussions(self, site_id: str, course_id: int, topics: list[dict[str, Any]]) -> None:
        path = self.get_api_raw_dir(site_id, course_id) / "discussions.json"
        self._save_raw_json(path, topics)

    def get_discussions(self, site_id: str, course_id: int) -> list[dict[str, Any]]:
        path = self.get_api_raw_dir(site_id, course_id) / "discussions.json"
        return self._read_raw_json(path) or []

    def save_discussion_entry(
        self, site_id: str, course_id: int, topic_id: int, data: dict[str, Any]
    ) -> None:
        disc_dir = self.get_api_raw_dir(site_id, course_id) / "discussions"
        disc_dir.mkdir(parents=True, exist_ok=True)
        path = disc_dir / f"{topic_id}.json"
        self._save_raw_json(path, data)

    def get_discussion_entry(
        self, site_id: str, course_id: int, topic_id: int
    ) -> dict[str, Any] | None:
        disc_dir = self.get_api_raw_dir(site_id, course_id) / "discussions"
        path = disc_dir / f"{topic_id}.json"
        return self._read_raw_json(path)

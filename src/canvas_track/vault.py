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
import uuid
from datetime import datetime
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
        else:
            self.deduplicate_sites()

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

    def find_duplicate_site(
        self,
        domain: str,
        user_id: int | None = None,
        token: str | None = None,
        exclude_site_id: str | None = None,
    ) -> SiteConfig | None:
        """Find an existing site that matches the same domain and user ID, or same token."""
        clean_domain = domain.strip().lower()
        clean_token = token.strip() if token else None
        for s in self.list_sites():
            if exclude_site_id and s.id == exclude_site_id:
                continue
            if clean_token and s.token == clean_token:
                return s
            if (
                s.domain.strip().lower() == clean_domain
                and user_id is not None
                and s.user_id == user_id
            ):
                return s
        return None

    def deduplicate_sites(self) -> list[str]:
        """Detect and remove existing duplicate sites from config.json.

        Returns the IDs of the removed duplicate sites.
        """
        config = self._read_raw_json(self.config_file) or {"sites": []}
        raw_sites = config.get("sites", [])
        unique_sites: list[dict[str, Any]] = []
        seen_user_domain: set[tuple[str, int]] = set()
        seen_tokens: set[str] = set()
        seen_ids: set[str] = set()
        removed_ids: list[str] = []

        for s in raw_sites:
            sid = s.get("id")
            domain = (s.get("domain") or "").strip().lower()
            uid = s.get("user_id")
            token = (s.get("token") or "").strip()

            is_dup = (
                sid in seen_ids
                or (bool(token) and token in seen_tokens)
                or (bool(domain) and uid is not None and (domain, uid) in seen_user_domain)
            )

            if is_dup:
                if sid:
                    removed_ids.append(sid)
                logger.info("Removed duplicate site entry: %s (%s)", sid, domain)
            else:
                unique_sites.append(s)
                if sid:
                    seen_ids.add(sid)
                if token:
                    seen_tokens.add(token)
                if domain and uid is not None:
                    seen_user_domain.add((domain, uid))

        if removed_ids:
            config["sites"] = unique_sites
            self._save_raw_json(self.config_file, config)

        return removed_ids

    def update_site(
        self,
        site_id: str,
        new_site_id: str,
        domain: str,
        token: str,
        user_name: str | None = None,
        user_id: int | None = None,
    ) -> SiteConfig:
        """Update an existing site's configuration and optionally rename its directory."""
        config = self._read_raw_json(self.config_file) or {"sites": []}
        site_idx = next(
            (i for i, s in enumerate(config.get("sites", [])) if s.get("id") == site_id),
            None,
        )
        if site_idx is None:
            raise ValueError(f"Site '{site_id}' not found.")

        old_site_raw = config["sites"][site_idx]
        new_sid = new_site_id.strip() if new_site_id else site_id
        clean_domain = domain.strip().lower()

        # Rename vault directory if site_id changed
        if new_sid != site_id:
            old_dir = self.root / "sites" / sanitize_filename(site_id)
            new_dir = self.root / "sites" / sanitize_filename(new_sid)
            if old_dir.exists() and not new_dir.exists():
                old_dir.rename(new_dir)

        updated_site = SiteConfig(
            id=new_sid,
            domain=clean_domain,
            base_url=f"https://{clean_domain}",
            user_name=user_name if user_name is not None else old_site_raw.get("user_name"),
            user_id=user_id if user_id is not None else old_site_raw.get("user_id"),
            token=token.strip(),
            created_at=old_site_raw.get("created_at") or datetime.now().isoformat(),
        )

        config["sites"][site_idx] = updated_site.model_dump()
        self._save_raw_json(self.config_file, config)
        return updated_site

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

    def get_course_file_path(self, site_id: str, course_id: int, file_id: int) -> Path | None:
        """Find the local path on disk for a given course file ID."""
        files = self.get_files_metadata(site_id, course_id)
        target = next(
            (f for f in files if f.get("id") == file_id or str(f.get("id")) == str(file_id)),
            None,
        )
        files_dir = self.get_files_dir(site_id, course_id)
        if not files_dir.exists():
            return None

        if target:
            display_name = target.get("display_name", "")
            sanitized = sanitize_filename(display_name)
            folder_id = target.get("folder_id")

            # Try locating via folder mapping
            if folder_id:
                folders = self.get_folders_metadata(site_id, course_id)
                folder_obj = next((f for f in folders if f.get("id") == folder_id), None)
                if folder_obj and folder_obj.get("full_name"):
                    name_parts = folder_obj["full_name"].split("/")
                    if name_parts and name_parts[0].lower() in ("course files", "course_files"):
                        rel_parts = [sanitize_filename(p) for p in name_parts[1:] if p.strip()]
                    else:
                        rel_parts = [sanitize_filename(p) for p in name_parts if p.strip()]
                    folder_rel = Path(*rel_parts) if rel_parts else Path()
                    candidate = files_dir / folder_rel / sanitized
                    if candidate.is_file():
                        return candidate

            # Try direct file in root files dir
            direct = files_dir / sanitized
            if direct.is_file():
                return direct

            # Recursive search by display_name or filename
            raw_filename = target.get("filename")
            for p in files_dir.rglob("*"):
                if p.is_file() and (
                    p.name == sanitized
                    or p.name == display_name
                    or (raw_filename and p.name == raw_filename)
                ):
                    return p

        # Fallback search by file_id in name
        for p in files_dir.rglob("*"):
            if p.is_file() and str(file_id) in p.name:
                return p

        return None

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

    # Page Comments / Notes
    def get_page_comments_path(self, site_id: str, course_id: int, page_url: str) -> Path:
        """Get the JSON path where comments for a specific page are stored."""
        return (
            self.get_course_dir(site_id, course_id)
            / "comments"
            / f"{sanitize_filename(page_url)}.json"
        )

    def get_page_comments(
        self, site_id: str, course_id: int, page_url: str
    ) -> list[dict[str, Any]]:
        """Retrieve local notes/comments for a specific page."""
        path = self.get_page_comments_path(site_id, course_id, page_url)
        return self._read_raw_json(path) or []

    def add_page_comment(
        self, site_id: str, course_id: int, page_url: str, text: str
    ) -> dict[str, Any]:
        """Add a local note/comment to a specific page."""
        comments = self.get_page_comments(site_id, course_id, page_url)
        new_comment = {
            "id": str(uuid.uuid4())[:8],
            "text": text.strip(),
            "created_at": datetime.now().isoformat(),
        }
        comments.append(new_comment)
        path = self.get_page_comments_path(site_id, course_id, page_url)
        self._save_raw_json(path, comments)
        return new_comment

    def delete_page_comment(
        self, site_id: str, course_id: int, page_url: str, comment_id: str
    ) -> bool:
        """Delete a local note/comment by its ID."""
        comments = self.get_page_comments(site_id, course_id, page_url)
        filtered = [c for c in comments if c.get("id") != comment_id]
        if len(filtered) != len(comments):
            path = self.get_page_comments_path(site_id, course_id, page_url)
            self._save_raw_json(path, filtered)
            return True
        return False

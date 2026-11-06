"""Sync Engine for Canvas Track.

Orchestrates read-only synchronization of Canvas courses into the local vault,
with priority on wiki pages (including front page/home page), incremental file
downloads, and real-time progress updates.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Coroutine
from datetime import datetime
from typing import Any

from canvas_track.client import CanvasClient
from canvas_track.models import CanvasPage, CourseMeta
from canvas_track.vault import VaultManager, compute_sha256, sanitize_filename

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[dict[str, Any]], Coroutine[Any, Any, None] | None]


def format_bytes(size: int) -> str:
    """Format bytes count into human-readable representation."""
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    if size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    return f"{size / (1024 * 1024 * 1024):.1f} GB"


class SyncEngine:
    """Manages course synchronization from Canvas to local vault storage."""

    def __init__(self, client: CanvasClient, vault: VaultManager, site_id: str) -> None:
        self.client = client
        self.vault = vault
        self.site_id = site_id

    async def sync_course(
        self,
        course_id: int,
        progress_cb: ProgressCallback | None = None,
        download_files: bool = True,
    ) -> CourseMeta:
        """Execute a complete, read-only sync of a Canvas course."""

        async def emit(stage: str, message: str, current: int = 0, total: int = 0) -> None:
            if progress_cb:
                payload = {
                    "stage": stage,
                    "message": message,
                    "current": current,
                    "total": total,
                    "timestamp": datetime.now().isoformat(),
                }
                res = progress_cb(payload)
                if res is not None:
                    await res

        await emit("init", f"Starting sync for course {course_id}...")

        # 1. Fetch Course Info & Home Page Configuration
        course = await self.client.get_course(course_id)
        api_raw_dir = self.vault.get_api_raw_dir(self.site_id, course_id)
        self.vault._save_raw_json(api_raw_dir / "course.json", course.model_dump())

        front_page_url: str | None = None
        front_page_title: str | None = None

        # Fetch front page (Home Page)
        await emit("pages", "Checking course home page and front page...")
        front_page = await self.client.get_course_front_page(course_id)
        if front_page:
            front_page_url = front_page.url
            front_page_title = front_page.title
            self.vault.save_front_page(self.site_id, course_id, front_page.model_dump())
            await emit("pages", f"Saved home page: {front_page.title}")

        # 2. Fetch Modules
        await emit("modules", "Fetching course modules...")
        try:
            modules = await self.client.list_course_modules(course_id)
        except Exception as e:
            logger.warning("Could not fetch modules for course %d: %s", course_id, e)
            modules = []
        self.vault.save_modules(self.site_id, course_id, [m.model_dump() for m in modules])
        await emit("modules", f"Saved {len(modules)} modules")

        # 3. Fetch Wiki Pages
        await emit("pages", "Fetching course pages list...")
        try:
            pages_summary = await self.client.list_course_pages(course_id)
        except Exception as e:
            logger.warning("Could not fetch pages list for course %d: %s", course_id, e)
            pages_summary = []

        known_page_urls = {p.url for p in pages_summary}

        # Include front page if present but omitted from /pages listing
        if front_page and front_page.url not in known_page_urls:
            pages_summary.append(front_page)
            known_page_urls.add(front_page.url)

        # Harvest wiki pages referenced inside module items
        for m in modules:
            for it in m.items:
                if it.type == "Page" and it.page_url and it.page_url not in known_page_urls:
                    pages_summary.append(
                        CanvasPage(
                            url=it.page_url,
                            title=it.title or it.page_url,
                            front_page=False,
                        )
                    )
                    known_page_urls.add(it.page_url)

        self.vault.save_pages_list(self.site_id, course_id, [p.model_dump() for p in pages_summary])

        total_pages = len(pages_summary)
        for idx, p in enumerate(pages_summary, start=1):
            await emit(
                "pages",
                f"Fetching page ({idx}/{total_pages}): {p.title}",
                current=idx,
                total=total_pages,
            )
            # If front_page already has complete body, reuse it
            if front_page and p.url == front_page.url and front_page.body:
                self.vault.save_page(self.site_id, course_id, p.url, front_page.model_dump())
                continue

            try:
                full_page = await self.client.get_course_page(course_id, p.url)
                if full_page:
                    self.vault.save_page(self.site_id, course_id, p.url, full_page.model_dump())
            except Exception as e:
                logger.warning("Could not fetch page %s: %s", p.url, e)

        # 4. Fetch Folders & Files
        await emit("files", "Fetching folder and file hierarchies...")
        try:
            folders = await self.client.list_course_folders(course_id)
        except Exception as e:
            logger.warning("Could not fetch folders for course %d: %s", course_id, e)
            folders = []

        try:
            files = await self.client.list_course_files(course_id)
        except Exception as e:
            logger.warning("Could not fetch files for course %d: %s", course_id, e)
            files = []

        known_file_ids = {f.id for f in files}

        # Harvest files referenced inside module items (even if /files is 403 restricted)
        for m in modules:
            for it in m.items:
                if it.type == "File" and it.content_id and it.content_id not in known_file_ids:
                    try:
                        f_meta = await self.client.get_file(course_id, it.content_id)
                        if f_meta:
                            files.append(f_meta)
                            known_file_ids.add(f_meta.id)
                    except Exception as e:
                        logger.warning(
                            "Could not fetch metadata for module file %s: %s",
                            it.content_id,
                            e,
                        )

        # Harvest files referenced in page bodies, front page, and syllabus
        html_sources: list[str] = []
        if course.syllabus_body:
            html_sources.append(course.syllabus_body)
        if front_page and front_page.body:
            html_sources.append(front_page.body)
        for p in pages_summary:
            saved_p = self.vault.get_page(self.site_id, course_id, p.url)
            if saved_p and saved_p.get("body"):
                html_sources.append(saved_p["body"])

        file_ref_regex = re.compile(
            r"(?:/files/|preview=|\$CANVAS_OBJECT_REFERENCE\$/files/)(\d+)",
            re.IGNORECASE,
        )
        for html_text in html_sources:
            for fid_match in file_ref_regex.finditer(html_text):
                try:
                    ref_fid = int(fid_match.group(1))
                except (ValueError, IndexError):
                    continue
                if ref_fid not in known_file_ids:
                    try:
                        f_meta = await self.client.get_file(course_id, ref_fid)
                        if f_meta:
                            files.append(f_meta)
                            known_file_ids.add(f_meta.id)
                    except Exception as e:
                        logger.warning(
                            "Could not fetch metadata for referenced file %d: %s",
                            ref_fid,
                            e,
                        )

        self.vault.save_folders_metadata(self.site_id, course_id, [f.model_dump() for f in folders])
        self.vault.save_files_metadata(self.site_id, course_id, [f.model_dump() for f in files])

        # Build folder path lookup: folder_id -> relative folder path
        folder_paths: dict[int, str] = {}
        for f in folders:
            # Canvas folder full_name typically starts with "course files"
            name_parts = f.full_name.split("/")
            if name_parts and name_parts[0].lower() in ("course files", "course_files"):
                rel_parts = [sanitize_filename(p) for p in name_parts[1:] if p.strip()]
            else:
                rel_parts = [sanitize_filename(p) for p in name_parts if p.strip()]
            folder_paths[f.id] = "/".join(rel_parts)

        # Download files incrementally
        course_files_dir = self.vault.get_files_dir(self.site_id, course_id)
        file_hashes: dict[str, str] = {}
        prev_meta = self.vault.get_course_meta(self.site_id, course_id)
        prev_hashes = prev_meta.file_hashes if prev_meta else {}

        if download_files and files:
            total_files = len(files)
            for idx, file_item in enumerate(files, start=1):
                folder_rel = folder_paths.get(file_item.folder_id or 0, "")
                dest_folder = course_files_dir / folder_rel if folder_rel else course_files_dir
                dest_file = dest_folder / sanitize_filename(file_item.display_name)
                rel_key = str(file_item.id)
                size_str = f" ({format_bytes(file_item.size)})" if file_item.size else ""

                # Check if already present and matches expected size
                if (
                    dest_file.exists()
                    and file_item.size
                    and dest_file.stat().st_size == file_item.size
                ):
                    msg = (
                        f"File already up to date ({idx}/{total_files}): "
                        f"{file_item.display_name}{size_str}"
                    )
                    await emit("download", msg, current=idx, total=total_files)
                    if rel_key in prev_hashes:
                        file_hashes[rel_key] = prev_hashes[rel_key]
                    else:
                        file_hashes[rel_key] = compute_sha256(dest_file)
                    continue

                await emit(
                    "download",
                    f"Downloading file ({idx}/{total_files}): {file_item.display_name}{size_str}",
                    current=idx,
                    total=total_files,
                )

                if file_item.url:
                    try:
                        await self.client.download_file(
                            download_url=file_item.url,
                            dest_path=dest_file,
                            expected_size=file_item.size,
                        )
                        if dest_file.exists():
                            # Cache hash
                            file_hashes[rel_key] = compute_sha256(dest_file)
                    except Exception as e:
                        logger.error("Failed to download file %s: %s", file_item.display_name, e)
                        if rel_key in prev_hashes:
                            file_hashes[rel_key] = prev_hashes[rel_key]

        # 5. Fetch Assignments & Personal Submissions
        await emit("assignments", "Fetching course assignments & rubrics...")
        try:
            assignments = await self.client.list_course_assignments(course_id)
        except Exception as e:
            logger.warning("Could not fetch assignments for course %d: %s", course_id, e)
            assignments = []
        self.vault.save_assignments(self.site_id, course_id, [a.model_dump() for a in assignments])

        await emit("submissions", "Fetching your personal submissions and grades...")
        try:
            submissions = await self.client.list_course_submissions(course_id)
        except Exception as e:
            logger.warning("Could not fetch submissions for course %d: %s", course_id, e)
            submissions = []
        self.vault.save_submissions(self.site_id, course_id, [s.model_dump() for s in submissions])

        # 6. Fetch Announcements & Discussions
        await emit("announcements", "Fetching course announcements...")
        try:
            announcements = await self.client.list_course_announcements(course_id)
        except Exception as e:
            logger.warning("Could not fetch announcements for course %d: %s", course_id, e)
            announcements = []
        self.vault.save_announcements(self.site_id, course_id, announcements)

        await emit("discussions", "Fetching course discussions & threads...")
        try:
            discussions = await self.client.list_course_discussions(course_id)
        except Exception as e:
            logger.warning("Could not fetch discussions for course %d: %s", course_id, e)
            discussions = []
        self.vault.save_discussions(self.site_id, course_id, discussions)

        for topic in discussions:
            topic_id = topic.get("id")
            if topic_id:
                try:
                    entries = await self.client.get_discussion_entries(course_id, topic_id)
                    self.vault.save_discussion_entry(self.site_id, course_id, topic_id, entries)
                except Exception as e:
                    logger.warning("Could not fetch entries for discussion %s: %s", topic_id, e)

        # 7. Update CourseMeta
        meta = CourseMeta(
            course_id=course.id,
            course_name=course.name,
            course_code=course.course_code,
            default_view=course.default_view,
            front_page_url=front_page_url,
            front_page_title=front_page_title,
            last_synced_at=datetime.now().isoformat(),
            total_pages=len(pages_summary),
            total_modules=len(modules),
            total_files=len(files),
            total_assignments=len(assignments),
            file_hashes=file_hashes,
        )
        self.vault.save_course_meta(self.site_id, course_id, meta)
        await emit("done", f"Sync completed successfully for {course.name}!", current=1, total=1)
        return meta

"""Moodle Sync Engine for Canvas Track.

Orchestrates read-only synchronization of Moodle courses into the local vault,
translating Moodle course sections and module activities into normalized vault models,
with incremental file downloads and real-time SSE progress updates.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from datetime import datetime
from typing import Any

from canvas_track.models import CanvasModule, CanvasModuleItem, CourseMeta
from canvas_track.moodle_client import MoodleClient
from canvas_track.sync import format_bytes
from canvas_track.vault import VaultManager, compute_sha256, sanitize_filename

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[dict[str, Any]], Coroutine[Any, Any, None] | None]


def _format_timestamp(ts: int | None) -> str | None:
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(ts).isoformat()
    except Exception:
        return None


class MoodleSyncEngine:
    """Manages course synchronization from Moodle to local vault storage."""

    def __init__(self, client: MoodleClient, vault: VaultManager, site_id: str) -> None:
        self.client = client
        self.vault = vault
        self.site_id = site_id

    async def sync_course(
        self,
        course_id: int,
        progress_cb: ProgressCallback | None = None,
        download_files: bool = True,
    ) -> CourseMeta:
        """Execute a complete, read-only sync of a Moodle course."""

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

        await emit("init", f"Starting sync for Moodle course {course_id}...")

        # 1. Fetch Course Info
        courses = await self.client.list_courses()
        course_info = next(
            (c for c in courses if c.get("id") == course_id or str(c.get("id")) == str(course_id)),
            None,
        )

        course_name = (
            course_info.get("fullname", f"Moodle Course {course_id}")
            if course_info
            else f"Moodle Course {course_id}"
        )
        course_code = course_info.get("shortname") if course_info else None

        api_raw_dir = self.vault.get_api_raw_dir(self.site_id, course_id)
        raw_course_dict = {
            "id": course_id,
            "name": course_name,
            "course_code": course_code,
            "default_view": "modules",
            "syllabus_body": course_info.get("summary") if course_info else None,
            "moodle_raw": course_info,
        }
        self.vault._save_raw_json(api_raw_dir / "course.json", raw_course_dict)

        # 2. Fetch Course Contents (Sections & Modules)
        await emit("modules", "Fetching course sections and modules...")
        sections = await self.client.get_course_contents(course_id)
        self.vault._save_raw_json(api_raw_dir / "moodle_sections.json", sections)

        modules: list[CanvasModule] = []
        files_metadata: list[dict[str, Any]] = []
        cmid_to_file: dict[int, dict[str, Any]] = {}
        pages_from_modules: list[dict[str, Any]] = []

        mod_type_mapping = {
            "resource": "File",
            "folder": "Folder",
            "page": "Page",
            "assign": "Assignment",
            "forum": "Discussion",
            "url": "ExternalUrl",
            "label": "SubHeader",
            "quiz": "Quiz",
        }

        file_id_counter = 1000

        for s_idx, section in enumerate(sections):
            sec_id = section.get("id") or (s_idx + 1)
            sec_name = section.get("name") or f"Section {s_idx}"
            sec_items: list[CanvasModuleItem] = []

            for m_idx, mod in enumerate(section.get("modules", [])):
                cmid = mod.get("id")
                modname = mod.get("modname", "unknown")
                item_type = mod_type_mapping.get(modname, modname.capitalize())

                # Check if module contains embedded page / label HTML
                if modname in ("page", "label") and mod.get("description"):
                    pages_from_modules.append(
                        {
                            "url": f"page-{cmid}",
                            "title": mod.get("name") or "Page",
                            "body": mod.get("description"),
                            "page_id": cmid,
                        }
                    )

                # Process files in module contents
                for content in mod.get("contents", []):
                    file_url = content.get("fileurl")
                    if file_url and content.get("filename"):
                        file_id_counter += 1
                        file_rec = {
                            "id": cmid or file_id_counter,
                            "display_name": content.get("filename"),
                            "filename": content.get("filename"),
                            "content_type": content.get("mimetype"),
                            "url": file_url,
                            "size": content.get("filesize", 0),
                            "modified_at": _format_timestamp(content.get("timemodified")),
                            "created_at": _format_timestamp(content.get("timecreated")),
                            "section_name": sec_name,
                            "module_name": mod.get("name"),
                        }
                        files_metadata.append(file_rec)
                        if cmid:
                            cmid_to_file[cmid] = file_rec

                item = CanvasModuleItem(
                    id=cmid or (sec_id * 100 + m_idx),
                    title=mod.get("name") or "Unnamed Item",
                    position=m_idx + 1,
                    type=item_type,
                    module_id=sec_id,
                    url=mod.get("url"),
                    page_url=f"page-{cmid}" if modname == "page" else None,
                    content_id=cmid,
                )
                sec_items.append(item)

            c_mod = CanvasModule(
                id=sec_id,
                name=sec_name,
                position=s_idx + 1,
                items_count=len(sec_items),
                items=sec_items,
            )
            modules.append(c_mod)

        self.vault.save_modules(self.site_id, course_id, [m.model_dump() for m in modules])
        await emit(
            "modules",
            f"Saved {len(modules)} sections and modules",
            len(modules),
            len(modules),
        )

        # 3. Fetch Pages (mod_page)
        await emit("pages", "Fetching course pages...")
        raw_pages = await self.client.list_pages(course_id)
        pages_list: list[dict[str, Any]] = []

        for p in raw_pages:
            cmid = p.get("coursemodule") or p.get("id")
            slug = f"page-{cmid}"
            page_dict = {
                "url": slug,
                "title": p.get("name") or "Page",
                "body": p.get("content") or p.get("intro"),
                "page_id": cmid,
                "created_at": _format_timestamp(p.get("timecreated")),
                "updated_at": _format_timestamp(p.get("timemodified")),
            }
            pages_list.append(page_dict)
            self.vault.save_page(self.site_id, course_id, slug, page_dict)

        # Merge any pages extracted from section modules
        existing_slugs = {p["url"] for p in pages_list}
        for pm in pages_from_modules:
            if pm["url"] not in existing_slugs:
                pages_list.append(pm)
                self.vault.save_page(self.site_id, course_id, pm["url"], pm)

        self.vault.save_pages_list(self.site_id, course_id, pages_list)
        await emit("pages", f"Saved {len(pages_list)} pages", len(pages_list), len(pages_list))

        # 4. Fetch Assignments (mod_assign)
        await emit("assignments", "Fetching course assignments...")
        raw_assigns = await self.client.list_assignments(course_id)
        normalized_assignments: list[dict[str, Any]] = []
        submissions: list[dict[str, Any]] = []

        for a in raw_assigns:
            aid = a.get("id")
            norm_assign = {
                "id": aid,
                "name": a.get("name") or "Assignment",
                "description": a.get("intro"),
                "due_at": _format_timestamp(a.get("duedate")),
                "points_possible": a.get("grade"),
                "grading_type": "points",
            }
            normalized_assignments.append(norm_assign)

            # Check submission status for student
            if aid:
                try:
                    sub_status = await self.client.get_submission_status(aid)
                    last_sub = sub_status.get("lastattempt", {}).get("submission", {})
                    if last_sub:
                        submissions.append(
                            {
                                "assignment_id": aid,
                                "status": last_sub.get("status"),
                                "submitted_at": _format_timestamp(last_sub.get("timemodified")),
                            }
                        )
                except Exception:
                    pass

        self.vault.save_assignments(self.site_id, course_id, normalized_assignments)
        self.vault.save_submissions(self.site_id, course_id, submissions)
        await emit(
            "assignments",
            f"Saved {len(normalized_assignments)} assignments",
            len(normalized_assignments),
            len(normalized_assignments),
        )

        # 5. Fetch Forums & Discussions
        await emit("discussions", "Fetching course forums and discussions...")
        try:
            forums = await self.client.list_forums(course_id)
            discussions: list[dict[str, Any]] = []
            for forum in forums:
                fid = forum.get("id")
                f_name = forum.get("name") or "Forum"
                if fid:
                    threads = await self.client.list_discussions(fid)
                    for th in threads:
                        discussions.append(
                            {
                                "id": th.get("discussion") or th.get("id"),
                                "title": th.get("name") or f_name,
                                "message": th.get("message"),
                                "user_name": th.get("userfullname"),
                                "posted_at": _format_timestamp(th.get("created")),
                                "discussion_sub-entry_count": th.get("numreplies", 0),
                            }
                        )
            self.vault.save_discussions(self.site_id, course_id, discussions)
            await emit("discussions", f"Saved {len(discussions)} discussions")
        except Exception as e:
            logger.debug("Could not fetch forums for course %s: %s", course_id, e)

        # 6. Save Files Metadata & Download Assets
        self.vault.save_files_metadata(self.site_id, course_id, files_metadata)
        files_dir = self.vault.get_files_dir(self.site_id, course_id)
        file_hashes: dict[str, str] = {}

        if download_files and files_metadata:
            total_files = len(files_metadata)
            await emit("files", f"Downloading {total_files} course files...", 0, total_files)

            for idx, f_meta in enumerate(files_metadata):
                f_name = sanitize_filename(f_meta["display_name"])
                sec_folder = sanitize_filename(f_meta.get("section_name", "General"))
                dest_path = files_dir / sec_folder / f_name

                dl_url = f_meta.get("url")
                expected_size = f_meta.get("size", 0)

                if dl_url:
                    try:
                        await self.client.download_file(
                            download_url=dl_url,
                            dest_path=dest_path,
                            expected_size=expected_size,
                        )
                        if dest_path.exists():
                            rel_path = str(dest_path.relative_to(files_dir)).replace("\\", "/")
                            file_hashes[rel_path] = compute_sha256(dest_path)
                    except Exception as e:
                        logger.warning("Failed downloading %s: %s", f_name, e)

                current = idx + 1
                human_size = format_bytes(expected_size)
                await emit(
                    "files",
                    f"[{current}/{total_files}] Downloaded {f_name} ({human_size})",
                    current,
                    total_files,
                )

        # 7. Create and Save Course Metadata
        meta = CourseMeta(
            course_id=course_id,
            course_name=course_name,
            course_code=course_code,
            default_view="modules",
            last_synced_at=datetime.now().isoformat(),
            total_pages=len(pages_list),
            total_modules=len(modules),
            total_files=len(files_metadata),
            total_assignments=len(normalized_assignments),
            file_hashes=file_hashes,
        )
        self.vault.save_course_meta(self.site_id, course_id, meta)
        await emit("done", f"Moodle sync completed for {course_name}!", 100, 100)

        return meta

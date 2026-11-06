"""FastAPI application for Canvas Track.

Provides REST and SSE endpoints for site management, Canvas synchronization,
and offline course browsing with link rewriting and file serving.
"""

from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
import os
import subprocess
import sys
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from canvas_track.client import CanvasClient
from canvas_track.models import SiteConfig
from canvas_track.rewriter import CanvasLinkRewriter
from canvas_track.sync_manager import sync_manager
from canvas_track.vault import VaultManager, sanitize_filename

logger = logging.getLogger(__name__)


class AddSiteRequest(BaseModel):
    domain: str
    token: str
    site_id: str | None = None


class UpdateSiteRequest(BaseModel):
    domain: str
    token: str
    site_id: str | None = None


class AddCommentRequest(BaseModel):
    text: str


def create_app(vault_dir: Path | str | None = None) -> FastAPI:
    vault = VaultManager(vault_dir)
    app = FastAPI(title="Canvas Track", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # 1. Site Management
    @app.get("/api/sites")
    def list_sites() -> list[dict[str, Any]]:
        sites = vault.list_sites()
        return [
            {
                "id": s.id,
                "domain": s.domain,
                "base_url": s.base_url,
                "user_name": s.user_name,
                "user_id": s.user_id,
                "token": s.token,
                "created_at": s.created_at,
            }
            for s in sites
        ]

    @app.post("/api/sites")
    async def add_site(payload: AddSiteRequest) -> dict[str, Any]:
        domain = payload.domain.strip().lower()
        if not domain:
            raise HTTPException(status_code=400, detail="Canvas domain is required.")

        async with CanvasClient(domain, payload.token) as client:
            try:
                user = await client.get_user_profile()
            except Exception as e:
                logger.error("Failed to authenticate with Canvas at %s: %s", domain, e)
                msg = f"Failed to authenticate with Canvas at {domain}. Please check your token."
                raise HTTPException(status_code=401, detail=msg) from e

            # Check duplicate site detection
            existing_dup = vault.find_duplicate_site(domain, user.id, payload.token.strip())
            if existing_dup:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Duplicate site! A site for user '{existing_dup.user_name or user.name}' "
                        f"on {domain} is already registered under ID '{existing_dup.id}'."
                    ),
                )

            site_id = (
                payload.site_id.strip()
                if payload.site_id
                else sanitize_filename(domain.replace(".", "_"))
            )
            if vault.get_site(site_id):
                raise HTTPException(
                    status_code=409,
                    detail=f"Site ID '{site_id}' is already in use. Please choose a different ID.",
                )

            site = SiteConfig(
                id=site_id,
                domain=domain,
                base_url=client.base_url,
                user_name=user.name,
                user_id=user.id,
                token=payload.token.strip(),
            )
            vault.save_site(site)
            return {
                "success": True,
                "site": {
                    "id": site.id,
                    "domain": site.domain,
                    "base_url": site.base_url,
                    "user_name": site.user_name,
                    "user_id": site.user_id,
                    "token": site.token,
                },
            }

    @app.put("/api/sites/{site_id}")
    async def update_site(site_id: str, payload: UpdateSiteRequest) -> dict[str, Any]:
        existing = vault.get_site(site_id)
        if not existing:
            raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found.")

        domain = payload.domain.strip().lower()
        if not domain:
            raise HTTPException(status_code=400, detail="Canvas domain is required.")

        async with CanvasClient(domain, payload.token) as client:
            try:
                user = await client.get_user_profile()
            except Exception as e:
                logger.error("Failed to authenticate with Canvas at %s: %s", domain, e)
                msg = f"Failed to authenticate with Canvas at {domain}. Please check your token."
                raise HTTPException(status_code=401, detail=msg) from e

            new_sid = payload.site_id.strip() if payload.site_id else site_id
            # Duplicate check excluding the current site
            dup = vault.find_duplicate_site(
                domain, user.id, payload.token.strip(), exclude_site_id=site_id
            )
            if dup:
                raise HTTPException(
                    status_code=409,
                    detail=f"Duplicate site! Matching account already registered as '{dup.id}'.",
                )

            if new_sid != site_id and vault.get_site(new_sid):
                raise HTTPException(
                    status_code=409,
                    detail=f"Site ID '{new_sid}' is already in use. Please choose another ID.",
                )

            updated = vault.update_site(
                site_id=site_id,
                new_site_id=new_sid,
                domain=domain,
                token=payload.token.strip(),
                user_name=user.name,
                user_id=user.id,
            )
            return {
                "success": True,
                "site": {
                    "id": updated.id,
                    "domain": updated.domain,
                    "base_url": updated.base_url,
                    "user_name": updated.user_name,
                    "user_id": updated.user_id,
                    "token": updated.token,
                },
            }

    @app.post("/api/sites/deduplicate")
    def deduplicate_sites() -> dict[str, Any]:
        removed = vault.deduplicate_sites()
        return {"success": True, "removed": removed}

    @app.delete("/api/sites/{site_id}")
    def delete_site(site_id: str, delete_files: bool = Query(default=False)) -> dict[str, bool]:
        vault.delete_site(site_id, delete_files=delete_files)
        return {"success": True}

    # 2. Canvas Remote Courses
    @app.get("/api/sites/{site_id}/courses")
    async def list_remote_courses(site_id: str) -> list[dict[str, Any]]:
        site = vault.get_site(site_id)
        if not site:
            raise HTTPException(status_code=404, detail="Site not found.")

        async with CanvasClient(site.domain, site.token) as client:
            try:
                remote_courses = await client.list_courses()
            except Exception as e:
                logger.error("Failed to query remote courses for site %s: %s", site_id, e)
                raise HTTPException(
                    status_code=502, detail=f"Failed to fetch courses from Canvas: {e}"
                ) from e

        archived = {m.course_id: m for m in vault.list_archived_courses(site_id)}
        results: list[dict[str, Any]] = []
        for rc in remote_courses:
            meta = archived.get(rc.id)
            results.append(
                {
                    "id": rc.id,
                    "name": rc.name,
                    "course_code": rc.course_code,
                    "default_view": rc.default_view,
                    "is_synced": meta is not None,
                    "last_synced_at": meta.last_synced_at if meta else None,
                    "total_pages": meta.total_pages if meta else 0,
                    "total_modules": meta.total_modules if meta else 0,
                    "total_files": meta.total_files if meta else 0,
                }
            )
        return results

    # 3. Background Sync & Streaming (SSE)
    @app.get("/api/sync/jobs")
    def list_sync_jobs(site_id: str | None = None) -> list[dict[str, Any]]:
        return [s.model_dump() for s in sync_manager.list_jobs(site_id)]

    @app.get("/api/sites/{site_id}/courses/{course_id}/sync/status")
    def get_sync_status(site_id: str, course_id: int) -> dict[str, Any]:
        job = sync_manager.get_job(site_id, course_id)
        if not job:
            raise HTTPException(status_code=404, detail="No sync job found for course.")
        return job.status.model_dump()

    @app.post("/api/sites/{site_id}/courses/{course_id}/sync")
    def trigger_course_sync(
        site_id: str,
        course_id: int,
        download_files: bool = Query(default=True),
        course_name: str = Query(default=""),
    ) -> dict[str, Any]:
        site = vault.get_site(site_id)
        if not site:
            raise HTTPException(status_code=404, detail="Site not found.")

        job = sync_manager.start_job(
            vault=vault,
            site_id=site_id,
            course_id=course_id,
            course_name=course_name,
            download_files=download_files,
        )
        return {"status": job.status.status, "job": job.status.model_dump()}

    @app.post("/api/sync/all")
    async def sync_all_courses(
        download_files: bool = Query(default=True),
    ) -> dict[str, Any]:
        """Trigger synchronization for all remote courses across all registered sites."""
        sites = vault.list_sites()
        started_jobs: list[dict[str, Any]] = []
        for s in sites:
            try:
                async with CanvasClient(s.domain, s.token) as client:
                    remote_courses = await client.list_courses()
                for rc in remote_courses:
                    job = sync_manager.start_job(
                        vault=vault,
                        site_id=s.id,
                        course_id=rc.id,
                        course_name=rc.name,
                        download_files=download_files,
                    )
                    started_jobs.append(job.status.model_dump())
            except Exception as e:
                logger.error("Failed to query courses for sync all on site %s: %s", s.id, e)

        return {"success": True, "count": len(started_jobs), "jobs": started_jobs}

    @app.get("/api/sites/{site_id}/courses/{course_id}/sync")
    async def sync_course_stream(
        site_id: str,
        course_id: int,
        download_files: bool = Query(default=True),
        course_name: str = Query(default=""),
    ) -> StreamingResponse:
        site = vault.get_site(site_id)
        if not site:
            raise HTTPException(status_code=404, detail="Site not found.")

        job = sync_manager.start_job(
            vault=vault,
            site_id=site_id,
            course_id=course_id,
            course_name=course_name,
            download_files=download_files,
        )
        queue = job.add_subscriber()

        async def event_generator() -> AsyncGenerator[str, None]:
            try:
                while True:
                    item = await queue.get()
                    if item is None:
                        yield "data: [DONE]\n\n"
                        break
                    payload = json.dumps(item, ensure_ascii=False)
                    yield f"data: {payload}\n\n"
            except asyncio.CancelledError:
                pass
            finally:
                job.remove_subscriber(queue)

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    def get_rewriter(site_id: str, course_id: int) -> CanvasLinkRewriter:
        site = vault.get_site(site_id)
        domain = site.domain if site else None
        return CanvasLinkRewriter(site_id, course_id, base_domain=domain)

    # 4. Offline Vault Browsing APIs
    @app.get("/api/vault/sites/{site_id}/courses")
    def list_vault_courses(site_id: str) -> list[dict[str, Any]]:
        archived = vault.list_archived_courses(site_id)
        return [m.model_dump() for m in archived]

    @app.get("/api/vault/courses/{site_id}/{course_id}")
    def get_vault_course(site_id: str, course_id: int) -> dict[str, Any]:
        meta = vault.get_course_meta(site_id, course_id)
        if not meta:
            raise HTTPException(status_code=404, detail="Course archive not found.")

        api_raw = vault.get_api_raw_dir(site_id, course_id)
        raw_course = vault._read_raw_json(api_raw / "course.json") or {}

        # Rewrite syllabus if present
        syllabus = raw_course.get("syllabus_body")
        if syllabus:
            rewriter = get_rewriter(site_id, course_id)
            syllabus = rewriter.rewrite_html(syllabus)

        site = vault.get_site(site_id)
        canvas_url = f"https://{site.domain}/courses/{course_id}" if site and site.domain else ""

        return {
            "meta": meta.model_dump(),
            "course": raw_course,
            "syllabus_rewritten": syllabus,
            "canvas_url": canvas_url,
        }

    @app.delete("/api/vault/courses/{site_id}/{course_id}")
    def delete_vault_course(site_id: str, course_id: int) -> dict[str, Any]:
        job = sync_manager.get_job(site_id, course_id)
        if job and job.status.status == "running":
            raise HTTPException(
                status_code=400,
                detail="Cannot delete local backup while synchronization is in progress.",
            )

        size_bytes = vault.get_course_backup_size(site_id, course_id)
        deleted = vault.delete_course_archive(site_id, course_id)
        sync_manager.remove_job(site_id, course_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Course archive not found in vault.")

        return {
            "success": True,
            "site_id": site_id,
            "course_id": course_id,
            "freed_bytes": size_bytes,
            "message": "Local course backup deleted successfully.",
        }

    # Pages & Front Page
    @app.get("/api/vault/courses/{site_id}/{course_id}/front_page")
    def get_vault_front_page(site_id: str, course_id: int) -> dict[str, Any]:
        fp = vault.get_front_page(site_id, course_id)
        if not fp:
            return {"url": None, "title": None, "body": None, "body_rewritten": None}

        rewriter = get_rewriter(site_id, course_id)
        body = rewriter.rewrite_html(fp.get("body"))
        return {**fp, "body_rewritten": body}

    @app.get("/api/vault/courses/{site_id}/{course_id}/pages")
    def list_vault_pages(site_id: str, course_id: int) -> list[dict[str, Any]]:
        return vault.get_pages_list(site_id, course_id)

    @app.get("/api/vault/courses/{site_id}/{course_id}/pages/{page_url}")
    def get_vault_page(site_id: str, course_id: int, page_url: str) -> dict[str, Any]:
        page = vault.get_page(site_id, course_id, page_url)
        if not page:
            raise HTTPException(status_code=404, detail=f"Page '{page_url}' not found.")

        rewriter = get_rewriter(site_id, course_id)
        body = rewriter.rewrite_html(page.get("body"))
        return {**page, "body_rewritten": body}

    # Modules
    @app.get("/api/vault/courses/{site_id}/{course_id}/modules")
    def list_vault_modules(site_id: str, course_id: int) -> list[dict[str, Any]]:
        return vault.get_modules(site_id, course_id)

    # Assignments & Submissions
    @app.get("/api/vault/courses/{site_id}/{course_id}/assignments")
    def list_vault_assignments(site_id: str, course_id: int) -> list[dict[str, Any]]:
        assignments = vault.get_assignments(site_id, course_id)
        rewriter = get_rewriter(site_id, course_id)
        for a in assignments:
            if a.get("description"):
                a["description_rewritten"] = rewriter.rewrite_html(a["description"])
        return assignments

    @app.get("/api/vault/courses/{site_id}/{course_id}/submissions")
    def list_vault_submissions(site_id: str, course_id: int) -> list[dict[str, Any]]:
        return vault.get_submissions(site_id, course_id)

    # Announcements & Discussions
    @app.get("/api/vault/courses/{site_id}/{course_id}/announcements")
    def list_vault_announcements(site_id: str, course_id: int) -> list[dict[str, Any]]:
        announcements = vault.get_announcements(site_id, course_id)
        rewriter = get_rewriter(site_id, course_id)
        for ann in announcements:
            if ann.get("message"):
                ann["message_rewritten"] = rewriter.rewrite_html(ann["message"])
        return announcements

    @app.get("/api/vault/courses/{site_id}/{course_id}/discussions")
    def list_vault_discussions(site_id: str, course_id: int) -> list[dict[str, Any]]:
        topics = vault.get_discussions(site_id, course_id)
        rewriter = get_rewriter(site_id, course_id)
        for top in topics:
            if top.get("message"):
                top["message_rewritten"] = rewriter.rewrite_html(top["message"])
        return topics

    @app.get("/api/vault/courses/{site_id}/{course_id}/discussions/{topic_id}")
    def get_vault_discussion_thread(site_id: str, course_id: int, topic_id: int) -> dict[str, Any]:
        entry = vault.get_discussion_entry(site_id, course_id, topic_id)
        if not entry:
            raise HTTPException(status_code=404, detail="Discussion thread not found.")
        return entry

    # Files listing and serving
    @app.get("/api/vault/courses/{site_id}/{course_id}/files")
    def list_vault_files(site_id: str, course_id: int) -> list[dict[str, Any]]:
        files = vault.get_files_metadata(site_id, course_id)
        result: list[dict[str, Any]] = []
        for f in files:
            fid = f.get("id")
            path = vault.get_course_file_path(site_id, course_id, fid) if fid else None
            item = dict(f)
            item["is_downloaded"] = path is not None and path.exists()
            if path and path.exists():
                item["local_path"] = str(path.resolve())
                item["local_size"] = path.stat().st_size
            result.append(item)
        return result

    @app.get("/api/vault/files/{site_id}/{course_id}/{file_id}")
    def serve_vault_file(site_id: str, course_id: int, file_id: int) -> FileResponse:
        file_path = vault.get_course_file_path(site_id, course_id, file_id)
        if not file_path or not file_path.exists():
            raise HTTPException(status_code=404, detail="File content not found on disk.")

        files = vault.get_files_metadata(site_id, course_id)
        target_file = next(
            (f for f in files if f.get("id") == file_id or str(f.get("id")) == str(file_id)),
            {},
        )

        media_type = target_file.get("content_type")
        if not media_type:
            guessed_type, _ = mimetypes.guess_type(file_path.name)
            media_type = guessed_type or "application/octet-stream"

        return FileResponse(
            file_path,
            filename=target_file.get("display_name") or file_path.name,
            media_type=media_type,
            content_disposition_type="inline",
        )

    @app.post("/api/vault/files/{site_id}/{course_id}/{file_id}/open")
    def open_vault_file_in_system(site_id: str, course_id: int, file_id: int) -> dict[str, Any]:
        """Open the downloaded local course file using the operating system's default viewer."""
        file_path = vault.get_course_file_path(site_id, course_id, file_id)
        if not file_path or not file_path.exists():
            raise HTTPException(
                status_code=404,
                detail=(
                    f"File {file_id} not found in local vault. Ensure course files are downloaded."
                ),
            )

        abs_path = str(file_path.resolve())
        try:
            if sys.platform == "win32":
                os.startfile(abs_path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", abs_path])
            else:
                subprocess.Popen(["xdg-open", abs_path])
        except Exception as e:
            logger.exception("Failed to launch system viewer for %s", abs_path)
            raise HTTPException(status_code=500, detail=f"Failed to open file: {e}") from e

        return {
            "success": True,
            "file_id": file_id,
            "filename": file_path.name,
            "file_path": abs_path,
            "message": f"Opened {file_path.name} in system viewer.",
        }

    # 5. Page Comments / Notes
    @app.get("/api/vault/courses/{site_id}/{course_id}/pages/{page_url}/comments")
    def get_page_comments(site_id: str, course_id: int, page_url: str) -> list[dict[str, Any]]:
        return vault.get_page_comments(site_id, course_id, page_url)

    @app.post("/api/vault/courses/{site_id}/{course_id}/pages/{page_url}/comments")
    def add_page_comment(
        site_id: str, course_id: int, page_url: str, payload: AddCommentRequest
    ) -> dict[str, Any]:
        text = payload.text.strip()
        if not text:
            raise HTTPException(status_code=400, detail="Comment text cannot be empty.")
        comment = vault.add_page_comment(site_id, course_id, page_url, text)
        return {"success": True, "comment": comment}

    @app.delete("/api/vault/courses/{site_id}/{course_id}/pages/{page_url}/comments/{comment_id}")
    def delete_page_comment(
        site_id: str, course_id: int, page_url: str, comment_id: str
    ) -> dict[str, bool]:
        deleted = vault.delete_page_comment(site_id, course_id, page_url, comment_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Comment not found.")
        return {"success": True}

    # 6. Serve Svelte Frontend Static Build
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

        @app.get("/{full_path:path}")
        async def serve_spa(request: Request, full_path: str) -> FileResponse:
            target = static_dir / full_path
            if target.is_file():
                return FileResponse(target)
            return FileResponse(static_dir / "index.html")

    return app

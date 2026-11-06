"""Strictly read-only Canvas LMS API Client.

Performs only GET requests against the Canvas REST API, with automated
pagination, rate limit throttling, and resumable file streaming.
"""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import Any

import httpx

from canvas_track.models import (
    CanvasAssignment,
    CanvasCourse,
    CanvasFile,
    CanvasFolder,
    CanvasModule,
    CanvasPage,
    CanvasSubmission,
    CanvasUser,
)

logger = logging.getLogger(__name__)


def parse_link_header(header_value: str | None) -> dict[str, str]:
    """Parse RFC 5988 Link header into a dict of {rel: url}."""
    links: dict[str, str] = {}
    if not header_value:
        return links
    pattern = re.compile(r'<([^>]+)>;\s*rel="([^"]+)"')
    for match in pattern.finditer(header_value):
        url, rel = match.groups()
        links[rel] = url
    return links


class CanvasClient:
    """Read-only asynchronous client for Canvas LMS."""

    def __init__(self, base_url: str, token: str, timeout: float = 30.0) -> None:
        clean_url = base_url.strip().rstrip("/")
        if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
            clean_url = f"https://{clean_url}"
        self.base_url = clean_url
        self.api_url = f"{self.base_url}/api/v1"
        self.token = token.strip()
        self.timeout = timeout
        self._headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "User-Agent": "CanvasTrack/0.1.0",
        }
        self._http_client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        """Get or initialize persistent HTTP client session with connection pooling."""
        if self._http_client is None or self._http_client.is_closed:
            limits = httpx.Limits(
                max_keepalive_connections=20, max_connections=50, keepalive_expiry=30.0
            )
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout, read=60.0),
                limits=limits,
                headers=self._headers,
                follow_redirects=True,
            )
        return self._http_client

    async def aclose(self) -> None:
        """Close persistent HTTP client session and release connections."""
        if self._http_client is not None and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None

    async def close(self) -> None:
        """Alias for aclose."""
        await self.aclose()

    async def __aenter__(self) -> CanvasClient:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.aclose()

    async def _handle_rate_limits(self, response: httpx.Response) -> None:
        """Throttle if Canvas rate limit remaining quota is low."""
        remaining_str = response.headers.get("X-Rate-Limit-Remaining")
        if remaining_str:
            try:
                remaining = float(remaining_str)
                if remaining < 10.0:
                    wait_time = (10.0 - remaining) * 0.5 + 1.0
                    logger.warning(
                        "Canvas rate limit low (%.1f remaining). Throttling for %.2fs",
                        remaining,
                        wait_time,
                    )
                    await asyncio.sleep(wait_time)
            except ValueError:
                pass

    async def get_raw(
        self,
        endpoint_or_url: str,
        params: dict[str, Any] | None = None,
        retries: int = 3,
    ) -> httpx.Response:
        """Execute a strictly read-only GET request with automatic retry."""
        if endpoint_or_url.startswith("http://") or endpoint_or_url.startswith("https://"):
            url = endpoint_or_url
        else:
            clean_endpoint = endpoint_or_url.lstrip("/")
            url = f"{self.api_url}/{clean_endpoint}"

        backoff = 1.0
        client = self._get_client()
        for attempt in range(retries):
            try:
                response = await client.get(url, headers=self._headers, params=params)
                await self._handle_rate_limits(response)

                if response.status_code in (403, 429) and "rate limit" in response.text.lower():
                    logger.warning(
                        "Rate limited by Canvas (attempt %d/%d). Sleeping %.1fs",
                        attempt + 1,
                        retries,
                        backoff,
                    )
                    await asyncio.sleep(backoff)
                    backoff *= 2
                    continue

                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (401, 404):
                    # Do not retry unauthorized or not found
                    raise
                if attempt == retries - 1:
                    raise
                await asyncio.sleep(backoff)
                backoff *= 2
            except (httpx.TransportError, httpx.TimeoutException):
                if attempt == retries - 1:
                    raise
                await asyncio.sleep(backoff)
                backoff *= 2

        raise RuntimeError(f"Failed to fetch {url} after {retries} retries")

    async def get_json(self, endpoint_or_url: str, params: dict[str, Any] | None = None) -> Any:
        """Fetch and parse JSON from a GET endpoint."""
        resp = await self.get_raw(endpoint_or_url, params=params)
        return resp.json()

    async def get_paginated(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        per_page: int = 100,
    ) -> list[dict[str, Any]]:
        """Fetch all pages of a paginated Canvas GET endpoint."""
        query_params = dict(params or {})
        query_params["per_page"] = per_page

        all_items: list[dict[str, Any]] = []
        next_url: str | None = f"{self.api_url}/{endpoint.lstrip('/')}"
        is_first_page = True

        while next_url:
            current_params = query_params if is_first_page else None
            try:
                resp = await self.get_raw(next_url, params=current_params)
            except httpx.HTTPStatusError as e:
                # If an optional course feature is disabled, Canvas returns 404/403
                if is_first_page and e.response.status_code in (404, 403):
                    logger.debug(
                        "Endpoint '%s' returned %d; returning empty list",
                        endpoint,
                        e.response.status_code,
                    )
                    return []
                raise

            data = resp.json()
            if isinstance(data, list):
                all_items.extend(data)
            else:
                break

            links = parse_link_header(resp.headers.get("Link"))
            next_url = links.get("next")
            is_first_page = False

        return all_items

    async def get_user_profile(self) -> CanvasUser:
        """Fetch current user profile to verify token and permissions."""
        data = await self.get_json("users/self")
        return CanvasUser.model_validate(data)

    async def list_courses(self) -> list[CanvasCourse]:
        """Fetch courses the user has access to."""
        params = {
            "include[]": ["term", "syllabus_body", "front_page", "total_students"],
            "state[]": ["available", "completed"],
        }
        raw_courses = await self.get_paginated("courses", params=params)
        courses: list[CanvasCourse] = []
        for c in raw_courses:
            # Filter out deleted courses or entries without an ID/name
            if c.get("id") and c.get("name"):
                courses.append(CanvasCourse.model_validate(c))
        return courses

    async def get_course(self, course_id: int) -> CanvasCourse:
        """Fetch course details including default_view, front_page, and syllabus."""
        params = {"include[]": ["term", "syllabus_body", "front_page", "total_students"]}
        data = await self.get_json(f"courses/{course_id}", params=params)
        return CanvasCourse.model_validate(data)

    async def get_course_front_page(self, course_id: int) -> CanvasPage | None:
        """Fetch the designated front page for a course, if configured."""
        try:
            data = await self.get_json(f"courses/{course_id}/front_page")
            return CanvasPage.model_validate(data)
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (404, 403):
                return None
            raise

    async def list_course_pages(self, course_id: int) -> list[CanvasPage]:
        """Fetch list of all wiki pages in a course."""
        raw_pages = await self.get_paginated(f"courses/{course_id}/pages")
        pages: list[CanvasPage] = []
        for p in raw_pages:
            pages.append(CanvasPage.model_validate(p))
        return pages

    async def get_course_page(self, course_id: int, page_url: str) -> CanvasPage | None:
        """Fetch full details and HTML body for a single course wiki page."""
        try:
            data = await self.get_json(f"courses/{course_id}/pages/{page_url}")
            return CanvasPage.model_validate(data)
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (404, 403):
                return None
            raise

    async def get_file(self, course_id: int, file_id: int) -> CanvasFile | None:
        """Fetch metadata for an individual course file by ID."""
        try:
            data = await self.get_json(f"courses/{course_id}/files/{file_id}")
            return CanvasFile.model_validate(data)
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (404, 403):
                # Fallback to global files endpoint if course files endpoint is forbidden
                try:
                    data = await self.get_json(f"files/{file_id}")
                    return CanvasFile.model_validate(data)
                except httpx.HTTPStatusError as e2:
                    if e2.response.status_code in (404, 403):
                        return None
                    raise
            raise

    async def list_course_modules(self, course_id: int) -> list[CanvasModule]:
        """Fetch all course modules and their nested module items."""
        params = {"include[]": ["items"]}
        raw_modules = await self.get_paginated(f"courses/{course_id}/modules", params=params)
        modules: list[CanvasModule] = []
        for m in raw_modules:
            modules.append(CanvasModule.model_validate(m))
        return modules

    async def list_course_files(self, course_id: int) -> list[CanvasFile]:
        """Fetch all files belonging to a course."""
        raw_files = await self.get_paginated(f"courses/{course_id}/files")
        files: list[CanvasFile] = []
        for f in raw_files:
            files.append(CanvasFile.model_validate(f))
        return files

    async def list_course_folders(self, course_id: int) -> list[CanvasFolder]:
        """Fetch all folder structures in a course."""
        raw_folders = await self.get_paginated(f"courses/{course_id}/folders")
        folders: list[CanvasFolder] = []
        for f in raw_folders:
            folders.append(CanvasFolder.model_validate(f))
        return folders

    async def list_course_assignments(self, course_id: int) -> list[CanvasAssignment]:
        """Fetch course assignments and rubrics."""
        params = {"include[]": ["rubric", "all_dates"]}
        raw_assignments = await self.get_paginated(
            f"courses/{course_id}/assignments", params=params
        )
        assignments: list[CanvasAssignment] = []
        for a in raw_assignments:
            assignments.append(CanvasAssignment.model_validate(a))
        return assignments

    async def list_course_submissions(self, course_id: int) -> list[CanvasSubmission]:
        """Fetch user's own submissions with rubric assessment and teacher comments."""
        params = {
            "include[]": ["rubric_assessment", "submission_comments", "assignment"],
        }
        raw_submissions = await self.get_paginated(
            f"courses/{course_id}/students/submissions", params=params
        )
        submissions: list[CanvasSubmission] = []
        for s in raw_submissions:
            submissions.append(CanvasSubmission.model_validate(s))
        return submissions

    async def list_course_announcements(self, course_id: int) -> list[dict[str, Any]]:
        """Fetch course announcements."""
        params = {"context_codes[]": [f"course_{course_id}"]}
        return await self.get_paginated("announcements", params=params)

    async def list_course_discussions(self, course_id: int) -> list[dict[str, Any]]:
        """Fetch course discussion topics."""
        return await self.get_paginated(f"courses/{course_id}/discussion_topics")

    async def get_discussion_entries(self, course_id: int, topic_id: int) -> dict[str, Any]:
        """Fetch full discussion topic thread including all student replies."""
        try:
            return await self.get_json(f"courses/{course_id}/discussion_topics/{topic_id}/view")
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (404, 403):
                return {}
            raise

    async def download_file(
        self,
        download_url: str,
        dest_path: Path,
        expected_size: int = 0,
    ) -> bool:
        """Download a file with resume support and streaming chunks."""
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        existing_size = dest_path.stat().st_size if dest_path.exists() else 0
        if expected_size > 0 and existing_size == expected_size:
            logger.debug("File %s already downloaded (%d bytes)", dest_path.name, existing_size)
            return True

        headers = dict(self._headers)
        mode = "wb"
        if existing_size > 0:
            headers["Range"] = f"bytes={existing_size}-"
            mode = "ab"

        client = self._get_client()
        async with client.stream("GET", download_url, headers=headers) as resp:
            if resp.status_code == 416:  # Range not satisfiable (already complete)
                return True
            if resp.status_code not in (200, 206):
                # If Range wasn't accepted, restart download from beginning
                if mode == "ab":
                    headers.pop("Range", None)
                    async with client.stream("GET", download_url, headers=headers) as retry_resp:
                        retry_resp.raise_for_status()
                        with open(dest_path, "wb") as f:
                            async for chunk in retry_resp.aiter_bytes(chunk_size=65536):
                                f.write(chunk)
                        return True
                resp.raise_for_status()

            with open(dest_path, mode) as f:
                async for chunk in resp.aiter_bytes(chunk_size=65536):
                    f.write(chunk)

        return True

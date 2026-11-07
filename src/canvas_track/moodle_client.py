"""Strictly read-only Moodle LMS REST Web Service Client.

Performs student-level POST requests against Moodle's REST API endpoint
(/webservice/rest/server.php) with automated token verification, error parsing,
and resumable file streaming.
"""

from __future__ import annotations

import asyncio
import logging
import urllib.parse
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class MoodleAPIError(Exception):
    """Exception raised when Moodle REST API returns an error response."""

    def __init__(self, message: str, errorcode: str | None = None, exception: str | None = None):
        super().__init__(message)
        self.errorcode = errorcode
        self.exception = exception


class MoodleClient:
    """Read-only asynchronous client for Moodle LMS Web Services."""

    def __init__(self, base_url: str, token: str, timeout: float = 30.0) -> None:
        clean_url = base_url.strip().rstrip("/")
        if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
            clean_url = f"https://{clean_url}"
        self.base_url = clean_url
        self.api_url = f"{self.base_url}/webservice/rest/server.php"
        self.token = token.strip()
        self.timeout = timeout
        self._headers = {
            "Accept": "application/json",
            "User-Agent": "CanvasTrack-Moodle/0.1.0",
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

    async def __aenter__(self) -> MoodleClient:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.aclose()

    async def call(
        self,
        wsfunction: str,
        params: dict[str, Any] | None = None,
        retries: int = 3,
    ) -> Any:
        """Call a Moodle Web Service function with automatic retries and error checking."""
        data: dict[str, Any] = {
            "wstoken": self.token,
            "wsfunction": wsfunction,
            "moodlewsrestformat": "json",
        }
        if params:
            data.update(params)

        backoff = 1.0
        client = self._get_client()

        for attempt in range(retries):
            try:
                response = await client.post(self.api_url, data=data)
                response.raise_for_status()

                result = response.json()
                # Check for Moodle API error payloads
                if isinstance(result, dict) and (
                    "exception" in result or "errorcode" in result or "error" in result
                ):
                    errorcode = result.get("errorcode", "moodle_error")
                    message = result.get("message") or result.get("error", "Unknown Moodle error")
                    exception = result.get("exception")
                    raise MoodleAPIError(
                        f"Moodle error ({errorcode}): {message}",
                        errorcode=errorcode,
                        exception=exception,
                    )

                return result

            except MoodleAPIError:
                # Do not retry invalid token or explicit API errors
                raise
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (401, 403, 404):
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

        raise RuntimeError(f"Failed to call Moodle function '{wsfunction}' after {retries} retries")

    async def get_site_info(self) -> dict[str, Any]:
        """Fetch Moodle site and student user profile info."""
        return await self.call("core_webservice_get_site_info")

    async def list_courses(self, userid: int | None = None) -> list[dict[str, Any]]:
        """Fetch all courses the student is enrolled in."""
        uid = userid
        if uid is None:
            info = await self.get_site_info()
            uid = info.get("userid")

        courses = await self.call("core_enrol_get_users_courses", {"userid": uid})
        return courses if isinstance(courses, list) else []

    async def get_course_contents(self, course_id: int) -> list[dict[str, Any]]:
        """Fetch all course sections and activity modules (resources, pages, assignments, etc.)."""
        contents = await self.call("core_course_get_contents", {"courseid": course_id})
        return contents if isinstance(contents, list) else []

    async def list_assignments(self, course_id: int) -> list[dict[str, Any]]:
        """Fetch assignments for the course."""
        try:
            data = await self.call("mod_assign_get_assignments", {"courseids[0]": course_id})
            courses = data.get("courses", []) if isinstance(data, dict) else []
            for c in courses:
                if c.get("id") == course_id or str(c.get("id")) == str(course_id):
                    return c.get("assignments", [])
            # Fallback to first course in list
            if courses:
                return courses[0].get("assignments", [])
            return []
        except MoodleAPIError as e:
            logger.warning("Could not fetch assignments for Moodle course %s: %s", course_id, e)
            return []

    async def get_submission_status(self, assign_id: int) -> dict[str, Any]:
        """Fetch student's own submission status for an assignment."""
        try:
            return await self.call("mod_assign_get_submission_status", {"assignid": assign_id})
        except MoodleAPIError as e:
            logger.debug("Could not fetch submission status for assign %s: %s", assign_id, e)
            return {}

    async def list_pages(self, course_id: int) -> list[dict[str, Any]]:
        """Fetch rich text pages (mod_page) for the course."""
        try:
            data = await self.call("mod_page_get_pages_by_courses", {"courseids[0]": course_id})
            if isinstance(data, dict):
                return data.get("pages", [])
            return []
        except MoodleAPIError as e:
            logger.debug("Could not fetch pages for Moodle course %s: %s", course_id, e)
            return []

    async def list_forums(self, course_id: int) -> list[dict[str, Any]]:
        """Fetch discussion forums for the course."""
        try:
            data = await self.call("mod_forum_get_forums_by_courses", {"courseids[0]": course_id})
            return data if isinstance(data, list) else []
        except MoodleAPIError as e:
            logger.debug("Could not fetch forums for Moodle course %s: %s", course_id, e)
            return []

    async def list_discussions(self, forum_id: int) -> list[dict[str, Any]]:
        """Fetch discussion threads for a forum."""
        try:
            data = await self.call("mod_forum_get_forum_discussions", {"forumid": forum_id})
            if isinstance(data, dict):
                return data.get("discussions", [])
            return []
        except MoodleAPIError as e:
            logger.debug("Could not fetch discussions for forum %s: %s", forum_id, e)
            return []

    async def download_file(
        self,
        download_url: str,
        dest_path: Path,
        expected_size: int = 0,
    ) -> bool:
        """Download a file with token authentication, resume support, and chunk streaming."""
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        existing_size = dest_path.stat().st_size if dest_path.exists() else 0
        if expected_size > 0 and existing_size == expected_size:
            logger.debug("File %s already downloaded (%d bytes)", dest_path.name, existing_size)
            return True

        # Append wstoken if not already present in download URL
        parsed = urllib.parse.urlparse(download_url)
        query_params = urllib.parse.parse_qs(parsed.query)
        if "token" not in query_params:
            delimiter = "&" if parsed.query else "?"
            authenticated_url = f"{download_url}{delimiter}token={self.token}"
        else:
            authenticated_url = download_url

        headers = dict(self._headers)
        mode = "wb"
        if existing_size > 0:
            headers["Range"] = f"bytes={existing_size}-"
            mode = "ab"

        client = self._get_client()
        async with client.stream("GET", authenticated_url, headers=headers) as resp:
            if resp.status_code == 416:  # Range not satisfiable (already complete)
                return True
            if resp.status_code not in (200, 206):
                # If Range wasn't accepted, restart download from beginning
                if mode == "ab":
                    headers.pop("Range", None)
                    async with client.stream(
                        "GET", authenticated_url, headers=headers
                    ) as retry_resp:
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

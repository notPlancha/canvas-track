"""HTML content link and media rewriter for offline Canvas viewing.

Rewrites internal Canvas links, embedded images, and file download references to
resolve locally within the offline vault and Svelte application router.
"""

from __future__ import annotations

import re


class CanvasLinkRewriter:
    """Rewrites Canvas internal links and embedded media for offline consumption."""

    def __init__(
        self,
        site_id: str,
        course_id: int,
        base_domain: str | None = None,
        file_id_map: dict[int, str] | None = None,  # file_id -> relative local path
    ) -> None:
        self.site_id = site_id
        self.course_id = course_id
        self.base_domain = base_domain.lower().strip() if base_domain else ""
        self.file_id_map = file_id_map or {}

    def rewrite_html(self, html_content: str | None) -> str:
        """Rewrite all Canvas internal URLs within an HTML fragment."""
        if not html_content:
            return ""

        content = html_content

        # 1. Rewrite $CANVAS_OBJECT_REFERENCE$ links
        content = re.sub(
            r'href=[\'"]\$CANVAS_OBJECT_REFERENCE\$/pages/([^\'"?#]+)[\'"]',
            rf'href="#/site/{self.site_id}/course/{self.course_id}/pages/\1"',
            content,
            flags=re.IGNORECASE,
        )
        content = re.sub(
            r'href=[\'"]\$CANVAS_OBJECT_REFERENCE\$/assignments/(\d+)[\'"]',
            rf'href="#/site/{self.site_id}/course/{self.course_id}/assignments/\1"',
            content,
            flags=re.IGNORECASE,
        )
        content = re.sub(
            r'href=[\'"]\$CANVAS_OBJECT_REFERENCE\$/modules[\'"]',
            rf'href="#/site/{self.site_id}/course/{self.course_id}/modules"',
            content,
            flags=re.IGNORECASE,
        )
        content = re.sub(
            r'(?:href|src)=[\'"]\$CANVAS_OBJECT_REFERENCE\$/files/(\d+)(?:[?#][^\'"\s]*)?[\'"]',
            rf'href="/api/vault/files/{self.site_id}/{self.course_id}/\1"',
            content,
            flags=re.IGNORECASE,
        )

        # Domain matcher: matches self.base_domain if set, or any domain prefix
        domain_prefix = (
            rf"(?:https?://(?:{re.escape(self.base_domain)}|[^/'\"\s]+))?"
            if self.base_domain
            else r"(?:https?://[^/'\"\s]+)?"
        )

        # 2. Rewrite Canvas page links: /courses/:course_id/pages/:page_url
        page_pattern = re.compile(
            rf"{domain_prefix}/courses/{self.course_id}/pages/([a-zA-Z0-9_\-\.\%]+)(?:[?#][^'\"\s]*)?",
            re.IGNORECASE,
        )
        content = page_pattern.sub(
            rf"#/site/{self.site_id}/course/{self.course_id}/pages/\1", content
        )

        # 3. Rewrite Canvas assignment links: /courses/:course_id/assignments/:assignment_id
        assignment_pattern = re.compile(
            rf"{domain_prefix}/courses/{self.course_id}/assignments/(\d+)(?:[?#][^'\"\s]*)?",
            re.IGNORECASE,
        )
        content = assignment_pattern.sub(
            rf"#/site/{self.site_id}/course/{self.course_id}/assignments/\1", content
        )

        # 4. Rewrite Canvas discussion links: /courses/:course_id/discussion_topics/:topic_id
        disc_pattern = re.compile(
            rf"{domain_prefix}/courses/{self.course_id}/discussion_topics/(\d+)(?:[?#][^'\"\s]*)?",
            re.IGNORECASE,
        )
        content = disc_pattern.sub(
            rf"#/site/{self.site_id}/course/{self.course_id}/discussions/\1", content
        )

        # 5. Rewrite Canvas modules links: /courses/:course_id/modules
        module_pattern = re.compile(
            rf"{domain_prefix}/courses/{self.course_id}/modules(?:[?#][^'\"\s]*)?",
            re.IGNORECASE,
        )
        content = module_pattern.sub(
            rf"#/site/{self.site_id}/course/{self.course_id}/modules", content
        )

        # 6. Rewrite folder preview file links:
        # /courses/:course_id/files/folder/<path>?preview=:file_id
        folder_preview_pattern = re.compile(
            rf"{domain_prefix}/courses/(?:{self.course_id}|\d+)/files/folder/[^?#'\"\s]*\?"
            r"(?:[^#'\"\s]*&)?preview=(\d+)(?:[#][^'\"\s]*)?",
            re.IGNORECASE,
        )

        def replace_file(match: re.Match[str]) -> str:
            fid = int(match.group(1))
            return f"/api/vault/files/{self.site_id}/{self.course_id}/{fid}"

        content = folder_preview_pattern.sub(replace_file, content)

        # 7. Rewrite file downloads and preview links: /courses/:course_id/files/:file_id
        file_pattern = re.compile(
            rf"{domain_prefix}/courses/{self.course_id}/files/(\d+)(?:/(?:download|preview))?(?:[?#][^'\"\s]*)?",
            re.IGNORECASE,
        )
        content = file_pattern.sub(replace_file, content)

        # 8. Also handle user and global file links: /users/:user_id/files/:file_id, /files/:file_id
        global_file_pattern = re.compile(
            rf"{domain_prefix}(?:/users/\d+)?/files/(\d+)(?:/(?:download|preview))?(?:[?#][^'\"\s]*)?",
            re.IGNORECASE,
        )
        content = global_file_pattern.sub(replace_file, content)

        return content

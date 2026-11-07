"""HTML content link and media rewriter for offline Moodle viewing.

Rewrites internal Moodle links (/mod/page/view.php, /mod/resource/view.php,
/mod/assign/view.php, /mod/forum/view.php, pluginfile.php) to resolve
locally within the offline vault and Svelte application router.
"""

from __future__ import annotations

import re


class MoodleLinkRewriter:
    """Rewrites Moodle internal links and embedded media for offline consumption."""

    def __init__(
        self,
        site_id: str,
        course_id: int,
        base_domain: str | None = None,
        cmid_to_page_url: dict[int, str] | None = None,
        cmid_to_file_id: dict[int, int] | None = None,
    ) -> None:
        self.site_id = site_id
        self.course_id = course_id
        self.base_domain = base_domain.lower().strip() if base_domain else ""
        self.cmid_to_page_url = cmid_to_page_url or {}
        self.cmid_to_file_id = cmid_to_file_id or {}

    def rewrite_html(self, html_content: str | None) -> str:
        """Rewrite all Moodle internal URLs within an HTML fragment."""
        if not html_content:
            return ""

        content = html_content

        # Domain matcher: matches self.base_domain if set, or generic http/https prefix
        domain_prefix = (
            rf"(?:https?://(?:{re.escape(self.base_domain)}|[^/'\"\s]+))?"
            if self.base_domain
            else r"(?:https?://[^/'\"\s]+)?"
        )

        # 1. Rewrite course home: /course/view.php?id=:course_id
        course_home_pattern = re.compile(
            rf"{domain_prefix}/course/view\.php\?id={self.course_id}(?:[&#][^'\"\s]*)?",
            re.IGNORECASE,
        )
        content = course_home_pattern.sub(
            rf"#/site/{self.site_id}/course/{self.course_id}/modules", content
        )

        # 2. Rewrite page links: /mod/page/view.php?id=(:cmid)
        def _replace_page(match: re.Match[str]) -> str:
            cmid = int(match.group(1))
            page_id = self.cmid_to_page_url.get(cmid, str(cmid))
            return f"#/site/{self.site_id}/course/{self.course_id}/pages/{page_id}"

        content = re.sub(
            rf"{domain_prefix}/mod/page/view\.php\?id=(\d+)(?:[&#][^'\"\s]*)?",
            _replace_page,
            content,
            flags=re.IGNORECASE,
        )

        # 3. Rewrite resource/file links: /mod/resource/view.php?id=(:cmid)
        def _replace_resource(match: re.Match[str]) -> str:
            cmid = int(match.group(1))
            fid = self.cmid_to_file_id.get(cmid, cmid)
            return f"/api/vault/files/{self.site_id}/{self.course_id}/{fid}"

        content = re.sub(
            rf"{domain_prefix}/mod/resource/view\.php\?id=(\d+)(?:[&#][^'\"\s]*)?",
            _replace_resource,
            content,
            flags=re.IGNORECASE,
        )

        # 4. Rewrite assignment links: /mod/assign/view.php?id=(:cmid)
        content = re.sub(
            rf"{domain_prefix}/mod/assign/view\.php\?id=(\d+)(?:[&#][^'\"\s]*)?",
            rf"#/site/{self.site_id}/course/{self.course_id}/assignments/\1",
            content,
            flags=re.IGNORECASE,
        )

        # 5. Rewrite forum/discussion links: /mod/forum/view.php?id=(:cmid)
        content = re.sub(
            rf"{domain_prefix}/mod/forum/view\.php\?id=(\d+)(?:[&#][^'\"\s]*)?",
            rf"#/site/{self.site_id}/course/{self.course_id}/discussions/\1",
            content,
            flags=re.IGNORECASE,
        )

        # 6. Rewrite pluginfile embedded images and media
        content = re.sub(
            rf"(href|src)=[\'\"]{domain_prefix}/(?:webservice/)?pluginfile\.php/(\d+)/[^\'\"]*[\'\"]",
            rf'\1="/api/vault/files/{self.site_id}/{self.course_id}/\2"',
            content,
            flags=re.IGNORECASE,
        )

        return content

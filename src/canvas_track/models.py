"""Data models for Canvas LMS entities and local vault state."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CanvasUser(BaseModel):
    id: int
    name: str
    short_name: str | None = None
    sortable_name: str | None = None
    avatar_url: str | None = None
    primary_email: str | None = None
    login_id: str | None = None


class CanvasCourse(BaseModel):
    id: int
    name: str
    course_code: str | None = None
    workflow_state: str | None = None
    account_id: int | None = None
    start_at: str | None = None
    end_at: str | None = None
    default_view: str = "wiki"  # wiki, modules, syllabus, assignments, feed
    syllabus_body: str | None = None
    front_page_title: str | None = None
    enrollments: list[dict[str, Any]] = Field(default_factory=list)
    total_students: int | None = None


class CanvasPage(BaseModel):
    url: str  # page slug identifier
    title: str
    created_at: str | None = None
    updated_at: str | None = None
    editing_roles: str | None = None
    page_id: int | None = None
    published: bool = True
    front_page: bool = False
    html_url: str | None = None
    body: str | None = None  # Full HTML body content


class CanvasModuleItem(BaseModel):
    id: int
    title: str
    position: int | None = None
    indent: int | None = None
    type: str  # Page, File, Assignment, Discussion, SubHeader, ExternalUrl, ExternalTool
    module_id: int | None = None
    html_url: str | None = None
    page_url: str | None = None
    url: str | None = None
    content_id: int | None = None


class CanvasModule(BaseModel):
    id: int
    name: str
    position: int | None = None
    unlock_at: str | None = None
    require_sequential_progress: bool = False
    items_count: int = 0
    items: list[CanvasModuleItem] = Field(default_factory=list)


class CanvasFile(BaseModel):
    id: int
    folder_id: int | None = None
    display_name: str
    filename: str
    content_type: str | None = None
    url: str | None = None  # Download URL
    size: int = 0
    created_at: str | None = None
    updated_at: str | None = None
    modified_at: str | None = None
    locked: bool = False
    hidden: bool = False


class CanvasFolder(BaseModel):
    id: int
    name: str
    full_name: str
    parent_folder_id: int | None = None
    files_count: int = 0
    folders_count: int = 0


class CanvasAssignment(BaseModel):
    id: int
    name: str
    description: str | None = None
    due_at: str | None = None
    points_possible: float | None = None
    grading_type: str | None = None
    submission_types: list[str] = Field(default_factory=list)
    html_url: str | None = None
    rubric: list[dict[str, Any]] | None = None


class CanvasSubmission(BaseModel):
    id: int | None = None
    assignment_id: int
    user_id: int
    grade: str | None = None
    score: float | None = None
    submitted_at: str | None = None
    submission_type: str | None = None
    body: str | None = None
    submission_comments: list[dict[str, Any]] = Field(default_factory=list)
    rubric_assessment: dict[str, Any] | None = None
    attachments: list[dict[str, Any]] = Field(default_factory=list)


class CanvasAnnouncement(BaseModel):
    id: int
    title: str
    message: str | None = None
    posted_at: str | None = None
    delayed_post_at: str | None = None
    author: dict[str, Any] | None = None
    html_url: str | None = None


class CanvasDiscussionTopic(BaseModel):
    id: int
    title: str
    message: str | None = None
    posted_at: str | None = None
    user_name: str | None = None
    discussion_sub_entry_count: int = Field(default=0, alias="discussion_sub-entry_count")
    discussion_type: str | None = None
    html_url: str | None = None


class SiteConfig(BaseModel):
    id: str  # sanitized identifier or hash
    domain: str  # e.g., canvas.ltu.se
    base_url: str = ""  # https://canvas.ltu.se
    user_name: str | None = None
    user_id: int | None = None
    token: str  # Personal Access Token
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class CourseMeta(BaseModel):
    course_id: int
    course_name: str
    course_code: str | None = None
    default_view: str = "wiki"
    front_page_url: str | None = None
    front_page_title: str | None = None
    last_synced_at: str | None = None
    total_pages: int = 0
    total_modules: int = 0
    total_files: int = 0
    total_assignments: int = 0
    file_hashes: dict[str, str] = Field(default_factory=dict)  # relative_path -> sha256

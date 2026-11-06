# Canvas Track 🎓

> Offline sync engine and reader for Canvas LMS courses. Built with modern Python (**FastAPI** + **uv**) and **Svelte 5** (via **bun**).

Sync entire Canvas LMS courses into an offline-ready local folder vault. Canvas Track creates a local archive of your course materials, rich wiki pages (including front page / home page), modules, files, announcements, assignments, rubrics, and discussions—with local link rewriting so you can browse the course completely offline.

---

## ✨ Features

- **Strictly Read-Only**: Performs only read-only `GET` requests against Canvas API; never alters or modifies your courses or account.
- **Pages & Home Page First-Class Support**:
  - Automatically detects whether a course uses a Wiki front page, modules, or syllabus as its home page.
  - Downloads complete HTML bodies for all wiki pages.
  - Rewrites internal Canvas links (`/courses/:id/pages/...`, `/files/:id/...`, `$CANVAS_OBJECT_REFERENCE$...`) to navigate seamlessly offline.
- **Hassle-Free Personal Access Token Setup**: Direct 1-click link to your Canvas account's Approved Integrations with step-by-step guidance and instant profile verification.
- **Full LMS Offline UI**: Svelte 5 frontend mirroring the Canvas experience (Modules tree, Pages explorer, Assignments & student feedback, Discussions with student reply threads, Announcements).
- **Incremental Sync with Resume**: Tracks SHA-256 hashes and file sizes; skips unchanged files and resumes interrupted downloads.
- **Self-Contained Vault**: Backups are stored in human-readable JSON API dumps and mirrored folder hierarchies without requiring Git for end users.

---

## 🚀 Quick Start

### 1. Run the Web Application

With [`uv`](https://docs.astral.sh/uv/) installed, run:

```bash
uv run canvas-track serve
```

This launches the local server and automatically opens `http://127.0.0.1:8000` in your default browser.

### 2. Command Line Usage

Register a Canvas site directly from the terminal:

```bash
uv run canvas-track add-site canvas.ltu.se <YOUR_PERSONAL_ACCESS_TOKEN> --id ltu
```

List registered sites:

```bash
uv run canvas-track list-sites
```

Sync a course to your offline vault:

```bash
# Sync course 29010 (Advanced Data Mining)
uv run canvas-track sync ltu 29010
```

---

## 🛠️ Development & Building

### Frontend (Svelte 5 + Bun)

```bash
cd frontend
bun install
bun run build    # Compiles directly into src/canvas_track/static/
```

### Python Backend & Tests

```bash
uv run pytest
uv run ruff check .
uv run ty check src/
```

---

## 📄 License

Apache-2.0

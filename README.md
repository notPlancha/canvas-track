# Canvas Track 🎓

> Offline sync engine and reader for Canvas LMS and Moodle LMS courses. Built with modern Python (**FastAPI** + **uv**) and **Svelte 5** (via **bun**).

Sync entire Canvas and Moodle LMS courses into an offline-ready local folder vault. Canvas Track creates a local archive of your course materials, rich wiki pages, sections & modules, files, announcements, assignments, rubrics, and discussions—with local link rewriting so you can browse courses completely offline.

---

## ✨ Features

- **Strictly Read-Only**: Performs only read-only requests against Canvas and Moodle APIs; never alters or modifies your courses or account.
- **Dual LMS Architecture**: Unified offline viewer and vault structure supporting both **Canvas LMS** and **Moodle LMS**.
- **Hands-Free Moodle Student SSO**: 1-click Single Sign-On bridge (`canvastrack://`) supporting institutional Microsoft / SAML logins with automatic token handoff.
- **Pages & Home Page First-Class Support**:
  - Automatically detects home page configurations (wiki front pages, modules, syllabus).
  - Downloads complete HTML bodies for all pages and resources.
  - Rewrites internal links to navigate seamlessly offline.
- **Incremental Sync with Resume**: Tracks SHA-256 hashes and file sizes; skips unchanged files and resumes interrupted downloads.
- **Self-Contained Vault**: Backups are stored in human-readable JSON API dumps and mirrored folder hierarchies without requiring Git for end users.

---

## 🚀 Quick Start

### 1. Configuration (Optional `.env`)

Copy the example environment file to configure your Canvas or Moodle domain and tokens:

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Canvas Configuration
CANVAS_DOMAIN=canvas.ltu.se
CANVAS_TOKEN=<YOUR_CANVAS_TOKEN>
CANVAS_SITE_ID=ltu
CANVAS_COURSE_ID=29010

# Moodle Configuration
MOODLE_URL=https://moodle.example.edu
MOODLE_TOKEN=<YOUR_MOODLE_TOKEN_OR_SSO_LINK>
MOODLE_COURSE_ID=73674
```

When set, the web GUI pre-populates your connection modal and settings links, and CLI commands default to these values without requiring manual entry.

### 2. Run the Web Application

With [`uv`](https://docs.astral.sh/uv/) installed, run:

```bash
uv run canvas-track serve
```

This launches the local server and automatically opens `http://127.0.0.1:8000` in your default browser.

### 3. Command Line Usage

Register a Canvas or Moodle site directly from the terminal:

```bash
# Register a Canvas site:
uv run canvas-track add-site canvas.ltu.se <TOKEN> --id ltu

# Register a Moodle site:
uv run canvas-track add-site moodle.example.edu <TOKEN_OR_SSO_LINK> --platform moodle --id lnu
```

List registered sites:

```bash
uv run canvas-track list-sites
```

Sync a course to your offline vault:

```bash
# Sync course by site ID and course ID:
uv run canvas-track sync lnu 73674
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

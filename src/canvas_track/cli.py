"""Command Line Interface for Canvas Track.

Provides commands to start the local web GUI server, trigger syncs,
and manage Canvas sites directly from the terminal.
"""

from __future__ import annotations

import asyncio
import logging
import os
import webbrowser
from pathlib import Path
from typing import Annotated

import typer
import uvicorn
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from canvas_track.client import CanvasClient
from canvas_track.models import SiteConfig
from canvas_track.moodle_client import MoodleClient
from canvas_track.moodle_sync import MoodleSyncEngine
from canvas_track.protocol import extract_moodle_token, register_protocol_handler
from canvas_track.server import create_app
from canvas_track.sync import SyncEngine
from canvas_track.vault import VaultManager, sanitize_filename

load_dotenv()
logger = logging.getLogger(__name__)

load_dotenv()

app = typer.Typer(
    name="canvas-track",
    help="Offline sync engine and reader for Canvas LMS courses.",
)
console = Console()


@app.callback(invoke_without_command=True)
def main_callback(ctx: typer.Context) -> None:
    """Offline sync engine and reader for Canvas LMS courses."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(serve)



@app.command()
def serve(
    port: Annotated[int, typer.Option("--port", "-p", help="Port to bind the server to.")] = 8000,
    host: Annotated[str, typer.Option("--host", "-h", help="Host interface.")] = "127.0.0.1",
    vault_dir: Annotated[
        Path | None, typer.Option("--vault-dir", "-v", help="Vault directory path.")
    ] = None,
    no_browser: Annotated[bool, typer.Option("--no-browser", help="Do not open browser.")] = False,
) -> None:
    """Launch the Canvas Track local server and GUI in your default browser."""
    if vault_dir:
        os.environ["CANVAS_TRACK_VAULT"] = str(vault_dir.resolve())

    url = f"http://{host}:{port}"
    console.print(f"[bold green]Starting Canvas Track[/bold green] on [link={url}]{url}[/link]")

    if not no_browser:

        async def open_browser() -> None:
            await asyncio.sleep(1.0)
            webbrowser.open(url)

        try:
            loop = asyncio.get_event_loop()
            loop.create_task(open_browser())
        except Exception:
            pass

    fastapi_app = create_app(vault_dir)
    uvicorn.run(fastapi_app, host=host, port=port, log_level="info")


@app.command()
def add_site(
    domain: Annotated[
        str | None,
        typer.Argument(
            help="LMS domain (e.g. canvas.ltu.se or moodle.example.edu). Defaults to env var if set."
        ),
    ] = None,
    token: Annotated[
        str | None,
        typer.Argument(help="Access Token or SSO link. Defaults to env var if set."),
    ] = None,
    site_id: Annotated[
        str | None,
        typer.Option(
            "--id", help="Custom identifier for the site"
        ),
    ] = None,
    platform: Annotated[
        str,
        typer.Option("--platform", "-p", help="LMS platform: canvas or moodle"),
    ] = "canvas",
    vault_dir: Annotated[Path | None, typer.Option("--vault-dir", "-v")] = None,
) -> None:
    """Validate and register a new Canvas or Moodle site with an Access Token or SSO link."""
    is_moodle = platform.lower() == "moodle"
    default_domain = os.environ.get("MOODLE_URL" if is_moodle else "CANVAS_DOMAIN", "")
    default_token = os.environ.get("MOODLE_TOKEN" if is_moodle else "CANVAS_TOKEN", "")

    resolved_domain = (domain or default_domain).strip()
    resolved_domain = resolved_domain.replace("https://", "").replace("http://", "").rstrip("/")
    resolved_token = (token or default_token).strip()
    resolved_site_id = (site_id or os.environ.get("CANVAS_SITE_ID", "")).strip() or None

    if not resolved_domain:
        platform_name = "Moodle" if is_moodle else "Canvas"
        env_var = "MOODLE_URL" if is_moodle else "CANVAS_DOMAIN"
        console.print(
            f"[bold red]Error:[/bold red] {platform_name} domain is required. "
            f"Pass it as an argument or set {env_var} in your .env file."
        )
        raise typer.Exit(code=1)

    if not resolved_token:
        env_var = "MOODLE_TOKEN" if is_moodle else "CANVAS_TOKEN"
        console.print(
            "[bold red]Error:[/bold red] Token or SSO link is required. "
            f"Pass it as an argument or set {env_var} in your .env file."
        )
        raise typer.Exit(code=1)

    vault = VaultManager(vault_dir)

    async def _add() -> None:
        if is_moodle:
            clean_token = extract_moodle_token(resolved_token)
            client = MoodleClient(resolved_domain, clean_token)
            async with client:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    transient=True,
                ) as progress:
                    progress.add_task(description="Authenticating with Moodle...", total=None)
                    info = await client.get_site_info()

                sid = (
                    resolved_site_id
                    if resolved_site_id
                    else sanitize_filename(resolved_domain.replace(".", "_"))
                )
                user_name = info.get("fullname") or info.get("username") or "Moodle User"
                user_id = info.get("userid")
                site = SiteConfig(
                    id=sid,
                    domain=resolved_domain,
                    base_url=client.base_url,
                    platform="moodle",
                    user_name=user_name,
                    user_id=user_id,
                    token=clean_token,
                )
                vault.save_site(site)
                console.print(
                    f"[bold green]Registered Moodle site '[cyan]{sid}[/cyan]'![/bold green] "
                    f"User: [bold]{user_name}[/bold] (ID: {user_id})"
                )
        else:
            client = CanvasClient(resolved_domain, resolved_token)
            async with client:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    transient=True,
                ) as progress:
                    progress.add_task(description="Authenticating with Canvas...", total=None)
                    user = await client.get_user_profile()

                sid = (
                    resolved_site_id
                    if resolved_site_id
                    else sanitize_filename(resolved_domain.replace(".", "_"))
                )
                site = SiteConfig(
                    id=sid,
                    domain=resolved_domain,
                    base_url=client.base_url,
                    platform="canvas",
                    user_name=user.name,
                    user_id=user.id,
                    token=resolved_token,
                )
                vault.save_site(site)
                console.print(
                    f"[bold green]Registered Canvas site '[cyan]{sid}[/cyan]'![/bold green] "
                    f"User: [bold]{user.name}[/bold] (ID: {user.id})"
                )

    asyncio.run(_add())


@app.command()
def list_sites(
    vault_dir: Annotated[Path | None, typer.Option("--vault-dir", "-v")] = None,
) -> None:
    """List all registered LMS sites in the local vault."""
    vault = VaultManager(vault_dir)
    sites = vault.list_sites()

    if not sites:
        console.print(
            "[yellow]No sites registered yet. Use 'canvas-track add-site' or open GUI.[/yellow]"
        )
        return

    table = Table(title="Registered LMS Sites")
    table.add_column("Site ID", style="cyan")
    table.add_column("Platform", style="blue")
    table.add_column("Domain", style="magenta")
    table.add_column("User", style="green")
    table.add_column("Created At", style="dim")

    for s in sites:
        plat_label = "Moodle" if s.platform == "moodle" else "Canvas"
        table.add_row(s.id, plat_label, s.domain, s.user_name or "N/A", s.created_at[:19])

    console.print(table)


@app.command()
def sync(
    site_id: Annotated[
        str | None,
        typer.Argument(
            help="Registered site ID (defaults to env var or single registered site)"
        ),
    ] = None,
    course_id: Annotated[
        int | None,
        typer.Argument(help="Course ID to sync (defaults to env var)"),
    ] = None,
    download_files: Annotated[
        bool, typer.Option("--files/--no-files", help="Download course files & attachments")
    ] = True,
    vault_dir: Annotated[Path | None, typer.Option("--vault-dir", "-v")] = None,
) -> None:
    """Sync a course into the local offline vault from the terminal."""
    vault = VaultManager(vault_dir)
    resolved_site_id = (site_id or os.environ.get("CANVAS_SITE_ID", "")).strip()

    if not resolved_site_id:
        sites = vault.list_sites()
        if len(sites) == 1:
            resolved_site_id = sites[0].id
        elif len(sites) > 1:
            console.print(
                "[bold red]Error:[/bold red] Multiple sites registered. "
                "Specify site_id or set CANVAS_SITE_ID in .env."
            )
            raise typer.Exit(code=1)
        else:
            console.print(
                "[bold red]Error:[/bold red] No sites registered. "
                "Run 'canvas-track add-site' first or configure .env."
            )
            raise typer.Exit(code=1)

    site = vault.get_site(resolved_site_id)
    if not site:
        console.print(f"[bold red]Error:[/bold red] Site '{resolved_site_id}' not found in vault.")
        raise typer.Exit(code=1)

    resolved_course_id = course_id
    if resolved_course_id is None:
        env_course = (
            os.environ.get("MOODLE_COURSE_ID", "")
            if site.platform == "moodle"
            else os.environ.get("CANVAS_COURSE_ID", "")
        ).strip()
        if env_course and env_course.isdigit():
            resolved_course_id = int(env_course)

    if resolved_course_id is None:
        console.print(
            "[bold red]Error:[/bold red] Course ID is required. "
            "Pass it as an argument or set COURSE_ID in your .env file."
        )
        raise typer.Exit(code=1)

    is_moodle = site.platform == "moodle"
    sync_engine: MoodleSyncEngine | SyncEngine
    client: MoodleClient | CanvasClient

    if is_moodle:
        m_client = MoodleClient(site.domain, site.token)
        client = m_client
        sync_engine = MoodleSyncEngine(m_client, vault, resolved_site_id)
    else:
        c_client = CanvasClient(site.domain, site.token)
        client = c_client
        sync_engine = SyncEngine(c_client, vault, resolved_site_id)

    async def _sync() -> None:
        async with client:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
            ) as progress:
                task = progress.add_task(
                    description=f"Syncing course {resolved_course_id}...", total=None
                )

                async def progress_cb(evt: dict) -> None:
                    stage = evt.get("stage", "")
                    msg = evt.get("message", "")
                    progress.update(task, description=f"[{stage.upper()}] {msg}")

                meta = await sync_engine.sync_course(
                    resolved_course_id, progress_cb=progress_cb, download_files=download_files
                )

            console.print("\n[bold green]Course synced successfully![/bold green]")
            console.print(f"Name: [bold]{meta.course_name}[/bold]")
            console.print(f"Default view: [cyan]{meta.default_view}[/cyan]")
            console.print(f"Pages synced: [bold]{meta.total_pages}[/bold]")
            console.print(
                f"Modules: [bold]{meta.total_modules}[/bold] | "
                f"Files: [bold]{meta.total_files}[/bold]"
            )

    asyncio.run(_sync())


@app.command(name="auth-callback", hidden=True)
def auth_callback(
    url: Annotated[str, typer.Argument(help="canvastrack:// URL callback from OS")],
) -> None:
    """Handle OS protocol invocation from canvastrack:// and post to local server."""
    import httpx

    try:
        httpx.post(
            "http://127.0.0.1:8000/api/auth/moodle-callback",
            json={"url": url},
            timeout=5.0,
        )
    except Exception as e:
        logger.debug("Failed sending auth callback to server: %s", e)


@app.command()
def register_protocol() -> None:
    """Register the canvastrack:// protocol handler in Windows HKCU."""
    ok = register_protocol_handler()
    if ok:
        console.print(
            "[bold green]Registered canvastrack:// protocol handler successfully.[/bold green]"
        )
    else:
        console.print(
            "[yellow]Protocol handler registration skipped or unsupported on this OS.[/yellow]"
        )


@app.command()
def delete_backup(
    site_id: Annotated[str, typer.Argument(help="Registered site ID")],
    course_id: Annotated[int, typer.Argument(help="Canvas course ID")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation prompt")] = False,
    vault_dir: Annotated[Path | None, typer.Option("--vault-dir", "-v")] = None,
) -> None:
    """Permanently delete a course's local offline backup from the vault."""
    vault = VaultManager(vault_dir)
    meta = vault.get_course_meta(site_id, course_id)
    name = meta.course_name if meta else f"Course {course_id}"
    size_bytes = vault.get_course_backup_size(site_id, course_id)
    size_mb = size_bytes / (1024 * 1024)

    if not yes:
        confirm = typer.confirm(
            f"Are you sure you want to delete the local backup for '{name}' ({size_mb:.1f} MB)?"
        )
        if not confirm:
            console.print("[yellow]Deletion cancelled.[/yellow]")
            return

    deleted = vault.delete_course_archive(site_id, course_id)
    if deleted:
        console.print(
            f"[bold green]Deleted local backup for '[cyan]{name}[/cyan]' "
            f"({size_mb:.1f} MB freed).[/bold green]"
        )
    else:
        console.print(
            f"[yellow]No local backup found for course {course_id} under site '{site_id}'.[/yellow]"
        )

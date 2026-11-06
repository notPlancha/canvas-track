"""Command Line Interface for Canvas Track.

Provides commands to start the local web GUI server, trigger syncs,
and manage Canvas sites directly from the terminal.
"""

from __future__ import annotations

import asyncio
import os
import webbrowser
from pathlib import Path
from typing import Annotated

import typer
import uvicorn
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from canvas_track.client import CanvasClient
from canvas_track.models import SiteConfig
from canvas_track.server import create_app
from canvas_track.sync import SyncEngine
from canvas_track.vault import VaultManager, sanitize_filename

app = typer.Typer(
    name="canvas-track",
    help="Offline sync engine and reader for Canvas LMS courses.",
)
console = Console()


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
    domain: Annotated[str, typer.Argument(help="Canvas domain (e.g. canvas.ltu.se)")],
    token: Annotated[str, typer.Argument(help="Personal Access Token")],
    site_id: Annotated[
        str | None, typer.Option("--id", help="Custom identifier for the site")
    ] = None,
    vault_dir: Annotated[Path | None, typer.Option("--vault-dir", "-v")] = None,
) -> None:
    """Validate and register a new Canvas site with a Personal Access Token."""
    vault = VaultManager(vault_dir)
    client = CanvasClient(domain, token)

    async def _add() -> None:
        async with client:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                transient=True,
            ) as progress:
                progress.add_task(description="Authenticating with Canvas...", total=None)
                user = await client.get_user_profile()

            sid = site_id.strip() if site_id else sanitize_filename(domain.replace(".", "_"))
            site = SiteConfig(
                id=sid,
                domain=domain,
                base_url=client.base_url,
                user_name=user.name,
                user_id=user.id,
                token=token,
            )
            vault.save_site(site)
            console.print(
                f"[bold green]Registered site '[cyan]{sid}[/cyan]'![/bold green] "
                f"User: [bold]{user.name}[/bold] (ID: {user.id})"
            )

    asyncio.run(_add())


@app.command()
def list_sites(
    vault_dir: Annotated[Path | None, typer.Option("--vault-dir", "-v")] = None,
) -> None:
    """List all registered Canvas sites in the local vault."""
    vault = VaultManager(vault_dir)
    sites = vault.list_sites()

    if not sites:
        console.print(
            "[yellow]No sites registered yet. Use 'canvas-track add-site' or open GUI.[/yellow]"
        )
        return

    table = Table(title="Registered Canvas Sites")
    table.add_column("Site ID", style="cyan")
    table.add_column("Domain", style="magenta")
    table.add_column("User", style="green")
    table.add_column("Created At", style="dim")

    for s in sites:
        table.add_row(s.id, s.domain, s.user_name or "N/A", s.created_at[:19])

    console.print(table)


@app.command()
def sync(
    site_id: Annotated[str, typer.Argument(help="Registered site ID")],
    course_id: Annotated[int, typer.Argument(help="Canvas course ID to sync")],
    download_files: Annotated[
        bool, typer.Option("--files/--no-files", help="Download course files & attachments")
    ] = True,
    vault_dir: Annotated[Path | None, typer.Option("--vault-dir", "-v")] = None,
) -> None:
    """Sync a course into the local offline vault from the terminal."""
    vault = VaultManager(vault_dir)
    site = vault.get_site(site_id)
    if not site:
        console.print(f"[bold red]Error:[/bold red] Site '{site_id}' not found in vault.")
        raise typer.Exit(code=1)

    client = CanvasClient(site.domain, site.token)
    sync_engine = SyncEngine(client, vault, site_id)

    async def _sync() -> None:
        async with client:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
            ) as progress:
                task = progress.add_task(description=f"Syncing course {course_id}...", total=None)

                async def progress_cb(evt: dict) -> None:
                    stage = evt.get("stage", "")
                    msg = evt.get("message", "")
                    progress.update(task, description=f"[{stage.upper()}] {msg}")

                meta = await sync_engine.sync_course(
                    course_id, progress_cb=progress_cb, download_files=download_files
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

# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "pyinstaller>=6.22.0",
#     "rich>=15.0.0",
# ]
# ///
"""Build script for packaging Canvas Track into a standalone Windows executable.

Usage:
    uv run python scripts/build_executable.py
    uv run python scripts/build_executable.py --rebuild-frontend
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from rich.console import Console

console = Console()
ROOT_DIR = Path(__file__).resolve().parent.parent


def check_prerequisites(rebuild_frontend: bool = False) -> None:
    """Verify that frontend build exists or can be built."""
    static_index = ROOT_DIR / "src" / "canvas_track" / "static" / "index.html"
    frontend_dir = ROOT_DIR / "frontend"

    if rebuild_frontend or not static_index.exists():
        console.print("[cyan]Building Svelte 5 frontend with bun...[/cyan]")
        bun_path = shutil.which("bun")
        if not bun_path:
            raise RuntimeError(
                "Bun is not installed or not in PATH, but frontend build is required."
            )
        subprocess.run([bun_path, "run", "build"], cwd=frontend_dir, check=True)
        console.print("[green]Frontend build completed successfully.[/green]")
    else:
        console.print("[green]Found existing frontend static build.[/green]")


def run_pyinstaller() -> Path:
    """Run PyInstaller with the project spec file."""
    spec_file = ROOT_DIR / "canvas-track.spec"
    if not spec_file.exists():
        raise FileNotFoundError(f"Spec file not found: {spec_file}")

    console.print(f"[cyan]Running PyInstaller using {spec_file.name}...[/cyan]")
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        str(spec_file),
        "--noconfirm",
        "--clean",
    ]
    subprocess.run(cmd, cwd=ROOT_DIR, check=True)

    exe_path = ROOT_DIR / "dist" / "canvas-track.exe"
    if not exe_path.exists():
        raise FileNotFoundError(f"Expected output binary not found at: {exe_path}")

    return exe_path


def verify_executable(exe_path: Path) -> None:
    """Run a quick sanity check against the compiled binary."""
    console.print("[cyan]Verifying compiled executable (--help)...[/cyan]")
    result = subprocess.run(
        [str(exe_path), "--help"],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    if "Usage:" not in result.stdout:
        raise RuntimeError("Sanity check failed: --help output did not match expected CLI usage.")
    console.print("[green]Executable sanity check passed successfully.[/green]")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Canvas Track standalone executable.")
    parser.add_argument(
        "--rebuild-frontend",
        action="store_true",
        help="Force rebuild of Svelte 5 frontend before packaging.",
    )
    args = parser.parse_args()

    console.rule("[bold cyan]Canvas Track Executable Builder[/bold cyan]")
    try:
        check_prerequisites(rebuild_frontend=args.rebuild_frontend)
        exe_path = run_pyinstaller()
        verify_executable(exe_path)

        size_mb = exe_path.stat().st_size / (1024 * 1024)
        console.rule("[bold green]Build Succeeded[/bold green]")
        console.print(f"[bold]Location:[/bold]  {exe_path}")
        console.print(f"[bold]Size:[/bold]      {size_mb:.2f} MB")
        console.print(
            "\n[bold green]To run:[/bold green]\n"
            "  - Double-click [cyan]dist\\canvas-track.exe[/cyan] to launch the web GUI & browser\n"
            "  - Or run [cyan].\\dist\\canvas-track.exe --help[/cyan] from the terminal\n"
        )
    except Exception as exc:
        console.print(f"[bold red]Build failed:[/bold red] {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()

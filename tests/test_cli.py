"""Unit tests for Canvas Track CLI commands."""

from pathlib import Path

from typer.testing import CliRunner

from canvas_track.cli import app
from canvas_track.models import CourseMeta, SiteConfig
from canvas_track.vault import VaultManager

runner = CliRunner()


def test_cli_delete_backup(tmp_path: Path) -> None:
    vault = VaultManager(tmp_path)
    site = SiteConfig(
        id="test_site",
        domain="canvas.example.edu",
        base_url="https://canvas.example.edu",
        user_name="Student Test",
        user_id=123,
        token="mock_tok",
    )
    vault.save_site(site)

    meta = CourseMeta(
        course_id=456,
        course_name="Database Systems",
        default_view="wiki",
    )
    vault.save_course_meta("test_site", 456, meta)

    # Call delete-backup with --yes flag
    result = runner.invoke(
        app,
        ["delete-backup", "test_site", "456", "--yes", "--vault-dir", str(tmp_path)],
    )
    assert result.exit_code == 0
    assert "Deleted local backup for 'Database Systems'" in result.stdout

    # Second invocation reports not found
    result2 = runner.invoke(
        app,
        ["delete-backup", "test_site", "456", "--yes", "--vault-dir", str(tmp_path)],
    )
    assert result2.exit_code == 0
    assert "No local backup found" in result2.stdout


def test_cli_add_site_missing_args_error(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("CANVAS_DOMAIN", raising=False)
    monkeypatch.delenv("CANVAS_TOKEN", raising=False)

    result = runner.invoke(app, ["add-site", "--vault-dir", str(tmp_path)])
    assert result.exit_code != 0
    assert "Canvas domain is required" in result.stdout


def test_cli_default_invocation_calls_serve(monkeypatch) -> None:
    called = []
    monkeypatch.setattr("canvas_track.cli.serve", lambda **kwargs: called.append(True))
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert called == [True]


def test_cli_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "serve" in result.stdout
    assert "add-site" in result.stdout
    assert "sync" in result.stdout

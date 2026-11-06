"""Canvas Track: Offline sync engine and reader for Canvas LMS courses."""

from canvas_track.cli import app


def main() -> None:
    app()


__all__ = ["app", "main"]

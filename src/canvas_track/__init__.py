"""Canvas Track: Offline sync engine and reader for Canvas LMS courses."""

from dotenv import load_dotenv

from canvas_track.cli import app

# Automatically load environment variables from .env if present
load_dotenv()


def main() -> None:
    app()


__all__ = ["app", "main"]

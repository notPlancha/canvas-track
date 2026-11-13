"""Entry point for Canvas Track when run with python -m canvas_track or as a packaged executable."""

from __future__ import annotations

import multiprocessing

from canvas_track import main

if __name__ == "__main__":
    # Required for Windows frozen executable multiprocessing support
    multiprocessing.freeze_support()
    main()

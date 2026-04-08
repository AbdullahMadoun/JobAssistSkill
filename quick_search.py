#!/usr/bin/env python
"""Small convenience wrapper for a local dual-stream search run."""

from __future__ import annotations

import sys

from main import main


if __name__ == "__main__":
    args = sys.argv[1:] or ["search", "software engineer", "--stream", "both"]
    if args[0] != "search":
        args = ["search", *args]
    raise SystemExit(main(args))

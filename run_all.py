#!/usr/bin/env python
"""Compatibility wrapper around the agent-oriented batch workflow."""

from __future__ import annotations

import sys

from main import main


if __name__ == "__main__":
    raise SystemExit(main(["batch", *sys.argv[1:]]))

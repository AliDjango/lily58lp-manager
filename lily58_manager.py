#!/usr/bin/env python3
"""Backward-compatible local launcher; prefer `uv run lily58lp-manager`."""

from lily58lp_manager.app import main

if __name__ == "__main__":
    raise SystemExit(main())

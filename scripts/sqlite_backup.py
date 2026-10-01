#!/usr/bin/env python3
"""Crea una copia consistente de una base SQLite mediante su API backup."""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    if not args.source.is_file():
        raise SystemExit(f"No existe la base SQLite: {args.source}")
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    source = sqlite3.connect(args.source)
    destination = sqlite3.connect(args.destination)
    try:
        source.backup(destination)
        integrity = destination.execute("PRAGMA integrity_check").fetchone()
        if integrity != ("ok",):
            raise SystemExit(f"La copia no supera integrity_check: {integrity}")
    finally:
        destination.close()
        source.close()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Indexes every plow.log message into the hidden SQLite file ~/.plow-agent.db.

Usage:
  indexer.py            index once
  indexer.py --watch    keep running in the background, re-indexing every 10 s
"""
import os
import re
import sqlite3
import sys
import time
from pathlib import Path

import plow

DB = Path(os.environ.get("PLOW_DB", Path.home() / ".plow-agent.db"))
# "[simulação]" is the marker written by v0.1 logs; both are read.
LINE = re.compile(r"^(\S+ \S+) (\[(?:dry-run|simulação)\] )?(\S+) (.*)$")


def index(log: Path = None, db: Path = None) -> int:
    """Returns how many new messages were stored."""
    log, db = log or plow.LOG, db or DB
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, ts TEXT, dry_run INTEGER,"
        " action TEXT, text TEXT, UNIQUE(ts, dry_run, action, text))"
    )
    new = 0
    if log.exists():
        # ponytail: re-reads the whole log and lets UNIQUE dedupe; keep an offset if the log grows large
        for line in log.read_text().splitlines():
            if m := LINE.match(line):
                cur = con.execute(
                    "INSERT OR IGNORE INTO messages (ts, dry_run, action, text) VALUES (?, ?, ?, ?)",
                    (m[1], bool(m[2]), m[3], m[4]),
                )
                new += cur.rowcount
    con.commit()
    con.close()
    return new


if __name__ == "__main__":
    while True:
        if n := index():
            print(f"{n} new messages in {DB}")
        if "--watch" not in sys.argv:
            break
        time.sleep(10)

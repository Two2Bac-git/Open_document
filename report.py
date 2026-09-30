#!/usr/bin/env python3
"""Runs Plow's Agent Index client unchanged, minus its direct OpenClaw collector when that
would count the same tokens twice.

When OpenClaw drives the local `claude` binary, every OpenClaw turn is also a Claude Code
transcript that agentsview already counts, and the client SUMS its collectors. Measured on
2026-09-29 for the same day: 2,578,952 tokens in those transcripts vs 2,867,421 in OpenClaw's
own store. agent_index_client.py itself stays byte-identical to the copy Plow pins.
"""
import glob
import os
import sys

import agent_index_client as client

AGENTSVIEW = ("~/.local/bin/agentsview", "/opt/homebrew/bin/agentsview", "/usr/local/bin/agentsview")  # the client's own lookup


def openclaw_counted_twice(home: str) -> bool:
    """True when agentsview already sees OpenClaw's turns as Claude Code transcripts."""
    has_agentsview = any(os.access(p.replace("~", home, 1), os.X_OK) for p in AGENTSVIEW)
    return has_agentsview and bool(glob.glob(os.path.join(home, ".claude", "projects", "*openclaw*")))


def count_from(days: list, since: str) -> list:
    """Days before `since` (the install date) go out as zeros. The server replaces each
    (day, model) it receives, so this clears the machine's usage from before the agent
    existed instead of leaving it on the board until it ages out."""
    zero = dict.fromkeys(client.KEYS, 0)
    return [d if d["date"] >= since else {"date": d["date"], "models": [{**m, **zero} for m in d["models"]]}
            for d in days]


if __name__ == "__main__":
    if openclaw_counted_twice(os.path.expanduser("~")):
        print("  openclaw store skipped: its turns are already in agentsview's Claude Code count")
        client.from_openclaw = lambda days, state=None: {}
    if since := os.environ.get("PLOW_SINCE"):
        print(f"  counting from {since}; earlier days are sent as zero")
        merge = client.merge
        client.merge = lambda *sources: count_from(merge(*sources), since)
    sys.exit(client.main(sys.argv[1:]))

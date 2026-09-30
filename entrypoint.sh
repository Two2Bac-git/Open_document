#!/bin/sh
# Container main process: indexes plow.log into SQLite. It never moves a file on its own;
# sorting is always `docker compose exec plow-agent python3 plow.py plan|apply ~/Downloads`.
# Agent Index usage is reported from the host (install.sh), where the token usage happens.
trap 'kill "$pid" 2>/dev/null; exit 0' TERM INT
python3 /app/indexer.py --watch &
pid=$!
echo "$pid" > /tmp/indexer.pid
wait "$pid"

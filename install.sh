#!/usr/bin/env bash
# Installs Plow-Agent's usage reporting on this machine: registers this install on the
# Agent Index and reports token usage (per day and model) every 5 minutes.
# First: `plow-agents login` (https://github.com/plow-pbc/plow-agents).
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
CLIENT="$DIR/agent_index_client.py"
TOKEN_FILE="${PLOW_TOKEN_FILE:-$HOME/.config/plow/token}"

set +e; python3 "$CLIENT" status >/dev/null; st=$?; set -e
case $st in
  0) echo "This install is already registered." ;;
  3)
    [ -r "$TOKEN_FILE" ] || { echo "Run 'plow-agents login' first ($TOKEN_FILE not found)." >&2; exit 1; }
    PLOW_AGENT_TOKEN="$(cat "$TOKEN_FILE")" python3 "$CLIENT" --register --agent plow-agent ;;
  *) echo "Client state is unreadable; fix the message above before registering again." >&2; exit 1 ;;
esac

UNIT="$HOME/.config/systemd/user"
mkdir -p "$UNIT"
cat > "$UNIT/plow-agent-index.service" <<EOF
[Unit]
Description=Plow-Agent: report usage to the Agent Index

[Service]
Type=oneshot
ExecStart=/usr/bin/env python3 $CLIENT --agent plow-agent
EOF
cat > "$UNIT/plow-agent-index.timer" <<EOF
[Unit]
Description=Plow-Agent: usage report every 5 minutes

[Timer]
OnBootSec=1min
OnUnitActiveSec=5min

[Install]
WantedBy=timers.target
EOF
systemctl --user daemon-reload
systemctl --user enable --now plow-agent-index.timer
echo "Done. Check: systemctl --user list-timers plow-agent-index.timer"

#!/usr/bin/env bash
# Installs Open to CC's usage reporting on this machine: registers this install on the
# Agent Index and reports token usage (per day and model) every 5 minutes.
# First: `plow-agents login` (https://github.com/plow-pbc/plow-agents).
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
CLIENT="$DIR/agent_index_client.py"
TOKEN_FILE="${PLOW_TOKEN_FILE:-$HOME/.config/plow/token}"

# agentsview: the collector Plow's own OpenClaw image installs, same version and checksum
# (plow-pbc/plow-openclaw-agent Dockerfile). It is what sees Claude Code usage.
AV="$HOME/.local/bin/agentsview"
if [ ! -x "$AV" ] && [ "$(uname -sm)" = "Linux x86_64" ]; then
  tmp="$(mktemp)"
  curl -fsS --max-time 120 -L -o "$tmp" \
    https://github.com/kenn-io/agentsview/releases/download/v0.44.0/agentsview_0.44.0_linux_amd64.tar.gz
  echo "037ea7a46d52e06b20363b4aa7cd7f28e32f31d8215803d6e9a0c96bac5818e3  $tmp" | sha256sum -c - >/dev/null
  mkdir -p "$(dirname "$AV")" && tar -xzf "$tmp" -C "$(dirname "$AV")" agentsview && rm "$tmp"
  echo "Installed agentsview v0.44.0 (checksum verified)."
fi

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
# Usage counts from the first install day; a re-install keeps that day. Override: PLOW_SINCE=YYYY-MM-DD
SINCE="${PLOW_SINCE:-$(sed -n 's/^Environment=PLOW_SINCE=//p' "$UNIT/plow-agent-index.service" 2>/dev/null || true)}"
SINCE="${SINCE:-$(date +%F)}"
cat > "$UNIT/plow-agent-index.service" <<EOF
[Unit]
Description=Open to CC: report usage to the Agent Index

[Service]
Type=oneshot
Environment=AGENTSVIEW_NO_DAEMON=1
Environment=PLOW_SINCE=$SINCE
# agentsview answers from its own database and fills it only on sync (as Plow's boot does)
ExecStartPre=-/bin/sh -c '[ -x "$AV" ] && "$AV" sync >/dev/null'
ExecStart=/usr/bin/env python3 $DIR/report.py --agent plow-agent
EOF
cat > "$UNIT/plow-agent-index.timer" <<EOF
[Unit]
Description=Open to CC: usage report every 5 minutes

[Timer]
OnBootSec=1min
OnUnitActiveSec=5min

[Install]
WantedBy=timers.target
EOF
systemctl --user daemon-reload
systemctl --user enable --now plow-agent-index.timer
echo "Done. Check: systemctl --user list-timers plow-agent-index.timer"

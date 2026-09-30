#!/usr/bin/env bash
# One command from a fresh clone to an install counted on the Agent Index:
#   1. Plow account: fetches the pinned plow-agents CLI if missing, then runs its login
#   2. registers this install
#   3. installs agentsview (Linux x86_64, Plow's pinned build) so Claude Code usage counts
#   4. reports usage every 5 minutes (systemd --user, or prints a crontab line) and once now
# Sorting files needs none of this: `python3 plow.py plan ~/Downloads` works on its own.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
CLIENT="$DIR/agent_index_client.py"
TOKEN_FILE="${PLOW_TOKEN_FILE:-$HOME/.config/plow/token}"
PLOW_CLI_COMMIT=3033a59754067bb21b4b6b2844967db343ecf7bd   # plow-pbc/plow-agents, 2026-09-20
say() { printf '\n==> %s\n' "$*"; }
pyat() { python3 -c "import sys; sys.exit(sys.version_info < ($1, $2))"; }

pyat 3 9 || { echo "Python 3.9+ is required (found: $(python3 --version 2>&1))." >&2; exit 1; }

# 1. Plow account -- nothing is downloaded or registered before this succeeds
if [ ! -s "$TOKEN_FILE" ]; then
  [ -t 0 ] || { echo "Run ./install.sh in a terminal: the Plow login shows you a code to text." >&2; exit 1; }
  PA="$(command -v plow-agents || true)"
  if [ -z "$PA" ]; then
    pyat 3 11 || { echo "Plow's login tool needs Python 3.11+ (found: $(python3 --version 2>&1)). Sorting files works without it." >&2; exit 1; }
    CLI="${XDG_DATA_HOME:-$HOME/.local/share}/plow-agents"
    [ -d "$CLI/.git" ] || git clone -q https://github.com/plow-pbc/plow-agents.git "$CLI"
    git -C "$CLI" fetch -q origin
    git -C "$CLI" -c advice.detachedHead=false checkout -q "$PLOW_CLI_COMMIT"
    PA="$CLI/bin/plow-agents"
  fi
  say "Plow login: it prints a short code and a US number; text the code from your phone and keep this window open"
  "$PA" login
fi

# 2. Register this install (0 registered, 3 not yet, 2 unreadable state: never register over it)
set +e; python3 "$CLIENT" status >/dev/null; st=$?; set -e
case $st in
  0) say "This install is already registered." ;;
  3) say "Registering this install"; PLOW_AGENT_TOKEN="$(cat "$TOKEN_FILE")" python3 "$CLIENT" --register --agent plow-agent ;;
  *) echo "Client state is unreadable; fix the message above before registering again." >&2; exit 1 ;;
esac

# 3. agentsview: the collector Plow's own OpenClaw image installs, same version and checksum
AV="$HOME/.local/bin/agentsview"
if [ ! -x "$AV" ] && [ "$(uname -sm)" = "Linux x86_64" ]; then
  tmp="$(mktemp)"
  curl -fsS --max-time 120 -L -o "$tmp" \
    https://github.com/kenn-io/agentsview/releases/download/v0.44.0/agentsview_0.44.0_linux_amd64.tar.gz
  echo "037ea7a46d52e06b20363b4aa7cd7f28e32f31d8215803d6e9a0c96bac5818e3  $tmp" | sha256sum -c - >/dev/null
  mkdir -p "$(dirname "$AV")" && tar -xzf "$tmp" -C "$(dirname "$AV")" agentsview && rm "$tmp"
  say "Installed agentsview v0.44.0 (checksum verified)"
elif [ ! -x "$AV" ]; then
  say "agentsview is only installed on Linux x86_64 (Plow pins that build); Claude Code usage will not count here"
fi

# 4. Schedule. Usage counts from the first install day; a re-install keeps it. Override: PLOW_SINCE=YYYY-MM-DD
UNIT="$HOME/.config/systemd/user"
SINCE="${PLOW_SINCE:-$(sed -n 's/^Environment=PLOW_SINCE=//p' "$UNIT/plow-agent-index.service" 2>/dev/null || true)}"
SINCE="${SINCE:-$(date +%F)}"
if command -v systemctl >/dev/null && systemctl --user show-environment >/dev/null 2>&1; then
  mkdir -p "$UNIT"
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
  say "First report"
  systemctl --user start plow-agent-index.service && journalctl --user -u plow-agent-index.service -n 3 --no-pager -o cat
  say "Done. Every 5 min from now; stop with: systemctl --user disable --now plow-agent-index.timer"
else
  say "First report"
  PLOW_SINCE="$SINCE" AGENTSVIEW_NO_DAEMON=1 python3 "$DIR/report.py" --agent plow-agent
  say "No systemd user session here (macOS, WSL, containers). To report every 5 min, add this with 'crontab -e':"
  echo "*/5 * * * * PLOW_SINCE=$SINCE AGENTSVIEW_NO_DAEMON=1 /usr/bin/env python3 $DIR/report.py --agent plow-agent >/dev/null 2>&1"
fi

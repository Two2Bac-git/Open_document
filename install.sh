#!/usr/bin/env bash
# Instala o Plow-Agent nesta máquina: registra a instalação no Agent Index
# e liga o relatório de uso (tokens por dia/modelo) a cada 5 minutos.
# Antes: `plow-agents login` (https://github.com/plow-pbc/plow-agents).
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
CLIENT="$DIR/agent_index_client.py"
TOKEN_FILE="${PLOW_TOKEN_FILE:-$HOME/.config/plow/token}"

set +e; python3 "$CLIENT" status >/dev/null; st=$?; set -e
case $st in
  0) echo "Instalação já registrada." ;;
  3)
    [ -r "$TOKEN_FILE" ] || { echo "Rode 'plow-agents login' antes (não achei $TOKEN_FILE)." >&2; exit 1; }
    PLOW_AGENT_TOKEN="$(cat "$TOKEN_FILE")" python3 "$CLIENT" --register --agent plow-agent ;;
  *) echo "Estado do cliente ilegível; veja a mensagem acima e corrija antes de registrar de novo." >&2; exit 1 ;;
esac

UNIT="$HOME/.config/systemd/user"
mkdir -p "$UNIT"
cat > "$UNIT/plow-agent-index.service" <<EOF
[Unit]
Description=Plow-Agent: reporta uso ao Agent Index

[Service]
Type=oneshot
ExecStart=/usr/bin/env python3 $CLIENT --agent plow-agent
EOF
cat > "$UNIT/plow-agent-index.timer" <<EOF
[Unit]
Description=Plow-Agent: relatório a cada 5 minutos

[Timer]
OnBootSec=1min
OnUnitActiveSec=5min

[Install]
WantedBy=timers.target
EOF
systemctl --user daemon-reload
systemctl --user enable --now plow-agent-index.timer
echo "Pronto. Ver: systemctl --user list-timers plow-agent-index.timer"

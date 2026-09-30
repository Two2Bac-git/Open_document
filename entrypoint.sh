#!/bin/sh
# Processo principal do contêiner. Nunca move arquivo sozinho: organizar é sempre
# `podman compose exec plow-agent python3 plow.py plan|apply ~/Downloads`.
# 1) indexa o plow.log no SQLite (2º plano)
# 2) com PLOW_AGENT_TOKEN: registra a instalação uma vez e reporta ao Agent Index a cada 5 min
python3 /app/indexer.py --watch &
while :; do
  if [ -n "${PLOW_AGENT_TOKEN:-}" ]; then
    python3 /app/agent_index_client.py status >/dev/null 2>&1; st=$?
    [ "$st" -eq 3 ] && python3 /app/agent_index_client.py --register --agent "$AGENT_ID"
    [ "$st" -ne 2 ] && python3 /app/agent_index_client.py --agent "$AGENT_ID"
  else
    echo "sem PLOW_AGENT_TOKEN: Agent Index desligado (organizar e indexar funcionam)"
  fi
  sleep 300
done

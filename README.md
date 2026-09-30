# Plow-Agent

Organizador de arquivos por metadados — nunca lê o conteúdo. Tudo tem simulação antes.

| Bloco | Arquivo | O que faz |
|---|---|---|
| Organizar | `plow.py plan\|apply <pasta>` | Move arquivos soltos para `<pasta>/Imagens`, `Documentos`, `Videos`... |
| Reparar links | `plow.py directory-open [--apply] <pasta>` | Acha symlinks quebrados; repara quando há um único candidato |
| Índice | `indexer.py [--watch]` | Copia cada ação do `plow.log` para `~/.plow-agent.db` (SQLite) |
| Agente Haiku | `.claude/agents/plow-organizador.md` | Roda plan, espera sua confirmação, roda apply |
| Agente Sonnet | `.claude/agents/plow-reparador.md` | directory-open + propõe reparo para links ambíguos |

## Regras de segurança
- Só pastas visíveis dentro do home. Recusa: ocultas, sistema/app, o próprio home, e qualquer pasta dentro de repositório git (inclusive via symlink).
- Symlink: move o link, nunca o alvo; links relativos são reescritos.
- Nunca sobrescreve: colisão vira `nome (1).ext`.

## Uso
```sh
python3 plow.py plan ~/Downloads     # veja
python3 plow.py apply ~/Downloads    # faça
nohup python3 indexer.py --watch >/dev/null 2>&1 &   # índice em 2º plano
python3 test_plow.py                 # autoteste (pasta temporária)
```

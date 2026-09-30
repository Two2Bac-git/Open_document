# Plow-Agent

Sorts your folders by file metadata — it never reads file content. Every action has a dry-run first.

> A 100% customizable repo within the rules of the game ;) — that's how GitHub works. Your folders end up the way that best defines your directory, without breaking symlinks. Updates from me and from others are welcome, with care: Andrey Bacelar

| Block | File | What it does |
|---|---|---|
| Sort | `plow.py plan\|apply <folder>` | Moves loose files into `<folder>/<Category>/` |
| Repair links | `plow.py directory-open [--apply] <folder>` | Finds broken symlinks; repairs them when there is exactly one candidate |
| Index | `indexer.py [--watch]` | Copies every action from `plow.log` into `~/.plow-agent.db` (SQLite) |
| Haiku agent | `.claude/agents/plow-organizer.md` | Runs plan, waits for your confirmation, runs apply |
| Sonnet agent | `.claude/agents/plow-repairer.md` | directory-open + proposes repairs for ambiguous links |

Category folders follow your system: the XDG names it already uses (`~/.config/user-dirs.dirs`), otherwise your `LANG` (English and Portuguese built in).

## Install
```sh
git clone https://github.com/Two2Bac-git/Open_document.git plow-agent && cd plow-agent
python3 test_plow.py                    # self-check (temp folder only)
python3 plow.py plan ~/Downloads        # look
python3 plow.py apply ~/Downloads       # do it
```

### Usage reporting (Agent Index)
```sh
plow-agents login    # Plow account, code arrives by SMS: https://github.com/plow-pbc/plow-agents
./install.sh         # registers this install and reports usage every 5 min
```
Only token counts per day and model are sent to the [Agent Index](https://aiworthusing.com/agent-index/plow-agent) — no prompts, text or paths. Stop: `systemctl --user disable --now plow-agent-index.timer`.

### Container (Docker or Podman)
```sh
PLOW_FOLDER=~/Downloads docker compose up -d --build                  # never moves anything on its own
docker compose exec plow-agent python3 plow.py plan ~/Downloads       # look
docker compose exec plow-agent python3 plow.py apply ~/Downloads      # do it
```
Prebuilt: `ghcr.io/two2bac-git/plow-agent`. The image only builds if the self-check passes, carries OCI labels (source, MIT license, commit) and a healthcheck.

## Safety rules
- Only visible folders inside HOME. Refused: hidden folders, system/app folders, HOME itself, and anything inside a git repository (symlinks included).
- Symlinks: the link moves, never its target; relative links are rewritten.
- Never overwrites: a collision becomes `name (1).ext`.

## Releasing
```sh
./release.sh v2      # refuses dirty trees, unpushed commits and existing tags; prints the digest
```

## License
MIT. `agent_index_client.py` is © The Plow Collective, Apache-2.0 (`LICENSE-APACHE`), redistributed unchanged.

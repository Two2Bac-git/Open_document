#!/bin/sh
# Clean-room check of the README "Install" steps, as a first-time visitor types them.
# Run in a throwaway container, e.g.:
#   podman run --rm -v "$PWD/cleanroom.sh:/c.sh:ro" python:3.9-slim sh -c "apt-get update -qq; apt-get install -y -qq git >/dev/null; sh /c.sh"
# SRC=<path or URL> tests another checkout. Prints PASS/FAIL per step; nothing stops the run.
step() { name="$1"; shift; out="$( "$@" 2>&1 )"; code=$?
  if [ $code -eq 0 ]; then echo "PASS  $name"; else echo "FAIL  $name (exit $code)"; echo "$out" | tail -3 | sed 's/^/      /'; fi; }
cd "$HOME"
echo "python: $(python3 --version 2>&1) | git: $(git --version 2>&1 | cut -d' ' -f3) | os: $(. /etc/os-release; echo $PRETTY_NAME)"
step "git clone"            git clone -q "${SRC:-https://github.com/Two2Bac-git/Open_document.git}" plow-agent
cd plow-agent 2>/dev/null || exit 1
step "self-check"           python3 test_plow.py
step "missing folder is refused" sh -c "! python3 plow.py plan ~/Downloads"
mkdir -p ~/Downloads && echo x > ~/Downloads/a.pdf && echo x > ~/Downloads/b.jpg
step "plan ~/Downloads"     python3 plow.py plan ~/Downloads
step "apply ~/Downloads"    python3 plow.py apply ~/Downloads
step "result in place"      test -e ~/Downloads/Documents/a.pdf -o -e ~/Downloads/Documentos/a.pdf
step "refusal exits non-zero" sh -c "! python3 plow.py plan ~/.hidden-x"
step "./install.sh without a terminal stops early" sh -c "! ./install.sh"
step "nothing downloaded before login" sh -c "test ! -e ~/.local/bin/agentsview && test ! -e ~/.local/share/plow-agents"
echo "systemctl --user: $(systemctl --user is-system-running 2>&1 | head -1)"

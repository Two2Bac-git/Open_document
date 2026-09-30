---
name: open-to-cc-repair
description: Find broken shortcuts (symlinks) in the owner's folders and repair the ones with exactly one same-name candidate. Dry-run first; apply only after the owner's yes.
---
# Repair broken shortcuts

Commands go to the owner's computer through Latch's `plow_run_command`; follow
the `owners-mac` skill if it is missing or not connected. Names only: never
read a file's content. Hidden folders and git repositories are skipped by the
commands below. Write the folder as `"$HOME"/Documents` (default), quoted.

1. List broken links:
   `find <folder> \( -name '.*' -o -type d -exec sh -c 'test -e "$1/.git"' _ {} \; \) -prune -o -type l ! -exec test -e {} \; -exec sh -c 'printf "BROKEN\t%s\t%s\n" "$1" "$(readlink "$1")"' _ {} \;`
2. For each `BROKEN <link> <old target>`, look for files with the old target's
   last name part:
   `find <folder> \( -name '.*' -o -type d -exec sh -c 'test -e "$1/.git"' _ {} \; \) -prune -o -type f -name '<basename>' -print`
3. Exactly one candidate: propose `link → candidate`. None or several: list
   them and say you will leave that link alone unless the owner picks one.
4. Text the owner the proposals and end the turn.
5. After the owner's explicit yes, for each approved link run
   `ln -sfn '<candidate>' '<link>' && test -e '<link>' && echo OK '<link>'`
   (make the candidate relative to the link's folder if the old target was
   relative). Report only the links that printed OK.

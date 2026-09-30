---
name: open-to-cc
description: Sort the loose files of a folder on the owner's computer (Downloads, Desktop...) into subfolders by type, from names and types only. Dry-run first; apply only after the owner's yes.
---
# Sort a folder

`PLOW=/opt/plow/skills/open-to-cc/scripts/plow.py` runs here, in your
container. Commands for the owner's computer go through Latch's
`plow_run_command` (the tool name may be server-prefixed); follow the
`owners-mac` skill when it is missing or not connected. Work files live in
`/var/lib/plow/open-to-cc/` (create it with `mkdir -p`).

## Dry-run (every request starts here)

1. Take the folder from the request; default `~/Downloads`. Run
   `python3 $PLOW survey-cmd '<folder>'` here and send its whole output, as is,
   as one `plow_run_command` on the owner's computer. It prints names, kinds
   and link targets only.
2. Save that output with the `write` tool to
   `/var/lib/plow/open-to-cc/survey.txt`.
3. Run `python3 $PLOW plan-survey /var/lib/plow/open-to-cc/survey.txt --script /var/lib/plow/open-to-cc/apply.sh`.
   - `REFUSED <folder>: <reason>` (exit 1): tell the owner the folder and the
     reason, and stop. Do not suggest a way around it.
   - No `MOVE` lines: say the folder has no loose files to sort, and stop.
4. Text the owner the plan: how many files go into each folder, then up to 10
   `name → folder` lines ("and N more" beyond that). Say nothing is changed yet
   and ask for a yes. End the turn.

## Apply (only after the owner's explicit yes to that plan)

1. Survey again (dry-run steps 1–3). If the `MOVE` lines differ from the plan
   the owner approved, send the new plan and ask again instead of applying.
2. Send the whole of `/var/lib/plow/open-to-cc/apply.sh`, as is, as one
   `plow_run_command`. Never edit it or write moves by hand. It never
   overwrites: a name that became taken is skipped.
3. Count the `MOVED` lines it printed. Survey once more and confirm those files
   are gone from the top level. Report what moved and anything skipped. Only
   claim what the output shows.

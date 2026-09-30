#!/usr/bin/env python3
"""Open to CC: sorts loose files by metadata (name/extension) and never reads their content.

Usage:
  plow.py plan <folder>...                       show what would happen; touches nothing
  plow.py apply <folder>...                      move loose files into <folder>/<Category>/
  plow.py directory-open [--apply] <folder>...   find broken symlinks; --apply repairs them
"""
from __future__ import annotations  # `Path | None` hints on Python 3.9 (macOS's stock python3)

import mimetypes
import os
import posixpath
import re
import shlex
import sys
from datetime import datetime
from pathlib import Path, PurePath, PurePosixPath

HOME = Path.home()
LOG = Path(os.environ.get("PLOW_LOG", Path(__file__).resolve().parent / "plow.log"))
# System/app folders inside HOME that are never a root.
BLOCKED = {"snap", "Applications", "go", "bin", "lib", "node_modules"}
# category -> (XDG key that names it on this system, fallback name per language)
CATEGORIES = {
    "images": ("PICTURES", {"en": "Pictures", "pt": "Imagens"}),
    "videos": ("VIDEOS", {"en": "Videos", "pt": "Vídeos"}),
    "audio": ("MUSIC", {"en": "Music", "pt": "Músicas"}),
    "documents": ("DOCUMENTS", {"en": "Documents", "pt": "Documentos"}),
    "archives": (None, {"en": "Archives", "pt": "Compactados"}),
    "other": (None, {"en": "Other", "pt": "Outros"}),
}
BY_TYPE = {"image": "images", "video": "videos", "audio": "audio", "text": "documents"}
DOCS = ("pdf", "msword", "document", "sheet", "presentation", "rtf", "epub")
ARCHIVES = ("zip", "tar", "7z", "rar", "compressed", "gzip", "bzip")


def log(msg, dry_run=False):
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} {'[dry-run] ' if dry_run else ''}{msg}"
    print(line)
    with LOG.open("a") as f:
        f.write(line + "\n")


def category(p: Path) -> str:
    mime = mimetypes.guess_type(p.name)[0] or ""
    kind, _, sub = mime.partition("/")
    if kind in BY_TYPE:
        return BY_TYPE[kind]
    if any(k in sub for k in DOCS):
        return "documents"
    if any(k in sub for k in ARCHIVES):
        return "archives"
    return "other"


def xdg_dirs() -> dict:
    """This system's XDG user dirs, e.g. {"PICTURES": "Imagens"}; dirs pointing at HOME are disabled."""
    f = HOME / ".config" / "user-dirs.dirs"
    found = {}
    if f.exists():
        for key, value in re.findall(r'^XDG_(\w+)_DIR="(.*)"', f.read_text(), re.M):
            path = Path(value.replace("$HOME", str(HOME)))
            if path != HOME:
                found[key] = path.name
    return found


def folder_names() -> dict:
    """Folder per category: the system's own XDG name, else the LANG default, else English."""
    xdg, lang = xdg_dirs(), os.environ.get("LANG", "")[:2]
    return {cat: xdg.get(key) or names.get(lang, names["en"]) for cat, (key, names) in CATEGORIES.items()}


def _has_git(d: Path) -> bool:
    return (d / ".git").exists()


def refusal(root: Path):
    """None if the root may be sorted; otherwise the reason it is refused."""
    real = root.expanduser().resolve()
    if not real.is_dir():
        return "not a folder"
    return _refusal(real, HOME, _has_git)


def _refusal(real: PurePath, home: PurePath, has_git) -> str | None:
    """The rules shared by a local folder and a surveyed one on the owner's computer."""
    if home not in real.parents:
        return "outside HOME (or HOME itself)"
    parts = real.relative_to(home).parts
    if any(x.startswith(".") for x in parts):
        return "hidden folder"
    if parts[0] in BLOCKED:
        return "system/app folder"
    if any(has_git(d) for d in [real, *real.parents] if home in d.parents):
        return "inside a git repository"
    return None


def free(dst: PurePath, taken: set | None = None) -> PurePath:
    """First free name for dst: on disk, or, given `taken`, among those relative paths."""
    exists = (lambda p: str(p) in taken) if taken is not None else (lambda p: p.exists() or p.is_symlink())
    n = 1
    target = dst
    while exists(target):
        target = dst.with_name(f"{dst.stem} ({n}){dst.suffix}")
        n += 1
    return target


def plan(root: Path):
    """Loose files at the first level only; folders (and links to folders) stay put."""
    names = folder_names()
    for p in sorted(root.iterdir()):
        if p.name.startswith(".") or p.is_dir() or not p.exists():
            continue  # hidden, folder, or broken symlink (that one is directory-open's job)
        yield p, free(root / names[category(p)] / p.name)


def move(src: Path, dst: Path):
    if dst.exists() or dst.is_symlink():
        raise FileExistsError(dst)  # never overwrite
    dst.parent.mkdir(exist_ok=True)
    if src.is_symlink() and not os.path.isabs(target := os.readlink(src)):
        # relative link: recompute the path from the new folder; the target is never touched
        absolute = os.path.normpath(os.path.join(src.parent, target))
        os.symlink(os.path.relpath(absolute, dst.parent), dst)
        src.unlink()
    else:
        os.rename(src, dst)  # for an absolute symlink this moves the link itself


def walk(root: Path):
    """Everything under root, without entering hidden folders, git repositories or folder links."""
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if not d.startswith(".") and not _has_git(Path(dirpath, d))]
        for name in dirs + files:
            if not name.startswith("."):
                yield Path(dirpath, name)


def choose_repair(link: Path, old_target: str, candidates: list) -> Path | None:
    # ponytail: only unambiguous repairs; ties go to the plow-repairer agent (Sonnet)
    return candidates[0] if len(candidates) == 1 else None


def directory_open(roots, apply):
    everything = [p for r in roots for p in walk(r)]
    by_name = {}
    for p in everything:
        if p.exists() and not p.is_symlink():
            by_name.setdefault(p.name, []).append(p)
    for link in (p for p in everything if p.is_symlink() and not p.exists()):
        old = os.readlink(link)
        new = choose_repair(link, old, by_name.get(Path(old).name, []))
        if new is None:
            log(f"BROKEN no repair: {link} -> {old}", not apply)
            continue
        target = os.path.relpath(new, link.parent) if not os.path.isabs(old) else str(new)
        log(f"REPAIR {link}: {old} -> {target}", not apply)
        if apply:
            link.unlink()
            os.symlink(target, link)


# --- Remote mode: the deployed agent sorts a folder on the owner's computer (via Latch).
# It never sees file content: the owner's machine answers SURVEY with names, kinds and
# link targets; the plan is decided here; the owner's machine runs the returned script.
SURVEY = r"""cd {folder} 2>/dev/null || {{ echo NOFOLDER; exit 0; }}
printf 'HOME\t%s\nREAL\t%s\nOS\t%s\n' "$HOME" "$(pwd -P)" "$(uname -s)"
p="$(pwd -P)"; while [ "$p" != / ]; do [ -e "$p/.git" ] && printf 'GIT\t%s\n' "$p"; p="$(dirname "$p")"; done
for f in * */*; do [ -e "$f" ] || [ -L "$f" ] || continue
  if [ -L "$f" ]; then if [ -d "$f" ]; then k=dirlink; elif [ -e "$f" ]; then k=link; else k=broken; fi
  elif [ -d "$f" ]; then k=dir; else k=file; fi
  printf 'ENTRY\t%s\t%s\t%s\n' "$k" "$f" "$(readlink "$f" 2>/dev/null)"
done"""
# macOS keeps English folder names on disk whatever the UI language.
MAC_NAMES = {"images": "Pictures", "videos": "Movies", "audio": "Music",
             "documents": "Documents", "archives": "Archives", "other": "Other"}


def survey_cmd(folder: str) -> str:
    """The POSIX sh the owner's computer runs to describe `folder` (~ allowed)."""
    target = '"$HOME"/' + shlex.quote(folder[2:]) if folder.startswith("~/") else shlex.quote(folder)
    return SURVEY.format(folder=target)


def read_survey(text: str) -> dict:
    # ponytail: tab/newline inside a file name breaks the TSV; such files are skipped by plan_survey's checks
    s = {"entries": [], "gits": set()}
    for line in text.splitlines():
        tag, *fields = line.split("\t")
        if tag == "NOFOLDER":
            s["missing"] = True
        elif tag in ("HOME", "REAL", "OS") and fields:
            s[tag.lower()] = fields[0]
        elif tag == "GIT" and fields:
            s["gits"].add(fields[0])
        elif tag == "ENTRY" and len(fields) >= 2:
            s["entries"].append((fields[0], fields[1], fields[2] if len(fields) > 2 else ""))
    return s


def plan_survey(s: dict):
    """(refusal, moves) for a surveyed folder; moves are (src, dst, kind, link target), relative."""
    if s.get("missing") or "real" not in s or "home" not in s:
        return "not a folder", []
    reason = _refusal(PurePosixPath(s["real"]), PurePosixPath(s["home"]), lambda d: str(d) in s["gits"])
    if reason:
        return reason, []
    names = MAC_NAMES if s.get("os") == "Darwin" else {c: n["en"] for c, (_, n) in CATEGORIES.items()}
    taken = {name for _, name, _ in s["entries"]}
    moves = []
    for kind, name, target in sorted(s["entries"], key=lambda e: e[1]):
        if "/" in name or kind not in ("file", "link"):
            continue  # nested entries only reserve names; folders and broken links stay put
        dst = str(free(PurePosixPath(names[category(PurePosixPath(name))]) / name, taken))
        taken.add(dst)
        moves.append((name, dst, kind, target))
    return None, moves


def apply_script(real: str, moves) -> str:
    """sh that performs `moves` inside `real`: never overwrites, rewrites relative links."""
    q = shlex.quote
    out = [f"cd {q(real)} || exit 1"]
    out += [f"mkdir -p {q(d)}" for d in sorted({posixpath.dirname(dst) for _, dst, _, _ in moves})]
    for src, dst, kind, target in moves:
        guard = f"[ -e {q(dst)} ] || [ -L {q(dst)} ] || "
        if kind == "link" and not target.startswith("/"):
            absolute = posixpath.normpath(posixpath.join(real, target))
            new = posixpath.relpath(absolute, posixpath.join(real, posixpath.dirname(dst)))
            out.append(guard + f"{{ ln -s {q(new)} {q(dst)} && rm {q(src)} && echo MOVED {q(src)}; }}")
        else:
            out.append(guard + f"{{ mv {q(src)} {q(dst)} && echo MOVED {q(src)}; }}")
    return "\n".join(out) + "\n"


def remote(argv) -> int:
    """survey-cmd <folder> | plan-survey <survey.txt> [--script <out.sh>]"""
    if argv[0] == "survey-cmd" and len(argv) == 2:
        print(survey_cmd(argv[1]))
        return 0
    if argv[0] == "plan-survey" and len(argv) in (2, 4):
        s = read_survey(Path(argv[1]).read_text())
        reason, moves = plan_survey(s)
        if reason:
            print(f"REFUSED {s.get('real', argv[1])}: {reason}")
            return 1
        for src, dst, _, _ in moves:
            print(f"[dry-run] MOVE {src} -> {dst}")
        if len(argv) == 4 and argv[2] == "--script":
            Path(argv[3]).write_text(apply_script(s["real"], moves))
        return 0
    print(remote.__doc__)
    return 2


def main(argv):
    if argv and argv[0] in ("survey-cmd", "plan-survey"):
        return remote(argv)
    if not argv or argv[0] not in ("plan", "apply", "directory-open"):
        print(__doc__)
        return 2
    cmd, *rest = argv
    apply = cmd == "apply" or "--apply" in rest
    roots, refused = [], False
    for arg in (a for a in rest if a != "--apply"):
        root = Path(arg).expanduser()
        if reason := refusal(root):
            log(f"REFUSED {root}: {reason}")
            refused = True
        else:
            roots.append(root)
    if cmd == "directory-open":
        directory_open(roots, apply)
    else:
        for root in roots:
            for src, dst in plan(root):
                log(f"MOVE {src} -> {dst}", not apply)
                if apply:
                    move(src, dst)
    return 1 if refused else 0  # the other folders still ran; the exit code says one was skipped


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

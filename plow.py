#!/usr/bin/env python3
"""Open to CC: sorts loose files by metadata (name/extension) and never reads their content.

Usage:
  plow.py plan <folder>...                       show what would happen; touches nothing
  plow.py apply <folder>...                      move loose files into <folder>/<Category>/
  plow.py directory-open [--apply] <folder>...   find broken symlinks; --apply repairs them
"""
import mimetypes
import os
import re
import sys
from datetime import datetime
from pathlib import Path

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
    if HOME not in real.parents:
        return "outside HOME (or HOME itself)"
    parts = real.relative_to(HOME).parts
    if any(x.startswith(".") for x in parts):
        return "hidden folder"
    if parts[0] in BLOCKED:
        return "system/app folder"
    if any(_has_git(d) for d in [real, *real.parents] if HOME in d.parents):
        return "inside a git repository"
    return None


def free(dst: Path) -> Path:
    n = 1
    target = dst
    while target.exists() or target.is_symlink():
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


def main(argv):
    if not argv or argv[0] not in ("plan", "apply", "directory-open"):
        print(__doc__)
        return 2
    cmd, *rest = argv
    apply = cmd == "apply" or "--apply" in rest
    roots = []
    for arg in (a for a in rest if a != "--apply"):
        root = Path(arg).expanduser()
        if reason := refusal(root):
            log(f"REFUSED {root}: {reason}")
        else:
            roots.append(root)
    if cmd == "directory-open":
        directory_open(roots, apply)
        return 0
    for root in roots:
        for src, dst in plan(root):
            log(f"MOVE {src} -> {dst}", not apply)
            if apply:
                move(src, dst)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

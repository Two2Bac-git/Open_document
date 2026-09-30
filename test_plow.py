"""Run with: python3 test_plow.py  (everything happens in a temp folder, never in the real HOME)."""
import os
import tempfile
from pathlib import Path

import indexer
import plow


def setup(tmp: Path):
    plow.HOME = tmp
    plow.LOG = tmp / "plow.log"
    dl = tmp / "Downloads"
    dl.mkdir()
    for name in ("note.pdf", "photo.jpg", "mystery", ".hidden.pdf"):
        (dl / name).write_text("x")
    (dl / "Projects").mkdir()
    (tmp / "target.txt").write_text("target")
    os.symlink("../target.txt", dl / "shortcut.txt")          # relative
    os.symlink(str(tmp / "target.txt"), dl / "absolute.txt")  # absolute
    (dl / "Documentos").mkdir()
    (dl / "Documentos" / "note.pdf").write_text("was already here")
    return dl


def test_plan_touches_nothing_and_apply_moves():
    os.environ["LANG"] = "pt_BR.UTF-8"
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        dl = setup(tmp)
        before = sorted(p.name for p in dl.iterdir())
        assert plow.main(["plan", str(dl)]) == 0
        assert sorted(p.name for p in dl.iterdir()) == before, "plan touched the disk"

        assert plow.main(["apply", str(dl)]) == 0
        assert (dl / "Imagens" / "photo.jpg").exists()
        assert (dl / "Documentos" / "note (1).pdf").read_text() == "x", "collision overwrote"
        assert (dl / "Documentos" / "note.pdf").read_text() == "was already here"
        assert (dl / "Outros" / "mystery").exists()
        assert (dl / ".hidden.pdf").exists() and (dl / "Projects").is_dir()
        # links: moved, target untouched, still resolving
        rel = dl / "Documentos" / "shortcut.txt"
        assert rel.is_symlink() and rel.read_text() == "target"
        assert os.readlink(rel) == "../../target.txt"
        assert (dl / "Documentos" / "absolute.txt").read_text() == "target"
        assert (tmp / "target.txt").exists()


def test_folder_names_follow_the_system():
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        plow.HOME = tmp
        os.environ["LANG"] = "en_US.UTF-8"
        names = plow.folder_names()
        assert (names["images"], names["other"]) == ("Pictures", "Other")
        (tmp / ".config").mkdir()
        (tmp / ".config" / "user-dirs.dirs").write_text(
            'XDG_PICTURES_DIR="$HOME/Imagens"\nXDG_VIDEOS_DIR="$HOME/"\n'
        )
        os.environ["LANG"] = "pt_BR.UTF-8"
        names = plow.folder_names()
        assert names["images"] == "Imagens", "XDG name ignored"
        assert names["videos"] == "Vídeos", "disabled XDG dir ($HOME/) was used as a name"
        assert names["archives"] == "Compactados"


def test_refusals():
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        plow.HOME = tmp
        repo = tmp / "Repo"
        (repo / ".git").mkdir(parents=True)
        (repo / "sub").mkdir()
        (tmp / ".hidden").mkdir()
        (tmp / "snap").mkdir()
        os.symlink(repo, tmp / "LinkToRepo")
        assert plow.refusal(repo)
        assert plow.refusal(repo / "sub"), "git repo subfolder passed"
        assert plow.refusal(tmp / "LinkToRepo"), "symlink to git repo passed"
        assert plow.refusal(tmp / ".hidden")
        assert plow.refusal(tmp / "snap")
        assert plow.refusal(tmp), "HOME itself passed"
        plow.LOG = tmp / "plow.log"
        assert plow.main(["plan", str(tmp / ".hidden")]) == 1, "a refusal must not exit 0"
        (tmp / "Free").mkdir()
        assert plow.refusal(tmp / "Free") is None


def test_directory_open_and_indexer():
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        plow.HOME, plow.LOG = tmp, tmp / "plow.log"
        root = tmp / "Docs"
        (root / "New").mkdir(parents=True)
        (root / "New" / "unique.txt").write_text("u")
        for d in ("A", "B"):
            (root / d).mkdir()
            (root / d / "dup.txt").write_text(d)
        os.symlink("Old/unique.txt", root / "l1")  # 1 candidate -> repaired
        os.symlink("Old/dup.txt", root / "l2")     # 2 candidates -> left alone
        plow.main(["directory-open", str(root)])
        assert not (root / "l1").exists(), "dry-run repaired"
        plow.main(["directory-open", "--apply", str(root)])
        assert (root / "l1").read_text() == "u" and os.readlink(root / "l1") == "New/unique.txt"
        assert (root / "l2").is_symlink() and not (root / "l2").exists()

        db = tmp / "idx.db"
        assert indexer.index(plow.LOG, db) == len(plow.LOG.read_text().splitlines()) == 4
        assert indexer.index(plow.LOG, db) == 0, "re-indexing duplicated"
        # v0.1 logs (Portuguese marker) still index
        (tmp / "old.log").write_text("2026-09-29 21:00:00 [simulação] MOVER /a -> /b\n")
        assert indexer.index(tmp / "old.log", db) == 1


def test_remote_survey_plan_apply_roundtrip():
    """The deployed agent's path: survey on the owner's machine, plan in the cloud, script back."""
    import subprocess
    with tempfile.TemporaryDirectory() as t:
        home = Path(t, "home")
        dl = home / "Downloads"
        (dl / "Documents").mkdir(parents=True)
        (dl / "Documents" / "note.pdf").write_text("old")
        for name in ("note.pdf", "photo.jpg", "it's a clip.mp4"):
            (dl / name).write_text("x")
        (home / "target.txt").write_text("target")
        os.symlink("../target.txt", dl / "shortcut.txt")
        os.symlink("Gone/x.txt", dl / "broken.txt")
        env = {**os.environ, "HOME": str(home)}
        sh = lambda script: subprocess.run(["sh", "-c", script], env=env, capture_output=True, text=True).stdout
        s = plow.read_survey(sh(plow.survey_cmd("~/Downloads")))
        s["os"] = "Darwin"  # exercise the macOS folder names
        reason, moves = plow.plan_survey(s)
        assert reason is None
        got = {src: dst for src, dst, _, _ in moves}
        assert got["note.pdf"] == "Documents/note (1).pdf", "collision with an existing file"
        assert got["it's a clip.mp4"] == "Movies/it's a clip.mp4"
        assert "broken.txt" not in got and "Documents" not in got
        out = sh(plow.apply_script(s["real"], moves))
        assert out.count("MOVED") == 4, out
        assert (dl / "Documents" / "note.pdf").read_text() == "old"
        assert (dl / "Movies" / "it's a clip.mp4").exists()
        assert (dl / "Documents" / "shortcut.txt").read_text() == "target", "relative link broke"
        assert (dl / "broken.txt").is_symlink(), "broken link was moved"
        (home / "Repo" / ".git").mkdir(parents=True)
        assert plow.plan_survey(plow.read_survey(sh(plow.survey_cmd("~/Repo"))))[0] == "inside a git repository"
        assert plow.plan_survey(plow.read_survey(sh(plow.survey_cmd("~/Nope"))))[0] == "not a folder"


if __name__ == "__main__":
    for name, f in list(globals().items()):
        if name.startswith("test_"):
            f()
            print("ok", name)

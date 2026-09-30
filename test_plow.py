"""Roda com: python3 test_plow.py  (tudo em pasta temporária, nunca no home real)."""
import os
import tempfile
from pathlib import Path

import plow


def montar(tmp: Path):
    plow.HOME = tmp
    plow.LOG = tmp / "plow.log"
    dl = tmp / "Downloads"
    dl.mkdir()
    for nome in ("nota.pdf", "foto.jpg", "misterio", ".oculto.pdf"):
        (dl / nome).write_text("x")
    (dl / "Projetos").mkdir()
    (tmp / "alvo.txt").write_text("alvo")
    os.symlink("../alvo.txt", dl / "atalho.txt")          # relativo
    os.symlink(str(tmp / "alvo.txt"), dl / "absoluto.txt")  # absoluto
    (dl / "Documentos").mkdir()
    (dl / "Documentos" / "nota.pdf").write_text("já existia")
    return dl


def test_plan_nao_mexe_e_apply_move():
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        dl = montar(tmp)
        antes = sorted(p.name for p in dl.iterdir())
        assert plow.main(["plan", str(dl)]) == 0
        assert sorted(p.name for p in dl.iterdir()) == antes, "plan mexeu no disco"

        assert plow.main(["apply", str(dl)]) == 0
        assert (dl / "Imagens" / "foto.jpg").exists()
        assert (dl / "Documentos" / "nota (1).pdf").read_text() == "x", "colisão sobrescreveu"
        assert (dl / "Documentos" / "nota.pdf").read_text() == "já existia"
        assert (dl / "Outros" / "misterio").exists()
        assert (dl / ".oculto.pdf").exists() and (dl / "Projetos").is_dir()
        # links: movidos, alvo intocado, ainda resolvem
        rel = dl / "Documentos" / "atalho.txt"
        assert rel.is_symlink() and rel.read_text() == "alvo"
        assert os.readlink(rel) == "../../alvo.txt"
        assert (dl / "Documentos" / "absoluto.txt").read_text() == "alvo"
        assert (tmp / "alvo.txt").exists()


def test_recusas():
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        plow.HOME = tmp
        repo = tmp / "Repo"
        (repo / ".git").mkdir(parents=True)
        (repo / "sub").mkdir()
        (tmp / ".escondida").mkdir()
        (tmp / "snap").mkdir()
        os.symlink(repo, tmp / "LinkProRepo")
        assert plow.motivo_recusa(repo)
        assert plow.motivo_recusa(repo / "sub"), "subpasta de repo git passou"
        assert plow.motivo_recusa(tmp / "LinkProRepo"), "symlink para repo git passou"
        assert plow.motivo_recusa(tmp / ".escondida")
        assert plow.motivo_recusa(tmp / "snap")
        assert plow.motivo_recusa(tmp), "o próprio home passou"
        (tmp / "Livre").mkdir()
        assert plow.motivo_recusa(tmp / "Livre") is None


def test_directory_open_e_indexer():
    import indexer
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        plow.HOME, plow.LOG = tmp, tmp / "plow.log"
        raiz = tmp / "Docs"
        (raiz / "Novo").mkdir(parents=True)
        (raiz / "Novo" / "unico.txt").write_text("u")
        for d in ("A", "B"):
            (raiz / d).mkdir()
            (raiz / d / "dup.txt").write_text(d)
        os.symlink("Velho/unico.txt", raiz / "l1")  # 1 candidato -> repara
        os.symlink("Velho/dup.txt", raiz / "l2")    # 2 candidatos -> não arrisca
        plow.main(["directory-open", str(raiz)])
        assert not (raiz / "l1").exists(), "simulação reparou"
        plow.main(["directory-open", "--apply", str(raiz)])
        assert (raiz / "l1").read_text() == "u" and os.readlink(raiz / "l1") == "Novo/unico.txt"
        assert (raiz / "l2").is_symlink() and not (raiz / "l2").exists()

        db = tmp / "idx.db"
        n = indexer.indexar(plow.LOG, db)
        assert n == len(plow.LOG.read_text().splitlines()) == 4
        assert indexer.indexar(plow.LOG, db) == 0, "reindexar duplicou"


if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("test_"):
            f()
            print("ok", nome)

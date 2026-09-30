#!/usr/bin/env python3
"""Plow-Agent: organiza arquivos soltos por metadados (nome/extensão), sem ler conteúdo.

Uso:
  plow.py plan <pasta>...                  mostra o que faria, não mexe em nada
  plow.py apply <pasta>...                 move os arquivos soltos para <pasta>/<Categoria>/
  plow.py directory-open [--apply] <pasta>...   acha symlinks quebrados e (com --apply) repara
"""
import mimetypes
import os
import sys
from datetime import datetime
from pathlib import Path

HOME = Path.home()
LOG = Path(os.environ.get("PLOW_LOG", Path(__file__).resolve().parent / "plow.log"))
# Pastas de sistema/apps dentro do home que nunca viram raiz.
PROIBIDAS = {"snap", "Applications", "go", "bin", "lib", "node_modules"}
POR_TIPO = {"image": "Imagens", "video": "Videos", "audio": "Audios", "text": "Documentos"}
DOCS = ("pdf", "msword", "document", "sheet", "presentation", "rtf", "epub")
PACOTES = ("zip", "tar", "7z", "rar", "compressed", "gzip", "bzip")


def log(msg, simulacao=False):
    linha = f"{datetime.now():%Y-%m-%d %H:%M:%S} {'[simulação] ' if simulacao else ''}{msg}"
    print(linha)
    with LOG.open("a") as f:
        f.write(linha + "\n")


def categoria(p: Path) -> str:
    mime = mimetypes.guess_type(p.name)[0] or ""
    tipo, _, sub = mime.partition("/")
    if tipo in POR_TIPO:
        return POR_TIPO[tipo]
    if any(k in sub for k in DOCS):
        return "Documentos"
    if any(k in sub for k in PACOTES):
        return "Compactados"
    return "Outros"


def _tem_git(d: Path) -> bool:
    return (d / ".git").exists()


def motivo_recusa(raiz: Path):
    """None se a raiz pode ser organizada; senão, o motivo da recusa."""
    real = raiz.expanduser().resolve()
    if not real.is_dir():
        return "não é pasta"
    if HOME not in real.parents:
        return "fora do home (ou é o próprio home)"
    partes = real.relative_to(HOME).parts
    if any(x.startswith(".") for x in partes):
        return "pasta oculta"
    if partes[0] in PROIBIDAS:
        return "pasta de sistema/app"
    if any(_tem_git(d) for d in [real, *real.parents] if HOME in d.parents):
        return "está dentro de um repositório git"
    return None


def livre(dst: Path) -> Path:
    n = 1
    alvo = dst
    while alvo.exists() or alvo.is_symlink():
        alvo = dst.with_name(f"{dst.stem} ({n}){dst.suffix}")
        n += 1
    return alvo


def planejar(raiz: Path):
    """Só arquivos soltos no primeiro nível; pastas (e links para pastas) ficam onde estão."""
    for p in sorted(raiz.iterdir()):
        if p.name.startswith(".") or p.is_dir() or not p.exists():
            continue  # oculto, pasta, ou symlink quebrado (isso é com o directory-open)
        yield p, livre(raiz / categoria(p) / p.name)


def mover(src: Path, dst: Path):
    if dst.exists() or dst.is_symlink():
        raise FileExistsError(dst)  # nunca sobrescrever
    dst.parent.mkdir(exist_ok=True)
    if src.is_symlink() and not os.path.isabs(alvo := os.readlink(src)):
        # link relativo: recalcula o caminho a partir da nova pasta; o alvo não é tocado
        absoluto = os.path.normpath(os.path.join(src.parent, alvo))
        os.symlink(os.path.relpath(absoluto, dst.parent), dst)
        src.unlink()
    else:
        os.rename(src, dst)  # em symlink absoluto, move o próprio link


def varrer(raiz: Path):
    """Tudo abaixo da raiz, sem entrar em ocultos, repositórios git ou links de pasta."""
    for dirpath, dirs, files in os.walk(raiz):
        dirs[:] = [d for d in dirs if not d.startswith(".") and not _tem_git(Path(dirpath, d))]
        for nome in dirs + files:
            if not nome.startswith("."):
                yield Path(dirpath, nome)


def escolher_reparo(link: Path, alvo_antigo: str, candidatos: list) -> Path | None:
    # ponytail: só repara sem ambiguidade; empates ficam para o agente plow-reparador (Sonnet)
    return candidatos[0] if len(candidatos) == 1 else None


def directory_open(raizes, aplicar):
    todos = [p for r in raizes for p in varrer(r)]
    por_nome = {}
    for p in todos:
        if p.exists() and not p.is_symlink():
            por_nome.setdefault(p.name, []).append(p)
    for link in (p for p in todos if p.is_symlink() and not p.exists()):
        alvo = os.readlink(link)
        novo = escolher_reparo(link, alvo, por_nome.get(Path(alvo).name, []))
        if novo is None:
            log(f"QUEBRADO sem reparo: {link} -> {alvo}", not aplicar)
            continue
        destino = os.path.relpath(novo, link.parent) if not os.path.isabs(alvo) else str(novo)
        log(f"REPARO {link}: {alvo} -> {destino}", not aplicar)
        if aplicar:
            link.unlink()
            os.symlink(destino, link)


def main(argv):
    if not argv or argv[0] not in ("plan", "apply", "directory-open"):
        print(__doc__)
        return 2
    cmd, *resto = argv
    aplicar = cmd == "apply" or "--apply" in resto
    raizes = []
    for arg in (a for a in resto if a != "--apply"):
        raiz = Path(arg).expanduser()
        if motivo := motivo_recusa(raiz):
            log(f"RECUSADA {raiz}: {motivo}")
        else:
            raizes.append(raiz)
    if cmd == "directory-open":
        directory_open(raizes, aplicar)
        return 0
    for raiz in raizes:
        for src, dst in planejar(raiz):
            log(f"MOVER {src} -> {dst}", not aplicar)
            if aplicar:
                mover(src, dst)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

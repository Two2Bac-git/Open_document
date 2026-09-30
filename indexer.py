#!/usr/bin/env python3
"""Indexa as mensagens do plow.log no SQLite oculto ~/.plow-agent.db.

Uso:
  indexer.py            indexa uma vez
  indexer.py --watch    fica em 2º plano, reindexando a cada 10 s
"""
import re
import sqlite3
import sys
import time
from pathlib import Path

import plow

DB = Path.home() / ".plow-agent.db"
LINHA = re.compile(r"^(\S+ \S+) (\[simulação\] )?(\S+) (.*)$")


def indexar(log: Path = None, db: Path = None) -> int:
    """Devolve quantas mensagens novas entraram."""
    log, db = log or plow.LOG, db or DB
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE IF NOT EXISTS mensagens (id INTEGER PRIMARY KEY, ts TEXT, simulacao INTEGER,"
        " tipo TEXT, texto TEXT, UNIQUE(ts, simulacao, tipo, texto))"
    )
    novas = 0
    if log.exists():
        # ponytail: relê o log inteiro e deixa o UNIQUE deduplicar; guardar offset se o log crescer muito
        for linha in log.read_text().splitlines():
            if m := LINHA.match(linha):
                cur = con.execute(
                    "INSERT OR IGNORE INTO mensagens (ts, simulacao, tipo, texto) VALUES (?, ?, ?, ?)",
                    (m[1], bool(m[2]), m[3], m[4]),
                )
                novas += cur.rowcount
    con.commit()
    con.close()
    return novas


if __name__ == "__main__":
    while True:
        if n := indexar():
            print(f"{n} mensagens novas em {DB}")
        if "--watch" not in sys.argv:
            break
        time.sleep(10)

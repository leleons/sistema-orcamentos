from __future__ import annotations

from typing import Callable


ConnectionFactory = Callable[[], object]


def listar_recorrencias(conn_factory: ConnectionFactory, tipo: str) -> list[dict]:
    conn = conn_factory()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM financeiro_recorrencias_v2 WHERE tipo=? ORDER BY id DESC", (tipo,))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

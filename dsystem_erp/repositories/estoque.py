from __future__ import annotations

from typing import Callable


ConnectionFactory = Callable[[], object]


def _fetchall(conn_factory: ConnectionFactory, sql: str, params: tuple = ()) -> list[dict]:
    conn = conn_factory()
    cursor = conn.cursor()
    cursor.execute(sql, params)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def listar_estoque(conn_factory: ConnectionFactory) -> list[dict]:
    return _fetchall(conn_factory, "SELECT * FROM estoque ORDER BY produto ASC")


def listar_alertas_estoque_minimo(conn_factory: ConnectionFactory) -> list[dict]:
    return _fetchall(
        conn_factory,
        """SELECT id, codigo_entrada, produto, categoria, quantidade, estoque_minimo, fornecedor
           FROM estoque
           WHERE estoque_minimo > 0 AND quantidade <= estoque_minimo
           ORDER BY quantidade ASC, produto ASC""",
    )


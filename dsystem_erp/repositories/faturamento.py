"""Acesso a dados de faturamento."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


ConnectionFactory = Callable[[], Any]


def _fetchall(conn_factory: ConnectionFactory, sql: str, params=()) -> list[dict]:
    conn = conn_factory()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def listar_faturamentos(conn_factory: ConnectionFactory) -> list[dict]:
    return _fetchall(conn_factory, "SELECT * FROM faturamento ORDER BY id DESC")


def listar_faturamentos_para_nf(conn_factory: ConnectionFactory) -> list[dict]:
    return _fetchall(
        conn_factory,
        """SELECT id, cliente, cnpj, tipo_nota, itens, valor_total, obs_nota
           FROM faturamento WHERE emite_nf='Sim' ORDER BY id DESC""",
    )


def listar_faturados_para_nf(conn_factory: ConnectionFactory) -> list[dict]:
    return _fetchall(
        conn_factory,
        """SELECT *
           FROM faturamento
           WHERE emite_nf='Sim' AND COALESCE(status,'Aberto') <> 'Cancelado'
           ORDER BY id DESC""",
    )

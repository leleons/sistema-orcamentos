"""Acesso a dados de clientes."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


ConnectionFactory = Callable[[], Any]


def listar_clientes(conn_factory: ConnectionFactory) -> list[dict]:
    conn = conn_factory()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM clientes ORDER BY nome")
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def buscar_cliente_por_nome(conn_factory: ConnectionFactory, nome: str | None) -> dict | None:
    nome = (nome or "").strip()
    if not nome:
        return None
    for cliente in listar_clientes(conn_factory):
        if (cliente.get("nome") or "").strip().lower() == nome.lower():
            return dict(cliente)
    return None


def buscar_cliente_portal_por_usuario(conn_factory: ConnectionFactory, usuario: str | None) -> dict | None:
    usuario = (usuario or "").strip()
    if not usuario:
        return None
    conn = conn_factory()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM clientes WHERE portal_username=%s", (usuario,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def buscar_cliente_resumo(conn_factory: ConnectionFactory, *, cliente_id=None, cliente_nome=None) -> dict | None:
    conn = conn_factory()
    try:
        cursor = conn.cursor(dictionary=True)
        if cliente_id:
            cursor.execute("SELECT nome, telefone, email, portal_username FROM clientes WHERE id=%s LIMIT 1", (cliente_id,))
        else:
            cursor.execute("SELECT nome, telefone, email, portal_username FROM clientes WHERE nome=%s LIMIT 1", (cliente_nome,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

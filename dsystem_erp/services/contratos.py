"""Persistência central de contratos gerados pelo ERP."""

from __future__ import annotations


def salvar_contrato_gerado(conn, *, tipo, parte_tipo, parte_id, parte_nome, nome_arquivo,
                           arquivo, valor="", inicio="", vencimento="", criado_por="", criado_em=""):
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO contratos
           (tipo, parte_tipo, parte_id, parte_nome, nome_arquivo, mime_type, arquivo,
            status, valor, data_inicio, data_vencimento, criado_por, criado_em)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (tipo, parte_tipo, parte_id, parte_nome, nome_arquivo, "application/pdf", arquivo,
         "Ativo", valor, inicio, vencimento, criado_por, criado_em),
    )
    conn.commit()
    return cursor.lastrowid

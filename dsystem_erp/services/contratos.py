"""Persistência central de contratos gerados pelo ERP."""

from __future__ import annotations


def salvar_contrato_gerado(conn, *, tipo, parte_tipo, parte_id, parte_nome, nome_arquivo,
                           arquivo, valor="", inicio="", vencimento="", criado_por="", criado_em="",
                           mime_type="application/pdf", arquivo_word=None, nome_arquivo_word=""):
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO contratos
           (tipo, parte_tipo, parte_id, parte_nome, nome_arquivo, mime_type, arquivo,
            status, valor, data_inicio, data_vencimento, criado_por, criado_em,
            arquivo_word, nome_arquivo_word)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (tipo, parte_tipo, parte_id, parte_nome, nome_arquivo, mime_type, arquivo,
         "Ativo", valor, inicio, vencimento, criado_por, criado_em, arquivo_word, nome_arquivo_word),
    )
    conn.commit()
    return cursor.lastrowid

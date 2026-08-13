"""Configuração, conexão e adaptadores de compatibilidade do MySQL."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from typing import Any

import mysql.connector

from .config import config_int, config_val
from .services.audit import (
    cliente_do_log,
    extrair_colunas_insert,
    extrair_colunas_update,
    extrair_tabela_sql,
    extrair_where_id,
    limpar_registro_log,
    montar_registro_params,
)


def mysql_connection_config(database: str | None = None, usar_database: bool = True) -> dict[str, Any]:
    config: dict[str, Any] = {
        "host": config_val("MYSQL_HOST", "localhost"),
        "port": config_int("MYSQL_PORT", 3306),
        "user": config_val("MYSQL_USER", "root"),
        "password": config_val("MYSQL_PASSWORD", ""),
        "charset": "utf8mb4",
        "use_unicode": True,
    }
    if usar_database and database:
        config["database"] = database
    return config


def adaptar_placeholders_mysql(sql: str) -> str:
    return sql.replace("?", "%s")


class CompatRow(dict):
    """Linha dicionário que preserva acesso posicional usado pelo legado."""

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class CompatCursor:
    def __init__(
        self,
        cursor,
        registrar_log: Callable | None = None,
        tabelas_sem_log: Iterable[str] = (),
    ):
        self._cursor = cursor
        self._lastrowid = None
        self._registrar_log = registrar_log
        self._tabelas_sem_log = frozenset(tabelas_sem_log)

    def _adaptar_sql(self, sql: str) -> str:
        return adaptar_placeholders_mysql(sql)

    def execute(self, sql, params=None):
        sql_adaptado = self._adaptar_sql(sql)
        acao = None
        if re.match(r"^\s*INSERT\s+INTO\s+", sql_adaptado, flags=re.I):
            acao = "insert"
        elif re.match(r"^\s*UPDATE\s+", sql_adaptado, flags=re.I):
            acao = "update"
        elif re.match(r"^\s*DELETE\s+FROM\s+", sql_adaptado, flags=re.I):
            acao = "delete"

        tabela = extrair_tabela_sql(sql_adaptado, acao) if acao else ""
        deve_logar = bool(
            self._registrar_log
            and acao
            and tabela
            and tabela not in self._tabelas_sem_log
        )
        antes = None
        registro_id = ""
        if deve_logar and acao in {"update", "delete"}:
            coluna_id, registro_id = extrair_where_id(sql_adaptado, params)
            if coluna_id and registro_id is not None:
                try:
                    self._cursor.execute(
                        f"SELECT * FROM `{tabela}` WHERE `{coluna_id}`=%s LIMIT 1",
                        (registro_id,),
                    )
                    antes = self._cursor.fetchone()
                except Exception:
                    antes = None

        resultado = self._cursor.execute(sql_adaptado, params)
        self._lastrowid = self._cursor.lastrowid

        if deve_logar:
            try:
                if acao == "insert":
                    registro_id = self._lastrowid or ""
                    dados = montar_registro_params(extrair_colunas_insert(sql_adaptado), params)
                    detalhes = {"novo": limpar_registro_log(dados)}
                    cliente = cliente_do_log(tabela, dados)
                elif acao == "update":
                    dados_update = montar_registro_params(extrair_colunas_update(sql_adaptado), params)
                    detalhes = {
                        "antes": limpar_registro_log(antes),
                        "alterado": limpar_registro_log(dados_update),
                    }
                    cliente = cliente_do_log(tabela, dados_update) or cliente_do_log(tabela, antes)
                else:
                    detalhes = {"excluido": limpar_registro_log(antes)}
                    cliente = cliente_do_log(tabela, antes)
                self._registrar_log(
                    self._cursor,
                    acao,
                    tabela,
                    registro_id,
                    cliente,
                    detalhes,
                )
            except Exception:
                # O log nunca pode impedir a operação de negócio principal.
                pass
        return resultado

    def executemany(self, sql, params=None):
        return self._cursor.executemany(self._adaptar_sql(sql), params)

    def fetchone(self):
        row = self._cursor.fetchone()
        return CompatRow(row) if isinstance(row, dict) else row

    def fetchall(self):
        rows = self._cursor.fetchall()
        return [CompatRow(row) if isinstance(row, dict) else row for row in rows]

    @property
    def lastrowid(self):
        return self._lastrowid if self._lastrowid is not None else self._cursor.lastrowid

    @property
    def raw_cursor(self):
        return self._cursor

    def close(self):
        return self._cursor.close()


class CompatConnection:
    row_factory = None

    def __init__(
        self,
        conn,
        registrar_log: Callable | None = None,
        tabelas_sem_log: Iterable[str] = (),
    ):
        self._conn = conn
        self._registrar_log = registrar_log
        self._tabelas_sem_log = tabelas_sem_log

    def cursor(self, *args, **kwargs):
        kwargs["dictionary"] = True
        return CompatCursor(
            self._conn.cursor(*args, **kwargs),
            registrar_log=self._registrar_log,
            tabelas_sem_log=self._tabelas_sem_log,
        )

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        return self._conn.close()


def conectar_mysql(
    database: str,
    usar_database: bool = True,
    registrar_log: Callable | None = None,
    tabelas_sem_log: Iterable[str] = (),
    registrar_erro: Callable | None = None,
    connector: Callable = mysql.connector.connect,
):
    config = mysql_connection_config(database, usar_database=usar_database)
    try:
        conexao = connector(**config)
        return CompatConnection(conexao, registrar_log, tabelas_sem_log)
    except mysql.connector.Error as erro:
        if usar_database and getattr(erro, "errno", None) == 1049:
            conexao_base = conectar_mysql(
                database,
                usar_database=False,
                registrar_log=registrar_log,
                tabelas_sem_log=tabelas_sem_log,
                registrar_erro=registrar_erro,
                connector=connector,
            )
            cursor = conexao_base.cursor()
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{database}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            conexao_base.commit()
            cursor.close()
            conexao_base.close()
            conexao = connector(**config)
            return CompatConnection(conexao, registrar_log, tabelas_sem_log)
        if registrar_erro:
            registrar_erro(erro, database)
        raise

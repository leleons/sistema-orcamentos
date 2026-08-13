"""Regras puras de auditoria e interpretacao de SQL."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any


CAMPOS_SENSIVEIS_LOG = {"password", "senha", "portal_password", "arquivo", "foto", "foto_mime", "foto_nome"}


def normalizar_parametros_log(params: Any) -> list | dict:
    if params is None:
        return []
    if isinstance(params, dict):
        return params
    if isinstance(params, (list, tuple)):
        return list(params)
    return [params]


def limpar_valor_log(valor: Any) -> Any:
    if isinstance(valor, (bytes, bytearray, memoryview)):
        return f"<arquivo {len(valor)} bytes>"
    if isinstance(valor, (date, datetime)):
        return valor.isoformat()
    return valor


def limpar_registro_log(registro: Any) -> dict:
    if not registro:
        return {}
    limpo = {}
    for chave, valor in dict(registro).items():
        chave_str = str(chave)
        chave_lower = chave_str.lower()
        if chave_lower in CAMPOS_SENSIVEIS_LOG or any(term in chave_lower for term in ["senha", "password", "secret", "arquivo", "foto"]):
            limpo[chave_str] = "***"
        else:
            limpo[chave_str] = limpar_valor_log(valor)
    return limpo


def extrair_tabela_sql(sql: str, acao: str) -> str:
    padroes = {
        "insert": r"^\s*INSERT\s+INTO\s+`?([a-zA-Z0-9_]+)`?",
        "update": r"^\s*UPDATE\s+`?([a-zA-Z0-9_]+)`?\s+SET\s+",
        "delete": r"^\s*DELETE\s+FROM\s+`?([a-zA-Z0-9_]+)`?",
    }
    padrao = padroes.get(acao)
    if not padrao:
        return ""
    match = re.search(padrao, sql or "", flags=re.I | re.S)
    return match.group(1) if match else ""


def extrair_colunas_insert(sql: str) -> list[str]:
    match = re.search(r"INSERT\s+INTO\s+`?[a-zA-Z0-9_]+`?\s*\((.*?)\)\s*VALUES", sql or "", flags=re.I | re.S)
    if not match:
        return []
    return [c.strip().strip("`") for c in match.group(1).split(",")]


def extrair_colunas_update(sql: str) -> list[str]:
    match = re.search(r"UPDATE\s+`?[a-zA-Z0-9_]+`?\s+SET\s+(.*?)\s+WHERE\s+", sql or "", flags=re.I | re.S)
    if not match:
        return []
    partes = []
    for parte in match.group(1).split(","):
        coluna = parte.split("=", 1)[0].strip().strip("`")
        if coluna:
            partes.append(coluna)
    return partes


def extrair_where_id(sql: str, params: Any) -> tuple[str | None, Any]:
    match = re.search(r"WHERE\s+`?([a-zA-Z0-9_]+)`?\s*=\s*(?:%s|\?)", sql or "", flags=re.I | re.S)
    if not match:
        return None, None
    params_norm = normalizar_parametros_log(params)
    if isinstance(params_norm, dict) or not params_norm:
        return match.group(1), None
    return match.group(1), params_norm[-1]


def montar_registro_params(colunas: list[str], params: Any) -> dict:
    params_norm = normalizar_parametros_log(params)
    if isinstance(params_norm, dict):
        return {col: params_norm.get(col) for col in colunas}
    return {col: params_norm[idx] for idx, col in enumerate(colunas) if idx < len(params_norm)}


def cliente_do_log(tabela: str, dados: Any) -> str:
    if not dados:
        return ""
    dados = dict(dados)
    for campo in ["cliente", "cliente_nome", "cliente_vinculado", "cliente_vinc", "nome"]:
        if campo == "nome" and tabela not in {"clientes"}:
            continue
        valor = dados.get(campo)
        if valor:
            return str(valor)
    return ""

"""Regras de autorização independentes da interface Streamlit."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from dsystem_erp.navigation import LEGACY_PERMISSOES


PERMISSOES_PORTAL_CLIENTE = frozenset(
    {
        "cliente.portal",
        "cliente.os",
        "cliente.autorizacao",
        "cliente.chamados",
        "cliente.propostas",
    }
)

# Administradores comuns também precisam destas permissões nominais.
# A conta principal Daniel.fabio, quando administradora, mantém acesso às senhas.
PERMISSOES_EXPLICITAS = frozenset({"infra.senhas.view", "inter.view", "inter.preparar", "inter.aprovar", "inter.executar", "inter.conciliar", "inter.configurar"})


def carregar_submodulos(valor: Any) -> set[str]:
    if not valor:
        return set()
    if isinstance(valor, (list, tuple, set)):
        return {str(item) for item in valor}
    try:
        dados = json.loads(valor)
    except (TypeError, ValueError, json.JSONDecodeError):
        return set()
    if isinstance(dados, dict):
        return {str(chave) for chave, ativo in dados.items() if ativo}
    if isinstance(dados, list):
        return {str(item) for item in dados}
    return set()


def valor_usuario(usuario: Any, chave: str, padrao: Any = 0) -> Any:
    if isinstance(usuario, Mapping):
        return usuario.get(chave, padrao)
    try:
        return usuario[chave]
    except (KeyError, TypeError, AttributeError):
        return padrao


def usuario_eh_gerencial(usuario: Any) -> bool:
    """Indica se o login pode consultar dados internos da própria Dsystem."""
    if valor_usuario(usuario, "tipo_login", "") == "cliente":
        return False
    def ativo(chave: str) -> bool:
        return str(valor_usuario(usuario, chave, 0)).strip().casefold() in {"1", "true", "sim"}

    return ativo("is_admin") or ativo("modulo_gerencial")


def permissoes_do_usuario(usuario: Any) -> set[str]:
    permissoes = carregar_submodulos(valor_usuario(usuario, "submodulos", "[]"))
    for acao, coluna in LEGACY_PERMISSOES.items():
        if valor_usuario(usuario, coluna, 0):
            permissoes.add(acao)
    return permissoes


def usuario_tem_permissao(acao: str, usuario: Any) -> bool:
    if valor_usuario(usuario, "tipo_login", "") == "cliente":
        return acao in PERMISSOES_PORTAL_CLIENTE
    if acao in PERMISSOES_EXPLICITAS:
        principal = str(valor_usuario(usuario, "username", "") or "").strip().casefold() == "daniel.fabio"
        administrador = str(valor_usuario(usuario, "is_admin", 0)).strip().casefold() in {"1", "true"}
        if acao == "infra.senhas.view" and principal and administrador:
            return True
        return acao in permissoes_do_usuario(usuario)
    if valor_usuario(usuario, "is_admin", 0):
        return True
    return acao in permissoes_do_usuario(usuario)


def usuario_tem_alguma_permissao(prefixo: str, usuario: Any) -> bool:
    if valor_usuario(usuario, "is_admin", 0):
        return True
    permissoes = permissoes_do_usuario(usuario)
    return any(item == prefixo or item.startswith(f"{prefixo}.") for item in permissoes)


def flags_legadas(permissoes: set[str]) -> dict[str, int]:
    return {coluna: int(acao in permissoes) for acao, coluna in LEGACY_PERMISSOES.items()}

"""Operações pequenas e reutilizáveis sobre a sessão da aplicação."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import Any, Iterable


def preencher_sessao(
    sessao: MutableMapping[str, Any],
    dados: Mapping[str, Any],
    excluir: Iterable[str] = ("password",),
) -> None:
    chaves_excluidas = set(excluir)
    for chave, valor in dados.items():
        if chave not in chaves_excluidas:
            sessao[chave] = valor


def limpar_sessao(sessao: MutableMapping[str, Any]) -> None:
    for chave in list(sessao.keys()):
        del sessao[chave]

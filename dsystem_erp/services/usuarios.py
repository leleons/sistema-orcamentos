"""Regras pequenas e testáveis do cadastro de usuários."""

from __future__ import annotations

import re


def normalizar_cpf(valor: object) -> str:
    return re.sub(r"\D", "", str(valor or ""))


def cpf_usuario_valido(valor: object) -> bool:
    return len(normalizar_cpf(valor)) == 11


def filtrar_usuarios(usuarios, termo: object):
    """Filtra por nome do funcionário, CPF ou login, sem alterar a ordem."""
    texto = str(termo or "").strip().lower()
    documento = normalizar_cpf(termo)
    if not texto:
        return list(usuarios or [])
    return [
        usuario for usuario in (usuarios or [])
        if texto in str(usuario.get("funcionario_nome") or "").lower()
        or texto in str(usuario.get("username") or "").lower()
        or (documento and documento in normalizar_cpf(usuario.get("funcionario_cpf")))
    ]


def cpf_em_uso(usuarios, cpf: object, *, ignorar_id: int | None = None) -> bool:
    documento = normalizar_cpf(cpf)
    if not documento:
        return False
    return any(
        normalizar_cpf(usuario.get("funcionario_cpf")) == documento
        and (ignorar_id is None or int(usuario.get("id") or 0) != int(ignorar_id))
        for usuario in (usuarios or [])
    )

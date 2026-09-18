"""Regras puras para dados de clientes."""

from __future__ import annotations

import re
from typing import Any

from dsystem_erp.services.permissions import usuario_eh_gerencial


def filtrar_cadastros_dsystem(clientes, cnpj_dsystem: object, usuario: object):
    """Oculta o cadastro interno da Dsystem de logins não gerenciais."""
    registros = list(clientes or [])
    if usuario_eh_gerencial(usuario):
        return registros
    documento_dsystem = re.sub(r"\D", "", str(cnpj_dsystem or ""))
    if not documento_dsystem:
        return registros
    return [
        cliente for cliente in registros
        if re.sub(r"\D", "", str(cliente.get("cnpj") or "")) != documento_dsystem
    ]


def montar_endereco_cliente(cliente: dict[str, Any] | None) -> str:
    if not cliente:
        return ""
    partes = [
        cliente.get("endereco") or "",
        cliente.get("numero") or "",
        cliente.get("complemento") or "",
        cliente.get("bairro") or "",
        cliente.get("cidade_estado") or "",
        cliente.get("cep") or "",
    ]
    return " - ".join([str(p).strip() for p in partes if str(p or "").strip()])


def dados_cliente_padrao(cliente: dict[str, Any] | None) -> dict[str, Any]:
    cliente = dict(cliente or {})
    return {
        "id": cliente.get("id"),
        "nome": cliente.get("nome") or "",
        "cpf_cnpj": cliente.get("cnpj") or "",
        "telefone": cliente.get("telefone") or cliente.get("telefone_secundario") or "",
        "email": cliente.get("email") or cliente.get("emails_cobranca") or "",
        "contato": cliente.get("contato_padrao") or cliente.get("contato") or cliente.get("nome") or "",
        "endereco": montar_endereco_cliente(cliente),
        "cidade_estado": cliente.get("cidade_estado") or "",
        "cep": cliente.get("cep") or "",
        "dia_vencimento": cliente.get("dia_vencimento") or "",
        "dia_faturamento": cliente.get("dia_faturamento") or "",
        "codigo_ibge": cliente.get("codigo_ibge") or "",
    }

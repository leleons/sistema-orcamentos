"""Regras de WhatsApp separadas da interface."""

from __future__ import annotations

import re
from urllib.parse import quote


def normalizar_telefone_whatsapp(numero: str | None) -> str:
    digitos = re.sub(r"\D", "", numero or "")
    if not digitos:
        return ""
    if len(digitos) in (10, 11):
        digitos = f"55{digitos}"
    return digitos


def criar_url_whatsapp(numero: str | None, mensagem: str) -> str:
    telefone = normalizar_telefone_whatsapp(numero)
    return f"https://wa.me/{telefone}?text={quote(mensagem)}" if telefone else ""

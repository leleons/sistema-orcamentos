"""Utilitarios de data e hora."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo


FUSO_SAO_PAULO = ZoneInfo("America/Sao_Paulo")

DIAS_SEMANA_PT_BR = (
    "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
    "sexta-feira", "sábado", "domingo",
)

MESES_PT_BR = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)


def agora_sao_paulo() -> datetime:
    return datetime.now(FUSO_SAO_PAULO)


def agora_br(fmt: str = "%d/%m/%Y %H:%M") -> str:
    return agora_sao_paulo().strftime(fmt)


def parse_data_flex(valor):
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    valor = str(valor or "").strip()
    if not valor:
        return None
    for formato in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(valor, formato).date()
        except Exception:
            pass
    return None


def data_para_br(valor):
    data = parse_data_flex(valor)
    if data:
        return data.strftime("%d/%m/%Y")
    return valor or ""


def data_para_banco_br(valor):
    data = parse_data_flex(valor)
    return data.strftime("%d/%m/%Y") if data else ""


def data_para_iso(valor):
    data = parse_data_flex(valor)
    return data.strftime("%Y-%m-%d") if data else ""


def data_input_valor(valor, padrao=None):
    return parse_data_flex(valor) or padrao or date.today()


def data_extenso_br(valor, incluir_ano=True):
    """Formata uma data sem depender do idioma instalado no servidor."""
    data = parse_data_flex(valor)
    if not data:
        return valor or ""
    texto = f"{DIAS_SEMANA_PT_BR[data.weekday()]}, {data.day} de {MESES_PT_BR[data.month - 1]}"
    return f"{texto} de {data.year}" if incluir_ano else texto

"""Regras para geração de atendimentos recorrentes na agenda."""

from __future__ import annotations

import calendar
from datetime import date, timedelta


def _adicionar_meses(data_base: date, meses: int) -> date:
    indice_mes = (data_base.month - 1) + meses
    ano = data_base.year + indice_mes // 12
    mes = indice_mes % 12 + 1
    dia = min(data_base.day, calendar.monthrange(ano, mes)[1])
    return date(ano, mes, dia)


def gerar_datas_recorrentes(
    data_inicial: date,
    periodicidade: str,
    quantidade: int = 1,
    dias_semana: set[int] | None = None,
) -> list[date]:
    """Gera datas recorrentes, preservando a data inicial quando aplicável."""
    quantidade = max(1, int(quantidade or 1))
    periodicidade = str(periodicidade or "Não").strip()

    if periodicidade == "Não":
        return [data_inicial]
    if periodicidade == "Diariamente":
        return [data_inicial + timedelta(days=i) for i in range(quantidade)]
    if periodicidade == "Semanalmente":
        return [data_inicial + timedelta(weeks=i) for i in range(quantidade)]
    if periodicidade == "Mensalmente":
        return [_adicionar_meses(data_inicial, i) for i in range(quantidade)]
    if periodicidade == "Anualmente":
        return [_adicionar_meses(data_inicial, 12 * i) for i in range(quantidade)]
    if periodicidade == "Dias da semana":
        escolhidos = set(dias_semana or set())
        if not escolhidos:
            return []
        fim = data_inicial + timedelta(days=(quantidade * 7) - 1)
        resultado: list[date] = []
        atual = data_inicial
        while atual <= fim:
            if atual.weekday() in escolhidos:
                resultado.append(atual)
            atual += timedelta(days=1)
        return resultado

    raise ValueError(f"Periodicidade não reconhecida: {periodicidade}")

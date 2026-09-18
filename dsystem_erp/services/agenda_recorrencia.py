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


def gerar_datas_agenda_configurada(
    data_inicial: date,
    periodicidade: str,
    *,
    quantidade: int | None = None,
    data_fim: date | None = None,
    horizonte: date | None = None,
    dia_semana: int | None = None,
    dia_mes: int | None = None,
    data_anual: date | None = None,
) -> list[date]:
    """Gera ocorrências com dia semanal/mensal/anual configurável.

    ``horizonte`` é usado pelas recorrências indefinidas para manter uma janela
    móvel de compromissos, sem criar infinitas linhas no banco de uma vez.
    """
    periodicidade = str(periodicidade or "Não").strip()
    if periodicidade == "Não":
        return [data_inicial]
    limite = data_fim or horizonte
    total = max(1, int(quantidade)) if quantidade else None
    if total is None and limite is None:
        raise ValueError("Informe a quantidade, a data final ou o horizonte da recorrência.")

    def adicionar(resultado: list[date], candidata: date) -> bool:
        if candidata < data_inicial:
            return True
        if limite and candidata > limite:
            return False
        resultado.append(candidata)
        return not total or len(resultado) < total

    resultado: list[date] = []
    if periodicidade == "Diariamente":
        candidata = data_inicial
        while adicionar(resultado, candidata):
            candidata += timedelta(days=1)
    elif periodicidade == "Semanalmente":
        alvo = data_inicial.weekday() if dia_semana is None else max(0, min(6, int(dia_semana)))
        candidata = data_inicial + timedelta(days=(alvo - data_inicial.weekday()) % 7)
        while adicionar(resultado, candidata):
            candidata += timedelta(days=7)
    elif periodicidade == "Mensalmente":
        alvo = max(1, min(31, int(dia_mes or data_inicial.day)))
        deslocamento = 0
        while True:
            base = _adicionar_meses(data_inicial.replace(day=1), deslocamento)
            candidata = base.replace(day=min(alvo, calendar.monthrange(base.year, base.month)[1]))
            if not adicionar(resultado, candidata):
                break
            deslocamento += 1
    elif periodicidade == "Anualmente":
        modelo = data_anual or data_inicial
        ano = data_inicial.year
        while True:
            dia = min(modelo.day, calendar.monthrange(ano, modelo.month)[1])
            candidata = date(ano, modelo.month, dia)
            if not adicionar(resultado, candidata):
                break
            ano += 1
    else:
        return gerar_datas_recorrentes(data_inicial, periodicidade, total or 1)
    return resultado

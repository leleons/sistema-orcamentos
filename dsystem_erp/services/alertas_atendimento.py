"""Regras dos alertas globais de atendimento e agenda."""

from __future__ import annotations

from datetime import date, datetime, time


STATUS_ENCERRADOS = {"concluído", "concluido", "fechado", "cancelado", "realizado"}


def chamado_esta_aberto(chamado: dict) -> bool:
    return str(chamado.get("status") or "novo").strip().lower() not in STATUS_ENCERRADOS


def horario_agendamento(agendamento: dict) -> datetime | None:
    data_txt = str(agendamento.get("data_visita") or "").strip()
    hora_txt = str(agendamento.get("hora_inicio") or "").strip()
    if not data_txt or not hora_txt:
        return None
    try:
        data_visita = datetime.strptime(data_txt, "%Y-%m-%d").date()
        hora_visita = datetime.strptime(hora_txt[:5], "%H:%M").time()
        return datetime.combine(data_visita, hora_visita)
    except (TypeError, ValueError):
        return None


def agendamentos_proximos(agendamentos: list[dict], agora: datetime, minutos: int = 30) -> list[dict]:
    proximos = []
    agora_local = agora.replace(tzinfo=None)
    for item in agendamentos:
        if str(item.get("status") or "agendado").strip().lower() in STATUS_ENCERRADOS:
            continue
        inicio = horario_agendamento(item)
        if inicio is None:
            continue
        diferenca = (inicio - agora_local).total_seconds() / 60
        if 0 <= diferenca <= minutos:
            proximos.append(item)
    return proximos


def ids_novos(registros: list[dict], ultimo_id: int | None) -> tuple[list[int], int]:
    ids = sorted(int(item.get("id") or 0) for item in registros if int(item.get("id") or 0) > 0)
    maior = max(ids, default=int(ultimo_id or 0))
    if ultimo_id is None:
        return [], maior
    return [item_id for item_id in ids if item_id > ultimo_id], maior

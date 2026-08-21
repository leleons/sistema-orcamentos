"""Regras de totalização, validade e renegociação de orçamentos."""

from __future__ import annotations

from datetime import date, timedelta

from dsystem_erp.utils.datas import parse_data_flex


STATUS_FINAIS_ORCAMENTO = {"Aprovado e lançado", "Aprovado", "Faturado", "Cancelado"}


def total_item_orcamento(valor_unitario, quantidade) -> float:
    return round(float(valor_unitario or 0) * int(quantidade or 0), 2)


def total_geral_orcamento(itens: list[dict]) -> float:
    return round(sum(float(item.get("t") or total_item_orcamento(item.get("v"), item.get("q"))) for item in itens), 2)


def data_validade_orcamento(data_emissao, dias: int = 10) -> date | None:
    emissao = parse_data_flex(data_emissao)
    return emissao + timedelta(days=int(dias)) if emissao else None


def orcamento_esta_vencido(orcamento: dict, hoje: date | None = None, dias: int = 10) -> bool:
    status = str(orcamento.get("status") or "Aberto")
    if status in STATUS_FINAIS_ORCAMENTO:
        return False
    validade = parse_data_flex(orcamento.get("data_validade")) or data_validade_orcamento(orcamento.get("data_orc"), dias)
    return bool(validade and (hoje or date.today()) > validade)


def preparar_edicao_orcamento(orcamento: dict, hoje: date | None = None, dias: int = 10) -> dict:
    """Renova datas e reabre um orçamento vencido quando ele entra em edição."""
    preparado = dict(orcamento or {})
    data_atual = hoje or date.today()
    status_vencido = str(preparado.get("status") or "").strip().casefold() == "vencido"
    if status_vencido or orcamento_esta_vencido(preparado, hoje=data_atual, dias=dias):
        preparado["data_orc"] = data_atual.strftime("%d/%m/%Y")
        preparado["data_validade"] = (data_atual + timedelta(days=int(dias))).strftime("%d/%m/%Y")
        preparado["status"] = "Aberto"
        preparado["_renovado_na_edicao"] = True
    return preparado


def numero_renegociacao(numero, versao: int) -> str:
    base = str(numero or "").split("-R", 1)[0]
    return f"{base}-R{max(2, int(versao or 1) + 1)}"


def aplicar_encargos_renegociacao(itens: list[dict], juros_percentual=0, taxa_fixa=0) -> list[dict]:
    fator = 1 + (max(0.0, float(juros_percentual or 0)) / 100)
    ajustados = []
    for item in itens:
        novo = dict(item)
        novo["v"] = round(float(novo.get("v") or 0) * fator, 2)
        novo["t"] = round(novo["v"] * int(novo.get("q") or 0), 2)
        ajustados.append(novo)
    if float(taxa_fixa or 0) > 0:
        ajustados.append({
            "d": "Taxa de renegociação",
            "tipo_item": "Serviço",
            "v": round(float(taxa_fixa), 2),
            "q": 1,
            "t": round(float(taxa_fixa), 2),
        })
    return ajustados

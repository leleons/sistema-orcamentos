"""Geração de vencimentos e títulos de cobranças recorrentes."""

from __future__ import annotations

import calendar
from datetime import date, timedelta

from dsystem_erp.utils.datas import parse_data_flex


def adicionar_meses(data_base: date, meses: int) -> date:
    indice = data_base.month - 1 + meses
    ano = data_base.year + indice // 12
    mes = indice % 12 + 1
    return date(ano, mes, min(data_base.day, calendar.monthrange(ano, mes)[1]))


def proximo_vencimento(data_atual: date, periodicidade: str) -> date:
    periodicidade = str(periodicidade or "Mensal").strip().lower()
    if periodicidade.startswith("di"):
        return data_atual + timedelta(days=1)
    if periodicidade.startswith("sem"):
        return data_atual + timedelta(days=7)
    if periodicidade.startswith("an"):
        return adicionar_meses(data_atual, 12)
    return adicionar_meses(data_atual, 1)


def vencimentos_no_periodo(cobranca: dict, limite: date) -> list[date]:
    inicio = parse_data_flex(cobranca.get("data_cobranca")) or parse_data_flex(cobranca.get("vigencia_inicio"))
    fim = parse_data_flex(cobranca.get("vigencia_fim")) or limite
    if not inicio or inicio > fim:
        return []
    fim = min(fim, limite)
    datas = []
    atual = inicio
    while atual <= fim:
        datas.append(atual)
        seguinte = proximo_vencimento(atual, cobranca.get("periodicidade"))
        if seguinte <= atual:
            break
        atual = seguinte
    return datas


def sincronizar_lancamentos_recorrentes(conn, hoje: date, usuario: str = "", horizonte_dias: int = 35) -> int:
    """Garante títulos até o horizonte sem duplicar cobrança e vencimento."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM cobrancas_recorrentes WHERE status='Ativa' ORDER BY id")
    cobrancas = [dict(item) for item in cursor.fetchall()]
    criados = 0
    limite = hoje + timedelta(days=max(0, horizonte_dias))
    for cobranca in cobrancas:
        valor = float(cobranca.get("valor_cobranca") or cobranca.get("valor_financeiro") or 0)
        if valor <= 0:
            continue
        cursor.execute("SELECT cnpj FROM clientes WHERE id=? LIMIT 1", (cobranca.get("cliente_id"),))
        cliente = cursor.fetchone() or {}
        for vencimento in vencimentos_no_periodo(cobranca, limite):
            competencia = vencimento.strftime("%Y-%m-%d")
            cursor.execute(
                "SELECT id FROM contas_receber WHERE cobranca_recorrente_id=? AND cobranca_competencia=? LIMIT 1",
                (cobranca.get("id"), competencia),
            )
            if cursor.fetchone():
                continue
            numero = f"COB-REC-{int(cobranca.get('id') or 0):05d}-{vencimento.strftime('%Y%m%d')}"
            descricao = f"Cobrança recorrente: {cobranca.get('tipo_cobranca') or 'Serviço recorrente'}"
            cursor.execute(
                """INSERT INTO contas_receber
                   (cliente_id, cliente, cpf_cnpj, numero_documento, tipo_receita, categoria,
                    data_emissao, data_competencia, data_vencimento, valor_original, valor_total,
                    valor_liquido, forma_recebimento, status, observacoes, criado_por, criado_em,
                    cobranca_recorrente_id, cobranca_competencia)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (cobranca.get("cliente_id"), cobranca.get("cliente_nome") or "", cliente.get("cnpj") or "",
                 numero, cobranca.get("tipo_cobranca") or "Receita recorrente", "Cobrança recorrente",
                 hoje.strftime("%Y-%m-%d"), competencia, competencia, valor, valor, valor,
                 cobranca.get("pagamento") or "", "Aberto", descricao, usuario,
                 hoje.strftime("%d/%m/%Y"), cobranca.get("id"), competencia),
            )
            criados += 1
    conn.commit()
    return criados

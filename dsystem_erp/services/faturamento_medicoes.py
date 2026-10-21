"""Medições parciais ligadas ao lançamento principal e ao seu saldo."""
import json
from decimal import Decimal


def resumo_medicoes(principal, medicoes):
    total = Decimal(str(principal.get("valor_total") or 0))
    ativo = [m for m in medicoes if m.get("status") != "Cancelado"]
    medido = sum((Decimal(str(m.get("valor_total") or 0)) for m in ativo), Decimal(0))
    faturado = sum((Decimal(str(m.get("valor_total") or 0)) for m in ativo if m.get("status") == "Faturado"), Decimal(0))
    return {"total": float(total), "medido": float(medido), "faturado": float(faturado),
            "saldo": float(total - medido), "percentual": float(medido * 100 / total) if total else 0,
            "percentual_faturado": float(faturado * 100 / total) if total else 0,
            "concluido": total > 0 and faturado == total}


def registrar_medicao(conn, principal_id, numero, valor, inicio, fim, historico, vencimento):
    valor = Decimal(str(valor)).quantize(Decimal("0.01"))
    if not numero.strip() or valor <= 0 or not historico.strip() or inicio > fim:
        raise ValueError("Informe número, valor positivo, histórico e período válido.")
    c = conn.cursor()
    try:
        c.execute("SELECT * FROM faturamento WHERE id=? FOR UPDATE", (principal_id,))
        principal = c.fetchone()
        if not principal or principal.get("modalidade_faturamento") != "Por medição" or principal.get("status") in ("Faturado", "Cancelado") or principal.get("medicao_principal_id"):
            raise ValueError("Selecione um lançamento principal por medição ainda aberto.")
        c.execute("SELECT valor_total, medicao_numero FROM faturamento WHERE medicao_principal_id=? AND COALESCE(status,'Aberto') <> 'Cancelado'", (principal_id,))
        anteriores = list(c.fetchall())
        if any(str(r["medicao_numero"]).strip() == numero.strip() for r in anteriores):
            raise ValueError("Já existe uma medição com este número.")
        total = Decimal(str(principal["valor_total"] or 0))
        usado = sum((Decimal(str(r["valor_total"] or 0)) for r in anteriores), Decimal(0))
        if valor > total - usado:
            raise ValueError("O valor da medição supera o saldo disponível.")
        itens = json.dumps([{"tipo_item": "Serviço", "desc": historico.strip(), "qtd": 1,
                            "vunit": float(valor), "vtotal": float(valor)}], ensure_ascii=False)
        c.execute("""INSERT INTO faturamento
            (data_lanc, cliente, cnpj, tipo, emite_nf, tipo_nota, forma_pag, itens, valor_total,
             parcelas, vencimento, orc_ref, obs_nota, modalidade_faturamento, medicao_numero,
             medicao_inicio, medicao_fim, medicao_percentual, medicao_referencia,
             medicao_historico, medicao_principal_id)
             VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (fim, principal["cliente"], principal.get("cnpj"), principal.get("tipo"), principal.get("emite_nf"),
             "Serviço", principal.get("forma_pag"), itens, valor, "Não", vencimento,
             principal.get("orc_ref"), historico, "Por medição", numero.strip(), inicio, fim,
             valor * 100 / total, f"Faturamento principal #{principal_id}", historico, principal_id))
        novo_id = c.lastrowid
        if any(principal.get(campo) for campo in ('categoria', 'centro', 'plano_contas', 'conta_bancaria')):
            c.execute('UPDATE faturamento SET categoria=?, centro=?, plano_contas=?, conta_bancaria=? WHERE id=?',
                      tuple(principal.get(campo) or '' for campo in ('categoria', 'centro', 'plano_contas', 'conta_bancaria')) + (novo_id,))
        c.execute("UPDATE faturamento SET documentos_entrega=? WHERE id=?", (principal.get("documentos_entrega") or "Nota e espelho", novo_id))
        c.execute("UPDATE faturamento SET emitir_automaticamente=? WHERE id=?", (int(bool(principal.get('emitir_automaticamente'))), novo_id))
        conn.commit()
        return novo_id
    except Exception:
        conn.rollback()
        raise

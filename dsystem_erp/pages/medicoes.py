"""Visão exclusiva de contratos por medição, parcelas e documentos vinculados."""
import base64
from dsystem_erp.services.faturamento_medicoes import resumo_medicoes
from dsystem_erp.services.faturamento_espelho import gerar_pdf_espelho_faturamento


def renderizar_medicoes(ctx):
    st = ctx["st"]
    moeda = ctx["formatar_moeda_br"]
    st.subheader("Faturamento por medição")
    registros = ctx["repo_listar_faturamentos"](ctx["conectar_banco"])
    registros = ctx["filtrar_registros_por_empresa"](registros, "cliente")
    contratos = [dict(r) for r in registros if r.get("modalidade_faturamento") == "Por medição" and not r.get("medicao_principal_id")]
    if not contratos:
        st.info("Cadastre um lançamento com modalidade Por medição e o valor total contratado para acompanhá-lo aqui.")
        return
    busca = st.text_input("Buscar contrato ou cliente:", key="medicoes_busca").strip().casefold()
    contratos = [c for c in contratos if not busca or busca in f"{c['id']} {c.get('cliente')} {c.get('medicao_referencia')}".casefold()]
    if not contratos:
        st.info("Nenhum contrato encontrado.")
        return
    por_id = {int(c["id"]): c for c in contratos}
    contrato_id = st.selectbox("Contrato por medição:", list(por_id),
        format_func=lambda k: f"#{k} - {por_id[k].get('cliente')} - {moeda(por_id[k].get('valor_total'))}", key="medicoes_contrato")
    principal = por_id[contrato_id]
    medicoes = sorted([dict(m) for m in registros if m.get("medicao_principal_id") and int(m["medicao_principal_id"]) == contrato_id], key=lambda m: int(m["id"]))
    resumo = resumo_medicoes(principal, medicoes)
    a, b, c, d = st.columns(4)
    a.metric("Total contratado", moeda(resumo["total"]))
    b.metric("Total medido", moeda(resumo["medido"]), f"{resumo['percentual']:.2f}% do total")
    c.metric("Já faturado", moeda(resumo["faturado"]), f"{resumo['percentual_faturado']:.2f}% do total")
    d.metric("Saldo a medir", moeda(resumo["saldo"]))
    st.progress(min(1.0, max(0.0, resumo["percentual"] / 100)), text=f"{resumo['percentual']:.2f}% do contrato medido")
    if resumo["concluido"]:
        st.success("Total contratado faturado. Confira abaixo as notas de cada medição e o espelho consolidado.")
    elif resumo["saldo"] == 0:
        st.info("100% medido. Ainda existem parcelas aguardando faturamento.")
    if ctx["tem_permissao"]("faturamento.edit") and st.button("Abrir contrato / lançar nova medição", key="medicoes_abrir_principal"):
        st.session_state["fat_em_edicao_id"] = contrato_id
        st.session_state["fat_aba_destino"] = "Histórico / Editar"
        st.rerun()
    conn = ctx["conectar_banco"]()
    try:
        cursor = conn.cursor()
        cursor.execute("""SELECT n.id, n.faturamento_id, n.numero_nota, n.status, n.pdf_base64
            FROM notas_fiscais n JOIN faturamento f ON f.id=n.faturamento_id
            WHERE f.medicao_principal_id=? ORDER BY n.id""", (contrato_id,))
        notas = [dict(n) for n in cursor.fetchall()]
    finally:
        conn.close()
    linhas, itens_consolidado = [], []
    acumulado = 0.0
    for m in medicoes:
        cancelado = m.get("status") == "Cancelado"
        valor = float(m.get("valor_total") or 0)
        if not cancelado:
            acumulado += valor
        notas_m = [n for n in notas if int(n["faturamento_id"]) == int(m["id"])]
        refs = "; ".join(f"{n.get('numero_nota') or '#' + str(n['id'])} ({n.get('status') or 'Pendente'})" for n in notas_m) or "Sem nota vinculada"
        percentual = valor * 100 / resumo["total"] if resumo["total"] else 0
        linhas.append({"Lançamento": m["id"], "Medição": m.get("medicao_numero"), "Valor": moeda(valor),
            "% do total": round(percentual, 2), "Acumulado": moeda(acumulado),
            "% acumulado": round(acumulado * 100 / resumo["total"], 2) if resumo["total"] else 0,
            "Status": m.get("status") or "Aberto", "Notas": refs})
        if not cancelado:
            itens_consolidado.append({"tipo_item": "Serviço", "qtd": 1, "vunit": valor, "vtotal": valor,
                "desc": f"Medição {m.get('medicao_numero')} - {percentual:.2f}% - {m.get('medicao_historico') or ''}. Notas: {refs}"})
    st.dataframe(linhas, hide_index=True, width="stretch")
    if medicoes:
        por_medicao = {int(m["id"]): m for m in medicoes}
        escolhido = st.selectbox("Abrir medição individual:", list(por_medicao), format_func=lambda k: f"#{k} - Medição {por_medicao[k].get('medicao_numero')}", key="medicoes_individual")
        if ctx["tem_permissao"]("faturamento.edit") and st.button("Abrir lançamento da medição", key="medicoes_abrir_filha"):
            st.session_state["fat_em_edicao_id"] = escolhido
            st.session_state["fat_aba_destino"] = "Histórico / Editar"
            st.rerun()
    st.markdown("#### Notas de todas as medições")
    st.caption("O status de faturamento é financeiro. A situação de emissão de cada nota aparece abaixo.")
    for nota in notas:
        st.write(f"Lançamento #{nota['faturamento_id']} - Nota {nota.get('numero_nota') or nota['id']} - {nota.get('status') or 'Pendente'}")
        if nota.get("pdf_base64"):
            try:
                pdf = base64.b64decode(nota["pdf_base64"])
                if not pdf.startswith(b"%PDF"):
                    raise ValueError("PDF inválido")
            except (ValueError, TypeError):
                st.caption("PDF indisponível; consulte os documentos do lançamento.")
            else:
                st.download_button("Baixar PDF da nota", pdf, file_name=f"nota_{nota['id']}.pdf", mime="application/pdf", key=f"medicoes_nota_{nota['id']}")
    consolidado = dict(principal)
    consolidado.update(itens=itens_consolidado, valor_total=resumo["medido"],
        obs_nota=f"CONSOLIDADO DO CONTRATO #{contrato_id}\nTotal contratado: {moeda(resumo['total'])}\nTotal medido: {moeda(resumo['medido'])} ({resumo['percentual']:.2f}%)\nSaldo a medir: {moeda(resumo['saldo'])}",
        obs_interna="", medicao_historico="")
    cliente = next((c for c in ctx["buscar_clientes"]() if c.get("nome") == principal.get("cliente")), None)
    st.download_button("Baixar espelho consolidado de todas as medições", gerar_pdf_espelho_faturamento(consolidado, cliente),
        file_name=f"consolidado_medicoes_{contrato_id}.pdf", mime="application/pdf", key="medicoes_consolidado")
    st.caption("O consolidado reúne os valores e referências das notas; não emite uma nova nota fiscal pelo total.")

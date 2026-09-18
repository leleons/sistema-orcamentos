from __future__ import annotations

import json
from datetime import date

from dsystem_erp.app_context import aplicar_contexto_pagina
from dsystem_erp.services.compras import MEIOS_COMPRA, id_melhor_cotacao, total_cotacao
from dsystem_erp.services.faturamento import itens_faturamento_lista
from dsystem_erp.services.garantias import (
    gerar_pdf_garantia,
    proximo_numero_garantia,
    validade_item_garantia,
)
from dsystem_erp.ui_consulta import tabela_clicavel_id


def _renderizar_cotacoes_compras(ctx: dict) -> None:
    aplicar_contexto_pagina(ctx, globals())
    if not tem_permissao("compras.view"):
        st.error("Você não tem permissão para acessar o módulo de compras.")
        st.stop()

    st.subheader("Compras e Cotações")
    st.caption("Compare até cinco fornecedores para cada item solicitado pelo estoque.")

    conn = conectar_banco()
    c = conn.cursor()
    c.execute("SELECT * FROM pedidos_compra ORDER BY id DESC")
    pedidos = c.fetchall()
    conn.close()
    if not pedidos:
        st.info("A lista de compras está vazia. Crie uma solicitação em Estoque → Solicitar Compra.")
        return

    filtro = st.selectbox("Situação:", ["Pendentes", "Todos", "Compra escolhida", "Comprado"], key="compras_filtro")
    if filtro == "Pendentes":
        pedidos = [p for p in pedidos if (p.get("status") or "Solicitado") not in {"Compra escolhida", "Comprado"}]
    elif filtro != "Todos":
        pedidos = [p for p in pedidos if (p.get("status") or "Solicitado") == filtro]
    if not pedidos:
        st.info("Nenhum item encontrado nessa situação.")
        return

    linhas_pedidos = [{
        "ID": p.get("id"), "Produto": p.get("produto") or p.get("codigo"),
        "Quantidade": p.get("quantidade_solicitada") or 0,
        "Fornecedor": p.get("fornecedor"), "Status": p.get("status") or "Solicitado",
    } for p in pedidos]
    pedido_clicado_id = tabela_clicavel_id(st, linhas_pedidos, "compras_pedidos_grade", campo_id="ID")
    if pedido_clicado_id:
        st.session_state["compras_pedido_id_ativo"] = int(pedido_clicado_id)
    pedido_id_ativo = int(st.session_state.get("compras_pedido_id_ativo") or 0)
    pedido = next((p for p in pedidos if int(p.get("id") or 0) == pedido_id_ativo), None)
    if not pedido:
        st.caption("Clique em qualquer item da lista para abrir suas cotações e ações.")
        return
    quantidade = int(pedido.get("quantidade_solicitada") or 0)
    st.write(f"**Produto:** {pedido.get('produto') or '—'}  |  **Quantidade:** {quantidade}  |  **Status:** {pedido.get('status') or 'Solicitado'}")
    if pedido.get("observacoes"):
        st.caption(f"Observações: {pedido.get('observacoes')}")

    conn = conectar_banco()
    c = conn.cursor()
    c.execute("SELECT * FROM cotacoes_compra WHERE pedido_compra_id=? ORDER BY id", (pedido["id"],))
    cotacoes = c.fetchall()
    conn.close()
    melhor_id = id_melhor_cotacao(cotacoes)

    st.subheader(f"Cotações ({len(cotacoes)}/5)")
    if cotacoes:
        tabela = []
        for cotacao in cotacoes:
            tabela.append({
                "ID": cotacao.get("id"),
                "Melhor opção": "✓" if cotacao.get("id") == melhor_id else "",
                "Fornecedor": cotacao.get("fornecedor"),
                "Telefone": cotacao.get("telefone"),
                "Meio de compra": cotacao.get("meio_compra"),
                "Valor unitário": formatar_moeda_br(cotacao.get("valor_item") or 0),
                "Total": formatar_moeda_br(total_cotacao(cotacao.get("valor_item"), quantidade)),
            })
        cotacao_clicada_id = tabela_clicavel_id(
            st, tabela, f"compras_cotacoes_grade_{pedido['id']}", campo_id="ID"
        )
        if cotacao_clicada_id:
            st.session_state["compras_cotacao_id_ativo"] = int(cotacao_clicada_id)
        if melhor_id:
            melhor = next(cot for cot in cotacoes if cot.get("id") == melhor_id)
            st.success(f"Melhor preço: {melhor.get('fornecedor')} — {formatar_moeda_br(melhor.get('valor_item'))} por unidade — total {formatar_moeda_br(total_cotacao(melhor.get('valor_item'), quantidade))}.")
    else:
        st.info("Nenhuma cotação cadastrada para este item.")

    cotacao_editar_id = int(st.session_state.get("compras_cotacao_id_ativo") or 0)
    cotacao_editar = next((cot for cot in cotacoes if int(cot.get("id") or 0) == cotacao_editar_id), None)
    if tem_permissao("compras.edit") and cotacao_editar:
        with st.expander(f"Editar cotação #{cotacao_editar_id}", expanded=True):
            ec1, ec2 = st.columns(2)
            cot_fornecedor = ec1.text_input("Fornecedor:", value=cotacao_editar.get("fornecedor") or "", key=f"cot_edit_fornecedor_{cotacao_editar_id}")
            cot_telefone = ec2.text_input("Telefone:", value=cotacao_editar.get("telefone") or "", key=f"cot_edit_telefone_{cotacao_editar_id}")
            ec3, ec4 = st.columns(2)
            meio_atual = cotacao_editar.get("meio_compra") if cotacao_editar.get("meio_compra") in MEIOS_COMPRA else MEIOS_COMPRA[0]
            cot_meio = ec3.selectbox("Meio de compra:", MEIOS_COMPRA, index=MEIOS_COMPRA.index(meio_atual), key=f"cot_edit_meio_{cotacao_editar_id}")
            cot_valor = ec4.number_input("Valor do item (R$):", min_value=0.01, value=float(cotacao_editar.get("valor_item") or 0.01), step=0.01, key=f"cot_edit_valor_{cotacao_editar_id}")
            cot_obs = st.text_area("Observações:", value=cotacao_editar.get("observacoes") or "", key=f"cot_edit_obs_{cotacao_editar_id}")
            if st.button("Salvar alterações da cotação", type="primary", width="stretch", key=f"cot_edit_salvar_{cotacao_editar_id}"):
                conn_edit_cot = conectar_banco()
                cedit_cot = conn_edit_cot.cursor()
                cedit_cot.execute(
                    "UPDATE cotacoes_compra SET fornecedor=?, telefone=?, meio_compra=?, valor_item=?, observacoes=? WHERE id=?",
                    (cot_fornecedor, cot_telefone, cot_meio, cot_valor, cot_obs, cotacao_editar_id),
                )
                conn_edit_cot.commit()
                conn_edit_cot.close()
                st.success("Cotação atualizada.")
                st.rerun()

    if tem_permissao("compras.edit") and len(cotacoes) < 5:
        with st.form(f"nova_cotacao_{pedido['id']}", clear_on_submit=True):
            fc1, fc2 = st.columns(2)
            fornecedor = fc1.text_input("Fornecedor:")
            telefone = fc2.text_input("Telefone de contato:")
            fc3, fc4 = st.columns(2)
            meio = fc3.selectbox("Meio de compra:", MEIOS_COMPRA)
            valor = fc4.number_input("Valor do item nesse fornecedor (R$):", min_value=0.01, step=0.01, format="%.2f")
            observacoes = st.text_area("Observações da cotação (opcional):")
            salvar = st.form_submit_button("Adicionar cotação", type="primary", width="stretch")
        if salvar:
            if not fornecedor.strip():
                st.error("Informe o fornecedor.")
            else:
                conn = conectar_banco()
                c = conn.cursor()
                c.execute("SELECT COUNT(*) AS total FROM cotacoes_compra WHERE pedido_compra_id=?", (pedido["id"],))
                total = c.fetchone()
                total = int(total.get("total") if isinstance(total, dict) else total[0])
                if total >= 5:
                    conn.close()
                    st.error("Este item já possui o limite de cinco cotações.")
                else:
                    c.execute("""INSERT INTO cotacoes_compra
                              (pedido_compra_id, fornecedor, telefone, meio_compra, valor_item, observacoes, criado_por, criado_em)
                              VALUES (?,?,?,?,?,?,?,?)""",
                              (pedido["id"], fornecedor.strip(), telefone.strip(), meio, valor, observacoes,
                               st.session_state.get("username", ""), agora_br()))
                    c.execute("UPDATE pedidos_compra SET status=? WHERE id=?", ("Em cotação", pedido["id"]))
                    conn.commit()
                    conn.close()
                    st.success("Cotação adicionada.")
                    st.rerun()

    if tem_permissao("compras.edit") and melhor_id:
        bc1, bc2 = st.columns(2)
        if bc1.button("Escolher automaticamente o menor preço", type="primary", width="stretch"):
            melhor = next(cot for cot in cotacoes if cot.get("id") == melhor_id)
            conn = conectar_banco()
            c = conn.cursor()
            c.execute("UPDATE cotacoes_compra SET escolhida=0 WHERE pedido_compra_id=?", (pedido["id"],))
            c.execute("UPDATE cotacoes_compra SET escolhida=1 WHERE id=?", (melhor_id,))
            c.execute("UPDATE pedidos_compra SET fornecedor=?, status=? WHERE id=?", (melhor.get("fornecedor"), "Compra escolhida", pedido["id"]))
            conn.commit()
            conn.close()
            st.success("Melhor opção vinculada ao pedido de compra.")
            st.rerun()
        if bc2.button("Marcar item como comprado", width="stretch"):
            conn = conectar_banco()
            c = conn.cursor()
            c.execute("UPDATE pedidos_compra SET status=? WHERE id=?", ("Comprado", pedido["id"]))
            conn.commit()
            conn.close()
            st.success("Item marcado como comprado.")
            st.rerun()

    if tem_permissao("compras.delete") and cotacoes:
        with st.expander("Excluir uma cotação"):
            apagar = {f"#{q['id']} — {q.get('fornecedor')} — {formatar_moeda_br(q.get('valor_item'))}": q["id"] for q in cotacoes}
            apagar_label = st.selectbox("Cotação:", list(apagar), key=f"cotacao_apagar_{pedido['id']}")
            if st.button("Excluir cotação selecionada", key=f"btn_cotacao_apagar_{pedido['id']}"):
                conn = conectar_banco()
                c = conn.cursor()
                c.execute("DELETE FROM cotacoes_compra WHERE id=?", (apagar[apagar_label],))
                conn.commit()
                conn.close()
                st.success("Cotação excluída.")
                st.rerun()


def _renderizar_garantias(ctx: dict) -> None:
    aplicar_contexto_pagina(ctx, globals())
    pode_emitir_garantia = tem_permissao("compras.edit")
    st.subheader("Garantias de produtos e serviços")
    st.caption(
        "Emita um certificado para peças, produtos e serviços prestados ao cliente. "
        "O documento ficará salvo para consulta e nova impressão."
    )
    clientes = buscar_clientes()
    clientes_por_id = {int(item["id"]): item for item in clientes}
    aba_emitir, aba_historico = st.tabs(["Emitir garantia", "Garantias emitidas"])

    with aba_emitir:
        if not pode_emitir_garantia:
            st.info("Seu usuário pode consultar garantias, mas não possui permissão para emitir novos documentos.")
        cliente_id = st.selectbox(
            "Cliente:", [0] + list(clientes_por_id),
            format_func=lambda valor: (
                "-- Selecionar cliente --" if valor == 0
                else clientes_por_id[valor].get("nome") or f"Cliente #{valor}"
            ),
            key="garantia_cliente_id",
        )
        cliente = clientes_por_id.get(int(cliente_id or 0), {})
        conn_fat = conectar_banco()
        cfat = conn_fat.cursor()
        if cliente:
            cfat.execute(
                """SELECT * FROM faturamento
                   WHERE cliente=? AND status='Faturado' ORDER BY id DESC LIMIT 200""",
                (cliente.get("nome") or "",),
            )
            faturamentos = [dict(item) for item in cfat.fetchall()]
        else:
            faturamentos = []
        conn_fat.close()
        faturamentos_por_id = {int(item["id"]): item for item in faturamentos}
        faturamento_id = st.selectbox(
            "Faturamento de origem (opcional):", [0] + list(faturamentos_por_id),
            format_func=lambda valor: (
                "-- Garantia sem faturamento vinculado --" if valor == 0 else
                f"#{valor} - {data_para_br(faturamentos_por_id[valor].get('data_lanc'))} - "
                f"{formatar_moeda_br(faturamentos_por_id[valor].get('valor_total'))}"
            ),
            key=f"garantia_faturamento_{cliente_id}",
        )
        faturamento = faturamentos_por_id.get(int(faturamento_id or 0), {})
        gar1, gar2 = st.columns(2)
        data_emissao = gar1.date_input("Data de emissão:", value=date.today(), key="garantia_data_emissao")
        origem = gar2.text_input(
            "Origem/atendimento:",
            value=f"Faturamento #{faturamento_id}" if faturamento_id else "Compras / atendimento",
            key=f"garantia_origem_{faturamento_id}",
        )

        itens_garantia = []
        itens_faturamento = itens_faturamento_lista(faturamento.get("itens")) if faturamento else []
        if itens_faturamento:
            st.markdown("#### Produtos e serviços do faturamento")
            for indice, item in enumerate(itens_faturamento, 1):
                gi1, gi2, gi3 = st.columns([4, 1.2, 1.3])
                descricao = item.get("desc") or f"Item {indice}"
                tipo_item = item.get("tipo_item") or "Serviço"
                gi1.text_input(
                    f"Item {indice}:", value=descricao, disabled=True,
                    key=f"garantia_item_desc_{faturamento_id}_{indice}",
                )
                gi2.text_input(
                    "Tipo:", value=tipo_item, disabled=True,
                    key=f"garantia_item_tipo_{faturamento_id}_{indice}",
                )
                prazo = gi3.number_input(
                    "Garantia (meses):", min_value=0, max_value=120,
                    value=3 if tipo_item == "Serviço" else 12, step=1,
                    key=f"garantia_item_prazo_{faturamento_id}_{indice}",
                )
                if int(prazo) > 0:
                    itens_garantia.append({
                        "tipo": tipo_item, "descricao": descricao,
                        "prazo_meses": int(prazo),
                        "validade": validade_item_garantia(data_emissao, int(prazo)).isoformat(),
                    })
        else:
            quantidade_itens = st.number_input(
                "Quantidade de produtos/serviços cobertos:", min_value=1, max_value=50,
                value=1, step=1, key="garantia_qtd_itens",
            )
            for indice in range(1, int(quantidade_itens) + 1):
                gi1, gi2, gi3 = st.columns([4, 1.2, 1.3])
                descricao = gi1.text_input(
                    f"Produto ou serviço {indice}:", key=f"garantia_manual_desc_{indice}"
                )
                tipo_item = gi2.selectbox(
                    "Tipo:", ["Peça/Produto", "Serviço"], key=f"garantia_manual_tipo_{indice}"
                )
                prazo = gi3.number_input(
                    "Garantia (meses):", min_value=0, max_value=120,
                    value=12 if tipo_item == "Peça/Produto" else 3, step=1,
                    key=f"garantia_manual_prazo_{indice}",
                )
                if descricao.strip() and int(prazo) > 0:
                    itens_garantia.append({
                        "tipo": tipo_item, "descricao": descricao.strip(),
                        "prazo_meses": int(prazo),
                        "validade": validade_item_garantia(data_emissao, int(prazo)).isoformat(),
                    })
        condicoes = st.text_area(
            "Condições da garantia:",
            value=(
                "A garantia cobre defeitos relacionados às peças e aos serviços descritos. "
                "Não cobre mau uso, danos elétricos externos, oxidação, quedas, violação do equipamento "
                "ou intervenção de terceiros não autorizados."
            ),
            height=110, key="garantia_condicoes",
        )
        historico = st.text_area(
            "Histórico e informações adicionais:", height=100, key="garantia_historico"
        )
        if st.button(
            "Emitir e salvar garantia", type="primary", width="stretch",
            disabled=not pode_emitir_garantia or not cliente_id or not itens_garantia,
            key="garantia_emitir",
        ):
            conn_gar = conectar_banco()
            cgar = conn_gar.cursor()
            try:
                cgar.execute("SELECT COALESCE(MAX(id), 0) AS ultimo FROM garantias_clientes")
                ultimo = cgar.fetchone() or {}
                numero = proximo_numero_garantia(int(ultimo.get("ultimo") or 0), data_emissao.year)
                dados_garantia = {
                    "numero": numero, "cliente": cliente.get("nome") or "",
                    "cliente_documento": cliente.get("cnpj") or "", "data_emissao": data_emissao,
                    "origem": origem, "condicoes": condicoes, "historico": historico,
                    "criado_por": st.session_state.get("username", ""),
                }
                pdf = gerar_pdf_garantia(dados_garantia, itens_garantia)
                nome_pdf = f"garantia_{numero}.pdf"
                cgar.execute(
                    """INSERT INTO garantias_clientes
                       (numero, cliente_id, cliente, cliente_documento, faturamento_id,
                        data_emissao, origem, itens, condicoes, historico, status,
                        pdf_nome, pdf_mime, pdf, criado_por, criado_em)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (numero, cliente_id, cliente.get("nome") or "", cliente.get("cnpj") or "",
                     faturamento_id or None, data_para_banco_br(data_emissao), origem,
                     json.dumps(itens_garantia, ensure_ascii=False), condicoes, historico,
                     "Emitida", nome_pdf, "application/pdf", pdf,
                     st.session_state.get("username", ""), agora_br()),
                )
                garantia_id = int(cgar.lastrowid)
                conn_gar.commit()
            except Exception as erro_garantia:
                conn_gar.rollback()
                st.error(f"Não foi possível emitir a garantia: {erro_garantia}")
            else:
                registrar_evento_sistema(
                    "emitir", "garantias_clientes", garantia_id, cliente.get("nome") or "",
                    {"numero": numero, "faturamento_id": faturamento_id or None,
                     "itens": len(itens_garantia)},
                )
                st.session_state["garantia_pdf_emitido"] = {
                    "numero": numero, "nome": nome_pdf, "dados": pdf,
                }
                st.success(f"Garantia {numero} emitida e salva.")
            finally:
                conn_gar.close()
        garantia_pdf_emitido = st.session_state.get("garantia_pdf_emitido")
        if garantia_pdf_emitido:
            st.download_button(
                f"Baixar garantia {garantia_pdf_emitido['numero']}",
                data=garantia_pdf_emitido["dados"], file_name=garantia_pdf_emitido["nome"],
                mime="application/pdf", type="primary", width="stretch",
                key="garantia_baixar_emitida",
            )

    with aba_historico:
        conn_hist = conectar_banco()
        chist = conn_hist.cursor()
        chist.execute("SELECT * FROM garantias_clientes ORDER BY id DESC LIMIT 500")
        garantias = [dict(item) for item in chist.fetchall()]
        conn_hist.close()
        busca = st.text_input(
            "Pesquisar número ou cliente:", key="garantia_busca"
        ).strip().casefold()
        if busca:
            garantias = [
                item for item in garantias
                if busca in f"{item.get('numero', '')} {item.get('cliente', '')}".casefold()
            ]
        linhas = [{
            "ID": item.get("id"), "Número": item.get("numero"),
            "Cliente": item.get("cliente"), "Emissão": data_para_br(item.get("data_emissao")),
            "Origem": item.get("origem"), "Status": item.get("status"),
        } for item in garantias]
        garantia_clicada = tabela_clicavel_id(
            st, linhas, "garantias_grade", campo_id="ID"
        ) if linhas else None
        if garantia_clicada:
            st.session_state["garantia_historico_id"] = int(garantia_clicada)
        garantia_aberta = next(
            (item for item in garantias if int(item.get("id") or 0) == int(st.session_state.get("garantia_historico_id") or 0)),
            None,
        )
        if garantia_aberta:
            st.download_button(
                f"Baixar {garantia_aberta.get('numero')}", data=garantia_aberta.get("pdf") or b"",
                file_name=garantia_aberta.get("pdf_nome") or "garantia.pdf",
                mime=garantia_aberta.get("pdf_mime") or "application/pdf",
                width="stretch", key=f"garantia_hist_baixar_{garantia_aberta.get('id')}",
            )
        elif not linhas:
            st.info("Nenhuma garantia emitida ainda.")


def renderizar_compras(ctx: dict) -> None:
    aplicar_contexto_pagina(ctx, globals())
    if not tem_permissao("compras.view"):
        st.error("Você não tem permissão para acessar o módulo de compras.")
        st.stop()
    st.title("Compras")
    aba_compras, aba_garantias = st.tabs(["Compras e Cotações", "Garantias"])
    with aba_compras:
        _renderizar_cotacoes_compras(ctx)
    with aba_garantias:
        _renderizar_garantias(ctx)

from __future__ import annotations

from dsystem_erp.app_context import aplicar_contexto_pagina
from dsystem_erp.services.compras import MEIOS_COMPRA, id_melhor_cotacao, total_cotacao


def renderizar_compras(ctx: dict) -> None:
    aplicar_contexto_pagina(ctx, globals())
    if not tem_permissao("compras.view"):
        st.error("Você não tem permissão para acessar o módulo de compras.")
        st.stop()

    st.title("Compras e Cotações")
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

    opcoes = {
        f"#{p['id']} — {p.get('produto') or p.get('codigo')} — {p.get('quantidade_solicitada') or 0} unidade(s)": p
        for p in pedidos
    }
    pedido_label = st.selectbox("Item da lista de compras:", list(opcoes), key="compras_pedido")
    pedido = opcoes[pedido_label]
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
                "Melhor opção": "✓" if cotacao.get("id") == melhor_id else "",
                "Fornecedor": cotacao.get("fornecedor"),
                "Telefone": cotacao.get("telefone"),
                "Meio de compra": cotacao.get("meio_compra"),
                "Valor unitário": formatar_moeda_br(cotacao.get("valor_item") or 0),
                "Total": formatar_moeda_br(total_cotacao(cotacao.get("valor_item"), quantidade)),
            })
        st.dataframe(tabela, width="stretch", hide_index=True)
        if melhor_id:
            melhor = next(cot for cot in cotacoes if cot.get("id") == melhor_id)
            st.success(f"Melhor preço: {melhor.get('fornecedor')} — {formatar_moeda_br(melhor.get('valor_item'))} por unidade — total {formatar_moeda_br(total_cotacao(melhor.get('valor_item'), quantidade))}.")
    else:
        st.info("Nenhuma cotação cadastrada para este item.")

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

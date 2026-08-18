from __future__ import annotations

from dsystem_erp.app_context import aplicar_contexto_pagina
from dsystem_erp.services.estoque_fiscal import (
    COMPRADO_COM_NOTA,
    SITUACOES_DOCUMENTO_COMPRA,
    normalizar_situacao_compra,
)
from dsystem_erp.services.precificacao_estoque import calcular_preco_revenda, decimal_valor
from dsystem_erp.ui_consulta import tabela_selecionavel_id


def renderizar_estoque(ctx: dict) -> None:
    aplicar_contexto_pagina(ctx, globals())
    st.title("Controle de Estoque e Inventário")
    aba_est1, aba_est2, aba_est3, aba_est4, aba_est5, aba_est6 = st.tabs(["Visão Geral e Movimentação", "Cadastrar Novo Produto", "Editar / Excluir", "Solicitar Compra", "Relatório de Compra", "Importar Excel"])

    estoque_data = repo_listar_estoque(conectar_banco)

    with aba_est1:
        st.subheader("Visão Geral do Estoque")
        if estoque_data:
            col_pesquisa, col_estado = st.columns([2, 1])
            pesquisa_estoque = col_pesquisa.text_input(
                "Pesquisar produto:",
                placeholder="Nome, código, nome genérico, categoria, caixa ou fornecedor",
                key="estoque_pesquisa",
            ).strip().casefold()
            estado_estoque = col_estado.selectbox(
                "Estado do produto:",
                ["Todos", "Novo", "Usado"],
                key="estoque_filtro_estado",
            )

            estoque_filtrado = []
            for produto in estoque_data:
                texto_pesquisavel = " ".join(
                    str(produto.get(campo) or "")
                    for campo in (
                        "codigo", "codigo_entrada", "produto", "nome_generico",
                        "categoria", "caixa", "fornecedor", "observacoes",
                    )
                ).casefold()
                corresponde_pesquisa = not pesquisa_estoque or pesquisa_estoque in texto_pesquisavel
                codigo_estado = str(produto.get("codigo") or "").casefold()
                corresponde_estado = estado_estoque == "Todos" or estado_estoque.casefold() in codigo_estado
                if corresponde_pesquisa and corresponde_estado:
                    estoque_filtrado.append(produto)

            st.caption(f"{len(estoque_filtrado)} de {len(estoque_data)} produto(s) encontrado(s).")
            df_estoque = pd.DataFrame(preparar_tabela_estoque(estoque_filtrado))
            id_estoque_selecionado = tabela_selecionavel_id(st, df_estoque.to_dict("records"), "estoque_grade_consulta", "ID")
            if id_estoque_selecionado:
                st.session_state["estoque_produto_selecionado"] = int(id_estoque_selecionado)
            st.caption("Clique no produto para abrir automaticamente a consulta/edição na aba Editar / Excluir.")
            st.download_button("Baixar estoque em Excel", data=gerar_excel_tabela(preparar_tabela_estoque(estoque_filtrado), "Relatório de Estoque"), file_name="relatorio_estoque.xls", mime="application/vnd.ms-excel", width="stretch")

            st.write("---")
            st.subheader("Entrada e Saída Rápida")
            col_mov1, col_mov2, col_mov3 = st.columns(3)
            
            lista_prod = [f"{p['id']} - {p.get('codigo_entrada') or p.get('produto')} (Qtd: {p['quantidade']})" for p in estoque_data]
            prod_sel = col_mov1.selectbox("Selecione o Produto para Movimentar:", lista_prod)
            
            if prod_sel:
                id_sel = int(prod_sel.split(" - ")[0])
                prod_info = next((p for p in estoque_data if p['id'] == id_sel), None)
                if prod_info and prod_info.get("foto"):
                    st.image(prod_info.get("foto"), caption=prod_info.get("foto_nome") or prod_info.get("produto"), width=260)
                
                qtd_mov = col_mov2.number_input("Quantidade:", min_value=1, value=1, step=1)
                tipo_mov = col_mov3.radio("Tipo de Movimentação:", ["Entrada (Adicionar)", "Saída (Subtrair)"], horizontal=True)
                
                if st.button("Confimar Movimentação de Estoque", type="primary"):
                    nova_qtd = prod_info['quantidade'] + qtd_mov if "Entrada" in tipo_mov else prod_info['quantidade'] - qtd_mov
                    if nova_qtd < 0:
                        st.error("Erro: A quantidade de saída não pode ser maior que o estoque atual!")
                    else:
                        conn = conectar_banco()
                        c = conn.cursor()
                        c.execute("UPDATE estoque SET quantidade=? WHERE id=?", (nova_qtd, prod_info['id']))
                        conn.commit()
                        conn.close()
                        acao_mov = "Entrada" if "Entrada" in tipo_mov else "Saída"
                        registrar_evento_sistema(
                            acao_mov,
                            "estoque",
                            prod_info["id"],
                            "",
                            {"produto": prod_info.get("produto"), "quantidade": qtd_mov, "estoque_anterior": prod_info.get("quantidade"), "estoque_atual": nova_qtd},
                        )
                        st.success(f"Movimentação registada com sucesso! Nova quantidade em estoque: {nova_qtd}")
                        st.rerun()
        else:
            st.info("Nenhum produto cadastrado no seu estoque ainda.")

    with aba_est2:
        st.subheader("Cadastrar Produto")
        with st.form("form_estoque", clear_on_submit=True):
            ce1, ce2, ce3 = st.columns(3)
            opcoes_fileira1 = ["", "1-01 Novo", "1-02 Usado"]
            opcoes_fileira2 = ["", "2-01 Informática", "2-02 CFTV", "2-03 Alarme", "2-04 Infraestrutura"]
            e_cod = ce1.selectbox("Fileira 1 (Obrigatório):", opcoes_fileira1)
            e_cat = ce2.selectbox("Fileira 2 (Obrigatório):", opcoes_fileira2)
            e_nome = ce3.text_input("Fileira 3 / Identificação do Produto (Obrigatório):")
            e_nome_generico = st.text_input("Nome genérico:")

            ce_loc1, ce_loc2 = st.columns(2)
            e_codigo_entrada = montar_codigo_entrada(e_cod, e_cat, e_nome)
            ce_loc1.text_input("Código Interno no BD:", value=e_codigo_entrada, disabled=True, help="Gerado automaticamente com Fileira 1 + Fileira 2 + Fileira 3.")
            e_caixa = ce_loc2.text_input("Caixa / Gaveta:")

            ce4, ce5 = st.columns(2)
            e_qtd = ce4.number_input("Quantidade Inicial em Estoque:", min_value=0, value=0)
            e_min = ce5.number_input("Estoque Mínimo (Alerta):", min_value=0, value=5)
            e_situacao_nota = st.radio(
                "Documento da compra:", list(SITUACOES_DOCUMENTO_COMPRA), horizontal=True,
                help="Produtos comprados sem nota serão classificados como serviço na venda, mas continuarão baixando o estoque.",
            )

            e_preco_auto = st.checkbox("Calcular preço de revenda automaticamente", value=True)
            ce6, ce7, ce8 = st.columns(3)
            e_custo = ce6.number_input("Valor de compra (R$):", min_value=0.0, step=0.01, format="%.2f")
            e_deslocamento = ce7.number_input("Deslocamento por unidade (R$):", min_value=0.0, step=0.01, format="%.2f")
            e_forn = ce8.text_input("Fornecedor Principal:")
            cp1, cp2, cp3 = st.columns(3)
            e_imposto = cp1.number_input("Impostos (%):", min_value=0.0, step=0.1, format="%.2f")
            e_lucro = cp2.number_input("Lucro (%):", min_value=0.0, step=0.1, format="%.2f")
            e_ajuste = cp3.checkbox("Permitir ajuste no orçamento/faturamento", value=False)
            preco_calculado = float(calcular_preco_revenda(e_custo, e_deslocamento, e_imposto, e_lucro))
            e_venda_manual = st.number_input(
                "Valor de revenda manual (R$):", min_value=0.0, step=0.01, format="%.2f",
                disabled=e_preco_auto, help="Usado somente quando o cálculo automático estiver desmarcado.",
            )
            st.metric("Preço de revenda utilizado", formatar_moeda_br(preco_calculado if e_preco_auto else e_venda_manual))

            e_obs = st.text_area("Observações Adicionais:")
            e_foto = st.file_uploader("Foto do item (opcional):", type=TIPOS_IMAGEM_UPLOAD, key="estoque_foto_novo")

            if st.form_submit_button("Salvar Produto no Estoque"):
                if e_cod and e_cat and e_nome:
                    if e_foto and not upload_dentro_limite(e_foto):
                        erro_upload_grande("foto")
                        st.stop()
                    conn = conectar_banco()
                    c = conn.cursor()
                    try:
                        cod_entrada_final = montar_codigo_entrada(e_cod, e_cat, e_nome)
                        foto_dados, foto_nome, foto_mime = dados_upload(e_foto)
                        valor_revenda = preco_calculado if e_preco_auto else e_venda_manual
                        c.execute('''INSERT INTO estoque (codigo, codigo_entrada, produto, nome_generico, categoria, fileira, caixa, quantidade, estoque_minimo, valor_custo, valor_venda, fornecedor, observacoes, foto_nome, foto_mime, foto, custo_deslocamento, imposto_percentual, lucro_percentual, preco_revenda_automatico, permitir_ajuste_preco, situacao_nota) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (e_cod, cod_entrada_final, e_nome, e_nome_generico, e_cat, e_cod, e_caixa, e_qtd, e_min, e_custo, valor_revenda, e_forn, e_obs, foto_nome, foto_mime, foto_dados, e_deslocamento, e_imposto, e_lucro, "Sim" if e_preco_auto else "Não", int(e_ajuste), e_situacao_nota))
                        conn.commit()
                        st.success("Produto cadastrado com sucesso!")
                    except Exception as e:
                        st.error(f"Erro ao salvar: {e}")
                    finally:
                        conn.close()
                        st.rerun()
                else:
                    st.error("Os campos 'Fileira 1', 'Fileira 2' e 'Fileira 3 / Identificação' são obrigatórios.")

    with aba_est3:
        st.subheader("Editar ou Excluir Produto")
        if estoque_data:
            act_est = st.radio("Selecione a Ação:", ["Editar Produto", "Excluir Produto"], horizontal=True)
            
            if act_est == "Excluir Produto":
                id_del_est = st.number_input("ID do Produto para excluir:", min_value=1, step=1)
                if st.button("Excluir Produto Permanentemente"):
                    deletar_registro('estoque', 'id', id_del_est)
                    st.success("Produto removido com sucesso.")
                    st.rerun()

                if eh_admin_master():
                    st.write("---")
                    with st.expander("Excluir todos os itens do estoque", expanded=False):
                        st.error("Atenção: esta ação excluirá permanentemente todos os produtos do estoque.")
                        confirmacao_excluir_estoque = st.text_input(
                            'Para confirmar, digite "EXCLUIR TODO O ESTOQUE":',
                            key="confirmacao_excluir_todo_estoque",
                        )
                        confirmar_exclusao_total = st.checkbox(
                            "Confirmo que desejo excluir todos os itens do estoque.",
                            key="checkbox_excluir_todo_estoque",
                        )
                        if st.button(
                            "Excluir todos os itens permanentemente",
                            type="primary",
                            disabled=not (
                                confirmar_exclusao_total
                                and confirmacao_excluir_estoque.strip().upper() == "EXCLUIR TODO O ESTOQUE"
                            ),
                            key="btn_excluir_todo_estoque",
                        ):
                            if not eh_admin_master():
                                st.error("Esta ação é exclusiva do administrador master Daniel.fabio.")
                                st.stop()
                            conn = conectar_banco()
                            c = conn.cursor()
                            try:
                                quantidade_excluida = len(estoque_data)
                                c.execute("DELETE FROM estoque")
                                conn.commit()
                            except Exception:
                                conn.rollback()
                                raise
                            finally:
                                conn.close()
                            registrar_evento_sistema(
                                "exclusao_total",
                                "estoque",
                                0,
                                "Todos os itens",
                                {"quantidade_excluida": quantidade_excluida},
                            )
                            st.success(f"Todos os {quantidade_excluida} itens do estoque foram excluídos.")
                            st.rerun()
                    
            elif act_est == "Editar Produto":
                id_ed_est = st.number_input("ID do Produto para editar:", min_value=1, step=1, value=int(st.session_state.get("estoque_produto_selecionado") or 1), key="estoque_id_edicao")
                prod_edit = next((p for p in estoque_data if p['id'] == id_ed_est), None)
                
                if prod_edit:
                    with st.expander(f"Editando Produto: {prod_edit.get('codigo_entrada') or prod_edit['produto']}", expanded=True):
                        opcoes_estado_edit = ["1-01 Novo", "1-02 Usado"]
                        estado_atual = str(prod_edit.get("codigo") or "")
                        if estado_atual and estado_atual not in opcoes_estado_edit:
                            opcoes_estado_edit.append(estado_atual)
                        ne_cod = st.selectbox(
                            "Fileira 1 / Estado:",
                            opcoes_estado_edit,
                            index=opcoes_estado_edit.index(estado_atual) if estado_atual in opcoes_estado_edit else 0,
                            key=f"ecod_{id_ed_est}",
                        )
                        ne_cat = st.text_input("Fileira 2:", value=prod_edit['categoria'], key=f"ecat_{id_ed_est}")
                        ne_nome = st.text_input("Fileira 3 / Identificação do Produto:", value=prod_edit['produto'], key=f"enom_{id_ed_est}")
                        ne_nome_generico = st.text_input("Nome genérico:", value=prod_edit.get("nome_generico") or "", key=f"enomegenerico_{id_ed_est}")
                        col_loc1, col_loc2 = st.columns(2)
                        ne_codigo_entrada = montar_codigo_entrada(ne_cod, ne_cat, ne_nome)
                        col_loc1.text_input("Código Interno no BD:", value=ne_codigo_entrada, disabled=True, key=f"ecodent_{id_ed_est}")
                        ne_caixa = col_loc2.text_input("Caixa / Gaveta:", value=prod_edit.get('caixa') or "", key=f"ecaixa_{id_ed_est}")
                        
                        col_eq1, col_eq2 = st.columns(2)
                        ne_qtd = col_eq1.number_input("Quantidade Atual:", value=prod_edit['quantidade'], key=f"eqtd_{id_ed_est}")
                        ne_min = col_eq2.number_input("Estoque Mínimo:", value=prod_edit['estoque_minimo'], key=f"emin_{id_ed_est}")
                        situacao_nota_atual = normalizar_situacao_compra(prod_edit.get("situacao_nota"))
                        ne_situacao_nota = st.radio(
                            "Documento da compra:", list(SITUACOES_DOCUMENTO_COMPRA),
                            index=0 if situacao_nota_atual == COMPRADO_COM_NOTA else 1, horizontal=True,
                            key=f"esituacaonota_{id_ed_est}",
                        )
                        
                        auto_atual = str(prod_edit.get("preco_revenda_automatico") or "Não").casefold() in {"sim", "1", "true"}
                        ne_preco_auto = st.checkbox("Calcular preço de revenda automaticamente", value=auto_atual, key=f"eprecoauto_{id_ed_est}")
                        col_ev1, col_ev2, col_ev3 = st.columns(3)
                        ne_custo = col_ev1.number_input("Valor de compra (R$):", min_value=0.0, value=float(decimal_valor(prod_edit.get('valor_custo'))), step=0.01, key=f"ecusto_{id_ed_est}")
                        ne_deslocamento = col_ev2.number_input("Deslocamento/unidade (R$):", min_value=0.0, value=float(decimal_valor(prod_edit.get('custo_deslocamento'))), step=0.01, key=f"edesloc_{id_ed_est}")
                        ne_forn = col_ev3.text_input("Fornecedor:", value=prod_edit['fornecedor'], key=f"eforn_{id_ed_est}")
                        col_pr1, col_pr2, col_pr3 = st.columns(3)
                        ne_imposto = col_pr1.number_input("Impostos (%):", min_value=0.0, value=float(prod_edit.get('imposto_percentual') or 0), step=0.1, key=f"eimposto_{id_ed_est}")
                        ne_lucro = col_pr2.number_input("Lucro (%):", min_value=0.0, value=float(prod_edit.get('lucro_percentual') or 0), step=0.1, key=f"elucro_{id_ed_est}")
                        ne_ajuste = col_pr3.checkbox("Permitir ajuste comercial", value=bool(prod_edit.get('permitir_ajuste_preco')), key=f"eajuste_{id_ed_est}")
                        preco_edit_calculado = float(calcular_preco_revenda(ne_custo, ne_deslocamento, ne_imposto, ne_lucro))
                        ne_venda_manual = st.number_input("Valor de revenda manual (R$):", min_value=0.0, value=float(decimal_valor(prod_edit.get('valor_venda'))), step=0.01, disabled=ne_preco_auto, key=f"evenda_{id_ed_est}")
                        st.metric("Preço de revenda utilizado", formatar_moeda_br(preco_edit_calculado if ne_preco_auto else ne_venda_manual))
                        
                        ne_obs = st.text_area("Observações:", value=prod_edit['observacoes'], key=f"eobs_{id_ed_est}")
                        if prod_edit.get("foto"):
                            st.image(prod_edit.get("foto"), caption=prod_edit.get("foto_nome") or "Foto atual", width=260)
                        ne_foto = st.file_uploader("Trocar foto do item (opcional):", type=TIPOS_IMAGEM_UPLOAD, key=f"efoto_{id_ed_est}")
                        
                        if st.button("Guardar Edição do Produto", type="primary"):
                            if ne_foto and not upload_dentro_limite(ne_foto):
                                erro_upload_grande("foto")
                                st.stop()
                            conn = conectar_banco()
                            c = conn.cursor()
                            cod_entrada_edit = montar_codigo_entrada(ne_cod, ne_cat, ne_nome)
                            ne_venda = preco_edit_calculado if ne_preco_auto else ne_venda_manual
                            if ne_foto:
                                foto_dados, foto_nome, foto_mime = dados_upload(ne_foto)
                                c.execute('''UPDATE estoque SET codigo=?, codigo_entrada=?, produto=?, nome_generico=?, categoria=?, fileira=?, caixa=?, quantidade=?, estoque_minimo=?, valor_custo=?, valor_venda=?, fornecedor=?, observacoes=?, foto_nome=?, foto_mime=?, foto=?, custo_deslocamento=?, imposto_percentual=?, lucro_percentual=?, preco_revenda_automatico=?, permitir_ajuste_preco=?, situacao_nota=? WHERE id=?''', (ne_cod, cod_entrada_edit, ne_nome, ne_nome_generico, ne_cat, ne_cod, ne_caixa, ne_qtd, ne_min, ne_custo, ne_venda, ne_forn, ne_obs, foto_nome, foto_mime, foto_dados, ne_deslocamento, ne_imposto, ne_lucro, "Sim" if ne_preco_auto else "Não", int(ne_ajuste), ne_situacao_nota, id_ed_est))
                            else:
                                c.execute('''UPDATE estoque SET codigo=?, codigo_entrada=?, produto=?, nome_generico=?, categoria=?, fileira=?, caixa=?, quantidade=?, estoque_minimo=?, valor_custo=?, valor_venda=?, fornecedor=?, observacoes=?, custo_deslocamento=?, imposto_percentual=?, lucro_percentual=?, preco_revenda_automatico=?, permitir_ajuste_preco=?, situacao_nota=? WHERE id=?''', (ne_cod, cod_entrada_edit, ne_nome, ne_nome_generico, ne_cat, ne_cod, ne_caixa, ne_qtd, ne_min, ne_custo, ne_venda, ne_forn, ne_obs, ne_deslocamento, ne_imposto, ne_lucro, "Sim" if ne_preco_auto else "Não", int(ne_ajuste), ne_situacao_nota, id_ed_est))
                            conn.commit()
                            conn.close()
                            st.success("Produto atualizado com sucesso!")
                            st.rerun()
                else:
                    st.info("Produto com este ID não foi encontrado.")

    with aba_est4:
        st.subheader("Pedidos de Compra")
        itens_baixos = [p for p in estoque_data if int(p['quantidade'] or 0) <= int(p['estoque_minimo'] or 0)]
        if itens_baixos:
            st.warning("Itens abaixo ou no estoque mínimo encontrados.")
            st.dataframe([dict(p) for p in itens_baixos], width="stretch", hide_index=True)
        else:
            st.info("Nenhum item está abaixo do estoque mínimo no momento.")

        st.write("---")
        if estoque_data:
            lista_compra = [f"{p['id']} - {p['codigo']} - {p['produto']} (Atual: {p['quantidade']} / Mín: {p['estoque_minimo']})" for p in estoque_data]
            compra_sel = st.selectbox("Produto para solicitar compra:", lista_compra)
            prod_id = int(compra_sel.split(" - ")[0])
            prod_compra = next((p for p in estoque_data if p['id'] == prod_id), None)

            pc1, pc2 = st.columns(2)
            qtd_solicitada = pc1.number_input("Quantidade solicitada:", min_value=1, value=1, step=1)
            fornecedor_sug = pc2.text_input("Fornecedor:", value=prod_compra['fornecedor'] if prod_compra else "")
            obs_compra = st.text_area("Observações do pedido:")

            if st.button("Salvar Solicitação de Compra", type="primary", width="stretch"):
                if prod_compra:
                    conn_pc = conectar_banco()
                    cpc = conn_pc.cursor()
                    cpc.execute('''INSERT INTO pedidos_compra
                        (data_pedido, produto_id, codigo, produto, quantidade_solicitada, fornecedor, status, observacoes)
                        VALUES (?,?,?,?,?,?,?,?)''',
                        (date.today().strftime("%d/%m/%Y"), prod_compra['id'], prod_compra['codigo'],
                         prod_compra['produto'], qtd_solicitada, fornecedor_sug, "Solicitado", obs_compra))
                    conn_pc.commit()
                    conn_pc.close()
                    st.success("Solicitação de compra salva.")
                    st.rerun()

        conn_pc = conectar_banco()
        conn_pc.row_factory = None
        cpc = conn_pc.cursor()
        cpc.execute("SELECT * FROM pedidos_compra ORDER BY id DESC")
        pedidos = cpc.fetchall()
        conn_pc.close()

        if pedidos:
            st.write("---")
            st.subheader("Histórico de Solicitações")
            st.dataframe([dict(p) for p in pedidos], width="stretch", hide_index=True)

    with aba_est5:
        st.subheader("Relatório de Compra")
        conn_rel = conectar_banco()
        cr = conn_rel.cursor()
        cr.execute('''
            SELECT pc.*, COALESCE(e.categoria, '') AS categoria,
                   COALESCE(e.codigo_entrada, '') AS codigo_entrada,
                   COALESCE(e.fileira, '') AS fileira, COALESCE(e.caixa, '') AS caixa
            FROM pedidos_compra pc
            LEFT JOIN estoque e ON e.id = pc.produto_id
            ORDER BY pc.id DESC
        ''')
        compras_rel = cr.fetchall()
        conn_rel.close()

        if compras_rel:
            status_opcoes = ["Todos"] + sorted({(p.get("status") or "Sem status") for p in compras_rel})
            filtro_status = st.selectbox("Filtrar por status:", status_opcoes)
            compras_filtradas = compras_rel if filtro_status == "Todos" else [p for p in compras_rel if (p.get("status") or "Sem status") == filtro_status]
            tabela_compras = preparar_tabela_compras(compras_filtradas)
            st.dataframe(tabela_compras, width="stretch", hide_index=True)
            st.download_button(
                "Baixar relatório de compra em Excel",
                data=gerar_excel_tabela(tabela_compras, "Relatório de Compra"),
                file_name="relatorio_compra.xls",
                mime="application/vnd.ms-excel",
                width="stretch",
            )
        else:
            st.info("Nenhuma solicitação de compra cadastrada.")

    with aba_est6:
        st.subheader("Importar Produtos de uma Planilha Excel")
        st.caption("A primeira linha deve conter os nomes das colunas. Formato aceito: .xlsx")
        arquivo_excel_estoque = st.file_uploader("Selecionar planilha de produtos:", type=["xlsx"], key="estoque_importar_excel")

        if arquivo_excel_estoque:
            try:
                cabecalhos_excel, produtos_excel = ler_excel_estoque(arquivo_excel_estoque)
            except Exception as ex:
                st.error(f"Não foi possível ler a planilha: {ex}")
                cabecalhos_excel, produtos_excel = [], []

            if produtos_excel:
                st.success(f"Planilha lida: {len(produtos_excel)} produtos encontrados.")
                st.write("**Prévia das primeiras linhas:**")
                st.dataframe(produtos_excel[:10], width="stretch", hide_index=True)

                st.write("**Relacionar colunas da planilha com o formato do estoque:**")
                opcoes_colunas = ["-- Não importar --"] + cabecalhos_excel
                mapeamento_estoque = {}
                cols_mapa = st.columns(3)
                for idx, (campo, rotulo) in enumerate(COLUNAS_ESTOQUE_IMPORTACAO.items()):
                    sugestao = sugerir_coluna_estoque(campo, cabecalhos_excel)
                    indice_sugestao = opcoes_colunas.index(sugestao) if sugestao in opcoes_colunas else 0
                    mapeamento_estoque[campo] = cols_mapa[idx % 3].selectbox(
                        rotulo, opcoes_colunas, index=indice_sugestao, key=f"mapa_estoque_{campo}"
                    )

                modo_importacao = st.radio(
                    "Quando o mesmo código interno e produto já existirem:",
                    ["Atualizar produto existente", "Ignorar produto repetido"],
                    horizontal=True,
                    key="estoque_modo_importacao",
                )

                if st.button("Importar produtos para o banco", type="primary", width="stretch", key="btn_importar_estoque_excel"):
                    if mapeamento_estoque["produto"] == "-- Não importar --" and mapeamento_estoque["nome_generico"] == "-- Não importar --":
                        st.error("Relacione pelo menos Produto / Identificação ou Nome genérico.")
                    else:
                        conn_imp = conectar_banco()
                        cimp = conn_imp.cursor()
                        importados, atualizados, ignorados = 0, 0, 0
                        erro_importacao = None
                        try:
                            for linha in produtos_excel:
                                dados_produto = {
                                    campo: linha.get(coluna) if coluna != "-- Não importar --" else ""
                                    for campo, coluna in mapeamento_estoque.items()
                                }
                                nome_generico = texto_importacao(dados_produto["nome_generico"])
                                produto = texto_importacao(dados_produto["produto"]) or nome_generico
                                if not produto:
                                    ignorados += 1
                                    continue
                                codigo = texto_importacao(dados_produto["codigo"])
                                categoria = texto_importacao(dados_produto["categoria"])
                                codigo_entrada = texto_importacao(dados_produto["codigo_entrada"]) or montar_codigo_entrada(codigo, categoria, produto)
                                valores = (
                                    codigo, codigo_entrada, produto, nome_generico, categoria, codigo,
                                    texto_importacao(dados_produto["caixa"]),
                                    inteiro_importacao(dados_produto["quantidade"]),
                                    inteiro_importacao(dados_produto["estoque_minimo"], 5),
                                    texto_importacao(dados_produto["valor_custo"]),
                                    texto_importacao(dados_produto["valor_venda"]),
                                    texto_importacao(dados_produto["fornecedor"]),
                                    texto_importacao(dados_produto["observacoes"]),
                                )
                                cimp.execute(
                                    "SELECT id FROM estoque WHERE codigo_entrada=? AND produto=? LIMIT 1",
                                    (codigo_entrada, produto),
                                )
                                existente = cimp.fetchone()
                                if existente and modo_importacao == "Ignorar produto repetido":
                                    ignorados += 1
                                elif existente:
                                    cimp.execute(
                                        """UPDATE estoque SET codigo=?, codigo_entrada=?, produto=?, nome_generico=?, categoria=?, fileira=?,
                                           caixa=?, quantidade=?, estoque_minimo=?, valor_custo=?, valor_venda=?, fornecedor=?, observacoes=?
                                           WHERE id=?""",
                                        valores + (existente["id"],),
                                    )
                                    atualizados += 1
                                else:
                                    cimp.execute(
                                        """INSERT INTO estoque
                                           (codigo, codigo_entrada, produto, nome_generico, categoria, fileira, caixa, quantidade,
                                            estoque_minimo, valor_custo, valor_venda, fornecedor, observacoes)
                                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                                        valores,
                                    )
                                    importados += 1
                            conn_imp.commit()
                        except Exception as ex:
                            conn_imp.rollback()
                            erro_importacao = str(ex)
                        finally:
                            conn_imp.close()

                        if erro_importacao:
                            st.error(f"A importação foi cancelada sem alterar o banco: {erro_importacao}")
                        else:
                            st.success(f"Importação concluída: {importados} novos, {atualizados} atualizados e {ignorados} ignorados.")
                            st.rerun()
            elif cabecalhos_excel:
                st.warning("A planilha não possui produtos abaixo do cabeçalho.")


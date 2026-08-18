from __future__ import annotations

from pathlib import Path

from dsystem_erp.app_context import aplicar_contexto_pagina
from dsystem_erp.pages.faturado_documentos import renderizar_central_documentos_faturados
from dsystem_erp.services.faturamento_parcelas import gerar_parcelas_faturamento
from dsystem_erp.services.estoque_fiscal import (
    COMPRADO_SEM_NOTA,
    normalizar_situacao_compra,
    tipo_fiscal_produto_estoque,
)
from dsystem_erp.services.nfse_certificado import certificado_bate_com_cnpj, inspecionar_certificado_pfx
from dsystem_erp.services.nfse_nacional import (
    assinar_xml_dps_nacional,
    endpoint_nacional,
    executar_fluxo_nfse_nacional,
    gerar_xml_dps_nacional,
)
from dsystem_erp.services.nfe_produto import (
    analisar_retorno_nfe_produto,
    assinar_xml_nfe_produto,
    enviar_xml_nfe_produto,
    gerar_xml_nfe_produto_400,
    validar_prontidao_envio_nfe_produto,
    validar_xml_nfe_produto_minimo,
)
from dsystem_erp.utils.formatadores import somente_digitos
from dsystem_erp.services.precificacao_estoque import preco_revenda_produto
from dsystem_erp.ui_consulta import tabela_selecionavel_id
try:
    from dsystem_erp.services.settings import endpoint_nfse_nacional_rest
except ImportError:
    def endpoint_nfse_nacional_rest(valor: str | None) -> bool:
        endpoint = str(valor or "").strip().lower().rstrip("/")
        return (
            ("adn." in endpoint and "nfse.gov.br" in endpoint)
            or ("sefin." in endpoint and "nfse.gov.br" in endpoint)
            or "/contribuintes" in endpoint
            or "/sefinnacional" in endpoint
        )


MENSAGEM_ENDPOINT_NACIONAL_REST = (
    "Esse endpoint e da API Nacional REST da NFS-e. Ele nao aceita o envio SOAP/XML ABRASF "
    "deste botao. Para emitir por esse caminho, use o fluxo DPS Nacional; para este botao, "
    "configure um WebService SOAP municipal compativel."
)


def mensagem_erro_emissao_nfse(ex: Exception, endpoint: str) -> str:
    texto = str(ex)
    if "HTTP Error 404" in texto:
        return (
            f"Endpoint nao encontrado: {endpoint}. "
            "Isso normalmente quer dizer que a URL configurada nao e o endpoint correto para este tipo de envio. "
            "O envio SOAP/XML ABRASF precisa de WebService municipal compativel. "
            "A API Nacional usa outro fluxo, com DPS/JSON."
        )
    if "SSL Certificate Required" in texto or "496" in texto:
        return (
            "O servidor exigiu certificado digital na conexao. "
            "Confira o caminho do PFX, a senha e se o endpoint aceita certificado A1/mTLS."
        )
    return texto


def renderizar_a_faturar(ctx: dict) -> None:
    aplicar_contexto_pagina(ctx, globals())
    st.title("A faturar")

    import io
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from datetime import date

    clientes_fat = buscar_clientes()
    nomes_clientes = ["-- Selecionar --"] + [c['nome'] for c in clientes_fat]

    aba_fat1, aba_fat2, aba_fat3 = st.tabs([
        "Lançar a faturar", "Histórico", "Exportar Modelo Excel"
    ])

    with aba_fat1:
        st.subheader("Novo lançamento a faturar")

        if st.session_state.pop('fat_salvo', None):
            st.toast("Lançamento salvo com sucesso!")

        f_col1, f_col2, f_col3 = st.columns(3)
        with f_col1:
            fat_cliente = st.selectbox("Cliente:", nomes_clientes, key="fat_cliente")
            fat_cliente_dados = next((c for c in clientes_fat if fat_cliente != '-- Selecionar --' and c['nome'] == fat_cliente), None)
            fat_cliente_padrao = dados_cliente_padrao(fat_cliente_dados)
        with f_col2:
            fat_cnpj = st.text_input("CNPJ (auto):", value=fat_cliente_padrao["cpf_cnpj"], disabled=True, key=f"fat_cnpj_{fat_cliente}")
        with f_col3:
            fat_data = st.date_input("Data do Lançamento:", value=date.today(), key="fat_data")

        if fat_cliente_dados:
            fd1, fd2, fd3 = st.columns(3)
            fd1.text_input("Telefone:", value=fat_cliente_padrao["telefone"], disabled=True, key=f"fat_tel_{fat_cliente}")
            fd2.text_input("E-mail:", value=fat_cliente_padrao["email"], disabled=True, key=f"fat_email_{fat_cliente}")
            fd3.text_input("Endereço:", value=montar_endereco_cliente(fat_cliente_dados), disabled=True, key=f"fat_end_{fat_cliente}")

        f_col4, f_col5 = st.columns(2)
        with f_col4:
            fat_tipo = st.selectbox("Tipo:", ["Eventual", "Mensal"], key="fat_tipo")
        with f_col5:
            fat_emite_nf = st.selectbox("Emite Nota Fiscal?", ["Sim", "Não"], key="fat_emite_nf")

        f_col6, f_col7 = st.columns(2)
        with f_col6:
            fat_tipo_nota = st.selectbox("Tipo de Nota Fiscal (ajustado automaticamente pelos itens):", ["Serviço", "Produto", "Produto e Serviço", "N/A"], key="fat_tipo_nota")
        with f_col7:
            fat_forma_pag = st.selectbox("Forma de Pagamento:", ["Boleto", "PIX", "Cartão", "Transferência", "Dinheiro", "Outro"], key="fat_forma_pag")

        st.write("---")
        st.markdown("#### Itens do Faturamento")

        qtd_itens = st.number_input("Quantidade de Itens:", min_value=1, max_value=20, value=1, key="fat_qtd_itens")
        produtos_estoque_fat = repo_listar_estoque(conectar_banco)
        opcoes_produto_fat = ["-- Selecionar produto do estoque --"] + [
            f"{p['id']} - {p.get('produto') or p.get('codigo_entrada')} — {normalizar_situacao_compra(p.get('situacao_nota'))} (Estoque: {p.get('quantidade') or 0})"
            for p in produtos_estoque_fat
        ]
        itens_fat = []
        total_fat = 0.0

        for i in range(qtd_itens):
            ic1, ic2, ic3, ic4, ic5 = st.columns([4, 1.5, 2, 2, 2])
            desc  = ic1.text_input(f"Descrição Item {i+1}:", key=f"fat_desc_{i}")
            tipo_item_fat = ic2.selectbox(f"Tipo Item {i+1}:", ["Serviço", "Produto"], key=f"fat_tipo_item_{i}")
            produto_fat = None
            tipo_item_fiscal_fat = tipo_item_fat
            situacao_nota_fat = ""
            ajuste_fat = 0.0
            preco_fat = 0.0
            if tipo_item_fat == "Produto":
                produto_escolhido_fat = st.selectbox(f"Produto do estoque {i+1}:", opcoes_produto_fat, key=f"fat_produto_estoque_{i}")
                if produto_escolhido_fat != opcoes_produto_fat[0]:
                    produto_id_fat = int(produto_escolhido_fat.split(" - ", 1)[0])
                    produto_fat = next((p for p in produtos_estoque_fat if int(p["id"]) == produto_id_fat), None)
                    if produto_fat:
                        situacao_nota_fat = normalizar_situacao_compra(produto_fat.get("situacao_nota"))
                        tipo_item_fiscal_fat = tipo_fiscal_produto_estoque(produto_fat)
                        desc = produto_fat.get("produto") or produto_fat.get("codigo_entrada") or desc
                        if produto_fat.get("permitir_ajuste_preco"):
                            ajuste_fat = st.number_input(f"Ajuste comercial do produto {i+1} (%):", min_value=-100.0, value=0.0, step=0.1, key=f"fat_ajuste_produto_{i}")
                        preco_fat = float(preco_revenda_produto(produto_fat, ajuste_fat))
                        st.caption(f"Preço do estoque aplicado: {formatar_moeda_br(preco_fat)} — {situacao_nota_fat}")
                        if situacao_nota_fat == COMPRADO_SEM_NOTA:
                            st.warning(f"Item {i+1}: sairá fiscalmente como Serviço, mantendo a baixa no estoque.")
            chave_preco_fat = f"fat_vunit_{i}_{produto_fat.get('id') if produto_fat else 'manual'}_{ajuste_fat:.2f}"
            vunit = ic3.number_input(f"Valor Unit. R$:", min_value=0.0, value=preco_fat, step=0.01, format="%.2f", key=chave_preco_fat, disabled=bool(produto_fat))
            qtd   = ic4.number_input(f"Quantidade:", min_value=0, step=1, value=1, key=f"fat_qtd_{i}")
            vtotal = vunit * qtd
            ic5.metric(f"Total Item {i+1}", f"R$ {vtotal:,.2f}".replace(',','X').replace('.',',').replace('X','.'))
            if desc:
                itens_fat.append({"desc": desc, "tipo_item": tipo_item_fiscal_fat, "vunit": vunit, "qtd": qtd, "vtotal": vtotal,
                                  "estoque_id": produto_fat.get("id") if produto_fat else None,
                                  "origem_item": "Produto do estoque" if produto_fat else tipo_item_fat,
                                  "situacao_nota": situacao_nota_fat,
                                  "ajuste_preco_percentual": ajuste_fat if produto_fat else 0})
                total_fat += vtotal

        st.write("---")
        fc1, fc2, fc3 = st.columns(3)
        with fc1:
            fat_parcelas = st.selectbox("Parcelado?", ["Não", "2x", "3x", "4x", "5x", "6x", "12x"], key="fat_parcelas")
        with fc2:
            fat_venc = st.date_input("Vencimento 1ª Parcela:", value=date.today(), key="fat_venc")
        with fc3:
            fat_orc_ref = st.text_input("Nº Orçamento de Referência (opcional):", key="fat_orc_ref")

        fat_obs_interna = st.text_area("Observação Interna:", key="fat_obs_int", height=70)
        fat_obs_nota    = st.text_area("Informações para Lançamento/Nota:", key="fat_obs_nota", height=70)
        fat_anexos = st.file_uploader(
            "Arquivos do faturamento (NF, orçamento, O.S. ou comprovante):",
            accept_multiple_files=True,
            key="fat_anexos",
        )

        st.metric("Valor Total do Lançamento", f"R$ {total_fat:,.2f}".replace(',','X').replace('.',',').replace('X','.'))

        if st.button("Salvar lançamento a faturar", type="primary", width="stretch"):
            if fat_cliente == "-- Selecionar --":
                st.error("Selecione um cliente.")
            elif not itens_fat:
                st.error("Adicione pelo menos um item com descrição.")
            else:
                import json as _json
                fat_tipo_nota_calculado = tipo_nota_por_itens(itens_fat)
                conn = conectar_banco()
                c = conn.cursor()
                try:
                    if DB_BACKEND != "mysql":
                        c.execute('''
                            CREATE TABLE IF NOT EXISTS faturamento (
                                id INT PRIMARY KEY AUTO_INCREMENT,
                                data_lanc TEXT, cliente TEXT, cnpj TEXT, tipo TEXT, emite_nf TEXT, tipo_nota TEXT,
                                forma_pag TEXT, itens TEXT, valor_total REAL, parcelas TEXT, vencimento TEXT,
                                orc_ref TEXT, obs_interna TEXT, obs_nota TEXT
                            )
                        ''')
                    c.execute('''
                        INSERT INTO faturamento (
                            data_lanc, cliente, cnpj, tipo, emite_nf, tipo_nota,
                            forma_pag, itens, valor_total, parcelas, vencimento,
                            orc_ref, obs_interna, obs_nota
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ''', (
                        data_para_banco_br(fat_data), fat_cliente, fat_cnpj, fat_tipo, fat_emite_nf,
                        fat_tipo_nota_calculado, fat_forma_pag, _json.dumps(itens_fat), total_fat,
                        fat_parcelas, data_para_banco_br(fat_venc), fat_orc_ref,
                        fat_obs_interna, fat_obs_nota
                    ))
                    fat_id_novo = c.lastrowid
                    for arq_fat in fat_anexos or []:
                        if arq_fat and not upload_dentro_limite(arq_fat):
                            erro_upload_grande(arq_fat.name)
                            st.stop()
                        dados_arq, nome_arq, mime_arq = dados_upload(arq_fat)
                        c.execute("""INSERT INTO faturamento_anexos
                                  (faturamento_id, tipo, nome_arquivo, mime_type, arquivo, criado_por, criado_em)
                                  VALUES (?,?,?,?,?,?,?)""",
                                  (fat_id_novo, "Faturamento", nome_arq, mime_arq, dados_arq,
                                   st.session_state.get("username", ""), agora_br()))
                    conn.commit()
                    st.session_state['fat_salvo'] = True
                    for chave_fat in list(st.session_state.keys()):
                        if str(chave_fat).startswith("fat_") and chave_fat not in ("fat_salvo",):
                            del st.session_state[chave_fat]
                except Exception as ex:
                    st.error(f"Erro ao salvar: {ex}")
                finally:
                    conn.close()
                st.rerun()

    with aba_fat2:
        st.subheader("Histórico de Lançamentos")
        hf1, hf2, hf3 = st.columns(3)
        fat_hist_mes = hf1.date_input("Filtrar por mês do lançamento:", value=None, key="fat_hist_mes")
        fat_hist_cliente = hf2.text_input("Filtrar por cliente:", key="fat_hist_cliente")
        fat_hist_status = hf3.selectbox("Status:", ["Todos", "Aberto", "Faturado", "Cancelado"], key="fat_hist_status")

        conn = conectar_banco()
        conn.row_factory = None
        c = conn.cursor()
        try:
            if DB_BACKEND != "mysql":
                c.execute('''
                    CREATE TABLE IF NOT EXISTS faturamento (
                        id INT PRIMARY KEY AUTO_INCREMENT, data_lanc TEXT, cliente TEXT, cnpj TEXT, tipo TEXT,
                        emite_nf TEXT, tipo_nota TEXT, forma_pag TEXT, itens TEXT, valor_total REAL, parcelas TEXT, vencimento TEXT,
                        orc_ref TEXT, obs_interna TEXT, obs_nota TEXT
                    )
                ''')
                conn.commit()
            rows_fat = repo_listar_faturamentos(conectar_banco)
            rows_fat = filtrar_registros_por_empresa(rows_fat, "cliente")
        except Exception:
            rows_fat = []
        conn.close()

        if rows_fat:
            import json as _json

            df_fat = [dict(r) for r in rows_fat]
            if fat_hist_mes:
                df_fat = [r for r in df_fat if parse_data_flex(r.get("data_lanc")) and parse_data_flex(r.get("data_lanc")).strftime("%Y-%m") == fat_hist_mes.strftime("%Y-%m")]
            if fat_hist_cliente.strip():
                df_fat = [r for r in df_fat if fat_hist_cliente.strip().lower() in str(r.get("cliente") or "").lower()]
            if fat_hist_status != "Todos":
                df_fat = [r for r in df_fat if (r.get("status") or "Aberto") == fat_hist_status]
            resumo_fat = []
            for r in df_fat:
                itens_reg = itens_faturamento_lista(r.get("itens"))
                resumo_fat.append({
                    "ID": r.get("id"),
                    "Data": data_para_br(r.get("data_lanc")),
                    "Cliente": r.get("cliente") or "",
                    "Tipo": r.get("tipo") or "",
                    "Itens": resumo_itens_faturamento(r.get("itens")),
                    "Qtd itens": len(itens_reg),
                    "Valor": formatar_moeda_br(r.get("valor_total")),
                    "Vencimento": data_para_br(r.get("vencimento")),
                    "Parcelas": r.get("parcelas") or "Não",
                    "Status": r.get("status") or "Aberto",
                })

            id_faturamento_selecionado = None
            if resumo_fat:
                total_filtrado = sum(float(r.get("valor_total") or 0) for r in df_fat)
                m1, m2, m3 = st.columns(3)
                m1.metric("Lançamentos filtrados", len(resumo_fat))
                m2.metric("Total filtrado", formatar_moeda_br(total_filtrado))
                m3.metric("Itens filtrados", sum(int(r.get("Qtd itens") or 0) for r in resumo_fat))
                id_faturamento_selecionado = tabela_selecionavel_id(st, resumo_fat, "faturamento_grade_consulta", "ID")
                st.caption("Clique no faturamento para abrir automaticamente a consulta/edição.")
                with st.expander("Ver itens detalhados dos faturamentos filtrados", expanded=False):
                    linhas_detalhe = linhas_faturamento_export(df_fat)
                    st.dataframe(linhas_detalhe, width="stretch", hide_index=True)
                    st.markdown("#### Mudar status para faturado")
                    st.caption("Ao faturar, o lançamento vai para Contas a Receber. Se houver item do tipo Produto, o estoque é baixado automaticamente.")
                    for fat_status_row in df_fat:
                        status_atual_fat = fat_status_row.get("status") or "Aberto"
                        ac1, ac2, ac3, ac4, ac5 = st.columns([0.7, 2.4, 1.4, 1.3, 1.8])
                        ac1.write(f"#{fat_status_row.get('id')}")
                        ac2.write(fat_status_row.get("cliente") or "")
                        ac3.write(formatar_moeda_br(fat_status_row.get("valor_total")))
                        ac4.write(status_atual_fat)
                        if status_atual_fat == "Faturado":
                            ac5.success("Já faturado")
                        elif status_atual_fat == "Cancelado":
                            ac5.caption("Cancelado")
                        elif ac5.button("Marcar como faturado", key=f"hist_faturar_{fat_status_row.get('id')}", width="stretch"):
                            resultado_fat = faturar_lancamento_com_integracoes(fat_status_row)
                            if resultado_fat.get("ok"):
                                st.success(resultado_fat.get("mensagem"))
                            else:
                                st.error(resultado_fat.get("mensagem"))
                            st.rerun()
            else:
                st.info("Nenhum faturamento encontrado com os filtros selecionados.")

            tot_ev = sum(float(r.get("valor_total") or 0) for r in df_fat if r.get("tipo") == "Eventual")
            tot_mn = sum(float(r.get("valor_total") or 0) for r in df_fat if r.get("tipo") == "Mensal")

            aliq = 0.06442
            t1, t2, t3 = st.columns(3)
            t1.metric("Total Eventual filtrado", f"R$ {tot_ev:,.2f}".replace(',','X').replace('.',',').replace('X','.'))
            t2.metric("Total Mensal filtrado",   f"R$ {tot_mn:,.2f}".replace(',','X').replace('.',',').replace('X','.'))
            t3.metric("Previsão Impostos (ISS 6,44%)",
                      f"R$ {(float(tot_ev) + float(tot_mn)) * float(aliq):,.2f}".replace(',','X').replace('.',',').replace('X','.'))

            st.write("---")
            if tem_permissao("faturamento.edit"):
                id_edit_fat = st.number_input("ID para editar/anexar arquivos:", min_value=1, step=1, value=int(id_faturamento_selecionado or 1), key=f"fat_edit_id_{id_faturamento_selecionado or 'manual'}")
                fat_edit = next((dict(r) for r in rows_fat if int(r.get("id") or 0) == int(id_edit_fat)), None)
            else:
                id_edit_fat = None
                fat_edit = None
                st.caption("Seu usuário não tem permissão para editar faturamentos.")
            if fat_edit:
                with st.expander(f"Editar faturamento #{id_edit_fat}", expanded=False):
                    faturamento_aberto_para_cliente = (fat_edit.get("status") or "Aberto") == "Aberto"
                    if faturamento_aberto_para_cliente:
                        clientes_fat_puxar, opcoes_fat_puxar = opcoes_clientes_para_puxar()
                        escolha_fat_puxar = st.selectbox("Puxar dados de outro cliente cadastrado:", opcoes_fat_puxar, key=f"fat_puxar_cliente_{id_edit_fat}")
                        if st.button("Aplicar cliente neste faturamento", width="stretch", key=f"fat_btn_puxar_cliente_{id_edit_fat}"):
                            cliente_fat_sel = next((cli for cli in clientes_fat_puxar if cli.get("nome") == escolha_fat_puxar), None)
                            if not cliente_fat_sel:
                                st.error("Selecione um cliente cadastrado para aplicar.")
                            else:
                                st.session_state[f"fat_e_cliente_{id_edit_fat}"] = cliente_fat_sel.get("nome") or ""
                                st.session_state[f"fat_e_cnpj_{id_edit_fat}"] = cliente_fat_sel.get("cnpj") or ""
                                st.success("Dados do cliente carregados no faturamento. Confira e salve.")
                                st.rerun()
                    else:
                        st.info("Cliente e CNPJ ficam bloqueados porque este faturamento já não está em aberto.")
                    ef1, ef2, ef3 = st.columns(3)
                    e_data = ef1.date_input("Data do lançamento:", value=parse_data_flex(fat_edit.get("data_lanc")) or date.today(), key=f"fat_e_data_{id_edit_fat}")
                    e_cliente = ef2.text_input("Cliente:", value=fat_edit.get("cliente") or "", key=f"fat_e_cliente_{id_edit_fat}", disabled=not faturamento_aberto_para_cliente)
                    e_status = ef3.selectbox("Status:", ["Aberto", "Faturado", "Cancelado"], index=["Aberto", "Faturado", "Cancelado"].index(fat_edit.get("status") or "Aberto") if (fat_edit.get("status") or "Aberto") in ["Aberto", "Faturado", "Cancelado"] else 0, key=f"fat_e_status_{id_edit_fat}")
                    ef4, ef5, ef6 = st.columns(3)
                    e_tipo = ef4.selectbox("Tipo:", ["Eventual", "Mensal"], index=0 if fat_edit.get("tipo") != "Mensal" else 1, key=f"fat_e_tipo_{id_edit_fat}")
                    e_forma = ef5.text_input("Forma de pagamento:", value=fat_edit.get("forma_pag") or "", key=f"fat_e_forma_{id_edit_fat}")
                    e_venc = ef6.date_input("Vencimento:", value=parse_data_flex(fat_edit.get("vencimento")) or date.today(), key=f"fat_e_venc_{id_edit_fat}")
                    ef7, ef8, ef9 = st.columns(3)
                    e_cnpj = ef7.text_input("CNPJ:", value=fat_edit.get("cnpj") or "", key=f"fat_e_cnpj_{id_edit_fat}", disabled=not faturamento_aberto_para_cliente)
                    e_emite_nf = ef8.selectbox("Emite NF?", ["Sim", "Não"], index=0 if fat_edit.get("emite_nf") != "Não" else 1, key=f"fat_e_nf_{id_edit_fat}")
                    opcoes_tipo_nota_fat = ["Serviço", "Produto", "Produto e Serviço", "N/A"]
                    e_tipo_nota = ef9.selectbox("Tipo de Nota:", opcoes_tipo_nota_fat, index=opcoes_tipo_nota_fat.index(fat_edit.get("tipo_nota") or "Serviço") if (fat_edit.get("tipo_nota") or "Serviço") in opcoes_tipo_nota_fat else 0, key=f"fat_e_tipo_nota_{id_edit_fat}")

                    st.markdown("#### Itens do faturamento")
                    itens_base_edit = itens_faturamento_lista(fat_edit.get("itens"))
                    if not itens_base_edit:
                        itens_base_edit = [{"desc": "", "qtd": 1, "vunit": float(fat_edit.get("valor_total") or 0), "vtotal": float(fat_edit.get("valor_total") or 0)}]
                    qtd_itens_edit = st.number_input(
                        "Quantidade de itens:",
                        min_value=1,
                        max_value=50,
                        value=max(1, len(itens_base_edit)),
                        step=1,
                        key=f"fat_e_qtd_itens_{id_edit_fat}",
                    )
                    itens_editados = []
                    e_valor = 0.0
                    for idx_item in range(int(qtd_itens_edit)):
                        item_padrao = itens_base_edit[idx_item] if idx_item < len(itens_base_edit) else {"desc": "", "qtd": 1, "vunit": 0.0, "vtotal": 0.0}
                        tipo_padrao_item = item_padrao.get("tipo_item") or "Serviço"
                        if tipo_padrao_item not in ["Produto", "Serviço"]:
                            tipo_padrao_item = "Serviço"
                        ii1, ii2, ii3, ii4, ii5 = st.columns([4, 1.4, 1.4, 1.6, 1.6])
                        desc_item = ii1.text_input("Descrição:", value=item_padrao.get("desc") or "", key=f"fat_e_item_desc_{id_edit_fat}_{idx_item}")
                        tipo_item_edit = ii2.selectbox("Tipo:", ["Serviço", "Produto"], index=["Serviço", "Produto"].index(tipo_padrao_item), key=f"fat_e_item_tipo_{id_edit_fat}_{idx_item}")
                        qtd_item = ii3.number_input("Qtd:", min_value=0, value=int(item_padrao.get("qtd") or 0), step=1, key=f"fat_e_item_qtd_{id_edit_fat}_{idx_item}")
                        vunit_item = ii4.number_input("Valor unit. R$:", min_value=0.0, value=float(item_padrao.get("vunit") or 0), step=0.01, format="%.2f", key=f"fat_e_item_vunit_{id_edit_fat}_{idx_item}")
                        vtotal_item = float(qtd_item) * float(vunit_item)
                        ii5.metric("Total", formatar_moeda_br(vtotal_item))
                        if desc_item.strip() or vtotal_item:
                            tipo_fiscal_preservado = (
                                tipo_fiscal_produto_estoque(item_padrao)
                                if item_padrao.get("estoque_id")
                                else tipo_item_edit
                            )
                            itens_editados.append({
                                "desc": desc_item.strip(), "tipo_item": tipo_fiscal_preservado,
                                "qtd": int(qtd_item), "vunit": float(vunit_item), "vtotal": float(vtotal_item),
                                "estoque_id": item_padrao.get("estoque_id"),
                                "origem_item": item_padrao.get("origem_item") or "",
                                "situacao_nota": (
                                    normalizar_situacao_compra(item_padrao.get("situacao_nota"))
                                    if item_padrao.get("estoque_id")
                                    else ""
                                ),
                                "ajuste_preco_percentual": item_padrao.get("ajuste_preco_percentual") or 0,
                            })
                            e_valor += vtotal_item
                    st.metric("Valor total recalculado", formatar_moeda_br(e_valor))
                    e_obs = st.text_area("Informações/observações:", value=fat_edit.get("obs_nota") or "", key=f"fat_e_obs_{id_edit_fat}")
                    e_obs_interna = st.text_area("Observação interna:", value=fat_edit.get("obs_interna") or "", key=f"fat_e_obs_int_{id_edit_fat}")
                    novos_anexos_fat = st.file_uploader("Adicionar arquivos neste faturamento:", accept_multiple_files=True, key=f"fat_e_anexos_{id_edit_fat}")
                    conn_ax = conectar_banco()
                    cax = conn_ax.cursor()
                    cax.execute("SELECT id, tipo, nome_arquivo, mime_type, arquivo FROM faturamento_anexos WHERE faturamento_id=? ORDER BY id DESC", (id_edit_fat,))
                    anexos_fat = [dict(a) for a in cax.fetchall()]
                    conn_ax.close()
                    for anexo_fat in anexos_fat:
                        st.download_button(
                            f"Baixar {anexo_fat.get('nome_arquivo')}",
                            data=anexo_fat.get("arquivo"),
                            file_name=anexo_fat.get("nome_arquivo") or "arquivo",
                            mime=anexo_fat.get("mime_type") or "application/octet-stream",
                            key=f"baixar_fat_anexo_{anexo_fat.get('id')}",
                        )
                    st.markdown("#### Gerar PDFs de orçamento a partir deste faturamento")
                    conn_orc_exist = conectar_banco()
                    corc_exist = conn_orc_exist.cursor()
                    corc_exist.execute(
                        "SELECT orc_id, numero, alterado_em FROM orcamentos WHERE faturamento_id=? AND status=? ORDER BY orc_id DESC LIMIT 1",
                        (id_edit_fat, "Gerado pelo faturamento"),
                    )
                    orc_existente_fat = corc_exist.fetchone()
                    conn_orc_exist.close()
                    if orc_existente_fat:
                        st.info(f"Já existe orçamento gerado para este faturamento: #{orc_existente_fat.get('numero') or orc_existente_fat.get('orc_id')}. Ao clicar no botão, ele será atualizado.")
                    tipo_orc_fat = st.selectbox("Tipo para salvar no gerador:", ["Serviço", "Produto"], key=f"fat_tipo_orc_pdf_{id_edit_fat}")
                    if st.button("Gerar 3 PDFs e salvar no Gerador de Orçamentos", type="primary", width="stretch", key=f"fat_gerar_orc_pdfs_{id_edit_fat}"):
                        if not itens_editados:
                            st.error("Informe pelo menos um item para gerar os orçamentos.")
                        else:
                            conn_go = conectar_banco()
                            cgo = conn_go.cursor()
                            cgo.execute(
                                "SELECT * FROM orcamentos WHERE faturamento_id=? AND status=? ORDER BY orc_id DESC LIMIT 1",
                                (id_edit_fat, "Gerado pelo faturamento"),
                            )
                            orc_existente = cgo.fetchone()
                            if orc_existente:
                                novo_numero_orc = orc_existente.get("numero") or f"FAT{id_edit_fat}"
                            else:
                                cgo.execute("SELECT numero FROM orcamentos ORDER BY orc_id DESC LIMIT 1")
                                ultimo_orc = cgo.fetchone()
                                try:
                                    novo_numero_orc = str(int(ultimo_orc[0]) + 1) if ultimo_orc and str(ultimo_orc[0]).isdigit() else f"FAT{id_edit_fat}"
                                except Exception:
                                    novo_numero_orc = f"FAT{id_edit_fat}"
                            itens_orc_fat = [
                                {
                                    "d": item.get("desc") or "",
                                    "tipo_item": item.get("tipo_item") or "Serviço",
                                    "q": int(item.get("qtd") or 0),
                                    "v": float(item.get("vunit") or 0),
                                    "t": float(item.get("vtotal") or 0),
                                }
                                for item in itens_editados
                            ]
                            dados_pdf_fat = dados_orcamento_base(
                                novo_numero_orc, e_cliente, e_cnpj, itens_orc_fat, e_forma,
                                "", f"Gerado pelo faturamento #{id_edit_fat}. Tipo: {tipo_orc_fat}. {e_obs or ''}",
                                date.today().strftime("%d/%m/%Y"),
                            )
                            valores_orc_fat = (
                                novo_numero_orc, data_para_banco_br(date.today()), e_cliente, e_cnpj,
                                formata_moeda(e_valor), e_forma, "", dados_pdf_fat.get("obs_geral"),
                                json.dumps(itens_orc_fat, ensure_ascii=False), "Gerado pelo faturamento", id_edit_fat,
                            )
                            if orc_existente:
                                orc_id_fat = orc_existente.get("orc_id")
                                cgo.execute("""UPDATE orcamentos SET numero=?, data_orc=?, cliente=?, cpf_cnpj=?,
                                            valor_total=?, forma_pagamento=?, obs_pag=?, obs_geral=?, itens=?,
                                            status=?, faturamento_id=?, alterado_por=?, alterado_em=?
                                            WHERE orc_id=?""",
                                            valores_orc_fat + (st.session_state.get("username", ""), agora_br(), orc_id_fat))
                            else:
                                cgo.execute("""INSERT INTO orcamentos
                                            (numero, data_orc, cliente, cpf_cnpj, valor_total, forma_pagamento,
                                             obs_pag, obs_geral, itens, status, faturamento_id)
                                            VALUES (?,?,?,?,?,?,?,?,?,?,?)""", valores_orc_fat)
                                orc_id_fat = cgo.lastrowid
                            salvar_pdfs_orcamento(cgo, orc_id_fat, dados_pdf_fat)
                            conn_go.commit()
                            conn_go.close()
                            if orc_existente:
                                st.success(f"Orçamento #{novo_numero_orc} atualizado no gerador.")
                            else:
                                st.success(f"Orçamento #{novo_numero_orc} salvo no gerador com os 3 PDFs.")
                            st.rerun()
                    if st.button("Salvar alterações do faturamento", type="primary", key=f"fat_btn_edit_{id_edit_fat}"):
                        status_original_fat = fat_edit.get("status") or "Aberto"
                        status_para_salvar = "Aberto" if e_status == "Faturado" and status_original_fat != "Faturado" else e_status
                        conn_ef = conectar_banco()
                        cef = conn_ef.cursor()
                        cef.execute("""UPDATE faturamento SET data_lanc=?, cliente=?, cnpj=?, tipo=?, emite_nf=?,
                                    tipo_nota=?, forma_pag=?, itens=?, vencimento=?, valor_total=?,
                                    obs_interna=?, obs_nota=?, status=?, alterado_por=?, alterado_em=?
                                    WHERE id=?""",
                                    (data_para_banco_br(e_data), e_cliente, e_cnpj, e_tipo, e_emite_nf,
                                     e_tipo_nota, e_forma, json.dumps(itens_editados, ensure_ascii=False),
                                     data_para_banco_br(e_venc), e_valor, e_obs_interna, e_obs, status_para_salvar,
                                     st.session_state.get("username", ""), agora_br(), id_edit_fat))
                        for arq_fat in novos_anexos_fat or []:
                            if arq_fat and not upload_dentro_limite(arq_fat):
                                erro_upload_grande(arq_fat.name)
                                st.stop()
                            dados_arq, nome_arq, mime_arq = dados_upload(arq_fat)
                            cef.execute("""INSERT INTO faturamento_anexos
                                        (faturamento_id, tipo, nome_arquivo, mime_type, arquivo, criado_por, criado_em)
                                        VALUES (?,?,?,?,?,?,?)""",
                                        (id_edit_fat, "Faturamento", nome_arq, mime_arq, dados_arq,
                                         st.session_state.get("username", ""), agora_br()))
                        conn_ef.commit()
                        conn_ef.close()
                        if e_status == "Faturado" and status_original_fat != "Faturado":
                            fat_integrar = dict(fat_edit)
                            fat_integrar.update({
                                "data_lanc": data_para_banco_br(e_data),
                                "cliente": e_cliente,
                                "cnpj": e_cnpj,
                                "tipo": e_tipo,
                                "emite_nf": e_emite_nf,
                                "tipo_nota": e_tipo_nota,
                                "forma_pag": e_forma,
                                "itens": json.dumps(itens_editados, ensure_ascii=False),
                                "vencimento": data_para_banco_br(e_venc),
                                "valor_total": e_valor,
                                "obs_interna": e_obs_interna,
                                "obs_nota": e_obs,
                                "status": status_original_fat,
                            })
                            resultado_fat = faturar_lancamento_com_integracoes(fat_integrar)
                            if resultado_fat.get("ok"):
                                st.success(resultado_fat.get("mensagem"))
                            else:
                                st.error(resultado_fat.get("mensagem"))
                        else:
                            st.success("Faturamento atualizado.")
                        st.rerun()

            if st.session_state.get('is_admin', 0) or tem_permissao("faturamento.delete"):
                del_id = st.number_input("ID para excluir:", min_value=1, step=1, key="fat_del_id")
                fat_excluir = next((dict(r) for r in rows_fat if int(r.get("id") or 0) == int(del_id)), None)
                if fat_excluir:
                    st.warning(
                        f"Você está prestes a excluir o faturamento #{del_id} de "
                        f"{fat_excluir.get('cliente') or 'cliente não informado'}, no valor de "
                        f"{formatar_moeda_br(fat_excluir.get('valor_total'))}."
                    )
                confirmar_exclusao_fat = st.checkbox(
                    "Confirmo que desejo excluir permanentemente este lançamento.",
                    key=f"fat_confirmar_exclusao_{del_id}",
                )
                if st.button("Excluir Lançamento", key="btn_del_fat", disabled=not confirmar_exclusao_fat or not fat_excluir):
                    deletar_registro('faturamento', 'id', del_id)
                    st.toast("Lançamento excluído!")
                    st.rerun()
        else:
            st.info("Nenhum lançamento registrado ainda.")

    with aba_fat3:
        st.subheader("Exportar Faturamento para Excel")
        st.write("Baixe o modelo vazio ou exporte os faturamentos já cadastrados com todos os itens.")

        def gerar_excel_faturamento():
            from openpyxl import Workbook
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

            wb2 = Workbook()
            ws2 = wb2.active
            ws2.title = "Faturamento"

            MOEDA  = '_-"R$"\\ * #,##0.00_-;\\-"R$"\\ * #,##0.00_-;_-"R$"\\ * "-"??_-;_-@_-'
            DATA   = 'dd/mm/yyyy'
            PERC   = '0.00%'
            thin   = Side(style='thin')
            medium = Side(style='medium')

            def brd(l=None,r=None,t=None,b=None):
                return Border(left=l or Side(), right=r or Side(), top=t or Side(), bottom=b or Side())
            def fnt(bold=False, size=11, color='000000'):
                return Font(name='Calibri', size=size, bold=bold, color=color)
            def aln(h='center', v='center', wrap=False):
                return Alignment(horizontal=h, vertical=v, wrap_text=wrap)

            fill_az  = PatternFill('solid', fgColor='BDD7EE')
            fill_vd  = PatternFill('solid', fgColor='E2EFDA')
            fill_am  = PatternFill('solid', fgColor='FFFF00')
            fill_cz  = PatternFill('solid', fgColor='D9D9D9')
            fill_az2 = PatternFill('solid', fgColor='2E74B5')
            fill_fc  = PatternFill('solid', fgColor='FCE4D6')
            fill_ffc = PatternFill('solid', fgColor='FFF2CC')

            colunas2 = [
                ('A','Cliente',                        fill_az, 23),
                ('B','CNPJ',                           fill_az, 20),
                ('C','3 Orçamentos',                   fill_vd, 13),
                ('D','Descritivo Itens',               fill_az, 42),
                ('E','Emite Nota Fiscal',              fill_az, 13),
                ('F','Tipo de Nota Fiscal',            fill_az, 20),
                ('G','Valor Unitário (R$)',            fill_az, 17),
                ('H','Quantidade',                     fill_az, 17),
                ('I','Valor Total Item (R$)',          fill_az, 15),
                ('J','Valor Total Faturar (R$)',       fill_vd, 17),
                ('K','Qtd Parcelas',                   fill_az, 15),
                ('L','Vencimento 1ª Parcela',          fill_az, 15),
                ('M','Forma de Pagamento',             fill_vd, 14),
                ('N','Mensal ou Eventual',             fill_az, 16),
                ('O','Valor do Orçamento (R$)',        fill_az, 16),
                ('P','Observação (interno)',           fill_az, 53),
                ('Q','Informações complementares\n(lançamento/nota)', fill_am, 47),
            ]

            ws2.row_dimensions[1].height = 45
            for cl, hdr, fl, wd in colunas2:
                cell = ws2[f'{cl}1']
                cell.value = hdr
                cell.font = fnt(bold=True)
                cell.fill = fl
                cell.alignment = aln(wrap=True)
                cell.border = brd(l=medium if cl=='A' else thin,
                                  r=medium if cl=='Q' else thin,
                                  t=medium, b=thin)
                ws2.column_dimensions[cl].width = wd

            next_r = 2
            data_starts = []
            for _ in range(20):
                sr = next_r
                er = sr + 2
                data_starts.append((sr, er))
                for r in range(sr, er + 1):
                    ws2.row_dimensions[r].height = 28 if r <= er else 8
                    for col in range(1, 18):
                        cell = ws2.cell(row=r, column=col)
                        cell.font = fnt(size=10)
                        cell.alignment = aln(h='left', v='center', wrap=True)
                        cell.border = brd(
                            l=medium if col==1 else thin,
                            r=medium if col==17 else thin,
                            t=medium if r==sr else thin,
                            b=medium if r==er else thin
                        )
                    ws2.cell(row=r, column=9).value  = f'=G{r}*H{r}'
                    ws2.cell(row=r, column=9).number_format = MOEDA
                    ws2.cell(row=r, column=7).number_format = MOEDA
                    ws2.cell(row=r, column=10).number_format = MOEDA
                    ws2.cell(row=r, column=12).number_format = DATA
                    ws2.cell(row=r, column=17).fill = fill_am
                    if r == sr:
                        ws2.cell(row=r, column=5).value  = 'Sim'
                        ws2.cell(row=r, column=13).value = 'Sim'
                        ws2.cell(row=r, column=14).value = 'Eventual'
                        jc = ws2.cell(row=r, column=10)
                        jc.value = f'=SUM(I{sr}:I{er})'
                        jc.fill = fill_vd
                        jc.font = fnt(bold=True, size=10)
                sep = er + 1
                ws2.row_dimensions[sep].height = 8
                ws2.merge_cells(f'A{sep}:Q{sep}')
                ws2.cell(sep, 1).fill = PatternFill('solid', fgColor='E7E6E6')
                next_r = sep + 1

            tr = next_r
            ws2.row_dimensions[tr].height = 5
            ws2.merge_cells(f'A{tr}:Q{tr}')
            ws2.cell(tr, 1).fill = fill_az2
            tr += 1

            fd = data_starts[0][0]
            ld = data_starts[-1][1]

            def tlabel(r2, txt, fl=None):
                fl = fl or fill_cz
                ws2.row_dimensions[r2].height = 22
                ws2.merge_cells(f'A{r2}:I{r2}')
                c2 = ws2.cell(r2, 1)
                c2.value = txt; c2.font = fnt(bold=True); c2.fill = fl
                c2.alignment = aln(h='left'); c2.border = brd(l=medium, r=thin, t=thin, b=thin)
                for col in range(10, 18): ws2.cell(r2, col).fill = fl

            def tval(r2, formula, fl=None, bold2=True, fmt=MOEDA):
                fl = fl or fill_cz
                jc2 = ws2.cell(r2, 10)
                jc2.value = formula; jc2.font = fnt(bold=bold2); jc2.fill = fl
                jc2.number_format = fmt
                jc2.alignment = aln(h='right'); jc2.border = brd(l=thin, r=medium, t=thin, b=thin)

            tlabel(tr, 'Faturamento Total Bruto', PatternFill('solid', fgColor='BDD7EE'))
            tval(tr, f'=SUM(J{fd}:J{ld})', PatternFill('solid', fgColor='BDD7EE'))
            r_tot = tr; tr += 1

            tlabel(tr, '   Faturamento Avulsos Sem Nota')
            tval(tr, '', bold2=False)
            r_sem = tr; tr += 1

            tlabel(tr, '   Faturamento com Nota (base imposto)')
            tval(tr, f'=J{r_tot}-J{r_sem}')
            r_com = tr; tr += 1

            ws2.row_dimensions[tr].height = 20
            ws2.merge_cells(f'A{tr}:I{tr}')
            ws2.cell(tr,1).value = '   Percentual Impostos (ISS)'
            ws2.cell(tr,1).font  = fnt(size=10); ws2.cell(tr,1).fill = fill_cz
            ws2.cell(tr,1).alignment = aln(h='left')
            alc = ws2.cell(tr, 10)
            alc.value = 0.06442; alc.number_format = PERC
            alc.font  = fnt(color='0000FF')
            alc.fill  = fill_am; alc.alignment = aln(h='right')
            alc.border = brd(l=thin, r=medium, t=thin, b=thin)
            for col in range(11,18): ws2.cell(tr,col).fill = fill_cz
            r_alq = tr; tr += 1

            tlabel(tr, '   Previsão Impostos – Avulsos', fill_fc)
            tval(tr, f'=J{r_com}*J{r_alq}', fill_fc)
            r_ia = tr; tr += 1

            tlabel(tr, '   Saldo Avulsos (após impostos)', PatternFill('solid', fgColor='E2EFDA'))
            tval(tr, f'=J{r_com}-J{r_ia}', PatternFill('solid', fgColor='E2EFDA'))
            r_sa = tr; tr += 2

            tlabel(tr, 'Faturamento Mensal (base)', PatternFill('solid', fgColor='BDD7EE'))
            tval(tr, '', PatternFill('solid', fgColor='BDD7EE'), bold2=False)
            r_mn = tr; tr += 1

            tlabel(tr, '   Previsão Impostos – Mensal', fill_fc)
            tval(tr, f'=J{r_mn}*J{r_alq}', fill_fc)
            r_im = tr; tr += 1

            tlabel(tr, '   Saldo Mensal (após impostos)', PatternFill('solid', fgColor='E2EFDA'))
            tval(tr, f'=J{r_mn}-J{r_im}', PatternFill('solid', fgColor='E2EFDA'))
            r_sm = tr; tr += 2

            ws2.row_dimensions[tr].height = 26
            ws2.merge_cells(f'A{tr}:I{tr}')
            c2 = ws2.cell(tr,1)
            c2.value='VALOR TOTAL A RECEBER'; c2.font=fnt(bold=True,size=12,color='FFFFFF')
            c2.fill=fill_az2; c2.alignment=aln(h='left')
            c2.border=brd(l=medium,r=thin,t=medium,b=medium)
            jc2 = ws2.cell(tr,10)
            jc2.value=f'=J{r_sa}+J{r_sm}'; jc2.font=fnt(bold=True,size=12,color='FFFFFF')
            jc2.fill=fill_az2; jc2.number_format=MOEDA
            jc2.alignment=aln(h='right'); jc2.border=brd(l=thin,r=medium,t=medium,b=medium)
            for col in range(11,18): ws2.cell(tr,col).fill=fill_az2
            tr += 2

            ws2.row_dimensions[tr].height = 22
            ws2.merge_cells(f'A{tr}:I{tr}')
            c2=ws2.cell(tr,1)
            c2.value='Total Guia Impostos (ISS)'; c2.font=fnt(bold=True)
            c2.fill=fill_ffc; c2.alignment=aln(h='left')
            c2.border=brd(l=medium,r=thin,t=thin,b=medium)
            jc2=ws2.cell(tr,10)
            jc2.value=f'=J{r_ia}+J{r_im}'; jc2.font=fnt(bold=True)
            jc2.fill=fill_ffc; jc2.number_format=MOEDA
            jc2.alignment=aln(h='right'); jc2.border=brd(l=thin,r=medium,t=thin,b=medium)
            for col in range(11,18): ws2.cell(tr,col).fill=fill_ffc
            tr += 2

            ws2.merge_cells(f'A{tr}:Q{tr}')
            nota2 = ws2.cell(tr,1)
            nota2.value = 'Vencimento do boleto para Eventuais: sempre 5 dias úteis a contar da emissão da nota fiscal.'
            nota2.font = fnt(bold=True,size=10,color='7B3F00')
            nota2.fill = PatternFill('solid', fgColor='92D050')
            nota2.alignment = aln(h='left', wrap=True)
            nota2.border = brd(l=medium,r=medium,t=medium,b=medium)
            ws2.row_dimensions[tr].height = 22

            ws2.freeze_panes = 'A2'
            ws2.auto_filter.ref = 'A1:Q1'

            buf = io.BytesIO()
            wb2.save(buf)
            buf.seek(0)
            return buf.getvalue()

        modo_export_fat = st.radio(
            "O que deseja exportar?",
            ["Modelo vazio para preenchimento", "Faturamentos cadastrados"],
            horizontal=True,
            key="fat_modo_export",
        )
        if modo_export_fat == "Modelo vazio para preenchimento":
            excel_bytes = gerar_excel_faturamento()
            st.download_button(
                label="Baixar Planilha Modelo de Faturamento (.xlsx)",
                data=excel_bytes,
                file_name=f"modelo_faturamento_{date.today().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch",
                type="primary"
            )
            st.caption("Planilha com 20 blocos de clientes, fórmulas automáticas de totais, previsão de impostos (ISS 6,44%) e resumo financeiro.")
        else:
            rows_export_fat = repo_listar_faturamentos(conectar_banco)
            rows_export_fat = filtrar_registros_por_empresa(rows_export_fat, "cliente")

            ex1, ex2, ex3, ex4 = st.columns(4)
            data_exp_ini = ex1.date_input("Data inicial:", value=None, key="fat_exp_ini")
            data_exp_fim = ex2.date_input("Data final:", value=None, key="fat_exp_fim")
            cliente_exp = ex3.selectbox("Cliente:", ["Todos"] + sorted({r.get("cliente") or "" for r in rows_export_fat if r.get("cliente")}), key="fat_exp_cliente")
            status_exp = ex4.selectbox("Status:", ["Todos", "Aberto", "Faturado", "Cancelado"], key="fat_exp_status")

            rows_export_filtrados = list(rows_export_fat)
            if data_exp_ini:
                rows_export_filtrados = [r for r in rows_export_filtrados if parse_data_flex(r.get("data_lanc")) and parse_data_flex(r.get("data_lanc")) >= data_exp_ini]
            if data_exp_fim:
                rows_export_filtrados = [r for r in rows_export_filtrados if parse_data_flex(r.get("data_lanc")) and parse_data_flex(r.get("data_lanc")) <= data_exp_fim]
            if cliente_exp != "Todos":
                rows_export_filtrados = [r for r in rows_export_filtrados if (r.get("cliente") or "") == cliente_exp]
            if status_exp != "Todos":
                rows_export_filtrados = [r for r in rows_export_filtrados if (r.get("status") or "Aberto") == status_exp]

            todos_itens_export = sorted({
                item.get("desc") or ""
                for r in rows_export_filtrados
                for item in itens_faturamento_lista(r.get("itens"))
                if item.get("desc")
            })
            item_exp = st.selectbox("Exportar item:", ["Todos"] + todos_itens_export, key="fat_exp_item")
            linhas_previas = linhas_faturamento_export(rows_export_filtrados, item_filtro=item_exp)
            p1, p2, p3 = st.columns(3)
            p1.metric("Faturamentos", len(rows_export_filtrados))
            p2.metric("Linhas de itens", len(linhas_previas))
            p3.metric("Total dos itens", formatar_moeda_br(sum(float(l.get("Valor Total Item") or 0) for l in linhas_previas)))
            if linhas_previas:
                st.dataframe(linhas_previas, width="stretch", hide_index=True)
                st.download_button(
                    label="Baixar faturamentos cadastrados (.xlsx)",
                    data=gerar_excel_faturamentos_registrados(rows_export_filtrados, "Faturamentos Cadastrados", item_filtro=item_exp),
                    file_name=f"faturamentos_{date.today().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width="stretch",
                    type="primary",
                )
            else:
                st.info("Nenhum faturamento/item encontrado para exportar com os filtros selecionados.")

    if False:
        st.subheader("Preparação e Controle de Emissão de Nota Fiscal")
        st.caption("A transmissão oficial dependerá da integração com a prefeitura ou provedor fiscal.")

        faturamentos_nf = filtrar_registros_por_empresa(repo_listar_faturamentos_para_nf(conectar_banco), "cliente")

        opcoes_nf = ["-- Selecionar lançamento --"] + [
            f"{f['id']} - {f.get('cliente') or ''} - {formatar_moeda_br(f.get('valor_total'))}" for f in faturamentos_nf
        ]
        escolha_nf = st.selectbox("Lançamento para preparar a nota:", opcoes_nf, key="nf_faturamento")
        fat_nf = None
        if escolha_nf != "-- Selecionar lançamento --":
            fat_nf_id = int(escolha_nf.split(" - ", 1)[0])
            fat_nf = next((f for f in faturamentos_nf if f["id"] == fat_nf_id), None)

        descricao_nf_padrao = ""
        if fat_nf:
            try:
                descricao_nf_padrao = "\n".join(
                    f"{item.get('desc', '')} - Qtd: {item.get('qtd', 0)} - Total: {formatar_moeda_br(item.get('vtotal'))}"
                    for item in json.loads(fat_nf.get("itens") or "[]")
                )
            except Exception:
                descricao_nf_padrao = fat_nf.get("obs_nota") or ""

        nf1, nf2, nf3 = st.columns(3)
        nf_cliente = nf1.text_input("Cliente da nota:", value=(fat_nf.get("cliente") or "") if fat_nf else "", disabled=True)
        nf_documento = nf2.text_input("CPF/CNPJ:", value=(fat_nf.get("cnpj") or "") if fat_nf else "", disabled=True)
        nf_tipo = nf3.selectbox("Tipo de nota:", ["Serviço", "Produto"], index=1 if fat_nf and fat_nf.get("tipo_nota") == "Produto" else 0)
        nf4, nf5, nf6 = st.columns(3)
        nf_competencia = nf4.date_input("Competência:", value=date.today(), key="nf_competencia")
        nf_codigo_servico = nf5.text_input("Código do serviço/produto:", key="nf_codigo_servico")
        nf_municipio = nf6.text_input("Município da prestação:", value="Belo Horizonte / MG", key="nf_municipio")
        nf_descricao = st.text_area("Descrição da nota:", value=descricao_nf_padrao, height=120, key="nf_descricao")
        nf7, nf8, nf9 = st.columns(3)
        nf_valor = nf7.number_input("Valor da nota R$:", min_value=0.0, value=float(fat_nf.get("valor_total") or 0) if fat_nf else 0.0, step=0.01, format="%.2f", key="nf_valor")
        nf_aliquota = nf8.number_input("Alíquota ISS %:", min_value=0.0, value=0.0, step=0.01, format="%.4f", key="nf_aliquota")
        nf_valor_iss = nf_valor * nf_aliquota / 100
        nf9.metric("ISS estimado", formatar_moeda_br(nf_valor_iss))
        nf_observacoes = st.text_area("Observações para emissão:", value=(fat_nf.get("obs_nota") or "") if fat_nf else "", height=70, key="nf_observacoes")

        if st.button("Salvar nota para emissão", type="primary", width="stretch", key="salvar_nota_emissao"):
            if not fat_nf:
                st.error("Selecione um lançamento de faturamento.")
            elif not nf_documento.strip():
                st.error("O cliente precisa ter CPF/CNPJ cadastrado.")
            elif not nf_descricao.strip() or nf_valor <= 0:
                st.error("Informe descrição e valor maior que zero.")
            else:
                conn_snf = conectar_banco()
                csnf = conn_snf.cursor()
                csnf.execute("SELECT id FROM notas_fiscais WHERE faturamento_id=? LIMIT 1", (fat_nf["id"],))
                existente_nf = csnf.fetchone()
                valores_nf = (
                    nf_cliente, nf_documento, nf_tipo, data_para_banco_br(nf_competencia), nf_descricao,
                    nf_valor, nf_aliquota, nf_valor_iss, nf_codigo_servico, nf_municipio, nf_observacoes,
                )
                if existente_nf:
                    csnf.execute("""UPDATE notas_fiscais SET cliente=?, cpf_cnpj=?, tipo_nota=?, data_competencia=?,
                                    descricao=?, valor_servicos=?, aliquota_iss=?, valor_iss=?, codigo_servico=?,
                                    municipio_prestacao=?, observacoes=? WHERE id=?""", valores_nf + (existente_nf["id"],))
                else:
                    csnf.execute("""INSERT INTO notas_fiscais
                                    (cliente, cpf_cnpj, tipo_nota, data_competencia, descricao, valor_servicos,
                                     aliquota_iss, valor_iss, codigo_servico, municipio_prestacao, observacoes,
                                     faturamento_id, status, criado_por, criado_em)
                                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                                 valores_nf + (fat_nf["id"], "Pendente", st.session_state.get("username", ""), datetime.now().strftime("%d/%m/%Y %H:%M")))
                conn_snf.commit()
                conn_snf.close()
                st.success("Nota adicionada/atualizada na fila de emissão.")
                st.rerun()

        st.write("---")
        st.markdown("#### Fila de notas")
        conn_lnf = conectar_banco()
        clnf = conn_lnf.cursor()
        clnf.execute("SELECT * FROM notas_fiscais ORDER BY id DESC")
        notas_nf = filtrar_registros_por_empresa([dict(r) for r in clnf.fetchall()], "cliente")
        conn_lnf.close()

        if notas_nf:
            st.dataframe([{
                "ID": n.get("id"), "Faturamento": n.get("faturamento_id"), "Cliente": n.get("cliente"),
                "CPF/CNPJ": n.get("cpf_cnpj"), "Tipo": n.get("tipo_nota"),
                "Valor": formatar_moeda_br(n.get("valor_servicos")), "ISS": formatar_moeda_br(n.get("valor_iss")),
                "Status": n.get("status"), "Número": n.get("numero_nota"), "Emitida em": n.get("emitido_em"),
            } for n in notas_nf], width="stretch", hide_index=True)

            id_nf = st.number_input("ID da nota para atualizar:", min_value=1, step=1, key="id_nota_atualizar")
            nota_nf = next((n for n in notas_nf if n.get("id") == id_nf), None)
            if nota_nf:
                statuses_nf = ["Pendente", "Pronta para emissão", "Emitida", "Cancelada", "Erro"]
                un1, un2 = st.columns(2)
                status_nf = un1.selectbox("Status:", statuses_nf, index=statuses_nf.index(nota_nf.get("status") or "Pendente"), key=f"status_nota_{id_nf}")
                numero_nf = un2.text_input("Número da nota:", value=nota_nf.get("numero_nota") or "", key=f"numero_nota_{id_nf}")
                chave_nf = st.text_input("Chave/código de verificação:", value=nota_nf.get("chave_acesso") or "", key=f"chave_nota_{id_nf}")
                link_nf = st.text_input("Link da nota/PDF:", value=nota_nf.get("link_nota") or "", key=f"link_nota_{id_nf}")
                if st.button("Atualizar situação da nota", type="primary", key=f"atualizar_nota_{id_nf}"):
                    emitido_em_nf = datetime.now().strftime("%d/%m/%Y %H:%M") if status_nf == "Emitida" else nota_nf.get("emitido_em")
                    conn_unf = conectar_banco()
                    cunf = conn_unf.cursor()
                    cunf.execute("""UPDATE notas_fiscais SET status=?, numero_nota=?, chave_acesso=?,
                                    link_nota=?, emitido_em=? WHERE id=?""",
                                 (status_nf, numero_nf, chave_nf, link_nf, emitido_em_nf, id_nf))
                    conn_unf.commit()
                    conn_unf.close()
                    st.success("Situação da nota atualizada.")
                    st.rerun()
        else:
            st.info("Nenhuma nota preparada para emissão.")

def renderizar_faturado(ctx: dict) -> None:
    aplicar_contexto_pagina(ctx, globals())
    if not (tem_permissao("faturamento.faturado") or tem_permissao("faturamento.view")):
        st.error("Você não tem permissão para acessar este módulo.")
        st.stop()

    st.title("Faturado")
    st.caption("Itens aprovados no faturamento separados por Produto e Serviço para emissão de nota.")
    aba_faturado_lista, aba_faturado_emissao, aba_faturado_notas, aba_faturado_documentos = st.tabs([
        "Faturados", "Emissão de Nota", "Notas Emitidas", "Enviar documentos"
    ])

    with aba_faturado_emissao:
        st.subheader("Preparação e Controle de Emissão de Nota Fiscal")
        st.caption("Selecione um faturamento já faturado e prepare nota de produto ou serviço.")

        faturamentos_nf_faturado = filtrar_registros_por_empresa(repo_listar_faturados_para_nf(conectar_banco), "cliente")

        opcoes_nf_faturado = ["-- Selecionar faturamento --"] + [
            f"{f['id']} - {f.get('cliente') or ''} - {formatar_moeda_br(f.get('valor_total'))}" for f in faturamentos_nf_faturado
        ]
        escolha_nf_faturado = st.selectbox("Faturamento para preparar a nota:", opcoes_nf_faturado, key="faturado_nf_faturamento")
        fat_nf_faturado = None
        if escolha_nf_faturado != "-- Selecionar faturamento --":
            fat_nf_id_faturado = int(escolha_nf_faturado.split(" - ", 1)[0])
            fat_nf_faturado = next((f for f in faturamentos_nf_faturado if int(f["id"]) == fat_nf_id_faturado), None)

        fat_nf_key = str(fat_nf_faturado.get("id") if fat_nf_faturado else "sem_faturamento")

        def buscar_cliente_faturamento(nome_cliente):
            if not nome_cliente:
                return None
            conn_cli_nf = conectar_banco()
            try:
                c_cli_nf = conn_cli_nf.cursor(dictionary=True)
                c_cli_nf.execute("""
                    SELECT * FROM clientes
                    WHERE nome=%s OR nome LIKE %s
                    ORDER BY CASE WHEN nome=%s THEN 0 ELSE 1 END, id DESC
                    LIMIT 1
                """, (nome_cliente, f"%{nome_cliente}%", nome_cliente))
                return c_cli_nf.fetchone()
            except Exception:
                return None
            finally:
                conn_cli_nf.close()

        cliente_nf_cadastro = buscar_cliente_faturamento(fat_nf_faturado.get("cliente") if fat_nf_faturado else "")
        itens_nf_faturado = itens_faturamento_lista(fat_nf_faturado.get("itens")) if fat_nf_faturado else []

        def normalizar_tipo_nf(valor):
            texto = str(valor or "").strip().lower()
            if "prod" in texto:
                return "Produto"
            return "Serviço"

        tipo_nf_padrao = normalizar_tipo_nf(fat_nf_faturado.get("tipo_nota") if fat_nf_faturado else "")

        def tipo_item_nf(item):
            return normalizar_tipo_nf(item.get("tipo_item") or tipo_nf_padrao)

        tipos_disponiveis_nf = sorted({tipo_item_nf(item) for item in itens_nf_faturado}) or [tipo_nf_padrao]
        nf_tipo_faturado = st.selectbox("Tipo de nota:", tipos_disponiveis_nf, key=f"faturado_nf_tipo_{fat_nf_key}")
        itens_tipo_nf = [item for item in itens_nf_faturado if tipo_item_nf(item) == nf_tipo_faturado]
        descricao_nf_faturado = "\n".join(
            f"{item.get('desc', '')} - Qtd: {item.get('qtd', 0)} - Total: {formatar_moeda_br(item.get('vtotal'))}"
            for item in itens_tipo_nf
        )
        valor_nf_faturado = sum(float(item.get("vtotal") or 0) for item in itens_tipo_nf)
        nf_cliente_padrao = (fat_nf_faturado.get("cliente") or (cliente_nf_cadastro or {}).get("nome") or "") if fat_nf_faturado else ""
        nf_doc_padrao = (
            fat_nf_faturado.get("cnpj")
            or fat_nf_faturado.get("cpf_cnpj")
            or (cliente_nf_cadastro or {}).get("cnpj")
            or (cliente_nf_cadastro or {}).get("cpf_cnpj")
            or ""
        ) if fat_nf_faturado else ""
        nf_doc_original_faturamento = (
            fat_nf_faturado.get("cnpj")
            or fat_nf_faturado.get("cpf_cnpj")
            or ""
        ) if fat_nf_faturado else ""
        if fat_nf_faturado:
            fat_nf_faturado["cliente"] = nf_cliente_padrao
            fat_nf_faturado["cnpj"] = nf_doc_padrao
            if cliente_nf_cadastro:
                fat_nf_faturado["telefone"] = fat_nf_faturado.get("telefone") or cliente_nf_cadastro.get("telefone") or ""
                fat_nf_faturado["email"] = fat_nf_faturado.get("email") or cliente_nf_cadastro.get("email") or ""
                fat_nf_faturado["endereco"] = fat_nf_faturado.get("endereco") or montar_endereco_cliente(cliente_nf_cadastro)
        nf1, nf2, nf3 = st.columns(3)
        nf_cliente_informado = nf1.text_input("Cliente da nota:", value=nf_cliente_padrao, key=f"faturado_nf_cliente_{fat_nf_key}")
        nf_doc_informado = nf2.text_input("CPF/CNPJ:", value=nf_doc_padrao, key=f"faturado_nf_doc_{fat_nf_key}")
        nf_competencia_faturado = nf3.date_input("Competência:", value=date.today(), key=f"faturado_nf_competencia_{fat_nf_key}")
        nf_cliente_padrao = (nf_cliente_informado or nf_cliente_padrao or "").strip()
        nf_doc_padrao = (nf_doc_informado or "").strip()
        if fat_nf_faturado:
            fat_nf_faturado["cliente"] = nf_cliente_padrao
            fat_nf_faturado["cnpj"] = nf_doc_padrao
            doc_mudou = somente_digitos(nf_doc_padrao) and somente_digitos(nf_doc_padrao) != somente_digitos(nf_doc_original_faturamento)
            if doc_mudou:
                try:
                    conn_doc_nf = conectar_banco()
                    c_doc_nf = conn_doc_nf.cursor()
                    c_doc_nf.execute("UPDATE faturamento SET cliente=?, cnpj=? WHERE id=?", (nf_cliente_padrao, nf_doc_padrao, fat_nf_faturado.get("id")))
                    conn_doc_nf.commit()
                    conn_doc_nf.close()
                    nf_doc_original_faturamento = nf_doc_padrao
                except Exception:
                    pass
        if fat_nf_faturado and not somente_digitos(nf_doc_padrao):
            st.warning("Informe o CPF/CNPJ do tomador antes de gerar ou emitir a nota.")

        conn_serv_nfse = conectar_banco()
        cserv_nfse = conn_serv_nfse.cursor(dictionary=True)
        cserv_nfse.execute("SELECT * FROM nfse_bh_servicos WHERE ativo='Sim' ORDER BY nome, id")
        servicos_nfse_bh = cserv_nfse.fetchall()
        conn_serv_nfse.close()
        opcoes_serv_nfse = ["-- Selecionar código salvo --"] + [
            f"{s.get('id')} - {s.get('nome') or 'Serviço'} | Código: {s.get('codigo_servico') or ''} | Item: {s.get('item_lista_servico') or ''}"
            for s in servicos_nfse_bh
        ]
        escolha_serv_nfse = st.selectbox("Código de serviço salvo:", opcoes_serv_nfse, key=f"faturado_nf_servico_salvo_{fat_nf_key}_{nf_tipo_faturado}")
        servico_nfse_sel = None
        if escolha_serv_nfse != "-- Selecionar código salvo --":
            servico_nfse_id = int(escolha_serv_nfse.split(" - ", 1)[0])
            servico_nfse_sel = next((s for s in servicos_nfse_bh if int(s.get("id") or 0) == servico_nfse_id), None)
        servico_nfse_key = str(servico_nfse_sel.get("id") if servico_nfse_sel else "sem_codigo")
        codigo_item_padrao = ""
        if itens_tipo_nf:
            codigo_item_padrao = itens_tipo_nf[0].get("codigo_servico") or itens_tipo_nf[0].get("codigo") or itens_tipo_nf[0].get("cod") or ""
        codigo_nf_padrao = ((servico_nfse_sel.get("codigo_servico") or "") if servico_nfse_sel else "") or codigo_item_padrao

        nf4, nf5 = st.columns(2)
        nf_codigo_faturado = nf4.text_input("Código do serviço/produto:", value=codigo_nf_padrao, key=f"faturado_nf_codigo_{fat_nf_key}_{nf_tipo_faturado}_{servico_nfse_key}")
        nf_municipio_faturado = nf5.text_input("Município da prestação:", value="Belo Horizonte / MG", key=f"faturado_nf_municipio_{fat_nf_key}")
        nf_descricao_faturado = st.text_area("Descrição da nota:", value=descricao_nf_faturado, height=120, key=f"faturado_nf_descricao_{fat_nf_key}_{nf_tipo_faturado}")
        nf6, nf7, nf8 = st.columns(3)
        nf_valor_faturado = nf6.number_input("Valor da nota R$:", min_value=0.0, value=float(valor_nf_faturado), step=0.01, format="%.2f", key=f"faturado_nf_valor_{fat_nf_key}_{nf_tipo_faturado}")
        nf_aliquota_faturado = nf7.number_input("Alíquota ISS %:", min_value=0.0, value=float(servico_nfse_sel.get("aliquota_iss") or 0) if servico_nfse_sel else 0.0, step=0.01, format="%.4f", key=f"faturado_nf_aliquota_{fat_nf_key}_{servico_nfse_key}")
        nf_valor_iss_faturado = nf_valor_faturado * nf_aliquota_faturado / 100
        nf8.metric("ISS estimado", formatar_moeda_br(nf_valor_iss_faturado))
        nf_observacoes_faturado = st.text_area("Observações para emissão:", value=(fat_nf_faturado.get("obs_nota") or "") if fat_nf_faturado else "", height=70, key=f"faturado_nf_obs_{fat_nf_key}")

        with st.expander("XML NFS-e de Serviço", expanded=False):
            st.caption("Este bloco gera NFS-e somente para itens de serviço. Produto usa NF-e/NFC-e e fica em outro modelo fiscal.")
            xml_col1, xml_col2, xml_col3 = st.columns(3)
            xml_numero_rps = xml_col1.number_input("Número do RPS:", min_value=1, value=int(fat_nf_faturado.get("id") or 1) if fat_nf_faturado else 1, step=1, key="nfse_bh_numero_rps")
            xml_numero_lote = xml_col2.number_input("Número do lote:", min_value=1, value=int(fat_nf_faturado.get("id") or 1) if fat_nf_faturado else 1, step=1, key="nfse_bh_numero_lote")
            xml_serie_rps = xml_col3.text_input("Série do RPS:", value="DS", key="nfse_bh_serie_rps")
            xml_item_lista = st.text_input("Item da lista de serviço:", value=(servico_nfse_sel.get("item_lista_servico") or "") if servico_nfse_sel else config_val("NFSE_ITEM_LISTA_SERVICO_PADRAO", ""), key="nfse_bh_item_lista")
            codigo_nacional_base = somente_digitos(xml_item_lista)
            if len(codigo_nacional_base) == 4:
                codigo_nacional_base += "01"
            elif len(codigo_nacional_base) == 5:
                codigo_nacional_base = codigo_nacional_base.zfill(6)
            xml_codigo_tributacao_nacional = st.text_input(
                "Código de tributação nacional (6 dígitos):",
                value=codigo_nacional_base,
                help="Exemplo: suporte técnico em informática = 010701. Confira o desdobro nacional aplicável.",
                key=f"nfse_codigo_tributacao_nacional_{fat_nf_key}",
            )
            with st.expander("Cadastrar novo código de serviço", expanded=False):
                novo_serv1, novo_serv2, novo_serv3 = st.columns(3)
                novo_nome_serv = novo_serv1.text_input("Nome para salvar:", key="nfse_novo_nome")
                novo_codigo_serv = novo_serv2.text_input("Código de tributação/serviço:", key="nfse_novo_codigo")
                novo_item_serv = novo_serv3.text_input("Item lista serviço:", key="nfse_novo_item")
                novo_serv4, novo_serv5 = st.columns([1, 2])
                novo_aliquota_serv = novo_serv4.number_input("Alíquota ISS %:", min_value=0.0, value=0.0, step=0.01, format="%.4f", key="nfse_novo_aliquota")
                novo_obs_serv = novo_serv5.text_input("Observação:", key="nfse_novo_obs")
                if st.button("Salvar código de serviço", width="stretch", key="nfse_salvar_codigo_servico"):
                    if not novo_nome_serv.strip():
                        st.error("Informe um nome para esse código.")
                    else:
                        conn_novo_serv = conectar_banco()
                        cnovo_serv = conn_novo_serv.cursor()
                        cnovo_serv.execute(
                            """INSERT INTO nfse_bh_servicos
                               (nome, codigo_servico, item_lista_servico, aliquota_iss, ativo, observacoes)
                               VALUES (?,?,?,?,?,?)""",
                            (novo_nome_serv, novo_codigo_serv, novo_item_serv, novo_aliquota_serv, "Sim", novo_obs_serv),
                        )
                        conn_novo_serv.commit()
                        conn_novo_serv.close()
                        st.success("Código de serviço salvo.")
                        st.rerun()
            if nf_tipo_faturado != "Serviço":
                st.info("O tipo selecionado e produto. NFS-e e apenas para servico; para produto sera necessario gerar NF-e/NFC-e em outro fluxo.")
            elif not somente_digitos(nf_doc_padrao):
                st.warning("Preencha o CPF/CNPJ do tomador acima para gerar o XML da NFS-e.")
            elif fat_nf_faturado and nf_valor_faturado > 0:
                dados_xml_nfse = {
                    "competencia": nf_competencia_faturado,
                    "codigo_servico": nf_codigo_faturado,
                    "item_lista_servico": xml_item_lista,
                    "descricao": nf_descricao_faturado,
                    "valor": nf_valor_faturado,
                    "aliquota_iss": nf_aliquota_faturado,
                    "observacoes": nf_observacoes_faturado,
                    "numero_rps": xml_numero_rps,
                    "numero_lote": xml_numero_lote,
                    "serie_rps": xml_serie_rps,
                }
                modo_nfse = config_sistema_val("NFSE_MODO_EMISSAO", "nacional")
                ambiente_nfse = config_sistema_val("NFSE_AMBIENTE", "homologacao")
                dados_dps_nacional = {
                    "ambiente": ambiente_nfse,
                    "cnpj_prestador": config_sistema_val("NFSE_CNPJ", config_sistema_val("NFSE_PRESTADOR_CNPJ", "23524449000154")),
                    "inscricao_municipal": config_sistema_val("NFSE_INSCRICAO_MUNICIPAL", config_sistema_val("NFSE_PRESTADOR_INSCRICAO_MUNICIPAL", "")),
                    "codigo_municipio": config_sistema_val("NFSE_CODIGO_MUNICIPIO", "3106200"),
                    "codigo_municipio_prestacao": config_sistema_val("NFSE_CODIGO_MUNICIPIO", "3106200"),
                    "serie_dps": config_sistema_val("NFSE_DPS_SERIE", "1"),
                    "numero_dps": xml_numero_rps,
                    "competencia": nf_competencia_faturado,
                    "codigo_tributacao_nacional": xml_codigo_tributacao_nacional,
                    "codigo_tributacao_municipal": nf_codigo_faturado,
                    "descricao": nf_descricao_faturado,
                    "valor": nf_valor_faturado,
                    "aliquota_iss": nf_aliquota_faturado,
                    "observacoes": nf_observacoes_faturado,
                    "opcao_simples_nacional": config_sistema_val("NFSE_OP_SIMPLES_NACIONAL", ""),
                    "regime_apuracao_simples": config_sistema_val("NFSE_REG_APURACAO_SIMPLES", ""),
                    "regime_especial_tributacao": config_sistema_val("NFSE_REGIME_ESPECIAL_NACIONAL", "0"),
                }
                xml_nfse_bh = gerar_xml_nfse_bh_rps(fat_nf_faturado, nf_tipo_faturado, dados_xml_nfse)
                st.download_button(
                    "Baixar XML GerarNfse PBH",
                    data=xml_nfse_bh,
                    file_name=f"nfse_pbh_gerar_nfse_{xml_numero_rps}.xml",
                    mime="application/xml",
                    width="stretch",
                    key="baixar_xml_nfse_bh",
                )
                endpoint_nfse = config_sistema_val("NFSE_ENDPOINT_SOAP", "https://bhisshomologaws.pbh.gov.br/bhiss-ws/nfse")
                endpoint_nfse_nacional = endpoint_nacional(
                    ambiente_nfse,
                    config_sistema_val("NFSE_NACIONAL_ENDPOINT", ""),
                )
                xsd_nfse = config_sistema_val("NFSE_XSD_PATH", "")
                endpoint_em_uso = endpoint_nfse_nacional if modo_nfse == "nacional" else endpoint_nfse
                st.caption(f"Modo: {modo_nfse} | Endpoint configurado para emissão: {endpoint_em_uso or 'não configurado'}")
                if modo_nfse == "nacional":
                    try:
                        xml_dps_preview = gerar_xml_dps_nacional(fat_nf_faturado, dados_dps_nacional)
                        st.download_button(
                            "Baixar XML DPS Nacional (não assinado)",
                            data=xml_dps_preview,
                            file_name=f"dps_nacional_{xml_numero_rps}.xml",
                            mime="application/xml",
                            width="stretch",
                            key="baixar_xml_dps_nacional",
                        )
                    except Exception as ex:
                        xml_dps_preview = b""
                        st.warning(f"Complete a configuração da DPS Nacional: {ex}")
                cert_diag_path = config_sistema_val("NFSE_CERT_PFX_PATH", "")
                cert_diag_password = config_sistema_val("NFSE_CERT_PASSWORD", config_val("NFSE_CERT_PASSWORD", ""))
                cnpj_prestador_nfse = config_sistema_val("NFSE_CNPJ", config_sistema_val("NFSE_PRESTADOR_CNPJ", "23524449000154"))
                with st.expander("Diagnostico do certificado A1/PFX", expanded=False):
                    st.caption(f"Certificado configurado: {cert_diag_path or 'nao configurado'}")
                    if st.button("Verificar certificado configurado", width="stretch", key=f"nfse_diag_cert_{fat_nf_key}"):
                        try:
                            info_cert = inspecionar_certificado_pfx(cert_diag_path, cert_diag_password)
                            diag1, diag2, diag3 = st.columns(3)
                            diag1.metric("CNPJ do certificado", info_cert.get("cnpj") or "-")
                            diag2.metric("CPF do certificado", info_cert.get("cpf") or "-")
                            diag3.metric("Status", "Vencido" if info_cert.get("vencido") else "Valido")
                            st.caption(f"Titular: {info_cert.get('nome') or '-'}")
                            st.caption(f"Validade: {info_cert.get('valido_de')} ate {info_cert.get('valido_ate')}")
                            if certificado_bate_com_cnpj(info_cert, cnpj_prestador_nfse):
                                st.success("O CNPJ configurado da Dsystem aparece no certificado.")
                            else:
                                st.warning(
                                    "O CNPJ configurado da Dsystem nao apareceu no certificado. "
                                    "A PBH pode recusar a conexao com erro 403."
                                )
                            if info_cert.get("vencido"):
                                st.error("O certificado esta vencido.")
                        except Exception as ex:
                            st.error(f"Falha ao ler o certificado configurado: {ex}")
                try:
                    timeout_nfse = int(float(config_sistema_val("NFSE_TIMEOUT", "30") or 30))
                except Exception:
                    timeout_nfse = 30

                col_fluxo_1, col_fluxo_2 = st.columns(2)
                if col_fluxo_1.button("Assinar e validar XML", width="stretch", key="nfse_assinar_validar"):
                    try:
                        cert_assinar_path = config_sistema_val("NFSE_CERT_PFX_PATH", "")
                        cert_assinar_password = config_sistema_val("NFSE_CERT_PASSWORD", config_val("NFSE_CERT_PASSWORD", ""))
                        if modo_nfse == "nacional":
                            xml_assinado_preview = assinar_xml_dps_nacional(
                                gerar_xml_dps_nacional(fat_nf_faturado, dados_dps_nacional),
                                cert_assinar_path,
                                cert_assinar_password,
                            )
                            erros_xml_nfse = []
                        else:
                            xml_assinado_preview = assinar_xml_nfse_bh(xml_nfse_bh, cert_assinar_path, cert_assinar_password)
                            erros_xml_nfse = validar_nfse(xml_assinado_preview, xsd_nfse or None)
                        st.session_state["nfse_xml_assinado_preview"] = xml_assinado_preview
                        st.session_state["nfse_xml_assinado_modo"] = modo_nfse
                        if erros_xml_nfse:
                            st.warning("XML assinado, mas a validação encontrou pendências: " + "; ".join(erros_xml_nfse))
                        else:
                            st.success("XML assinado e preparado para envio.")
                    except Exception as ex:
                        st.error(f"Falha ao assinar/validar XML: {ex}")

                xml_preview_assinado = st.session_state.get("nfse_xml_assinado_preview")
                if xml_preview_assinado and st.session_state.get("nfse_xml_assinado_modo") == modo_nfse:
                    st.download_button(
                        "Baixar XML DPS Nacional assinado" if modo_nfse == "nacional" else "Baixar XML GerarNfse PBH assinado",
                        data=xml_preview_assinado,
                        file_name=(f"dps_nacional_{xml_numero_rps}_assinado.xml" if modo_nfse == "nacional" else f"nfse_pbh_gerar_nfse_{xml_numero_rps}_assinado.xml"),
                        mime="application/xml",
                        width="stretch",
                        key="baixar_xml_nfse_bh_assinado",
                    )

                if col_fluxo_2.button("Emitir NFS-e completa", type="primary", width="stretch", key="nfse_emitir_completa"):
                    cert_nfse_path = config_sistema_val("NFSE_CERT_PFX_PATH", "")
                    cert_nfse_password = config_sistema_val("NFSE_CERT_PASSWORD", config_val("NFSE_CERT_PASSWORD", ""))
                    if not endpoint_em_uso:
                        st.error("Configure o endpoint/API em Configurações do Sistema > NFS-e.")
                    elif modo_nfse != "nacional" and endpoint_nfse_nacional_rest(endpoint_nfse):
                        st.error(MENSAGEM_ENDPOINT_NACIONAL_REST)
                    elif not cert_nfse_path:
                        st.error("Configure o caminho do certificado PFX em Configurações do Sistema > NFS-e.")
                    elif not cert_nfse_password:
                        st.error("Configure a senha do certificado PFX em Configura??es do Sistema > NFS-e.")
                    elif not Path(cert_nfse_path).exists():
                        st.error(f"Certificado PFX não encontrado neste caminho: {cert_nfse_path}")
                    else:
                        conn_envio_nfse = conectar_banco()
                        cenvio_nfse = conn_envio_nfse.cursor()
                        nota_id_envio = None
                        try:
                            nota_id_envio, _ = preparar_nota_fiscal_por_tipo(fat_nf_faturado, "Serviço", nf_competencia_faturado)
                            if modo_nfse == "nacional":
                                resultado_nacional = executar_fluxo_nfse_nacional(
                                    fat_nf_faturado,
                                    dados_dps_nacional,
                                    endpoint=endpoint_nfse_nacional,
                                    cert_path=cert_nfse_path,
                                    cert_password=cert_nfse_password,
                                    timeout=timeout_nfse,
                                )
                                retorno_nfse = resultado_nacional.xml_nfse or b""
                                xml_envio_nfse = resultado_nacional.xml_dps_assinado
                                retorno_info_nfse = {
                                    "status": resultado_nacional.status,
                                    "mensagem": resultado_nacional.mensagem,
                                    "protocolo": resultado_nacional.id_dps,
                                    "chave_acesso": resultado_nacional.chave_acesso,
                                    "numero_nfse": resultado_nacional.numero_nfse,
                                }
                                erros_validacao_nfse = []
                            else:
                                resultado_nfse = executar_fluxo_emissao_nfse(
                                    fat_nf_faturado,
                                    "Serviço",
                                    dados_xml_nfse,
                                    endpoint=endpoint_nfse,
                                    cert_path=cert_nfse_path,
                                    cert_password=cert_nfse_password,
                                    xsd_path=xsd_nfse or None,
                                    timeout=timeout_nfse,
                                    bloquear_com_erro_validacao=False,
                                )
                                retorno_nfse = resultado_nfse.xml_retorno or b""
                                xml_envio_nfse = resultado_nfse.xml_assinado or resultado_nfse.xml_gerado
                                retorno_info_nfse = resultado_nfse.retorno_info or {"status": resultado_nfse.status, "mensagem": resultado_nfse.mensagem}
                                erros_validacao_nfse = resultado_nfse.erros_validacao or []
                            status_salvo_nfse = salvar_retorno_nota_fiscal(nota_id_envio, xml_envio_nfse, retorno_nfse, retorno_info_nfse)
                            cenvio_nfse.execute(
                                """INSERT INTO nfse_envios
                                   (nota_id, faturamento_id, ambiente, status, protocolo, mensagem, xml_envio, xml_retorno, criado_por)
                                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                                (
                                    nota_id_envio, fat_nf_faturado.get("id"), ambiente_nfse, status_salvo_nfse,
                                    retorno_info_nfse.get("protocolo"), mensagem_retorno_nfse_legivel(retorno_info_nfse),
                                    xml_envio_nfse.decode("utf-8", errors="ignore"),
                                    retorno_nfse.decode("utf-8", errors="ignore"),
                                    st.session_state.get("username", ""),
                                ),
                            )
                            conn_envio_nfse.commit()
                            if erros_validacao_nfse:
                                st.warning("Validação: " + "; ".join(erros_validacao_nfse))
                            if status_salvo_nfse == "Autorizada":
                                st.success("NFS-e autorizada. XML e PDF foram salvos na nota.")
                            elif status_salvo_nfse == "Rejeitada":
                                st.error(mensagem_retorno_nfse_legivel(retorno_info_nfse))
                            else:
                                st.info(mensagem_retorno_nfse_legivel(retorno_info_nfse))
                            if retorno_nfse:
                                st.code(retorno_nfse.decode("utf-8", errors="ignore"), language="xml")
                        except Exception as ex:
                            cenvio_nfse.execute(
                                """INSERT INTO nfse_envios
                                   (nota_id, faturamento_id, ambiente, status, mensagem, xml_envio, criado_por)
                                   VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                                (nota_id_envio, fat_nf_faturado.get("id"), ambiente_nfse, "Erro", str(ex), (xml_dps_preview if modo_nfse == "nacional" else xml_nfse_bh).decode("utf-8", errors="ignore"), st.session_state.get("username", "")),
                            )
                            conn_envio_nfse.commit()
                            st.error(f"Falha na emissão NFS-e: {mensagem_erro_emissao_nfse(ex, endpoint_em_uso)}")
                        finally:
                            conn_envio_nfse.close()
                xml_exibicao = xml_dps_preview if modo_nfse == "nacional" else xml_nfse_bh
                if xml_exibicao:
                    st.code(xml_exibicao.decode("utf-8"), language="xml")
            else:
                st.info("Selecione um faturamento de serviço e informe valor maior que zero para gerar o XML.")

        with st.expander("XML NF-e de Produto", expanded=(nf_tipo_faturado == "Produto")):
            st.caption("Este bloco gera NF-e 4.00 para produto, assina com A1/PFX e prepara o envio SEFAZ NFeAutorizacao4.")
            if nf_tipo_faturado != "Produto":
                st.info("Selecione Produto no tipo de nota para gerar o XML de produto.")
            elif not fat_nf_faturado:
                st.info("Selecione um faturamento para gerar a nota de produto.")
            elif not itens_tipo_nf:
                st.info("Este faturamento nao tem itens classificados como produto.")
            else:
                conn_cod_prod = conectar_banco()
                ccod_prod = conn_cod_prod.cursor(dictionary=True)
                try:
                    ccod_prod.execute("SELECT nome, ncm, categoria, observacoes FROM codigos_fiscais_produtos WHERE ativo='Sim' ORDER BY nome")
                    codigos_produtos_nf = ccod_prod.fetchall()
                except Exception:
                    codigos_produtos_nf = []
                finally:
                    conn_cod_prod.close()

                opcoes_ncm = ["-- Selecionar NCM salvo --"] + [
                    f"{p.get('nome') or 'Produto'} | NCM: {p.get('ncm') or ''}"
                    for p in codigos_produtos_nf
                ]
                nfe_col1, nfe_col2, nfe_col3 = st.columns(3)
                nfe_ncm_sel = nfe_col1.selectbox("NCM do produto:", opcoes_ncm, key="nfe_produto_ncm_sel")
                nfe_ncm_manual = ""
                if nfe_ncm_sel != "-- Selecionar NCM salvo --":
                    nfe_ncm_manual = (nfe_ncm_sel.rsplit("NCM:", 1)[-1] or "").strip()
                nfe_ncm = nfe_col2.text_input("NCM final:", value=nfe_ncm_manual, key="nfe_produto_ncm")
                nfe_cfop = nfe_col3.text_input("CFOP:", value=config_sistema_val("NFE_CFOP_PADRAO", "5102"), key="nfe_produto_cfop")
                nfe_col4, nfe_col5, nfe_col6 = st.columns(3)
                nfe_unidade = nfe_col4.text_input("Unidade:", value="UN", key="nfe_produto_unidade")
                nfe_natureza = nfe_col5.text_input("Natureza da operacao:", value="Venda de mercadoria", key="nfe_produto_natureza")
                nfe_ambiente = nfe_col6.selectbox("Ambiente:", ["homologacao", "producao"], index=0, key="nfe_produto_ambiente")
                nfe_cfg1, nfe_cfg2, nfe_cfg3 = st.columns(3)
                nfe_numero = nfe_cfg1.number_input("Numero NF-e:", min_value=1, value=int(fat_nf_faturado.get("id") or 1), step=1, key="nfe_produto_numero")
                nfe_serie = nfe_cfg2.number_input("Serie NF-e:", min_value=1, value=int(config_sistema_val("NFE_SERIE", "1") or 1), step=1, key="nfe_produto_serie")
                nfe_uf = nfe_cfg3.text_input("UF emitente:", value=config_sistema_val("NFE_UF", "MG"), key="nfe_produto_uf").upper()
                nfe_emit1, nfe_emit2, nfe_emit3 = st.columns(3)
                nfe_ie_emitente_base = nfe_emit1.text_input(
                    "Inscricao Estadual:",
                    value=config_sistema_val("NFE_INSCRICAO_ESTADUAL", ""),
                    key="nfe_produto_ie_base",
                )
                nfe_regime_base = nfe_emit2.selectbox(
                    "CRT:",
                    ["1 - Simples Nacional", "2 - Simples Nacional excesso sublimite", "3 - Regime Normal"],
                    index=0,
                    key="nfe_produto_crt_base",
                )
                nfe_codigo_municipio = nfe_emit3.text_input(
                    "Codigo municipio IBGE:",
                    value=config_sistema_val("NFE_CODIGO_MUNICIPIO", "3156700"),
                    key="nfe_produto_codigo_municipio",
                )

                dados_nfe_produto = {
                    "competencia": nf_competencia_faturado,
                    "ambiente": nfe_ambiente,
                    "natureza_operacao": nfe_natureza,
                    "ncm": nfe_ncm,
                    "cfop": nfe_cfop,
                    "unidade": nfe_unidade,
                    "observacoes": nf_observacoes_faturado,
                    "emitente_nome": "Dsystem Tecnologia",
                    "emitente_cnpj": config_sistema_val("NFSE_CNPJ", "23524449000154"),
                    "emitente_fantasia": "Dsystem Tecnologia",
                    "emitente_logradouro": config_sistema_val("NFE_EMITENTE_LOGRADOURO", "Rua Gloria"),
                    "emitente_numero": config_sistema_val("NFE_EMITENTE_NUMERO", "25"),
                    "emitente_bairro": config_sistema_val("NFE_EMITENTE_BAIRRO", "Centro"),
                    "emitente_municipio": config_sistema_val("NFE_EMITENTE_MUNICIPIO", "Sabara"),
                    "emitente_cep": config_sistema_val("NFE_EMITENTE_CEP", "34500000"),
                    "emitente_telefone": config_sistema_val("WHATSAPP_OFICIAL", ""),
                    "inscricao_estadual": nfe_ie_emitente_base,
                    "regime_tributario": nfe_regime_base,
                    "uf": nfe_uf,
                    "codigo_municipio": nfe_codigo_municipio,
                    "numero": nfe_numero,
                    "serie": nfe_serie,
                    "codigo_nf": fat_nf_faturado.get("id"),
                }
                xml_nfe_produto = gerar_xml_nfe_produto_400(fat_nf_faturado, itens_tipo_nf, dados_nfe_produto)
                pendencias_xml_nfe = validar_xml_nfe_produto_minimo(xml_nfe_produto, dados_nfe_produto, itens_tipo_nf)
                if pendencias_xml_nfe:
                    st.warning("Revise estes pontos antes do envio oficial:")
                    for pendencia in pendencias_xml_nfe:
                        st.write(f"- {pendencia}")
                else:
                    st.success("XML NF-e 4.00 montado com os campos minimos de produto.")
                st.download_button(
                    "Baixar XML NF-e Produto 4.00",
                    data=xml_nfe_produto,
                    file_name=f"nfe_produto_faturamento_{fat_nf_faturado.get('id')}.xml",
                    mime="application/xml",
                    width="stretch",
                    key="baixar_xml_nfe_produto",
                )
                st.code(xml_nfe_produto.decode("utf-8"), language="xml")
                with st.expander("Envio oficial NF-e Produto / SEFAZ", expanded=False):
                    st.caption("NF-e de produto usa SEFAZ, XML NF-e 4.00 e webservice NFeAutorizacao4. Nao e o mesmo envio da NFS-e municipal.")
                    nfe_endpoint = st.text_input(
                        "Endpoint SEFAZ NFeAutorizacao4:",
                        value=config_sistema_val("NFE_SEFAZ_ENDPOINT_AUTORIZACAO", ""),
                        key="nfe_sefaz_endpoint_autorizacao",
                    )
                    sefaz_col3, sefaz_col4 = st.columns(2)
                    nfe_timeout = sefaz_col3.number_input("Timeout envio (segundos):", min_value=10, max_value=120, value=30, step=5, key="nfe_timeout_envio")
                    nfe_cert_path = sefaz_col4.text_input(
                        "Certificado A1/PFX:",
                        value=config_sistema_val("NFSE_CERT_PFX_PATH", ""),
                        key="nfe_cert_path",
                    )
                    nfe_cert_password = st.text_input(
                        "Senha certificado A1/PFX:",
                        value=config_sistema_val("NFSE_CERT_PASSWORD", ""),
                        type="password",
                        key="nfe_cert_password",
                    )
                    if st.button("Validar prontidao para envio SEFAZ", width="stretch", key="validar_prontidao_nfe_produto"):
                        prontidao_nfe = validar_prontidao_envio_nfe_produto(
                            endpoint=nfe_endpoint,
                            cert_path=nfe_cert_path,
                            cert_password=nfe_cert_password,
                            ncm=nfe_ncm,
                            cfop=nfe_cfop,
                            inscricao_estadual=nfe_ie_emitente_base,
                            regime_tributario=nfe_regime_base,
                            itens=itens_tipo_nf,
                        )
                        if prontidao_nfe.pronto:
                            st.success("Dados minimos preenchidos para assinar e tentar enviar a NF-e.")
                        else:
                            st.warning("Ainda nao esta pronto para envio oficial de NF-e:")
                            for pendencia in prontidao_nfe.pendencias:
                                st.write(f"- {pendencia}")
                    nfe_assinado_key = f"nfe_produto_xml_assinado_{fat_nf_faturado.get('id')}"
                    ass_col1, ass_col2 = st.columns(2)
                    if ass_col1.button("Assinar XML NF-e Produto", width="stretch", key="assinar_xml_nfe_produto"):
                        try:
                            xml_assinado = assinar_xml_nfe_produto(xml_nfe_produto, nfe_cert_path, nfe_cert_password)
                            st.session_state[nfe_assinado_key] = xml_assinado
                            st.success("XML NF-e de produto assinado.")
                        except Exception as ex:
                            st.error(f"Falha ao assinar XML NF-e de produto: {ex}")
                    xml_assinado_atual = st.session_state.get(nfe_assinado_key)
                    if xml_assinado_atual:
                        ass_col2.download_button(
                            "Baixar XML NF-e Produto assinado",
                            data=xml_assinado_atual,
                            file_name=f"nfe_produto_faturamento_{fat_nf_faturado.get('id')}_assinado.xml",
                            mime="application/xml",
                            width="stretch",
                            key="baixar_xml_nfe_produto_assinado",
                        )
                    fila_col1, fila_col2 = st.columns(2)
                    if fila_col1.button("Salvar produto na fila de emissao", width="stretch", key="salvar_nfe_produto_fila"):
                        nota_id_produto, _ = preparar_nota_fiscal_por_tipo(fat_nf_faturado, "Produto", nf_competencia_faturado)
                        salvar_retorno_nota_fiscal(
                            nota_id_produto,
                            xml_assinado_atual or xml_nfe_produto,
                            b"",
                            {"status": "Pendente", "mensagem": "NF-e de produto preparada para envio SEFAZ."},
                            gerar_pdf=False,
                        )
                        st.success(f"NF-e de produto salva na fila. Nota fiscal interna #{nota_id_produto}.")
                    if fila_col2.button("Enviar NF-e Produto para SEFAZ", type="primary", width="stretch", key="enviar_nfe_produto_sefaz"):
                        try:
                            if pendencias_xml_nfe:
                                raise ValueError("Corrija as pendencias do XML antes do envio.")
                            if not nfe_endpoint:
                                raise ValueError("Configure o endpoint NFeAutorizacao4 da SEFAZ.")
                            xml_para_envio = xml_assinado_atual or assinar_xml_nfe_produto(xml_nfe_produto, nfe_cert_path, nfe_cert_password)
                            nota_id_produto, _ = preparar_nota_fiscal_por_tipo(fat_nf_faturado, "Produto", nf_competencia_faturado)
                            retorno_nfe = enviar_xml_nfe_produto(
                                nfe_endpoint,
                                xml_para_envio,
                                nfe_cert_path,
                                nfe_cert_password,
                                timeout=int(nfe_timeout),
                            )
                            retorno_info_nfe = analisar_retorno_nfe_produto(retorno_nfe)
                            salvar_retorno_nota_fiscal(nota_id_produto, xml_para_envio, retorno_nfe, retorno_info_nfe, gerar_pdf=False)
                            if retorno_info_nfe.get("status") == "Autorizada":
                                st.success("NF-e de produto autorizada pela SEFAZ.")
                            else:
                                st.warning(retorno_info_nfe.get("mensagem") or "Retorno recebido da SEFAZ.")
                            st.code(retorno_nfe.decode("utf-8", errors="ignore"), language="xml")
                        except Exception as ex:
                            st.error(f"Falha no envio NF-e Produto: {ex}")

        if st.button("Salvar nota para emissão", type="primary", width="stretch", key="faturado_salvar_nota_emissao"):
            if not fat_nf_faturado:
                st.error("Selecione um faturamento.")
            elif not nf_descricao_faturado.strip() or nf_valor_faturado <= 0:
                st.error("Informe descrição e valor maior que zero.")
            else:
                nota_id, _ = preparar_nota_fiscal_por_tipo(fat_nf_faturado, nf_tipo_faturado, nf_competencia_faturado)
                conn_nf_up = conectar_banco()
                cnf_up = conn_nf_up.cursor()
                cnf_up.execute("""UPDATE notas_fiscais SET descricao=?, valor_servicos=?, aliquota_iss=?,
                                  valor_iss=?, codigo_servico=?, municipio_prestacao=?, observacoes=?
                                  WHERE id=?""",
                               (nf_descricao_faturado, nf_valor_faturado, nf_aliquota_faturado,
                                nf_valor_iss_faturado, nf_codigo_faturado, nf_municipio_faturado,
                                nf_observacoes_faturado, nota_id))
                conn_nf_up.commit()
                conn_nf_up.close()
                st.success("Nota adicionada/atualizada na fila de emissão.")
                st.rerun()

    with aba_faturado_lista:
        st.caption("Lista dos faturamentos já faturados e separados para emissão.")

    conn_faturado = conectar_banco()
    cfaturado = conn_faturado.cursor()
    try:
        cfaturado.execute("SELECT * FROM faturamento ORDER BY id DESC")
        rows_faturado = [dict(r) for r in cfaturado.fetchall()]
    except Exception:
        rows_faturado = []
    conn_faturado.close()
    rows_faturado = filtrar_registros_por_empresa(rows_faturado, "cliente")

    ft1, ft2, ft3, ft4 = st.columns(4)
    filtro_faturado_cliente = ft1.text_input("Pesquisar cliente/ID/orçamento:", key="faturado_filtro_cliente")
    filtro_faturado_status = ft2.selectbox("Status:", ["Faturado", "Todos", "Aberto", "Cancelado"], key="faturado_filtro_status")
    filtro_faturado_tipo = ft3.selectbox("Tipo de item:", ["Todos", "Produto", "Serviço"], key="faturado_filtro_tipo")
    filtro_faturado_mes = ft4.date_input("Mês:", value=None, key="faturado_filtro_mes")

    rows_faturado_filtrados = list(rows_faturado)
    termo_faturado = filtro_faturado_cliente.strip().lower()
    if termo_faturado:
        rows_faturado_filtrados = [
            r for r in rows_faturado_filtrados
            if termo_faturado in str(r.get("cliente") or "").lower()
            or termo_faturado in str(r.get("id") or "").lower()
            or termo_faturado in str(r.get("orc_ref") or "").lower()
        ]
    if filtro_faturado_status != "Todos":
        rows_faturado_filtrados = [
            r for r in rows_faturado_filtrados
            if (r.get("status") or "Aberto") == filtro_faturado_status
        ]
    if filtro_faturado_mes:
        rows_faturado_filtrados = [
            r for r in rows_faturado_filtrados
            if parse_data_flex(r.get("data_lanc")) and parse_data_flex(r.get("data_lanc")).strftime("%Y-%m") == filtro_faturado_mes.strftime("%Y-%m")
        ]
    if filtro_faturado_tipo != "Todos":
        rows_faturado_filtrados = [
            r for r in rows_faturado_filtrados
            if any((item.get("tipo_item") or "Serviço") == filtro_faturado_tipo for item in itens_faturamento_lista(r.get("itens")))
        ]

    linhas_faturado = []
    total_produtos = 0.0
    total_servicos = 0.0
    for fat_row in rows_faturado_filtrados:
        itens_row = itens_faturamento_lista(fat_row.get("itens"))
        valor_prod = sum(float(i.get("vtotal") or 0) for i in itens_row if (i.get("tipo_item") or "Serviço") == "Produto")
        valor_serv = sum(float(i.get("vtotal") or 0) for i in itens_row if (i.get("tipo_item") or "Serviço") == "Serviço")
        total_produtos += valor_prod
        total_servicos += valor_serv
        linhas_faturado.append({
            "ID": fat_row.get("id"),
            "Data": data_para_br(fat_row.get("data_lanc")),
            "Cliente": fat_row.get("cliente") or "",
            "Orçamento": fat_row.get("orc_ref") or "",
            "Produto": formatar_moeda_br(valor_prod),
            "Serviço": formatar_moeda_br(valor_serv),
            "Total": formatar_moeda_br(fat_row.get("valor_total")),
            "Status": fat_row.get("status") or "Aberto",
            "Vencimento": data_para_br(fat_row.get("vencimento")),
            "Parcelas": fat_row.get("parcelas") or "Não",
        })

    fm1, fm2, fm3 = st.columns(3)
    fm1.metric("Faturamentos filtrados", len(linhas_faturado))
    fm2.metric("Produtos", formatar_moeda_br(total_produtos))
    fm3.metric("Serviços", formatar_moeda_br(total_servicos))

    if linhas_faturado:
        st.dataframe(linhas_faturado, width="stretch", hide_index=True)
    else:
        st.info("Nenhum faturamento encontrado com os filtros selecionados.")

    st.write("---")
    id_faturado = st.number_input("ID do faturamento para preparar emissão:", min_value=1, step=1, key="faturado_id_emissao")
    fat_emitir = next((r for r in rows_faturado if int(r.get("id") or 0) == int(id_faturado)), None)
    if fat_emitir:
        itens_emitir = itens_faturamento_lista(fat_emitir.get("itens"))
        tipo_faturamento_padrao = fat_emitir.get("tipo_nota") if fat_emitir.get("tipo_nota") in ["Produto", "Serviço"] else "Serviço"

        def tipo_item_faturado(item):
            return item.get("tipo_item") or tipo_faturamento_padrao

        itens_produto = [i for i in itens_emitir if tipo_item_faturado(i) == "Produto"]
        itens_servico = [i for i in itens_emitir if tipo_item_faturado(i) == "Serviço"]

        st.markdown(f"#### Faturamento #{id_faturado} - {fat_emitir.get('cliente') or ''}")
        st.caption(f"CPF/CNPJ: {fat_emitir.get('cnpj') or ''} | Status: {fat_emitir.get('status') or 'Aberto'} | Orçamento: {fat_emitir.get('orc_ref') or '-'}")
        parcelas_faturado = gerar_parcelas_faturamento(fat_emitir)
        st.markdown("##### Parcelas do faturamento")
        st.dataframe([
            {
                "Parcela": parcela["rotulo"],
                "Documento financeiro": parcela["documento"],
                "Vencimento": parcela["vencimento"],
                "Valor": formatar_moeda_br(parcela["valor"]),
                "Forma": parcela["meio"],
            }
            for parcela in parcelas_faturado
        ], width="stretch", hide_index=True)
        competencia_faturado = st.date_input("Competência das notas:", value=date.today(), key=f"faturado_competencia_{id_faturado}")

        col_serv, col_prod = st.columns(2)
        with col_serv:
            st.markdown("##### Nota de Serviço")
            if itens_servico:
                st.dataframe([{
                    "Descrição": i.get("desc") or "",
                    "Qtd": i.get("qtd") or 0,
                    "Unitário": formatar_moeda_br(i.get("vunit")),
                    "Total": formatar_moeda_br(i.get("vtotal")),
                } for i in itens_servico], width="stretch", hide_index=True)
                st.metric("Total serviço", formatar_moeda_br(sum(float(i.get("vtotal") or 0) for i in itens_servico)))
                if st.button("Preparar nota de serviço", type="primary", width="stretch", key=f"prep_nf_serv_{id_faturado}"):
                    nota_id, valor_nota = preparar_nota_fiscal_por_tipo(fat_emitir, "Serviço", competencia_faturado)
                    st.success(f"Nota de serviço #{nota_id} preparada: {formatar_moeda_br(valor_nota)}.")
                    st.info("Agora abra a aba Notas Emitidas para conferir ou continuar a emissao.")
            else:
                st.info("Este faturamento não tem itens de serviço.")

        with col_prod:
            st.markdown("##### Nota de Produto")
            if itens_produto:
                st.dataframe([{
                    "Descrição": i.get("desc") or "",
                    "Qtd": i.get("qtd") or 0,
                    "Unitário": formatar_moeda_br(i.get("vunit")),
                    "Total": formatar_moeda_br(i.get("vtotal")),
                } for i in itens_produto], width="stretch", hide_index=True)
                st.metric("Total produto", formatar_moeda_br(sum(float(i.get("vtotal") or 0) for i in itens_produto)))
                if st.button("Preparar nota de produto", type="primary", width="stretch", key=f"prep_nf_prod_{id_faturado}"):
                    nota_id, valor_nota = preparar_nota_fiscal_por_tipo(fat_emitir, "Produto", competencia_faturado)
                    st.success(f"Nota de produto #{nota_id} preparada: {formatar_moeda_br(valor_nota)}.")
                    st.info("Agora abra a aba Notas Emitidas para conferir ou continuar a emissao.")
            else:
                st.info("Este faturamento não tem itens de produto.")

        if st.button("Marcar este faturamento como faturado", width="stretch", key=f"marcar_faturado_{id_faturado}"):
            resultado_fat = faturar_lancamento_com_integracoes(fat_emitir)
            if resultado_fat.get("ok"):
                st.success(resultado_fat.get("mensagem"))
            else:
                st.error(resultado_fat.get("mensagem"))
            st.rerun()

    with aba_faturado_documentos:
        renderizar_central_documentos_faturados(ctx, rows_faturado)

    with aba_faturado_notas:
        renderizar_notas_emitidas_tab()



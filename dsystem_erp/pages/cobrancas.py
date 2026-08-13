from __future__ import annotations

from dsystem_erp.app_context import aplicar_contexto_pagina
from dsystem_erp.services.cobrancas_recorrentes import sincronizar_lancamentos_recorrentes


def renderizar_cobrancas(ctx: dict) -> None:
    aplicar_contexto_pagina(ctx, globals())
    if not tem_permissao("faturamento.view"):
        st.error("Você não tem permissão para acessar este módulo.")
        st.stop()

    st.title("Cobranças Recorrentes")
    conn_sinc = conectar_banco()
    try:
        titulos_criados = sincronizar_lancamentos_recorrentes(
            conn_sinc, date.today(), st.session_state.get("username", ""), horizonte_dias=35
        )
    finally:
        conn_sinc.close()
    if titulos_criados:
        st.success(f"{titulos_criados} lançamento(s) recorrente(s) enviado(s) para Contas a Receber.")

    clientes_cobr = buscar_clientes()
    nomes_clientes_cobr = ["-- Selecionar --"] + [c["nome"] for c in clientes_cobr]

    aba_cob1, aba_cob2, aba_cob3 = st.tabs(["Cadastrar Cobrança", "Histórico", "Renovações"])

    hoje_cobranca = date.today()
    limite_renovacao = hoje_cobranca + timedelta(days=30)
    conn_alerta = conectar_banco()
    ca = conn_alerta.cursor()
    ca.execute("SELECT id, cliente_nome, tipo_cobranca, vigencia_fim FROM cobrancas_recorrentes WHERE status='Ativa' ORDER BY vigencia_fim")
    alertas_renovacao = []
    for item in ca.fetchall():
        fim = parse_data_flex(item.get("vigencia_fim"))
        if fim and fim <= limite_renovacao:
            dias = (fim - hoje_cobranca).days
            alertas_renovacao.append({
                "ID": item.get("id"), "Cliente": item.get("cliente_nome"),
                "Cobrança": item.get("tipo_cobranca"), "Vencimento": data_para_br(fim),
                "Situação": "Vencida" if dias < 0 else "Vence hoje" if dias == 0 else f"Faltam {dias} dias",
            })
    conn_alerta.close()
    if alertas_renovacao:
        st.warning("🔔 Existem cobranças próximas do vencimento que precisam de renovação.")
        st.dataframe(alertas_renovacao, width="stretch", hide_index=True)

    with aba_cob1:
        st.subheader("Nova Cobrança Recorrente")
        c1, c2, c3 = st.columns(3)
        cliente_cobr = c1.selectbox("Cliente:", nomes_clientes_cobr, key="cobr_cliente")
        cliente_cobr_dados = next((c for c in clientes_cobr if c.get("nome") == cliente_cobr), None)
        cliente_cobr_padrao = dados_cliente_padrao(cliente_cobr_dados)
        cliente_cobr_id = cliente_cobr_dados.get("id") if cliente_cobr_dados else None
        tipo_opcoes = ["Antivírus", "Backup", "Locação", "Hospedagem", "Licença", "Outro"]
        tipo_cobr = c2.selectbox("Qual cobrança:", tipo_opcoes, key="cobr_tipo")
        if tipo_cobr == "Outro":
            tipo_cobr = c2.text_input("Cadastrar outra cobrança:", key="cobr_tipo_outro")
        valor_financeiro = c3.number_input("Valor financeiro R$:", min_value=0.0, step=0.01, format="%.2f", key="cobr_valor_fin")
        if cliente_cobr_dados:
            emails_cobranca_cliente = cliente_cobr_dados.get("emails_cobranca") or cliente_cobr_padrao["email"]
            st.info(f"E-mails considerados para cobrança: {emails_cobranca_cliente or 'nenhum e-mail de cobrança cadastrado'}")

        c4, c5, c6 = st.columns(3)
        data_emp = c4.date_input("Data de empréstimo/locação:", value=date.today(), key="cobr_data_emp")
        quantidade = c5.number_input("Quantidade:", min_value=0, step=1, value=1, key="cobr_quantidade")
        data_cobranca = c6.date_input("Data da cobrança:", value=date.today(), key="cobr_data_cobranca")

        motivo = st.text_area("Motivo:", height=80, key="cobr_motivo")

        st.markdown("**Backup / Instalação**")
        b1, b2, b3 = st.columns(3)
        tipo_backup = b1.selectbox("Tipo do Backup:", ["Físico", "Nuvem", "Outro"], key="cobr_tipo_backup")
        if tipo_backup == "Outro":
            tipo_backup = b1.text_input("Cadastrar outro tipo de backup:", key="cobr_tipo_backup_outro")
        servidor_backup = b2.text_input("Servidor de Backup:", key="cobr_servidor_backup")
        maquina_backup = b3.text_input("Máquina instalada o Backup:", key="cobr_maquina_backup", placeholder="Servidor e/ou máquinas")

        st.markdown("**Cobrança e Vigência**")
        v1, v2, v3 = st.columns(3)
        valor_cobranca = v1.number_input("Valor da cobrança R$:", min_value=0.0, step=0.01, format="%.2f", key="cobr_valor_cobranca")
        vigencia_inicio = v2.date_input("Vigência - início:", value=date.today(), key="cobr_vig_ini")
        vigencia_fim = v3.date_input("Vigência - fim:", value=date.today() + timedelta(days=365), key="cobr_vig_fim")

        l1, l2 = st.columns(2)
        lic_servidor = l1.number_input("Quantidade de licenças - Servidor:", min_value=0, step=1, value=0, key="cobr_lic_servidor")
        lic_maquinas = l2.number_input("Quantidade de licenças - Máquinas:", min_value=0, step=1, value=0, key="cobr_lic_maquinas")

        p1, p2 = st.columns(2)
        pagamento = p1.selectbox(
            "Pagamento:",
            ["Faturamento via D-System", "Cartão do Cliente", "Boleto do Distribuidor para o Cliente"],
            key="cobr_pagamento",
        )
        periodicidade = p2.selectbox("Cobrança:", ["Diária", "Semanal", "Mensal", "Anual"], key="cobr_periodicidade")
        informacoes = st.text_area("Informações Gerais:", height=100, key="cobr_info")

        if st.button("Salvar Cobrança Recorrente", type="primary", width="stretch", key="btn_salvar_cobranca"):
            if cliente_cobr == "-- Selecionar --":
                st.error("Selecione um cliente.")
            elif not str(tipo_cobr or "").strip():
                st.error("Informe qual cobrança será cadastrada.")
            else:
                conn = conectar_banco()
                c = conn.cursor()
                c.execute(
                    """INSERT INTO cobrancas_recorrentes
                       (cliente_id, cliente_nome, tipo_cobranca, valor_financeiro, data_emprestimo_locacao,
                        motivo, tipo_backup, quantidade, servidor_backup, maquina_backup, data_cobranca,
                        valor_cobranca, vigencia_inicio, vigencia_fim, licencas_servidor, licencas_maquinas,
                        pagamento, periodicidade, informacoes, status, criado_por, criado_em)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        cliente_cobr_id,
                        cliente_cobr,
                        tipo_cobr,
                        valor_financeiro,
                        data_para_banco_br(data_emp),
                        motivo,
                        tipo_backup,
                        quantidade,
                        servidor_backup,
                        maquina_backup,
                        data_para_banco_br(data_cobranca),
                        valor_cobranca,
                        data_para_banco_br(vigencia_inicio),
                        data_para_banco_br(vigencia_fim),
                        lic_servidor,
                        lic_maquinas,
                        pagamento,
                        periodicidade,
                        informacoes,
                        "Ativa",
                        st.session_state.get("username", ""),
                        datetime.now().strftime("%d/%m/%Y %H:%M"),
                    ),
                )
                conn.commit()
                titulos_gerados = sincronizar_lancamentos_recorrentes(
                    conn, date.today(), st.session_state.get("username", ""), horizonte_dias=35
                )
                conn.close()
                st.success(f"Cobrança recorrente salva. {titulos_gerados} lançamento(s) criado(s) no Contas a Receber.")
                st.rerun()

    with aba_cob2:
        st.subheader("Cobranças Cadastradas")
        conn = conectar_banco()
        c = conn.cursor()
        c.execute("SELECT * FROM cobrancas_recorrentes ORDER BY id DESC")
        cobrancas = filtrar_registros_por_empresa(c.fetchall(), "cliente_nome")
        conn.close()

        if cobrancas:
            filtro_cliente = st.selectbox("Filtrar por cliente:", ["Todos"] + sorted({c.get("cliente_nome") or "" for c in cobrancas if c.get("cliente_nome")}), key="cobr_filtro_cliente")
            filtro_status = st.selectbox("Status:", ["Todos", "Ativa", "Encerrada"], key="cobr_filtro_status")
            busca_cobr = st.text_input("Buscar cobrança/motivo:", key="cobr_busca")
            cobrancas_filtradas = cobrancas
            if filtro_cliente != "Todos":
                cobrancas_filtradas = [c for c in cobrancas_filtradas if c.get("cliente_nome") == filtro_cliente]
            if filtro_status != "Todos":
                cobrancas_filtradas = [c for c in cobrancas_filtradas if c.get("status") == filtro_status]
            if busca_cobr.strip():
                termo = busca_cobr.strip().lower()
                cobrancas_filtradas = [
                    c for c in cobrancas_filtradas
                    if termo in " ".join(str(c.get(k) or "") for k in ["tipo_cobranca", "motivo", "tipo_backup", "servidor_backup", "maquina_backup", "informacoes"]).lower()
                ]

            st.dataframe(
                [{
                    "ID": c.get("id"),
                    "Cliente": c.get("cliente_nome"),
                    "Cobrança": c.get("tipo_cobranca"),
                    "Valor": formatar_moeda_br(c.get("valor_cobranca")),
                    "Periodicidade": c.get("periodicidade"),
                    "Pagamento": c.get("pagamento"),
                    "Início": data_para_br(c.get("vigencia_inicio")),
                    "Fim": data_para_br(c.get("vigencia_fim")),
                    "Status": c.get("status"),
                } for c in cobrancas_filtradas],
                width="stretch",
                hide_index=True,
            )

            id_cobr = st.number_input("ID para detalhes/ações:", min_value=1, step=1, key="cobr_id_acao")
            cobr_sel = next((dict(c) for c in cobrancas if int(c.get("id") or 0) == int(id_cobr)), None)
            if cobr_sel:
                with st.expander(f"Detalhes da cobrança #{id_cobr}", expanded=True):
                    st.write(f"**Cliente:** {cobr_sel.get('cliente_nome') or ''}")
                    st.write(f"**Cobrança:** {cobr_sel.get('tipo_cobranca') or ''}")
                    st.write(f"**Data da cobrança:** {data_para_br(cobr_sel.get('data_cobranca'))}")
                    st.write(f"**Vigência:** {data_para_br(cobr_sel.get('vigencia_inicio'))} até {data_para_br(cobr_sel.get('vigencia_fim'))}")
                    st.write(f"**Motivo:** {cobr_sel.get('motivo') or ''}")
                    st.write(f"**Backup:** {cobr_sel.get('tipo_backup') or ''} | **Servidor:** {cobr_sel.get('servidor_backup') or ''} | **Máquina:** {cobr_sel.get('maquina_backup') or ''}")
                    st.write(f"**Licenças:** Servidor {cobr_sel.get('licencas_servidor') or 0} | Máquinas {cobr_sel.get('licencas_maquinas') or 0}")
                    st.write(f"**Informações Gerais:** {cobr_sel.get('informacoes') or ''}")

                r1, r2, r3 = st.columns(3)
                nova_ini = r1.date_input("Nova vigência - início:", value=data_input_valor(cobr_sel.get("vigencia_fim"), date.today()), key=f"ren_ini_{id_cobr}")
                nova_fim = r2.date_input("Nova vigência - fim:", value=date.today() + timedelta(days=365), key=f"ren_fim_{id_cobr}")
                novo_valor = r3.number_input("Novo valor R$:", min_value=0.0, step=0.01, format="%.2f", value=float(cobr_sel.get("valor_cobranca") or 0), key=f"ren_valor_{id_cobr}")
                obs_ren = st.text_area("Observação da renovação:", key=f"ren_obs_{id_cobr}")
                if st.button("Renovação", type="primary", width="stretch", key=f"btn_renovar_{id_cobr}"):
                    conn = conectar_banco()
                    c = conn.cursor()
                    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
                    c.execute(
                        """INSERT INTO cobrancas_renovacoes
                           (cobranca_id, data_renovacao, vigencia_inicio_anterior, vigencia_fim_anterior,
                            vigencia_inicio_nova, vigencia_fim_nova, valor_cobranca, observacao, criado_por, criado_em)
                           VALUES (?,?,?,?,?,?,?,?,?,?)""",
                        (
                            id_cobr,
                            data_para_banco_br(date.today()),
                            cobr_sel.get("vigencia_inicio") or "",
                            cobr_sel.get("vigencia_fim") or "",
                            data_para_banco_br(nova_ini),
                            data_para_banco_br(nova_fim),
                            novo_valor,
                            obs_ren,
                            st.session_state.get("username", ""),
                            agora,
                        ),
                    )
                    c.execute(
                        "UPDATE cobrancas_recorrentes SET vigencia_inicio=?, vigencia_fim=?, valor_cobranca=?, status='Ativa' WHERE id=?",
                        (data_para_banco_br(nova_ini), data_para_banco_br(nova_fim), novo_valor, id_cobr),
                    )
                    conn.commit()
                    conn.close()
                    st.success("Renovação registrada e cobrança atualizada.")
                    st.rerun()

                if st.session_state.get("is_admin", 0):
                    if st.button("Encerrar Cobrança", key=f"btn_encerrar_cobr_{id_cobr}"):
                        conn = conectar_banco()
                        c = conn.cursor()
                        c.execute("UPDATE cobrancas_recorrentes SET status='Encerrada' WHERE id=?", (id_cobr,))
                        conn.commit()
                        conn.close()
                        st.success("Cobrança encerrada.")
                        st.rerun()
        else:
            st.info("Nenhuma cobrança recorrente cadastrada.")

    with aba_cob3:
        st.subheader("Histórico de Renovações")
        conn = conectar_banco()
        c = conn.cursor()
        c.execute(
            """SELECT r.id, r.cobranca_id, c.cliente_nome, c.tipo_cobranca, r.data_renovacao,
                      r.vigencia_inicio_anterior, r.vigencia_fim_anterior,
                      r.vigencia_inicio_nova, r.vigencia_fim_nova, r.valor_cobranca,
                      r.observacao, r.criado_por, r.criado_em
               FROM cobrancas_renovacoes r
               LEFT JOIN cobrancas_recorrentes c ON c.id = r.cobranca_id
               ORDER BY r.id DESC"""
        )
        renovacoes = filtrar_registros_por_empresa(c.fetchall(), "cliente_nome")
        conn.close()
        if renovacoes:
            dados_renovacoes = []
            for r in renovacoes:
                item = dict(r)
                for campo in ["data_renovacao", "vigencia_inicio_anterior", "vigencia_fim_anterior", "vigencia_inicio_nova", "vigencia_fim_nova"]:
                    item[campo] = data_para_br(item.get(campo))
                item["valor_cobranca"] = formatar_moeda_br(item.get("valor_cobranca"))
                dados_renovacoes.append(item)
            st.dataframe(dados_renovacoes, width="stretch", hide_index=True)
        else:
            st.info("Nenhuma renovação registrada ainda.")


from __future__ import annotations

from dsystem_erp.app_context import aplicar_contexto_pagina
from dsystem_erp.services.agenda_recorrencia import (
    gerar_datas_agenda_configurada,
    gerar_datas_recorrentes,
)
from dsystem_erp.ui_consulta import tabela_clicavel_id


def filtro_status_agenda(status="Não realizados"):
    """Retorna o filtro SQL sem remover visitas do histórico."""
    if status == "Todos":
        return "", []
    if status == "Não realizados":
        return (
            " AND LOWER(TRIM(COALESCE(status, ''))) NOT IN (?, ?, ?)",
            ["realizado", "concluído", "concluido"],
        )
    return " AND status=?", [status]


def _limpar_estado_editor_agenda(visit_id: int) -> None:
    """Remove valores de widgets antigos antes de recarregar uma visita."""
    chaves = (
        "e_status_ag",
        "e_data_ag",
        "e_tec_ag",
        "e_h_ini",
        "e_h_fim",
        "e_cli_ag",
        "e_cli_nome_ag",
        "e_tipo_ag",
        "e_desc_ag",
    )
    for prefixo in chaves:
        st.session_state.pop(f"{prefixo}_{visit_id}", None)


def renderizar_atendimentos_checklists(ctx: dict) -> None:
    aplicar_contexto_pagina(ctx, globals())
    if not tem_permissao("atendimentos.view"):
        st.error("Você não tem permissão para acessar este módulo.")
        st.stop()

    st.title("Gestão de Atendimentos e Checklists")
    visita_home = st.session_state.pop('agenda_abrir_home', None)
    if visita_home:
        visita_id = int(visita_home['id'])
        _limpar_estado_editor_agenda(visita_id)
        st.session_state['ag_id_edicao'] = visita_id
        st.session_state['agenda_edit_expanded_id'] = visita_id
        data_home = parse_data_flex(visita_home['data_visita'])
        st.session_state['agenda_mes_referencia'] = data_home.replace(day=1)
        st.session_state['ag_fil_data'] = data_home
        st.session_state['ag_fil_tec'] = 'Todos'
        st.session_state['ag_fil_status_v2'] = 'Todos'
        st.session_state['agenda_grade_versao'] = st.session_state.get('agenda_grade_versao', 0) + 1
    aba1, aba2, aba_intervencoes, aba_agenda = st.tabs(["Lançar Novo Atendimento", "Histórico e Gestão", "Histórico de Intervenções", "Agenda de Visitas"], default='Agenda de Visitas' if st.session_state.get('ag_id_edicao') else None)

    with aba1:
        st.write("A data de criação será registrada automaticamente.")
        
        c_tipo, c_tec, c_data = st.columns([2, 1, 1])
        tipo_atend = c_tipo.selectbox("Tipo de Atendimento:", ["Presencial (Na loja)", "Acesso Remoto", "Presencial (No cliente)"])
        funcionarios_cadastrados = listar_funcionarios_sistema()
        opcoes_tecnicos = [item["label"] for item in funcionarios_cadastrados]
        tecnico_label = c_tec.selectbox(
            "Técnico Responsável:",
            ["-- Selecionar --"] + opcoes_tecnicos,
        )
        tecnico_item = next((item for item in funcionarios_cadastrados if item["label"] == tecnico_label), None)
        tecnicos = (tecnico_item or {}).get("nome") or (tecnico_item or {}).get("username") or ""
        data_atend = c_data.date_input(
            "Data do Atendimento:", value=date.today(), format="DD/MM/YYYY"
        ).strftime("%d/%m/%Y")

        clientes_db = buscar_clientes()
        lista_clientes = ["-- Preencher Manualmente --"] + [c['nome'] for c in clientes_db]
        cli_sel = st.selectbox("Vincular a um Cliente Cadastrado:", lista_clientes)
        cliente = st.text_input("Nome do Cliente / Empresa:", value="" if cli_sel == "-- Preencher Manualmente --" else cli_sel)

        st.write("---")
        
        equipamento, func_atendido, maq_atendidas, obs_entrada = "", "", "", ""
        formatacao, bkp_conv, bkp_c, bkp_nav, bkp_email, data_bkp = "Não", "Não", "Não", "Não", "Não", ""
        p_dsys, l_int, l_ext, v_upd, s_indes, c_soft, b_ret, t_hw, sac = False, False, False, False, False, False, False, False, False
        v_desemp, obs_desemp, det_realizado, senhas_alt = "Não", "", "", ""

        if "Presencial" in tipo_atend:
            st.subheader("Equipamento e Entrada")
            equipamento = st.text_input("Equipamento:")
            obs_entrada = st.text_area("Observações de Entrada:")
            
            st.write("---")
            st.subheader("Formatação e Backup")
            formatacao = st.radio("Fazer Formatação?", ["Não", "Sim"], horizontal=True)
            if formatacao == "Sim":
                cb1, cb2, cb3, cb4, cb5 = st.columns(5)
                bkp_conv = cb1.selectbox("Arq. Convencionais?", ["Não", "Sim"])
                bkp_c = cb2.selectbox("Arq. no C?", ["Não", "Sim"])
                bkp_nav = cb3.selectbox("Navegadores?", ["Não", "Sim"])
                bkp_email = cb4.selectbox("E-mail?", ["Não", "Sim"])
                data_bkp = cb5.text_input("Data do Backup (dd/mm/aaaa):")

            st.write("---")
            st.subheader("Checklist de Saída")
            cc1, cc2, cc3 = st.columns(3)
            p_dsys = cc1.checkbox("Pasta Soft Dsys")
            l_int = cc1.checkbox("Limpeza Interna")
            l_ext = cc1.checkbox("Limpeza Externa")
            v_upd = cc2.checkbox("Update Windows")
            s_indes = cc2.checkbox("Verif. Soft. Indesejado")
            c_soft = cc2.checkbox("Confirmação Softwares")
            b_ret = cc3.checkbox("Backup retornou")
            t_hw = cc3.checkbox("Teste de Hardware")
            sac = cc3.checkbox("Sacola/Pasta")

        if tipo_atend in ["Acesso Remoto", "Presencial (No cliente)"]:
            st.write("---")
            st.subheader("Detalhes do Atendimento")
            func_atendido = st.text_input("Funcionário Atendido:")
            maq_atendidas = st.text_input("Máquinas Atendidas:")
            v_desemp = st.radio("Verificou Desempenho (CPU/RAM/Disco)?", ["Não", "Sim"], horizontal=True)
            if v_desemp == "Sim":
                obs_desemp = st.text_input("O que foi visto no desempenho?")
            det_realizado = st.text_area("Detalhes do que foi realizado:")
            senhas_alt = st.text_input("Senhas alteradas (se houver):")

        st.write("---")
        historico = st.text_area("Histórico Geral / Observações Finais:")
        status = st.selectbox("Status:", ["Em Andamento", "Concluído", "Aguardando Peça"])

        if st.button("Salvar Ficha de Atendimento", type="primary", width="stretch"):
            if not tecnicos:
                st.error("Selecione um técnico responsável cadastrado.")
            elif cliente:
                def b_s(v): return "Sim" if v else "Não"
                conn = conectar_banco()
                c = conn.cursor()
                c.execute('''INSERT INTO atendimentos_checklist (
                    tipo_atendimento, cliente, equipamento, funcionario_atendido, maquinas_atendidas, tecnicos, 
                    data_entrada, status, obs_entrada, formatacao, bkp_convencionais, bkp_c, bkp_nav, bkp_email, 
                    data_backup, pasta_dsys, limpeza_int, limpeza_ext, verif_update, soft_indesejado, 
                    confirma_soft, bkp_retornou, testado_hw, sacola, verif_desempenho, obs_desempenho, 
                    detalhes_realizado, senhas_alteradas, historico
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
                    tipo_atend, cliente, equipamento, func_atendido, maq_atendidas, tecnicos, 
                    data_atend, status, obs_entrada, formatacao, bkp_conv, bkp_c, bkp_nav, bkp_email, 
                    data_bkp, b_s(p_dsys), b_s(l_int), b_s(l_ext), b_s(v_upd), b_s(s_indes), b_s(c_soft), 
                    b_s(b_ret), b_s(t_hw), b_s(sac), v_desemp, obs_desemp, det_realizado, senhas_alt, historico
                ))
                conn.commit()
                conn.close()
                st.success("Atendimento salvo!")
                st.rerun()

    with aba2:
        st.subheader("Histórico e Gestão")
        conn = conectar_banco()
        conn.row_factory = None
        c = conn.cursor()
        c.execute('SELECT id, data_entrada, cliente, tipo_atendimento, status FROM atendimentos_checklist ORDER BY id DESC')
        dados = c.fetchall()
        dados = filtrar_registros_por_empresa(dados, "cliente")
        
        if dados:
            linhas_atendimentos = [dict(x) for x in dados]
            id_atendimento_clicado = tabela_clicavel_id(
                st, linhas_atendimentos, "atendimentos_historico_grade", campo_id="id"
            )
            if id_atendimento_clicado:
                st.session_state["atendimento_historico_id"] = int(id_atendimento_clicado)
            id_f = int(st.session_state.get("atendimento_historico_id") or 0)
            if not id_f:
                st.caption("Clique em qualquer informação para abrir as ações e a edição.")
            
            pode_editar = tem_permissao("atendimentos.edit")
            
            c1, c2, c3 = st.columns(3)
            if c1.button("Imprimir Ficha Completa", width="stretch"):
                c.execute('SELECT * FROM atendimentos_checklist WHERE id=?', (id_f,))
                row_f = c.fetchone()
                if row_f:
                    f = dict(row_f)
                    def m(v): return "☑" if v == "Sim" else "☐"

                    corpo = f"""
                    <h2 style="text-align:center;color:#1a3a6b;border-bottom:2px solid #1a3a6b;padding-bottom:8px;">
                        FICHA DE ATENDIMENTO &mdash; {f['tipo_atendimento'].upper()}
                    </h2>
                    <table style="width:100%;font-size:13px;margin-bottom:12px;">
                        <tr>
                            <td><b>ID:</b> {f['id']:05d}</td>
                            <td style="text-align:right"><b>Data:</b> {f['data_entrada']}</td>
                        </tr>
                        <tr>
                            <td><b>Cliente:</b> {f['cliente']}</td>
                            <td style="text-align:right"><b>Técnico(s):</b> {f.get('tecnicos') or '—'}</td>
                        </tr>
                        <tr><td><b>Status:</b> {f.get('status','')}</td></tr>
                    </table>
                    <hr style="border:1px solid #ccc;margin-bottom:12px;">
                    """

                    if "Presencial" in f['tipo_atendimento']:
                        corpo += f"""
                        <p><b>Equipamento:</b> {f.get('equipamento') or '—'}</p>
                        <p><b>Observações de Entrada:</b> {f.get('obs_entrada') or 'Nenhuma'}</p>
                        <p><b>Formatação:</b> {f.get('formatacao','Não')}</p>
                        <table style="width:100%;border:1px solid #000;border-collapse:collapse;margin:10px 0;font-size:12px;">
                            <tr style="background:#e8eaf6;">
                                <td style="border:1px solid #000;padding:6px;font-weight:bold;">
                                    BACKUP &nbsp;<i>(Realizado em: {f.get('data_backup') or 'N/A'})</i>
                                </td>
                                <td style="border:1px solid #000;padding:6px;font-weight:bold;">CONFERÊNCIA TÉCNICA</td>
                            </tr>
                            <tr>
                                <td style="border:1px solid #000;padding:8px;vertical-align:top;line-height:2;">
                                    [{m(f.get('bkp_convencionais','Não'))}] Arquivos Convencionais<br>
                                    [{m(f.get('bkp_c','Não'))}] Disco Local (C:)<br>
                                    [{m(f.get('bkp_nav','Não'))}] Navegadores / Senhas<br>
                                    [{m(f.get('bkp_email','Não'))}] Contas de E-mail
                                </td>
                                <td style="border:1px solid #000;padding:8px;vertical-align:top;line-height:2;">
                                    [{m(f.get('pasta_dsys','Não'))}] Pasta Soft Dsys &nbsp;|&nbsp; [{m(f.get('limpeza_int','Não'))}] Limpeza Interna<br>
                                    [{m(f.get('verif_update','Não'))}] Windows Update &nbsp;|&nbsp; [{m(f.get('soft_indesejado','Não'))}] Verif. Malware<br>
                                    [{m(f.get('bkp_retornou','Não'))}] Backup Restaurado &nbsp;|&nbsp; [{m(f.get('testado_hw','Não'))}] Teste Hardware<br>
                                    [{m(f.get('limpeza_ext','Não'))}] Limpeza Externa &nbsp;|&nbsp; [{m(f.get('sacola','Não'))}] Sacola/Acessórios
                                </td>
                            </tr>
                        </table>
                        """

                    if "Remoto" in f['tipo_atendimento'] or "cliente" in f['tipo_atendimento']:
                        corpo += f"""
                        <div style="border:1px solid #000;padding:10px;background:#fafafa;margin-top:10px;line-height:1.8;font-size:13px;">
                            <b>Funcionário Atendido:</b> {f.get('funcionario_atendido') or '—'}<br>
                            <b>Máquinas:</b> {f.get('maquinas_atendidas') or '—'}<br>
                            <b>Análise de Desempenho:</b> {f.get('verif_desempenho','—')} — {f.get('obs_desempenho','')}<br>
                            <b>Serviço Realizado:</b> {f.get('detalhes_realizado','—')}<br>
                            <b>Senhas Alteradas:</b> {f.get('senhas_alteradas','—')}
                        </div>
                        """

                    corpo += f"""
                    <p style="margin-top:15px;line-height:1.7;">
                        <b>Histórico / Conclusão:</b><br>
                        {(f.get('historico') or 'Sem histórico.').replace(chr(10),'<br>')}
                    </p>
                    <div style="margin-top:55px;text-align:center;font-size:13px;">
                        ________________________________<br>Assinatura Responsável
                    </div>
                    """

                    html_ficha = f"""<!DOCTYPE html>
    <html><head><meta charset="utf-8"><title>Ficha #{f['id']:05d}</title>
    <style>
      body{{font-family:Arial,sans-serif;padding:30px;color:#000;background:#fff;}}
      @media print{{body{{padding:15px;}} @page{{margin:1.5cm;}}}}
    </style></head>
    <body>{corpo}
    <script>window.onload=function(){{setTimeout(function(){{window.print();}},400);}};</script>
    </body></html>"""
                    components.html(html_ficha, height=700, scrolling=True)

            if pode_editar:
                if c2.button("Editar Registro", width="stretch"):
                    st.session_state['edit_atend_id'] = id_f

                if c3.button("Excluir", width="stretch"):
                    deletar_registro('atendimentos_checklist', 'id', id_f)
                    st.rerun()

            if pode_editar and st.session_state.get('edit_atend_id'):
                id_ed = st.session_state['edit_atend_id']
                c.execute('SELECT * FROM atendimentos_checklist WHERE id=?', (id_ed,))
                ed_row = c.fetchone()
                if ed_row:
                    ed = dict(ed_row)
                    with st.expander(f"Editando Atendimento #{id_ed} — {ed['cliente']}", expanded=True):
                        ed_col1, ed_col2 = st.columns(2)
                        ed_data   = ed_col1.text_input("Data:", value=ed['data_entrada'])
                        ed_status = ed_col2.selectbox("Status:", ["Em Andamento","Concluído","Aguardando Peça"],
                                        index=["Em Andamento","Concluído","Aguardando Peça"].index(ed['status'])
                                        if ed.get('status') in ["Em Andamento","Concluído","Aguardando Peça"] else 0,
                                        key=f"status_edit_{id_ed}"
                                       ) 

                        st.markdown("**Técnico(s) Responsável(is):**")
                        tec_atuais = [t.strip() for t in (ed.get('tecnicos') or '').split(',') if t.strip()]
                        if 'edit_tecnicos' not in st.session_state or st.session_state.get('_edit_tec_id') != id_ed:
                            st.session_state['edit_tecnicos'] = tec_atuais if tec_atuais else ['']
                            st.session_state['_edit_tec_id'] = id_ed

                        novos_tecs = []
                        for ti, tec in enumerate(st.session_state['edit_tecnicos']):
                            tc1, tc2 = st.columns([5, 1])
                            val = tc1.text_input(f"Técnico {ti+1}:", value=tec, key=f"ed_tec_{id_ed}_{ti}")
                            novos_tecs.append(val)
                            if ti > 0 and tc2.button("Remover", key=f"rm_tec_{id_ed}_{ti}"):
                                st.session_state['edit_tecnicos'].pop(ti)
                                st.rerun()

                        if st.button("Adicionar Técnico", key=f"add_tec_{id_ed}"):
                            st.session_state['edit_tecnicos'].append('')
                            st.rerun()

                        clientes_atend_puxar, opcoes_atend_puxar = opcoes_clientes_para_puxar()
                        escolha_atend_puxar = st.selectbox("Puxar dados de outro cliente cadastrado:", opcoes_atend_puxar, key=f"atend_puxar_cliente_{id_ed}")
                        if st.button("Aplicar cliente neste atendimento", width="stretch", key=f"atend_btn_puxar_cliente_{id_ed}"):
                            cliente_atend_sel = next((cli for cli in clientes_atend_puxar if cli.get("nome") == escolha_atend_puxar), None)
                            if not cliente_atend_sel:
                                st.error("Selecione um cliente cadastrado para aplicar.")
                            else:
                                st.session_state[f"cliente_edit_{id_ed}"] = cliente_atend_sel.get("nome") or ""
                                st.success("Cliente carregado no atendimento. Confira e salve.")
                                st.rerun()

                        ed_cliente = st.text_input("Cliente:", value=ed.get('cliente',''), key=f"cliente_edit_{id_ed}"
    )

                        ed_equip   = st.text_input("Equipamento:", value=ed.get('equipamento',''), key=f"equip_edit_{id_ed}"
    )
                        ed_obs_ent = st.text_area("Observações de Entrada:", value=ed.get('obs_entrada',''), height=70, key=f"obs_edit_{id_ed}"
    )
                        ed_hist    = st.text_area("Histórico / Conclusão:", value=ed.get('historico',''), height=100, key=f"hist_edit_{id_ed}")

                        if st.button("Salvar Alterações", type="primary", key=f"btn_sv_ed_{id_ed}"):
                            tecs_final = ', '.join(t for t in novos_tecs if t.strip())
                            conn_ed = conectar_banco()
                            ced = conn_ed.cursor()
                            ced.execute('''UPDATE atendimentos_checklist
                                           SET data_entrada=?, status=?, historico=?,
                                               tecnicos=?, cliente=?, equipamento=?, obs_entrada=?
                                           WHERE id=?''',
                                        (ed_data, ed_status, ed_hist, tecs_final,
                                         ed_cliente, ed_equip, ed_obs_ent, id_ed))
                            conn_ed.commit()
                            conn_ed.close()
                            for k in ['edit_atend_id','edit_tecnicos','_edit_tec_id']:
                                st.session_state.pop(k, None)
                            st.toast("Atendimento atualizado!")
                            st.rerun()
        conn.close()

    with aba_intervencoes:
        st.subheader("Histórico de Intervenções por Equipamento")
        clientes_interv = buscar_clientes()
        nomes_clientes_interv = [cli["nome"] for cli in clientes_interv]

        sub_int1, sub_int2 = st.tabs(["Registrar Intervenção", "Consultar Histórico"])

        with sub_int1:
            cliente_int_nome = st.selectbox("Cliente/empresa:", nomes_clientes_interv, key="int_cliente") if nomes_clientes_interv else ""
            cliente_int_id = next((cli.get("id") for cli in clientes_interv if cli.get("nome") == cliente_int_nome), None)
            i1, i2, i3 = st.columns(3)
            tipo_equip_int = i1.selectbox("Tipo de equipamento:", ["Desktop", "Notebook", "Impressora", "Servidor", "DVR", "Câmera", "Outro"], key="int_tipo_equip")
            equipamento_int = i2.text_input("Equipamento/máquina:", key="int_equipamento")
            identificacao_int = i3.text_input("Patrimônio/serial/identificação:", key="int_identificacao")
            i4, i5, i6 = st.columns(3)
            quem_usa_int = i4.text_input("Quem usa:", key="int_quem_usa")
            tecnico_int = i5.text_input("Técnico responsável:", value=st.session_state.get("funcionario_nome") or st.session_state.get("username", ""), key="int_tecnico")
            data_int = i6.date_input(
                "Data do atendimento/intervenção:", value=date.today(), key="int_data", format="DD/MM/YYYY"
            )

            descricao_int = st.text_area("O que foi realizado nesta máquina/equipamento:", height=120, key="int_descricao")

            st.markdown("**Preventiva**")
            p1, p2, p3, p4 = st.columns(4)
            preventiva_prevista = p1.selectbox("Criar preventiva?", ["Não", "Sim"], key="int_prevista")
            periodo_preventiva = p2.selectbox("Período de atualização/preventiva:", ["Sem recorrência", "30 dias", "6 meses", "1 ano"], key="int_periodo")
            preventiva_realizada = p3.selectbox("Foi realizada a preventiva?", ["Não", "Sim"], key="int_realizada")
            data_preventiva = p4.date_input(
                "Data da realização:", value=date.today(), key="int_data_prev", format="DD/MM/YYYY"
            ) if preventiva_realizada == "Sim" else None
            observacoes_int = st.text_area("Informações gerais / observações:", height=90, key="int_obs")

            if st.button("Salvar Intervenção", type="primary", width="stretch", key="btn_salvar_intervencao"):
                if not cliente_int_nome:
                    st.error("Selecione um cliente/empresa.")
                elif not equipamento_int.strip() and not identificacao_int.strip():
                    st.error("Informe o equipamento ou uma identificação.")
                else:
                    data_intervencao_txt = data_int.strftime("%d/%m/%Y")
                    data_preventiva_txt = data_preventiva.strftime("%d/%m/%Y") if data_preventiva else ""
                    proxima_preventiva = calcular_proxima_preventiva(data_preventiva or data_int, periodo_preventiva) if preventiva_prevista == "Sim" else ""
                    conn_int = conectar_banco()
                    cint = conn_int.cursor()
                    cint.execute(
                        """INSERT INTO atendimentos_intervencoes
                           (cliente_id, cliente_nome, equipamento, identificacao, tipo_equipamento, quem_usa, tecnico,
                            data_intervencao, descricao, preventiva_prevista, periodo_preventiva, preventiva_realizada,
                            data_preventiva, proxima_preventiva, observacoes, criado_por, criado_em)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            cliente_int_id,
                            cliente_int_nome,
                            equipamento_int,
                            identificacao_int,
                            tipo_equip_int,
                            quem_usa_int,
                            tecnico_int,
                            data_intervencao_txt,
                            descricao_int,
                            preventiva_prevista,
                            periodo_preventiva,
                            preventiva_realizada,
                            data_preventiva_txt,
                            proxima_preventiva,
                            observacoes_int,
                            st.session_state.get("username", ""),
                            datetime.now().strftime("%d/%m/%Y %H:%M"),
                        ),
                    )
                    conn_int.commit()
                    conn_int.close()
                    st.success("Intervenção registrada no histórico do cliente/equipamento.")
                    st.rerun()

        with sub_int2:
            conn_int = conectar_banco()
            cint = conn_int.cursor()
            cint.execute("SELECT * FROM atendimentos_intervencoes ORDER BY id DESC")
            intervencoes = filtrar_registros_por_empresa(cint.fetchall(), "cliente_nome")
            conn_int.close()

            if intervencoes:
                f1, f2, f3 = st.columns(3)
                clientes_hist = ["Todos"] + sorted({i.get("cliente_nome") or "" for i in intervencoes if i.get("cliente_nome")})
                filtro_cliente_hist = f1.selectbox("Cliente:", clientes_hist, key="int_filtro_cliente")
                filtro_prev = f2.selectbox("Preventiva:", ["Todas", "Com preventiva", "Realizada", "Não realizada"], key="int_filtro_prev")
                busca_hist = f3.text_input("Buscar equipamento/usuário:", key="int_busca")

                filtradas_int = intervencoes
                if filtro_cliente_hist != "Todos":
                    filtradas_int = [i for i in filtradas_int if i.get("cliente_nome") == filtro_cliente_hist]
                if filtro_prev == "Com preventiva":
                    filtradas_int = [i for i in filtradas_int if i.get("preventiva_prevista") == "Sim"]
                elif filtro_prev == "Realizada":
                    filtradas_int = [i for i in filtradas_int if i.get("preventiva_realizada") == "Sim"]
                elif filtro_prev == "Não realizada":
                    filtradas_int = [i for i in filtradas_int if i.get("preventiva_prevista") == "Sim" and i.get("preventiva_realizada") != "Sim"]
                if busca_hist.strip():
                    termo = busca_hist.strip().lower()
                    filtradas_int = [
                        i for i in filtradas_int
                        if termo in " ".join(str(i.get(c) or "") for c in ["equipamento", "identificacao", "tipo_equipamento", "quem_usa", "descricao"]).lower()
                    ]

                linhas_intervencoes = [{
                        "ID": i.get("id"),
                        "Cliente": i.get("cliente_nome"),
                        "Equipamento": i.get("equipamento"),
                        "Identificação": i.get("identificacao"),
                        "Tipo": i.get("tipo_equipamento"),
                        "Quem usa": i.get("quem_usa"),
                        "Data": i.get("data_intervencao"),
                        "Preventiva": i.get("preventiva_prevista"),
                        "Realizada": i.get("preventiva_realizada"),
                        "Próxima": i.get("proxima_preventiva"),
                    } for i in filtradas_int]
                id_intervencao_clicado = tabela_clicavel_id(
                    st, linhas_intervencoes, "intervencoes_grade", campo_id="ID"
                ) if linhas_intervencoes else None
                if id_intervencao_clicado:
                    st.session_state["int_id_ver_ativo"] = int(id_intervencao_clicado)
                id_int_ver = int(st.session_state.get("int_id_ver_ativo") or 0)
                int_sel = next((dict(i) for i in intervencoes if int(i.get("id") or 0) == int(id_int_ver)), None)
                if int_sel:
                    with st.expander(f"Detalhes da intervenção #{id_int_ver}", expanded=True):
                        st.write(f"**Cliente:** {int_sel.get('cliente_nome') or ''}")
                        st.write(f"**Equipamento:** {int_sel.get('tipo_equipamento') or ''} - {int_sel.get('equipamento') or ''}")
                        st.write(f"**Identificação:** {int_sel.get('identificacao') or ''}")
                        st.write(f"**Quem usa:** {int_sel.get('quem_usa') or ''}")
                        st.write(f"**Técnico:** {int_sel.get('tecnico') or ''}")
                        st.write(f"**Realizado:** {int_sel.get('descricao') or ''}")
                        st.write(f"**Preventiva:** {int_sel.get('preventiva_prevista') or 'Não'} | **Período:** {int_sel.get('periodo_preventiva') or ''}")
                        st.write(f"**Preventiva realizada:** {int_sel.get('preventiva_realizada') or 'Não'} | **Data:** {int_sel.get('data_preventiva') or ''}")
                        st.write(f"**Próxima preventiva:** {int_sel.get('proxima_preventiva') or ''}")
                        st.write(f"**Informações gerais:** {int_sel.get('observacoes') or ''}")
                if tem_permissao("atendimentos.edit") and int_sel:
                    if st.button("Excluir Intervenção", key="btn_del_intervencao"):
                        deletar_registro("atendimentos_intervencoes", "id", id_int_ver)
                        st.success("Intervenção excluída.")
                        st.rerun()
            else:
                st.info("Nenhuma intervenção registrada ainda.")

    with aba_agenda:
        from datetime import datetime, timedelta

        conn_ag = conectar_banco()
        conn_ag.row_factory = None
        cag = conn_ag.cursor()
        cag.execute("SELECT username FROM usuarios ORDER BY username")
        usuarios_dsystem = [row['username'] for row in cag.fetchall()]
        cag.execute("SELECT * FROM agenda_tipos_atendimento ORDER BY nome")
        tipos_agenda_cadastrados = [dict(row) for row in cag.fetchall()]
        tipos_agenda = [row.get("nome") for row in tipos_agenda_cadastrados if row.get("ativo") != "Não"]
        if not tipos_agenda:
            tipos_agenda = ["Suporte Presencial", "Instalação", "Manutenção Preventiva", "Reunião", "Outro"]

        # Mantém doze meses futuros para regras marcadas como indefinidas.
        cag.execute("SELECT * FROM agenda_recorrencias WHERE ativa='Sim' AND modo_termino='Tempo indefinido'")
        for regra in [dict(row) for row in cag.fetchall()]:
            inicio_regra = parse_data_flex(regra.get("data_inicio"))
            if not inicio_regra:
                continue
            try:
                data_anual_regra = date(
                    2000,
                    int(regra.get("mes_anual") or inicio_regra.month),
                    int(regra.get("dia_anual") or inicio_regra.day),
                )
            except ValueError:
                data_anual_regra = inicio_regra
            datas_regra = gerar_datas_agenda_configurada(
                max(inicio_regra, date.today()), regra.get("periodicidade") or "Não",
                horizonte=date.today() + timedelta(days=365),
                dia_semana=regra.get("dia_semana"), dia_mes=regra.get("dia_mes"),
                data_anual=data_anual_regra,
            )
            cag.execute("SELECT data_visita FROM agenda_visitas WHERE recorrencia_id=?", (regra.get("id"),))
            datas_existentes = {str(row.get("data_visita") or "") for row in cag.fetchall()}
            for indice_regra, data_regra in enumerate(datas_regra, 1):
                data_iso_regra = data_regra.strftime("%Y-%m-%d")
                if data_iso_regra in datas_existentes:
                    continue
                cag.execute('''INSERT INTO agenda_visitas
                    (tecnico, cliente_id, cliente_nome, data_visita, hora_inicio, hora_fim,
                     tipo_visita, descricao, status, criado_em, recorrencia_id, recorrencia_indice)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (regra.get("tecnico"), regra.get("cliente_id"), regra.get("cliente_nome"),
                     data_iso_regra, regra.get("hora_inicio") or "", regra.get("hora_fim") or "",
                     regra.get("tipo_atendimento") or "", regra.get("descricao") or "",
                     "Agendado", regra.get("criado_em") or agora_br(), regra.get("id"), indice_regra))
        conn_ag.commit()
        conn_ag.close()

        clientes_ag = buscar_clientes()
        nomes_clientes_ag = [c['nome'] for c in clientes_ag]

        sub_ag1, sub_ag2, sub_ag3, sub_ag4 = st.tabs([
            "Novo Agendamento", "Agenda / Gerenciar", "Tipos de atendimento", "Atividades rápidas"
        ], default='Agenda / Gerenciar' if st.session_state.get('ag_id_edicao') else None)

        with sub_ag1:
            st.subheader("Novo Agendamento de Visita")
            if st.session_state.pop('agenda_salva', None):
                st.toast("Visita agendada com sucesso!")

            ag_col1, ag_col2 = st.columns(2)
            with ag_col1:
                ag_tecnico = st.selectbox(
                    "Técnico Responsável (Dsystem):",
                    ["-- Selecionar --"] + usuarios_dsystem,
                    key="ag_tecnico"
                )
            with ag_col2:
                ag_tipo = st.selectbox(
                    "Tipo de Atendimento:", tipos_agenda,
                    key="ag_tipo"
                )

            ag_col3, ag_col4, ag_col5 = st.columns(3)
            with ag_col3:
                ag_data = ag_col3.date_input(
                    "Data da Visita:", value=date.today(), key="ag_data", format="DD/MM/YYYY"
                )
            with ag_col4:
                ag_hora_ini = ag_col4.time_input("Hora de Início:", value=None, key="ag_hora_ini", step=1800)
            with ag_col5:
                ag_hora_fim = ag_col5.time_input("Hora de Término:", value=None, key="ag_hora_fim", step=1800)

            st.write("---")
            st.markdown("**Cliente a ser atendido:**")
            ag_cli_col1, ag_cli_col2 = st.columns([3, 1])
            with ag_cli_col1:
                ag_cliente_sel = st.selectbox(
                    "Selecionar da Base de Clientes:",
                    ["-- Selecionar --"] + nomes_clientes_ag,
                    key="ag_cliente_sel"
                )
            with ag_cli_col2:
                st.write("")
                st.write("")
                ag_manual = st.checkbox("Preencher manualmente", key="ag_manual")

            if ag_manual or ag_cliente_sel == "-- Selecionar --":
                ag_cliente_nome = st.text_input("Nome do Cliente (manual):", key="ag_cliente_manual")
                ag_cliente_id = None
            else:
                ag_cliente_nome = ag_cliente_sel
                cli_encontrado = next((c for c in clientes_ag if c['nome'] == ag_cliente_sel), None)
                ag_cliente_id = cli_encontrado['id'] if cli_encontrado else None
                if cli_encontrado:
                    st.info(f"**{cli_encontrado['nome']}** — {cli_encontrado.get('endereco','') or ''} {cli_encontrado.get('numero','') or ''}, {cli_encontrado.get('cidade_estado','') or ''} | Tel: {cli_encontrado.get('telefone','') or ''}")

            ag_descricao = st.text_area("Descrição / Objetivo da Visita:", height=90, key="ag_descricao")
            st.markdown("**Recorrência da visita:**")
            ag_rec1, ag_rec2 = st.columns(2)
            ag_recorrencia = ag_rec1.selectbox(
                "Criar ação recorrente?",
                ["Não", "Diariamente", "Semanalmente", "Mensalmente", "Anualmente"],
                key="ag_recorrencia",
            )
            dias_semana_agenda = {
                "Segunda": 0,
                "Terça": 1,
                "Quarta": 2,
                "Quinta": 3,
                "Sexta": 4,
                "Sábado": 5,
                "Domingo": 6,
            }
            ag_dia_semana = ag_data.weekday()
            ag_dia_mes = ag_data.day
            ag_data_anual = ag_data
            if ag_recorrencia == "Semanalmente":
                nome_dia_padrao = next(nome for nome, indice in dias_semana_agenda.items() if indice == ag_data.weekday())
                nome_dia_semanal = ag_rec2.selectbox(
                    "Dia da semana:", list(dias_semana_agenda),
                    index=list(dias_semana_agenda).index(nome_dia_padrao), key="ag_dia_semanal",
                )
                ag_dia_semana = dias_semana_agenda[nome_dia_semanal]
            elif ag_recorrencia == "Mensalmente":
                ag_dia_mes = ag_rec2.number_input(
                    "Dia do mês:", min_value=1, max_value=31, value=ag_data.day,
                    step=1, key="ag_dia_mensal",
                )
            elif ag_recorrencia == "Anualmente":
                ag_data_anual = ag_rec2.date_input(
                    "Data anual:", value=ag_data, format="DD/MM/YYYY", key="ag_data_anual"
                )

            ag_modo_termino = "Quantidade"
            ag_quantidade = 1
            ag_data_fim = ag_data
            if ag_recorrencia != "Não":
                at1, at2 = st.columns(2)
                ag_modo_termino = at1.selectbox(
                    "Duração da recorrência:",
                    ["Quantidade", "Até uma data", "Tempo indefinido"],
                    key="ag_modo_termino",
                )
                if ag_modo_termino == "Quantidade":
                    ag_quantidade = at2.number_input(
                        "Quantidade de ocorrências:", min_value=1, max_value=500,
                        value=4, step=1, key="ag_quantidade_recorrencia",
                    )
                elif ag_modo_termino == "Até uma data":
                    ag_data_fim = at2.date_input(
                        "Repetir até:", value=ag_data + timedelta(days=30),
                        format="DD/MM/YYYY", key="ag_data_fim_recorrencia",
                    )
                else:
                    at2.info("A agenda manterá automaticamente os próximos 12 meses.")

            if st.button("Salvar Agendamento", type="primary", width="stretch", key="btn_salvar_agenda"):
                erros = []
                if ag_tecnico == "-- Selecionar --":
                    erros.append("Selecione o técnico responsável.")
                nome_final = ag_cliente_nome if ag_manual or ag_cliente_sel == "-- Selecionar --" else ag_cliente_sel
                if not nome_final.strip():
                    erros.append("Informe o cliente a ser atendido.")
                if ag_modo_termino == "Até uma data" and ag_data_fim < ag_data:
                    erros.append("A data final da recorrência não pode ser anterior ao primeiro atendimento.")
                datas_agendamento = gerar_datas_agenda_configurada(
                    ag_data, ag_recorrencia,
                    quantidade=int(ag_quantidade) if ag_modo_termino == "Quantidade" else None,
                    data_fim=ag_data_fim if ag_modo_termino == "Até uma data" else None,
                    horizonte=(ag_data + timedelta(days=365)) if ag_modo_termino == "Tempo indefinido" else None,
                    dia_semana=ag_dia_semana, dia_mes=int(ag_dia_mes), data_anual=ag_data_anual,
                )
                h_ini = ag_hora_ini.strftime("%H:%M") if ag_hora_ini else ""
                h_fim = ag_hora_fim.strftime("%H:%M") if ag_hora_fim else ""
                if h_ini and h_fim:
                    for data_ag_item in datas_agendamento:
                        conflito = conflito_agenda_funcionario(ag_tecnico, data_ag_item.strftime("%Y-%m-%d"), h_ini, h_fim)
                        if conflito:
                            erros.append(f"{data_ag_item.strftime('%d/%m/%Y')}: {conflito}")
                            break
                if erros:
                    for e in erros:
                        st.error(e)
                else:
                    criado = datetime.now().strftime("%d/%m/%Y %H:%M")
                    conn_sv = conectar_banco()
                    csv_ = conn_sv.cursor()
                    recorrencia_id = None
                    if ag_recorrencia != "Não":
                        csv_.execute('''INSERT INTO agenda_recorrencias
                            (tecnico, cliente_id, cliente_nome, data_inicio, hora_inicio, hora_fim,
                             tipo_atendimento, descricao, periodicidade, dia_semana, dia_mes,
                             mes_anual, dia_anual, modo_termino, quantidade, data_fim,
                             ativa, criado_por, criado_em)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                            (ag_tecnico, ag_cliente_id, nome_final, ag_data.strftime("%Y-%m-%d"),
                             h_ini, h_fim, ag_tipo, ag_descricao, ag_recorrencia,
                             ag_dia_semana, int(ag_dia_mes), ag_data_anual.month, ag_data_anual.day,
                             ag_modo_termino, int(ag_quantidade) if ag_modo_termino == "Quantidade" else None,
                             ag_data_fim.strftime("%Y-%m-%d") if ag_modo_termino == "Até uma data" else None,
                             "Sim", st.session_state.get("username", ""), criado))
                        recorrencia_id = csv_.lastrowid
                    for indice_agendamento, data_ag_item in enumerate(datas_agendamento, 1):
                        descricao_ag_item = ag_descricao
                        if ag_recorrencia != "Não":
                            descricao_ag_item = (
                                f"{ag_descricao}\n\nRecorrência: {ag_recorrencia}; "
                                f"duração: {ag_modo_termino}."
                            ).strip()
                        csv_.execute('''INSERT INTO agenda_visitas
                            (tecnico, cliente_id, cliente_nome, data_visita, hora_inicio, hora_fim,
                             tipo_visita, descricao, status, criado_em, recorrencia_id, recorrencia_indice)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                            (ag_tecnico, ag_cliente_id, nome_final,
                             data_ag_item.strftime("%Y-%m-%d"), h_ini, h_fim,
                             ag_tipo, descricao_ag_item, "Agendado", criado,
                             recorrencia_id, indice_agendamento))
                    conn_sv.commit()
                    conn_sv.close()
                    st.session_state['agenda_salva'] = len(datas_agendamento)
                    st.rerun()

        with sub_ag2:
            st.subheader("Agenda de Visitas")

            import calendar
            mes_referencia_agenda = st.date_input(
                "Mês da agenda:", value=date.today().replace(day=1),
                format="DD/MM/YYYY", key="agenda_mes_referencia",
            ).replace(day=1)
            ultimo_dia_mes = calendar.monthrange(
                mes_referencia_agenda.year, mes_referencia_agenda.month
            )[1]
            conn_cal = conectar_banco(); ccal = conn_cal.cursor()
            ccal.execute(
                """SELECT * FROM agenda_visitas WHERE data_visita>=? AND data_visita<=?
                   AND COALESCE(status,'') <> 'Cancelado'
                   ORDER BY data_visita, hora_inicio""",
                (mes_referencia_agenda.strftime("%Y-%m-%d"),
                 mes_referencia_agenda.replace(day=ultimo_dia_mes).strftime("%Y-%m-%d")),
            )
            visitas_mes = [dict(item) for item in ccal.fetchall()]
            conn_cal.close()
            visitas_por_dia = {}
            for visita_mes in visitas_mes:
                dia_visita = (parse_data_flex(visita_mes.get("data_visita")) or mes_referencia_agenda).day
                visitas_por_dia.setdefault(dia_visita, []).append(visita_mes)
            st.markdown(
                f"#### {mes_referencia_agenda.strftime('%m/%Y')} — {len(visitas_mes)} compromisso(s)"
            )
            cabecalho_semana = st.columns(7)
            for coluna_dia, nome_dia in zip(cabecalho_semana, ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]):
                coluna_dia.markdown(f"**{nome_dia}**")
            for semana in calendar.monthcalendar(mes_referencia_agenda.year, mes_referencia_agenda.month):
                colunas_semana = st.columns(7)
                for coluna_dia, numero_dia in zip(colunas_semana, semana):
                    with coluna_dia.container(border=True):
                        if not numero_dia:
                            st.write(" ")
                            continue
                        compromissos_dia = visitas_por_dia.get(numero_dia, [])
                        st.markdown(f"**{numero_dia}**")
                        for compromisso in compromissos_dia:
                            if st.button(
                                f"{compromisso.get('hora_inicio') or '--:--'} "
                                f"{compromisso.get('cliente_nome') or 'Sem cliente'}",
                                key=f"cal_visita_{compromisso['id']}", width="stretch",
                                type='primary' if st.session_state.get('ag_id_edicao') == int(compromisso['id']) else 'secondary',
                            ):
                                visita_id = int(compromisso['id'])
                                _limpar_estado_editor_agenda(visita_id)
                                st.session_state['ag_id_edicao'] = visita_id
                                st.session_state['agenda_edit_expanded_id'] = visita_id
                                st.session_state['ag_fil_data'] = parse_data_flex(compromisso['data_visita'])
                                st.session_state['ag_fil_tec'] = 'Todos'
                                st.session_state['ag_fil_status_v2'] = 'Todos'
                                st.session_state['agenda_grade_versao'] = st.session_state.get('agenda_grade_versao', 0) + 1

            if st.session_state.get('ag_id_edicao'):
                st.info(f"Visita #{st.session_state['ag_id_edicao']} selecionada. Os detalhes e a edição estão abaixo da lista.")
            ag_f1, ag_f2, ag_f3 = st.columns(3)
            with ag_f1:
                filtro_tec = st.selectbox("Filtrar por Técnico:", ["Todos"] + usuarios_dsystem, key="ag_fil_tec")
            with ag_f2:
                filtro_status = st.selectbox(
                    "Filtrar por Status:",
                    ["Não realizados", "Todos", "Agendado", "Adiado", "Cancelado", "Atrasado", "Transferido", "Reagendado"],
                    key="ag_fil_status_v2",
                    help="Os realizados e concluídos continuam no histórico. Selecione Todos para exibi-los.",
                )
            with ag_f3:
                filtro_data = st.date_input(
                    "Filtrar por Data (deixe em branco para ver tudo):",
                    value=None,
                    key="ag_fil_data",
                    format="DD/MM/YYYY",
                )

            conn_vis = conectar_banco()
            conn_vis.row_factory = None
            cv = conn_vis.cursor()

            query_ag = "SELECT * FROM agenda_visitas WHERE 1=1"
            params_ag = []
            if filtro_tec != "Todos":
                query_ag += " AND tecnico=?"
                params_ag.append(filtro_tec)
            condicao_status, parametros_status = filtro_status_agenda(filtro_status)
            query_ag += condicao_status
            params_ag.extend(parametros_status)
            if filtro_data:
                query_ag += " AND data_visita=?"
                params_ag.append(filtro_data.strftime("%Y-%m-%d"))
            query_ag += " ORDER BY data_visita ASC, hora_inicio ASC"

            cv.execute(query_ag, params_ag)
            visitas = [dict(r) for r in cv.fetchall()]
            conn_vis.close()

            if not visitas:
                st.info("Nenhuma visita encontrada com os filtros selecionados.")
            else:
                linhas_visitas = [{
                    "ID": vis.get("id"), "Data": vis.get("data_visita"),
                    "Início": vis.get("hora_inicio"), "Fim": vis.get("hora_fim"),
                    "Cliente": vis.get("cliente_nome"), "Técnico": vis.get("tecnico"),
                    "Tipo": vis.get("tipo_visita"), "Status": vis.get("status"),
                } for vis in visitas]
                visita_clicada_id = tabela_clicavel_id(
                    st, linhas_visitas, f"agenda_visitas_grade_{st.session_state.get('agenda_grade_versao', 0)}", campo_id="ID"
                )
                if visita_clicada_id:
                    visita_id = int(visita_clicada_id)
                    if st.session_state.get("ag_id_edicao") != visita_id:
                        _limpar_estado_editor_agenda(visita_id)
                    st.session_state["ag_id_edicao"] = visita_id
                    st.session_state["agenda_edit_expanded_id"] = visita_id
                st.caption("Clique em qualquer informação da visita para abrir a edição abaixo.")
                from collections import defaultdict
                por_data = defaultdict(list)
                for v in visitas:
                    por_data[v['data_visita']].append(v)

                STATUS_CORES = {
                    "Agendado":    "#1a73e8",
                    "Realizado":   "#34a853",
                    "Adiado":      "#fbbc05",
                    "Atrasado":    "#f29900",
                    "Transferido": "#7b61ff",
                    "Concluído":   "#34a853",
                    "Cancelado":   "#ea4335",
                    "Reagendado":  "#fbbc05",
                }


                for data_str in sorted(por_data.keys()):
                    try:
                        data_label = data_extenso_br(data_str).capitalize()
                    except Exception:
                        data_label = data_str

                    st.markdown(f"#### {data_label}")

                    for vis in por_data[data_str]:
                        cor = STATUS_CORES.get(vis['status'], '#888')
                        with st.container():
                            from dsystem_erp.pages.agenda_visual import cartao_visita
                            st.markdown(cartao_visita(vis, cor), unsafe_allow_html=True)
                            if st.button(f"Selecionar visita #{vis['id']:04d}", key=f"agenda_select_{vis['id']}"):
                                visita_id = int(vis["id"])
                                _limpar_estado_editor_agenda(visita_id)
                                st.session_state["ag_id_edicao"] = visita_id
                                st.session_state["agenda_edit_expanded_id"] = visita_id
                                st.rerun()

                    st.write("")

                st.write("---")
                st.subheader("Alterar Status / Editar Visita")
                ag_id_sel = int(st.session_state.get("ag_id_edicao") or 0)
                if not ag_id_sel:
                    st.info("Selecione uma visita na tabela acima.")

                conn_ed2 = conectar_banco()
                conn_ed2.row_factory = None
                ced2 = conn_ed2.cursor()
                ced2.execute("SELECT * FROM agenda_visitas WHERE id=?", (ag_id_sel,))
                vis_ed = ced2.fetchone()
                conn_ed2.close()

                if vis_ed:
                    vis_ed = dict(vis_ed)
                    edit_key = int(ag_id_sel)
                    with st.expander(
                        f"Editando Visita #{ag_id_sel} — {vis_ed['cliente_nome']}",
                        expanded=st.session_state.get("agenda_edit_expanded_id") == edit_key
                    ):
                        e_ag1, e_ag2, e_ag3 = st.columns(3)
                        with e_ag1:
                            status_agenda_opcoes = ["Agendado", "Realizado", "Adiado", "Cancelado", "Atrasado", "Transferido", "Reagendado", "Concluído"]
                            e_status_ag = st.selectbox(
                                "Status:",
                                status_agenda_opcoes,
                                index=status_agenda_opcoes.index(vis_ed['status'])
                                if vis_ed['status'] in status_agenda_opcoes else 0,
                                key=f"e_status_ag_{edit_key}"
                            )
                        with e_ag2:
                            try:
                                e_data_ag = st.date_input(
                                    "Data:",
                                    value=datetime.strptime(vis_ed['data_visita'], "%Y-%m-%d").date(),
                                    key=f"e_data_ag_{edit_key}",
                                    format="DD/MM/YYYY",
                                )
                            except Exception:
                                e_data_ag = st.date_input(
                                    "Data:", value=date.today(), key=f"e_data_ag_{edit_key}", format="DD/MM/YYYY"
                                )
                        with e_ag3:
                            e_tec_ag = st.selectbox(
                                "Técnico / transferir para:",
                                usuarios_dsystem,
                                index=usuarios_dsystem.index(vis_ed['tecnico']) if vis_ed['tecnico'] in usuarios_dsystem else 0,
                                key=f"e_tec_ag_{edit_key}"
                            )

                        e_ag4, e_ag5 = st.columns(2)
                        with e_ag4:
                            try:
                                h_ini_def = datetime.strptime(vis_ed['hora_inicio'], "%H:%M").time() if vis_ed.get('hora_inicio') else None
                            except Exception:
                                h_ini_def = None
                            e_h_ini = st.time_input("Hora Início:", value=h_ini_def, key=f"e_h_ini_{edit_key}", step=1800)
                        with e_ag5:
                            try:
                                h_fim_def = datetime.strptime(vis_ed['hora_fim'], "%H:%M").time() if vis_ed.get('hora_fim') else None
                            except Exception:
                                h_fim_def = None
                            e_h_fim = st.time_input("Hora Fim:", value=h_fim_def, key=f"e_h_fim_{edit_key}", step=1800)

                        e_cli_ag = st.selectbox(
                            "Cliente:",
                            ["-- Manual --"] + nomes_clientes_ag,
                            index=(nomes_clientes_ag.index(vis_ed['cliente_nome']) + 1)
                            if vis_ed['cliente_nome'] in nomes_clientes_ag else 0,
                            key=f"e_cli_ag_{edit_key}"
                        )
                        if e_cli_ag == "-- Manual --":
                            e_cli_nome = st.text_input("Nome manual:", value=vis_ed['cliente_nome'], key=f"e_cli_nome_ag_{edit_key}")
                            e_cli_id = None
                        else:
                            e_cli_nome = e_cli_ag
                            cli_e = next((c for c in clientes_ag if c['nome'] == e_cli_ag), None)
                            e_cli_id = cli_e['id'] if cli_e else None

                        e_tipo_ag = st.selectbox(
                            "Tipo:",
                            tipos_agenda + ([vis_ed['tipo_visita']] if vis_ed.get('tipo_visita') not in tipos_agenda else []),
                            index=(tipos_agenda + ([vis_ed['tipo_visita']] if vis_ed.get('tipo_visita') not in tipos_agenda else [])).index(vis_ed['tipo_visita'])
                            if vis_ed.get('tipo_visita') else 0,
                            key=f"e_tipo_ag_{edit_key}"
                        )
                        e_desc_ag = st.text_area("Descrição:", value=vis_ed.get('descricao',''), height=80, key=f"e_desc_ag_{edit_key}")

                        btn_col1, btn_col2 = st.columns(2)
                        if btn_col1.button("Salvar Alterações", type="primary", key=f"btn_sv_ag_{edit_key}", width="stretch"):
                            h_ini_s = e_h_ini.strftime("%H:%M") if e_h_ini else ""
                            h_fim_s = e_h_fim.strftime("%H:%M") if e_h_fim else ""
                            conn_up = conectar_banco()
                            cup = conn_up.cursor()
                            cup.execute('''UPDATE agenda_visitas SET
                                tecnico=?, cliente_id=?, cliente_nome=?, data_visita=?,
                                hora_inicio=?, hora_fim=?, tipo_visita=?, descricao=?, status=?
                                WHERE id=?''',
                                (e_tec_ag, e_cli_id, e_cli_nome,
                                 e_data_ag.strftime("%Y-%m-%d"), h_ini_s, h_fim_s,
                                 e_tipo_ag, e_desc_ag, e_status_ag, ag_id_sel))
                            conn_up.commit()
                            conn_up.close()
                            st.toast("Visita atualizada!")
                            st.rerun()

                        if btn_col2.button("Cancelar agendamento", key=f"btn_cancel_ag_{edit_key}", width="stretch"):
                            conn_cancel = conectar_banco()
                            try:
                                conn_cancel.cursor().execute("UPDATE agenda_visitas SET status=? WHERE id=?", ("Cancelado", ag_id_sel))
                                conn_cancel.commit()
                            finally:
                                conn_cancel.close()
                            st.toast("Agendamento cancelado e retirado do calendário.")
                            st.rerun()

        with sub_ag3:
            st.subheader("Tipos de atendimento da agenda")
            novo_tipo_agenda = st.text_input("Novo tipo de atendimento:", key="agenda_tipo_novo")
            if st.button(
                "Cadastrar tipo", type="primary",
                disabled=not tem_permissao("atendimentos.edit") or not novo_tipo_agenda.strip(),
                key="agenda_tipo_salvar",
            ):
                conn_tipo_ag = conectar_banco(); c_tipo_ag = conn_tipo_ag.cursor()
                try:
                    c_tipo_ag.execute(
                        "INSERT INTO agenda_tipos_atendimento (nome, ativo, criado_por, criado_em) VALUES (?,?,?,?)",
                        (novo_tipo_agenda.strip(), "Sim", st.session_state.get("username", ""), agora_br()),
                    )
                    conn_tipo_ag.commit()
                except Exception:
                    conn_tipo_ag.rollback(); st.warning("Esse tipo de atendimento já está cadastrado.")
                else:
                    st.success("Tipo de atendimento cadastrado."); st.rerun()
                finally:
                    conn_tipo_ag.close()
            if tipos_agenda_cadastrados:
                st.dataframe([
                    {"ID": item.get("id"), "Tipo": item.get("nome"), "Ativo": item.get("ativo") or "Sim"}
                    for item in tipos_agenda_cadastrados
                ], width="stretch", hide_index=True)
                tipo_agenda_id = st.selectbox(
                    "Tipo para ativar/desativar:", [int(item["id"]) for item in tipos_agenda_cadastrados],
                    format_func=lambda valor: next(item.get("nome") for item in tipos_agenda_cadastrados if int(item["id"]) == valor),
                    key="agenda_tipo_gerenciar",
                )
                tipo_agenda_atual = next(item for item in tipos_agenda_cadastrados if int(item["id"]) == tipo_agenda_id)
                nome_tipo_agenda_editado = st.text_input(
                    "Nome do tipo:", value=tipo_agenda_atual.get("nome") or "",
                    key=f"agenda_tipo_nome_{tipo_agenda_id}",
                )
                status_tipo_agenda = "Não" if tipo_agenda_atual.get("ativo") != "Não" else "Sim"
                bt_ag_nome, bt_ag_status = st.columns(2)
                if bt_ag_nome.button(
                    "Salvar nome", disabled=(not tem_permissao("atendimentos.edit")
                                              or not nome_tipo_agenda_editado.strip()),
                    key="agenda_tipo_salvar_nome", width="stretch",
                ):
                    conn_tipo_ag = conectar_banco(); c_tipo_ag = conn_tipo_ag.cursor()
                    try:
                        c_tipo_ag.execute(
                            "UPDATE agenda_tipos_atendimento SET nome=? WHERE id=?",
                            (nome_tipo_agenda_editado.strip(), tipo_agenda_id),
                        )
                        conn_tipo_ag.commit()
                    except Exception:
                        conn_tipo_ag.rollback(); st.warning("Já existe um tipo com esse nome.")
                    else:
                        st.success("Tipo atualizado."); st.rerun()
                    finally:
                        conn_tipo_ag.close()
                if bt_ag_status.button(
                    "Desativar tipo" if status_tipo_agenda == "Não" else "Reativar tipo",
                    disabled=not tem_permissao("atendimentos.edit"), key="agenda_tipo_status", width="stretch",
                ):
                    conn_tipo_ag = conectar_banco(); c_tipo_ag = conn_tipo_ag.cursor()
                    c_tipo_ag.execute(
                        "UPDATE agenda_tipos_atendimento SET ativo=? WHERE id=?",
                        (status_tipo_agenda, tipo_agenda_id),
                    )
                    conn_tipo_ag.commit(); conn_tipo_ag.close(); st.rerun()

            st.divider()
            st.subheader("Recorrências ativas")
            conn_regras = conectar_banco(); cregras = conn_regras.cursor()
            cregras.execute("SELECT * FROM agenda_recorrencias WHERE ativa='Sim' ORDER BY id DESC")
            regras_ativas = [dict(item) for item in cregras.fetchall()]
            conn_regras.close()
            if regras_ativas:
                st.dataframe([{
                    "ID": item.get("id"), "Cliente": item.get("cliente_nome"),
                    "Técnico": item.get("tecnico"), "Tipo": item.get("tipo_atendimento"),
                    "Periodicidade": item.get("periodicidade"), "Duração": item.get("modo_termino"),
                } for item in regras_ativas], width="stretch", hide_index=True)
                regra_encerrar_id = st.selectbox(
                    "Recorrência para encerrar:", [int(item["id"]) for item in regras_ativas],
                    format_func=lambda valor: next(
                        f"#{valor} - {item.get('cliente_nome') or 'Sem cliente'} - {item.get('tipo_atendimento') or ''}"
                        for item in regras_ativas if int(item["id"]) == valor
                    ), key="agenda_regra_encerrar_id",
                )
                if st.button(
                    "Encerrar recorrência", disabled=not tem_permissao("atendimentos.edit"),
                    key="agenda_regra_encerrar",
                ):
                    conn_regras = conectar_banco(); cregras = conn_regras.cursor()
                    cregras.execute("UPDATE agenda_recorrencias SET ativa='Não' WHERE id=?", (regra_encerrar_id,))
                    conn_regras.commit(); conn_regras.close(); st.success("Recorrência encerrada."); st.rerun()
            else:
                st.info("Nenhuma recorrência ativa.")

        with sub_ag4:
            st.subheader("Lançamento rápido de atividades")
            st.caption("Registre tarefas do dia a dia com data, horário e responsável pela execução.")
            atv1, atv2, atv3 = st.columns([2, 1, 1])
            atividade_rapida = atv1.text_input("Atividade:", key="atividade_rapida_desc")
            data_atividade = atv2.date_input(
                "Data de execução:", value=date.today(), format="DD/MM/YYYY", key="atividade_rapida_data"
            )
            hora_atividade = atv3.time_input(
                "Hora de execução:", value=None, step=1800, key="atividade_rapida_hora"
            )
            atv4, atv5 = st.columns(2)
            executor_atividade = atv4.selectbox(
                "Quem irá executar:", ["-- Selecionar --"] + usuarios_dsystem,
                key="atividade_rapida_executor",
            )
            cliente_atividade_nome = atv5.selectbox(
                "Cliente (opcional):", ["-- Sem cliente --"] + nomes_clientes_ag,
                key="atividade_rapida_cliente",
            )
            if st.button(
                "Lançar atividade", type="primary", width="stretch",
                disabled=(not tem_permissao("atendimentos.edit") or not atividade_rapida.strip()
                          or executor_atividade == "-- Selecionar --"),
                key="atividade_rapida_salvar",
            ):
                cliente_atividade = next(
                    (item for item in clientes_ag if item.get("nome") == cliente_atividade_nome), None
                )
                conn_atv = conectar_banco(); catv = conn_atv.cursor()
                catv.execute('''INSERT INTO agenda_atividades
                    (atividade, cliente_id, cliente_nome, data_execucao, hora_execucao,
                     executor, status, criado_por, criado_em)
                    VALUES (?,?,?,?,?,?,?,?,?)''',
                    (atividade_rapida.strip(), (cliente_atividade or {}).get("id"),
                     "" if cliente_atividade_nome == "-- Sem cliente --" else cliente_atividade_nome,
                     data_atividade.strftime("%Y-%m-%d"),
                     hora_atividade.strftime("%H:%M") if hora_atividade else "",
                     executor_atividade, "Pendente", st.session_state.get("username", ""), agora_br()))
                conn_atv.commit(); conn_atv.close(); st.success("Atividade lançada."); st.rerun()

            conn_atv = conectar_banco(); catv = conn_atv.cursor()
            catv.execute("SELECT * FROM agenda_atividades ORDER BY data_execucao, hora_execucao, id DESC")
            atividades = [dict(item) for item in catv.fetchall()]
            conn_atv.close()
            filtro_atv_status = st.selectbox(
                "Situação:", ["Pendentes", "Todas", "Concluída", "Cancelada"], key="atividade_filtro_status"
            )
            if filtro_atv_status == "Pendentes":
                atividades = [item for item in atividades if item.get("status") == "Pendente"]
            elif filtro_atv_status != "Todas":
                atividades = [item for item in atividades if item.get("status") == filtro_atv_status]
            linhas_atividades = [{
                "ID": item.get("id"), "Data": data_para_br(item.get("data_execucao")),
                "Hora": item.get("hora_execucao"), "Atividade": item.get("atividade"),
                "Cliente": item.get("cliente_nome"), "Executor": item.get("executor"),
                "Status": item.get("status"),
            } for item in atividades]
            atividade_id = tabela_clicavel_id(
                st, linhas_atividades, "agenda_atividades_grade", campo_id="ID"
            ) if linhas_atividades else None
            if atividade_id:
                atividade_aberta = next(item for item in atividades if int(item.get("id")) == int(atividade_id))
                novo_status_atividade = st.selectbox(
                    "Atualizar atividade:", ["Pendente", "Concluída", "Cancelada"],
                    index=["Pendente", "Concluída", "Cancelada"].index(atividade_aberta.get("status") or "Pendente"),
                    key=f"atividade_status_{atividade_id}",
                )
                if st.button(
                    "Salvar situação da atividade",
                    disabled=not tem_permissao("atendimentos.edit"),
                    key=f"atividade_status_salvar_{atividade_id}",
                ):
                    conn_atv = conectar_banco(); catv = conn_atv.cursor()
                    catv.execute(
                        "UPDATE agenda_atividades SET status=?, alterado_por=?, alterado_em=? WHERE id=?",
                        (novo_status_atividade, st.session_state.get("username", ""), agora_br(), atividade_id),
                    )
                    conn_atv.commit(); conn_atv.close(); st.rerun()


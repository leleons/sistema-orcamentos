from __future__ import annotations

from dsystem_erp.app_context import aplicar_contexto_pagina


def renderizar_gestao_emails(ctx: dict) -> None:
    aplicar_contexto_pagina(ctx, globals())
    st.warning("Gestão de E-mails agora fica dentro de ServiceDesk > Infraestrutura TI, na aba Gestão de E-mails.")
    if st.button("Abrir Infraestrutura TI", type="primary", width="stretch", key="abrir_infra_emails_redirecionado"):
        st.session_state["pagina_atual"] = "Infraestrutura TI"
        st.rerun()
    st.stop()
    st.title("Gestão de E-mails")
    aba1, aba2 = st.tabs(["Cadastrar Conta", "Banco de Dados"])

    with aba1:
        clis = buscar_clientes()
        nclis = ["-- Avulso --"] + [x['nome'] for x in clis]
        evinc = st.selectbox("Vincular a Cliente:", nclis)
        
        qtd_emails = st.number_input("Quantas contas de e-mail deseja cadastrar agora?", min_value=1, max_value=20, value=1)
        
        contas_para_salvar = []
        
        for i in range(qtd_emails):
            st.markdown(f"**Conta de E-mail {i+1}**")
            efun = st.text_input(f"Usuário / Funcionário da Conta {i+1}:", key=f"efun_{i}")
            
            e1, e2, e3 = st.columns(3)
            with e1: email = st.text_input(f"Endereço de E-mail {i+1}:", key=f"email_{i}")
            with e2: esenha = st.text_input(f"Senha {i+1}:", type="password", key=f"senha_{i}")
            with e3: eali = st.text_input(f"Aliases {i+1}:", key=f"ali_{i}")
                
            e4, e5, e6 = st.columns(3)
            with e4: eprov = st.text_input(f"Provedor {i+1}:", key=f"prov_{i}")
            with e5: ein = st.text_input(f"Entrada (IMAP/POP) {i+1}:", key=f"in_{i}")
            with e6: eout = st.text_input(f"Saída (SMTP) {i+1}:", key=f"out_{i}")
            
            if email: 
                contas_para_salvar.append((evinc, efun, email, esenha, eali, eprov, ein, eout))
            st.write("---")
            
        if st.button("Salvar Todas as Contas", type="primary"):
            if contas_para_salvar:
                conn = conectar_banco()
                c = conn.cursor()
                for conta in contas_para_salvar:
                  
                    c.execute('''INSERT INTO emails_clientes (cliente_vinculado, funcionario, email, senha, aliases, provedor, config_entrada, config_saida) 
                                 VALUES (?,?,?,?,?,?,?,?)''', conta) 
                conn.commit()
                conn.close()
                st.success(f"{len(contas_para_salvar)} E-mail(s) cadastrado(s) com sucesso!")
                st.rerun()
            else: 
                st.error("Preencha pelo menos um endereço de e-mail.")

    with aba2:
        conn = conectar_banco()
        conn.row_factory = None
        c = conn.cursor()
        c.execute('SELECT * FROM emails_clientes ORDER BY id DESC')
        erows = c.fetchall()
        conn.close()
        erows = filtrar_registros_por_empresa(erows, "cliente_vinculado")
        
        st.subheader("Pesquisar e-mails por empresa")
        empresas_cadastradas = sorted({r['cliente_vinculado'] for r in erows if r['cliente_vinculado']})
        empresa_filtro = st.selectbox("Empresa/cliente:", ["Todas as empresas"] + empresas_cadastradas)
        termo_email = st.text_input("Pesquisar por e-mail, usuário, funcionário, provedor ou alias:")

        erows_filtrados = list(erows)
        if empresa_filtro != "Todas as empresas":
            erows_filtrados = [r for r in erows_filtrados if r['cliente_vinculado'] == empresa_filtro]
        if termo_email.strip():
            termo = termo_email.strip().lower()
            erows_filtrados = [r for r in erows_filtrados if termo in " ".join(str(dict(r).get(campo, "")) for campo in dict(r).keys()).lower()]

        if erows: 
            st.write(f"Registros encontrados: {len(erows_filtrados)} de {len(erows)}")
            with st.expander("Liberar visualização de senhas", expanded=False):
                st.caption("Por segurança, as senhas ficam ocultas. Para visualizar ou baixar com senha real, confirme a senha do usuário logado.")
                senha_admin_email = st.text_input("Senha do usuário atual:", type="password", key="senha_admin_emails")
                if st.button("Liberar senhas nesta sessão", key="btn_liberar_senhas_email"):
                    if confirmar_senha_usuario_atual(senha_admin_email):
                        st.session_state["emails_senhas_liberadas"] = True
                        registrar_evento_sistema("update", "emails_clientes", "", empresa_filtro, {"evento": "Visualização de senhas liberada"})
                        st.success("Senhas liberadas nesta sessão.")
                    else:
                        st.error("Senha inválida.")
                if st.session_state.get("emails_senhas_liberadas"):
                    if st.button("Ocultar senhas novamente", key="btn_ocultar_senhas_email"):
                        st.session_state["emails_senhas_liberadas"] = False
                        st.rerun()
                    st.warning("Senhas reais visíveis apenas para esta sessão.")
            incluir_senhas_email = bool(st.session_state.get("emails_senhas_liberadas"))
            dados_emails = preparar_tabela_emails(erows_filtrados, incluir_senhas=incluir_senhas_email)
            if erows_filtrados:
                st.dataframe(dados_emails, width="stretch", hide_index=True)
            else:
                st.warning("Nenhum e-mail encontrado com esse filtro. Troque para 'Todas as empresas' ou limpe a pesquisa.")

            nome_empresa_arquivo = empresa_filtro if empresa_filtro != "Todas as empresas" else "todos_os_emails"
            nome_empresa_arquivo = "".join(ch if ch.isalnum() else "_" for ch in nome_empresa_arquivo).strip("_").lower()
            titulo_exportacao = f"Relatório de E-mails - {empresa_filtro}"

            col_exp1, col_exp2 = st.columns(2)
            with col_exp1:
                st.download_button("Baixar tabela em Excel", data=gerar_excel_emails(erows_filtrados, titulo_exportacao, incluir_senhas=incluir_senhas_email), file_name=f"emails_{nome_empresa_arquivo}.xls", mime="application/vnd.ms-excel", width="stretch")
            with col_exp2:
                st.download_button("Baixar tabela em PDF", data=gerar_pdf_emails(erows_filtrados, titulo_exportacao, incluir_senhas=incluir_senhas_email), file_name=f"emails_{nome_empresa_arquivo}.pdf", mime="application/pdf", width="stretch")
        else: 
            st.info("Sem contas de e-mail registadas.")

        act_em = []
        if tem_permissao("emails.edit"): act_em.append("Editar Completo")
        if tem_permissao("emails.delete"): act_em.append("Excluir E-mail")
        
        if act_em:
            st.write("---")
            aem = st.radio("Ação:", act_em, horizontal=True)
            
            if aem == "Excluir E-mail":
                ide_del = st.number_input("ID para excluir:", min_value=1, step=1, key="del_em_id")
                if st.button("Excluir permanentemente", key="btn_del_em"): 
                    deletar_registro('emails_clientes', 'id', ide_del)
                    st.success("Excluído.")
                    st.rerun()
                    
            elif aem == "Editar Completo":
                ide_ed = st.number_input("ID para editar:", min_value=1, step=1, key="edit_em_id")
                conn = conectar_banco()
                conn.row_factory = None
                c = conn.cursor()
                c.execute('SELECT * FROM emails_clientes WHERE id=?', (ide_ed,))
                edata = c.fetchone()
                conn.close()
                
                if edata:
                    with st.expander(f"Editando E-mail: {edata['email']}", expanded=True):
                        clientes_email = ["-- Avulso --"] + [x['nome'] for x in buscar_clientes()]
                        cliente_atual = edata.get('cliente_vinculado') or "-- Avulso --"
                        idx_cliente_email = clientes_email.index(cliente_atual) if cliente_atual in clientes_email else 0
                        ne_cliente = st.selectbox("Cliente vinculado:", clientes_email, index=idx_cliente_email, key=f"em_cliente_{ide_ed}")
                        ne_email = st.text_input("Atualizar E-mail:", value=edata['email'], key=f"em_email_{ide_ed}")
                        ne_senha = st.text_input("Nova senha (deixe em branco para manter):", type="password", key=f"em_senha_{ide_ed}")
                        ne_func = st.text_input("Atualizar Funcionário:", value=edata['funcionario'], key=f"em_func_{ide_ed}")
                        ne_aliases = st.text_input("Aliases:", value=edata.get('aliases') or "", key=f"em_aliases_{ide_ed}")
                        ne_provedor = st.text_input("Provedor:", value=edata.get('provedor') or "", key=f"em_prov_{ide_ed}")
                        ne_entrada = st.text_input("Entrada (IMAP/POP):", value=edata.get('config_entrada') or "", key=f"em_entrada_{ide_ed}")
                        ne_saida = st.text_input("Saída (SMTP):", value=edata.get('config_saida') or "", key=f"em_saida_{ide_ed}")
                        
                        c_eb1, c_eb2, c_eb3 = st.columns(3)
                        with c_eb1: ne_bkp = st.selectbox("Backup Feito?", ["Não", "Sim"], index=1 if edata['backup_realizado']=="Sim" else 0, key=f"em_bkp_{ide_ed}")
                        with c_eb2: ne_dbkp = st.text_input("Data do Backup:", value=edata['data_backup'], key=f"em_dbkp_{ide_ed}")
                        with c_eb3: ne_cap = st.text_input("Nova Capacidade:", value=edata['capacidade'], key=f"em_cap_{ide_ed}")
                        
                        if st.button("Guardar Edição do E-mail", type="primary", key=f"btn_save_em_{ide_ed}"):
                            conn = conectar_banco()
                            c = conn.cursor()
                            senha_email = ne_senha if ne_senha else edata.get('senha')
                            c.execute('''UPDATE emails_clientes SET cliente_vinculado=?, email=?, senha=?, funcionario=?, aliases=?, provedor=?, config_entrada=?, config_saida=?, backup_realizado=?, data_backup=?, capacidade=? WHERE id=?''', (ne_cliente, ne_email, senha_email, ne_func, ne_aliases, ne_provedor, ne_entrada, ne_saida, ne_bkp, ne_dbkp, ne_cap, ide_ed))
                            conn.commit()
                            conn.close()
                            st.success("E-mail atualizado!")
                            st.rerun()


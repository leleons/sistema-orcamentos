"""Telas de abertura, acompanhamento e gestão de chamados."""

from __future__ import annotations

from dsystem_erp.app_context import aplicar_contexto_pagina
from dsystem_erp.ui_consulta import tabela_clicavel_id

def renderizar_chat_chamado(chamado, cliente_portal, ctx=None):
    if ctx is not None:
        aplicar_contexto_pagina(ctx, globals())
    mensagens = mensagens_chamado(chamado.get("id"))
    if not mensagens:
        mensagens = [{
            "id": f"desc_{chamado.get('id')}",
            "autor_tipo": "cliente",
            "autor_nome": chamado.get("solicitante") or cliente_portal,
            "mensagem": chamado.get("descricao") or "",
            "criado_em": chamado.get("criado_em") or "",
        }]

    for msg in mensagens:
        autor_tipo = (msg.get("autor_tipo") or "").lower()
        classe = "chat-bubble cliente" if autor_tipo == "cliente" else "chat-bubble equipe"
        nome = h(msg.get("autor_nome") or ("Cliente" if autor_tipo == "cliente" else "Equipe Dsystem"))
        data_msg = h(msg.get("criado_em") or "")
        texto = h(msg.get("mensagem") or "").replace("\n", "<br>")
        st.markdown(
            f"""
<div class="{classe}">
  <div class="chat-meta">{nome} | {data_msg}</div>
  <div class="chat-text">{texto}</div>
</div>
""",
            unsafe_allow_html=True,
        )
        if msg.get("anexo"):
            if str(msg.get("anexo_mime") or "").startswith("image/"):
                st.image(msg.get("anexo"), caption=msg.get("anexo_nome") or "Imagem do chamado", width=420)
            st.download_button(
                f"Baixar anexo: {msg.get('anexo_nome') or 'arquivo'}",
                data=msg.get("anexo"),
                file_name=msg.get("anexo_nome") or "anexo",
                mime=msg.get("anexo_mime") or "application/octet-stream",
                key=f"baixar_anexo_chamado_msg_{msg.get('id')}",
            )

def renderizar_abertura_chamado(cliente_portal, cliente_id=None, ctx=None):
    if ctx is not None:
        aplicar_contexto_pagina(ctx, globals())
    st.subheader("Abrir chamado")
    if st.session_state.get("acao_portal") == "abrir_chamado":
        st.info("Preencha as informações abaixo para registrar seu chamado.")
    st.write("Descreva o que precisa ser feito. A equipe combinará o atendimento com você pelo próprio chamado.")
    msg_whats = f"Olá, sou {cliente_portal or 'cliente'} e quero abrir um chamado pelo portal."
    st.link_button("Falar pelo WhatsApp oficial", whatsapp_oficial_url(msg_whats), width="stretch")
    with st.form("form_novo_chamado_cliente"):
        c0, c1, c2 = st.columns(3)
        area_destino = c0.selectbox("Com quem deseja falar:", AREAS_CHAMADO)
        solicitante = c1.text_input("Solicitante:", value=st.session_state.get("username", ""))
        tipo = c2.selectbox("Tipo de atendimento:", ["Remoto", "Presencial", "Presencial ou remoto"])
        titulo = st.text_input("Assunto:")
        descricao = st.text_area("Informações do que precisa:", height=130)
        imagem = st.file_uploader("Imagem opcional:", type=TIPOS_IMAGEM_UPLOAD, key="novo_chamado_imagem")
        enviar = st.form_submit_button("Enviar chamado para Daniel.fabio", type="primary", width="stretch")

    if enviar:
        erros = []
        if not cliente_portal:
            erros.append("Cliente não identificado para abrir o chamado.")
        if not titulo.strip():
            erros.append("Informe o assunto do chamado.")
        if not descricao.strip():
            erros.append("Descreva o que precisa ser feito.")
        if imagem and not upload_dentro_limite(imagem):
            erros.append("A imagem ultrapassa o limite permitido.")
        if erros:
            for erro in erros:
                st.error(erro)
            return

        agora = datetime.now().strftime("%d/%m/%Y %H:%M")
        conn = conectar_banco()
        c = conn.cursor()
        funcionario_inicial = responsavel_area_chamado(area_destino)
        c.execute(
            """INSERT INTO chamados_cliente
               (cliente_id, cliente_nome, solicitante, area_destino, tipo_atendimento, data_solicitada,
                hora_inicio, hora_fim, titulo, descricao, status, administrador,
                funcionario_designado, criado_por, criado_em, atualizado_em)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                cliente_id,
                cliente_portal,
                solicitante,
                area_destino,
                tipo,
                "",
                "",
                "",
                titulo,
                descricao,
                "Novo",
                "Daniel.fabio",
                funcionario_inicial,
                st.session_state.get("username", ""),
                agora,
                agora,
            ),
        )
        chamado_id_novo = c.lastrowid
        anexo_dados, anexo_nome, anexo_mime = dados_upload(imagem)
        c.execute(
            """INSERT INTO chamados_mensagens
               (chamado_id, autor_tipo, autor_nome, mensagem, anexo_nome, anexo_mime, anexo, criado_em)
               VALUES (?,?,?,?,?,?,?,?)""",
            (chamado_id_novo, "cliente", solicitante or cliente_portal, descricao,
             anexo_nome, anexo_mime, anexo_dados, agora),
        )
        conn.commit()
        conn.close()
        destino = "Daniel.fabio" if funcionario_inicial else "fila de suporte"
        st.success(f"Chamado enviado para {area_destino} ({destino}).")
        st.rerun()

def renderizar_chamados_cliente(cliente_portal, cliente_id=None, ctx=None):
    if ctx is not None:
        aplicar_contexto_pagina(ctx, globals())
    st.subheader("Meus chamados")
    conn = conectar_banco()
    c = conn.cursor(dictionary=True)
    if cliente_id:
        c.execute(
            "SELECT * FROM chamados_cliente WHERE cliente_id=%s OR (cliente_id IS NULL AND cliente_nome=%s) ORDER BY id DESC",
            (cliente_id, cliente_portal),
        )
    else:
        c.execute("SELECT * FROM chamados_cliente WHERE cliente_nome=%s ORDER BY id DESC", (cliente_portal,))
    chamados = c.fetchall()
    conn.close()

    if not chamados:
        st.info("Nenhum chamado aberto para este cliente.")
        return

    filtro_status = st.selectbox(
        "Filtrar chamados:",
        ["Todos", "Abertos", "Aguardando cliente", "Concluídos", "Cancelados"],
        key="portal_chamados_filtro_status",
    )
    if filtro_status == "Abertos":
        chamados = [c for c in chamados if (c.get("status") or "Novo") not in ("Concluído", "Concluido", "Cancelado")]
    elif filtro_status == "Aguardando cliente":
        chamados = [c for c in chamados if "aguardando" in (c.get("status") or "").lower()]
    elif filtro_status == "Concluídos":
        chamados = [c for c in chamados if (c.get("status") or "") in ("Concluído", "Concluido")]
    elif filtro_status == "Cancelados":
        chamados = [c for c in chamados if (c.get("status") or "") == "Cancelado"]

    if not chamados:
        st.info("Nenhum chamado encontrado neste filtro.")
        return

    opcoes = [f"#{c.get('id')} - {c.get('titulo') or 'Sem assunto'}" for c in chamados]
    destaque = str(st.session_state.get("chamado_destacado") or "")
    idx_padrao = next((i for i, c in enumerate(chamados) if str(c.get("id")) == destaque), 0)
    escolha = st.selectbox("Selecione um chamado para conversar:", opcoes, index=idx_padrao, key="portal_chamado_chat_sel")
    chamado = chamados[opcoes.index(escolha)]

    data_ch, inicio_ch, fim_ch, tipo_ch, descricao_ch = periodo_chamado(chamado)
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Chamado", f"#{chamado.get('id')}")
    r2.metric("Status", chamado.get("status") or "Novo")
    r3.metric("Área", chamado.get("area_destino") or "Suporte")
    r4.metric("Responsável", chamado.get("funcionario_designado") or "Fila")

    st.markdown(f"#### {chamado.get('titulo') or 'Sem assunto'}")
    st.caption(f"{tipo_ch or 'Atendimento'} · criado em {chamado.get('criado_em') or '-'}")

    encerrado_cliente = (chamado.get("status") or "") in ("Concluído", "Concluido", "Fechado", "Cancelado")
    with st.expander("Editar informações do chamado", expanded=False):
        with st.form(f"form_editar_chamado_cliente_{chamado.get('id')}"):
            titulo_editado = st.text_input("Assunto:", value=chamado.get("titulo") or "")
            descricao_editada = st.text_area("Descrição principal:", value=chamado.get("descricao") or "", height=120)
            salvar_edicao = st.form_submit_button("Salvar informações", width="stretch", disabled=encerrado_cliente)
        if salvar_edicao:
            agora_edicao = datetime.now().strftime("%d/%m/%Y %H:%M")
            conn_ed = conectar_banco()
            ced = conn_ed.cursor()
            ced.execute(
                "UPDATE chamados_cliente SET titulo=?, descricao=?, atualizado_em=? WHERE id=? AND cliente_nome=?",
                (titulo_editado.strip(), descricao_editada.strip(), agora_edicao, chamado.get("id"), cliente_portal),
            )
            ced.execute(
                "INSERT INTO chamados_mensagens (chamado_id, autor_tipo, autor_nome, mensagem, criado_em) VALUES (?,?,?,?,?)",
                (chamado.get("id"), "cliente", st.session_state.get("username") or cliente_portal,
                 "As informações principais do chamado foram atualizadas pelo cliente.", agora_edicao),
            )
            conn_ed.commit()
            conn_ed.close()
            st.success("Chamado atualizado sem apagar o histórico da conversa.")
            st.rerun()

    if chamado.get("ajuste_descricao") or chamado.get("ajuste_data"):
        st.info("Daniel.fabio sugeriu alterações para este pedido. Confira e aprove ou recuse abaixo.")

    renderizar_chat_chamado(chamado, cliente_portal)

    st.markdown("#### Responder chamado")
    with st.form(f"form_responder_chamado_{chamado.get('id')}", clear_on_submit=True):
        resposta = st.text_area("Mensagem:", height=110, key=f"chat_resp_{chamado.get('id')}")
        anexo = st.file_uploader("Imagem opcional:", type=TIPOS_IMAGEM_UPLOAD, key=f"chat_anexo_{chamado.get('id')}")
        enviar = st.form_submit_button("Enviar mensagem", type="primary", width="stretch", disabled=encerrado_cliente)
    if enviar:
        if not resposta.strip() and not anexo:
            st.error("Digite uma mensagem ou anexe um arquivo.")
        elif anexo and not upload_dentro_limite(anexo):
            erro_upload_grande("anexo")
        else:
            salvar_mensagem_chamado(
                chamado.get("id"),
                "cliente" if st.session_state.get("tipo_login") == "cliente" else "equipe",
                st.session_state.get("username") or cliente_portal,
                resposta.strip(),
                anexo,
            )
            st.success("Mensagem enviada.")
            st.rerun()

    if not encerrado_cliente:
        with st.expander("Cancelar chamado", expanded=False):
            st.caption("O chamado sairá dos abertos, mas todo o lançamento e a conversa continuarão no histórico.")
            motivo_cancelamento = st.text_area("Motivo do cancelamento:", key=f"motivo_cancelar_ch_{chamado.get('id')}")
            if st.button("Confirmar cancelamento", key=f"cancelar_ch_{chamado.get('id')}", width="stretch"):
                agora_cancelamento = datetime.now().strftime("%d/%m/%Y %H:%M")
                conn_can = conectar_banco()
                ccan = conn_can.cursor()
                ccan.execute(
                    "UPDATE chamados_cliente SET status='Cancelado', atualizado_em=? WHERE id=? AND cliente_nome=?",
                    (agora_cancelamento, chamado.get("id"), cliente_portal),
                )
                ccan.execute(
                    "INSERT INTO chamados_mensagens (chamado_id, autor_tipo, autor_nome, mensagem, criado_em) VALUES (?,?,?,?,?)",
                    (chamado.get("id"), "cliente", st.session_state.get("username") or cliente_portal,
                     f"Chamado cancelado pelo cliente. {motivo_cancelamento}".strip(), agora_cancelamento),
                )
                conn_can.commit()
                conn_can.close()
                st.success("Chamado cancelado e mantido no histórico.")
                st.rerun()

    if chamado.get("status") == "Modificado - aguardando aprovação":
        st.markdown("#### Aprovação de alterações")
        resposta_decisao = st.text_area("Observação sobre a decisão:", key=f"resp_cli_ch_{chamado['id']}")
        b1, b2 = st.columns(2)
        if b1.button("Aprovar alterações", key=f"aprov_ch_{chamado['id']}", width="stretch"):
            conn_ap = conectar_banco()
            cap = conn_ap.cursor()
            agora = datetime.now().strftime("%d/%m/%Y %H:%M")
            cap.execute(
                "UPDATE chamados_cliente SET status=?, resposta_cliente=?, atualizado_em=? WHERE id=?",
                ("Aprovado pelo cliente", resposta_decisao, agora, chamado["id"]),
            )
            cap.execute(
                "INSERT INTO chamados_mensagens (chamado_id, autor_tipo, autor_nome, mensagem, criado_em) VALUES (?,?,?,?,?)",
                (chamado["id"], "cliente", st.session_state.get("username") or cliente_portal, f"Alterações aprovadas. {resposta_decisao}".strip(), agora),
            )
            conn_ap.commit()
            conn_ap.close()
            st.success("Alterações aprovadas.")
            st.rerun()
        if b2.button("Recusar alterações", key=f"rec_ch_{chamado['id']}", width="stretch"):
            conn_rec = conectar_banco()
            crec = conn_rec.cursor()
            agora = datetime.now().strftime("%d/%m/%Y %H:%M")
            crec.execute(
                "UPDATE chamados_cliente SET status=?, resposta_cliente=?, atualizado_em=? WHERE id=?",
                ("Recusado pelo cliente", resposta_decisao, agora, chamado["id"]),
            )
            crec.execute(
                "INSERT INTO chamados_mensagens (chamado_id, autor_tipo, autor_nome, mensagem, criado_em) VALUES (?,?,?,?,?)",
                (chamado["id"], "cliente", st.session_state.get("username") or cliente_portal, f"Alterações recusadas. {resposta_decisao}".strip(), agora),
            )
            conn_rec.commit()
            conn_rec.close()
            st.warning("Alterações recusadas.")
            st.rerun()

def renderizar_propostas_contratos(cliente_portal, cliente_id=None, ctx=None):
    if ctx is not None:
        aplicar_contexto_pagina(ctx, globals())
    st.subheader("Propostas/Contratos")

    if st.session_state.get("tipo_login") != "cliente":
        st.write("Envie propostas ou contratos para o cliente selecionado no portal.")
        with st.form(f"form_envio_proposta_{cliente_id or cliente_portal}"):
            p1, p2 = st.columns(2)
            tipo = p1.selectbox("Tipo:", ["Proposta", "Contrato"])
            titulo = p2.text_input("Título:")
            descricao = st.text_area("Observação para o cliente:", height=90)
            arquivo = st.file_uploader("Arquivo da proposta/contrato:", type=None)
            enviar = st.form_submit_button("Enviar para o cliente", type="primary", width="stretch")

        if enviar:
            if not cliente_portal:
                st.error("Selecione um cliente antes de enviar.")
            elif not titulo.strip():
                st.error("Informe o título.")
            elif arquivo is None:
                st.error("Selecione um arquivo.")
            elif not upload_dentro_limite(arquivo):
                erro_upload_grande("arquivo")
            else:
                conn_env = conectar_banco()
                cenv = conn_env.cursor()
                cenv.execute(
                    """INSERT INTO propostas_contratos_cliente
                       (cliente_id, cliente_nome, tipo, titulo, descricao, nome_arquivo, mime_type,
                        arquivo, status, criado_por, criado_em)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        cliente_id,
                        cliente_portal,
                        tipo,
                        titulo,
                        descricao,
                        arquivo.name,
                        arquivo.type or "application/octet-stream",
                        arquivo.getvalue(),
                        "Pendente",
                        st.session_state.get("username", ""),
                        datetime.now().strftime("%d/%m/%Y %H:%M"),
                    ),
                )
                if tipo == "Contrato":
                    salvar_contrato_gerado(
                        conn_env, tipo=titulo.strip() or "Contrato", parte_tipo="Cliente",
                        parte_id=cliente_id, parte_nome=cliente_portal, nome_arquivo=arquivo.name,
                        arquivo=arquivo.getvalue(), criado_por=st.session_state.get("username", ""),
                        criado_em=datetime.now().strftime("%d/%m/%Y %H:%M"),
                    )
                conn_env.commit()
                conn_env.close()
                st.success("Arquivo enviado para o cliente.")
                st.rerun()

    conn = conectar_banco()
    c = conn.cursor()
    c.execute(
        """SELECT id, tipo, titulo, descricao, nome_arquivo, mime_type, arquivo, status,
                  resposta_cliente, criado_por, criado_em, respondido_em
           FROM propostas_contratos_cliente
           WHERE cliente_nome=%s
           ORDER BY id DESC""",
        (cliente_portal,),
    )
    propostas = c.fetchall()
    conn.close()

    if not propostas:
        st.info("Nenhuma proposta ou contrato enviado para este cliente.")
        return

    if st.session_state.get("tipo_login") != "cliente":
        retornos = [
            p for p in propostas
            if (p.get("resposta_cliente") or "").strip() or p.get("status") == "Contraproposta"
        ]
        if retornos:
            st.write("---")
            st.subheader("Retornos do cliente")
            for proposta in retornos:
                with st.expander(f"#{proposta['id']} - {proposta.get('titulo')} - {proposta.get('status')}", expanded=proposta.get("status") == "Contraproposta"):
                    st.write(f"**Cliente:** {cliente_portal}")
                    st.write(f"**Respondido em:** {proposta.get('respondido_em') or 'Ainda não respondido'}")
                    st.write(f"**Resposta/observação:** {proposta.get('resposta_cliente') or 'Sem observação'}")

        st.write("---")
        st.subheader("Histórico enviado")

    for proposta in propostas:
        titulo_exp = f"#{proposta['id']} - {proposta.get('tipo') or 'Arquivo'} - {proposta.get('titulo') or 'Sem título'}"
        with st.expander(titulo_exp, expanded=st.session_state.get("tipo_login") == "cliente" and proposta.get("status") == "Pendente"):
            st.write(f"**Status:** {proposta.get('status') or 'Pendente'}")
            st.write(f"**Enviado em:** {proposta.get('criado_em') or ''}")
            if proposta.get("descricao"):
                st.write(f"**Observação:** {proposta.get('descricao')}")
            st.download_button(
                "Baixar arquivo",
                data=proposta.get("arquivo") or b"",
                file_name=proposta.get("nome_arquivo") or "arquivo",
                mime=proposta.get("mime_type") or "application/octet-stream",
                width="stretch",
                key=f"down_prop_{proposta['id']}",
            )

            if st.session_state.get("tipo_login") == "cliente":
                if proposta.get("status") == "Pendente":
                    resposta = st.text_area("Observação ou contraproposta:", key=f"resp_prop_{proposta['id']}")
                    b1, b2, b3 = st.columns(3)
                    if b1.button("Aceitar", type="primary", width="stretch", key=f"aceitar_prop_{proposta['id']}"):
                        conn_acc = conectar_banco()
                        cacc = conn_acc.cursor()
                        cacc.execute(
                            "UPDATE propostas_contratos_cliente SET status=?, resposta_cliente=?, respondido_em=? WHERE id=?",
                            ("Aceita", resposta, datetime.now().strftime("%d/%m/%Y %H:%M"), proposta["id"]),
                        )
                        conn_acc.commit()
                        conn_acc.close()
                        st.success("Proposta aceita.")
                        st.rerun()
                    if b2.button("Recusar", width="stretch", key=f"recusar_prop_{proposta['id']}"):
                        conn_rec = conectar_banco()
                        crec = conn_rec.cursor()
                        crec.execute(
                            "UPDATE propostas_contratos_cliente SET status=?, resposta_cliente=?, respondido_em=? WHERE id=?",
                            ("Recusada", resposta, datetime.now().strftime("%d/%m/%Y %H:%M"), proposta["id"]),
                        )
                        conn_rec.commit()
                        conn_rec.close()
                        st.warning("Proposta recusada.")
                        st.rerun()
                    if b3.button("Enviar contraproposta", width="stretch", key=f"contra_prop_{proposta['id']}"):
                        if not resposta.strip():
                            st.error("Escreva a contraproposta antes de enviar.")
                        else:
                            conn_ctr = conectar_banco()
                            cctr = conn_ctr.cursor()
                            cctr.execute(
                                "UPDATE propostas_contratos_cliente SET status=?, resposta_cliente=?, respondido_em=? WHERE id=?",
                                ("Contraproposta", resposta, datetime.now().strftime("%d/%m/%Y %H:%M"), proposta["id"]),
                            )
                            conn_ctr.commit()
                            conn_ctr.close()
                            st.info("Contraproposta enviada.")
                            st.rerun()
                elif proposta.get("resposta_cliente"):
                    st.write(f"**Sua resposta:** {proposta.get('resposta_cliente')}")
            elif proposta.get("resposta_cliente"):
                st.write(f"**Resposta do cliente:** {proposta.get('resposta_cliente')}")

def renderizar_gestao_chamados_chefe(ctx=None):
    if ctx is not None:
        aplicar_contexto_pagina(ctx, globals())
    st.subheader("Banco de chamados")
    funcionarios = listar_funcionarios_sistema()
    labels_func = ["-- Sem funcionário --"] + [f["label"] for f in funcionarios]
    mapa_func = {f["label"]: f["username"] for f in funcionarios}

    with st.expander("Enviar link para cliente abrir chamado", expanded=False):
        texto_abertura = texto_cliente_abrir_chamado()
        st.caption(f"Canal oficial de WhatsApp: {WHATSAPP_OFICIAL}")
        e1, e2 = st.columns(2)
        email_abertura = e1.text_input("E-mail do cliente:", key="link_abrir_ch_email")
        whats_abertura = e2.text_input("Celular/WhatsApp do cliente:", placeholder="(31) 99999-9999", key="link_abrir_ch_whats")
        st.text_area("Mensagem para enviar:", value=texto_abertura, height=120, key="link_abrir_ch_msg", disabled=True)
        b1, b2, b3 = st.columns(3)
        telefone_abertura = telefone_whatsapp(whats_abertura)
        if telefone_abertura:
            b1.link_button(
                "Abrir WhatsApp",
                url_whatsapp(telefone_abertura, texto_abertura),
                width="stretch",
            )
        else:
            b1.warning("Informe o celular.")
        if email_abertura.strip():
            b2.link_button(
                "Abrir Gmail",
                url_gmail(email_abertura, "Abrir chamado no portal", texto_abertura),
                width="stretch",
            )
        else:
            b2.warning("Informe o e-mail.")
        b3.text_input("Link direto:", value=url_abrir_chamado(), key="link_abrir_ch_direto")

    conn = conectar_banco()
    c = conn.cursor()
    c.execute("SELECT * FROM chamados_cliente ORDER BY id DESC")
    chamados = c.fetchall()
    conn.close()

    if not chamados:
        st.info("Nenhum chamado registrado.")
        return

    tabela = []
    for chamado in chamados:
        data_ch, inicio_ch, fim_ch, tipo_ch, _ = periodo_chamado(chamado)
        tabela.append({
            "ID": chamado.get("id"),
            "Cliente": chamado.get("cliente_nome"),
            "Área": chamado.get("area_destino") or "Suporte",
            "Assunto": chamado.get("titulo"),
            "Status": chamado.get("status"),
            "Funcionário": chamado.get("funcionario_designado") or "",
            "Data": texto_data_br(data_ch),
            "Horário": f"{inicio_ch} às {fim_ch}",
            "Tipo": tipo_ch,
            "Criado em": chamado.get("criado_em"),
        })
    pesquisa_chamado = st.text_input(
        "Pesquisar chamado:",
        placeholder="Cliente, assunto, área, funcionário, status ou ID",
        key="gest_ch_pesquisa",
    ).strip().casefold()
    tabela_filtrada = [
        linha for linha in tabela
        if not pesquisa_chamado or pesquisa_chamado in " ".join(str(valor or "") for valor in linha.values()).casefold()
    ]
    id_clicado = tabela_clicavel_id(st, tabela_filtrada, "gest_ch_grade", campo_id="ID") if tabela_filtrada else None
    if id_clicado:
        st.session_state["gest_ch_id_ativo"] = int(id_clicado)
    id_ed = int(st.session_state.get("gest_ch_id_ativo") or 0)
    if not id_ed:
        st.caption("Clique em qualquer informação do chamado para abrir o gerenciamento.")
        return
    chamado = next((item for item in chamados if item.get("id") == id_ed), None)
    if not chamado:
        return

    data_ch, inicio_ch, fim_ch, tipo_ch, descricao_ch = periodo_chamado(chamado)
    with st.expander(f"Gerenciando chamado #{id_ed} - {chamado.get('cliente_nome')}", expanded=True):
        st.write(f"**Pedido original:** {chamado.get('descricao') or ''}")
        st.write(f"**Solicitado para:** {texto_data_br(chamado.get('data_solicitada'))} das {chamado.get('hora_inicio')} às {chamado.get('hora_fim')}")
        contato_cliente = buscar_contato_cliente(chamado.get("cliente_id"), chamado.get("cliente_nome") or "")
        st.markdown("#### Conversa do chamado")
        renderizar_chat_chamado(chamado, chamado.get("cliente_nome") or "")
        with st.form(f"form_resposta_equipe_chamado_{id_ed}", clear_on_submit=True):
            msg_equipe = st.text_area("Responder no chat do chamado:", height=90, key=f"msg_equipe_ch_{id_ed}")
            anexo_equipe = st.file_uploader("Anexo opcional:", key=f"anexo_equipe_ch_{id_ed}")
            enviar_msg_equipe = st.form_submit_button("Enviar resposta para o cliente", type="primary", width="stretch")
        if enviar_msg_equipe:
            if not msg_equipe.strip() and not anexo_equipe:
                st.error("Digite uma resposta ou anexe um arquivo.")
            elif anexo_equipe and not upload_dentro_limite(anexo_equipe):
                erro_upload_grande("anexo")
            else:
                salvar_mensagem_chamado(id_ed, "equipe", st.session_state.get("username") or "Equipe Dsystem", msg_equipe.strip(), anexo_equipe)
                st.success("Resposta enviada no chamado.")
                st.rerun()

        with st.expander("Responder cliente por WhatsApp ou e-mail", expanded=False):
            r1, r2 = st.columns(2)
            email_cliente = r1.text_input(
                "E-mail do cliente:",
                value=(contato_cliente.get("email") or "").strip(),
                key=f"ch_email_cliente_{id_ed}",
            )
            telefone_digitado = r2.text_input(
                "Celular/WhatsApp do cliente:",
                value=contato_cliente.get("telefone") or "",
                placeholder="(31) 99999-9999",
                key=f"ch_whats_cliente_{id_ed}",
            )
            mensagem_retorno = st.text_area(
                "Mensagem para o cliente:",
                value="Temos uma atualização sobre o seu chamado. Acesse o portal pelo link abaixo para acompanhar ou responder.",
                height=100,
                key=f"ch_msg_cliente_{id_ed}",
            )
            texto_envio = texto_retorno_chamado(chamado, mensagem_retorno)
            st.text_area("Prévia da mensagem:", value=texto_envio, height=170, key=f"ch_preview_envio_{id_ed}", disabled=True)
            cwa, cgmail, cem = st.columns(3)
            telefone_cliente = telefone_whatsapp(telefone_digitado)
            if telefone_cliente:
                cwa.link_button(
                    "Abrir WhatsApp",
                    url_whatsapp(telefone_cliente, texto_envio),
                    width="stretch",
                )
            else:
                cwa.warning("Informe o celular para abrir o WhatsApp.")
            if email_cliente.strip():
                cgmail.link_button(
                    "Abrir Gmail",
                    url_gmail(email_cliente, f"Retorno do chamado #{id_ed}", texto_envio),
                    width="stretch",
                )
                cem.link_button(
                    "App de e-mail",
                    url_mailto(email_cliente, f"Retorno do chamado #{id_ed}", texto_envio),
                    width="stretch",
                )
            else:
                cgmail.warning("Informe o e-mail.")
                cem.warning("Informe o e-mail.")

        s1, s2, s3, s4 = st.columns(4)
        status_opcoes = ["Novo", "Em análise", "Modificado - aguardando aprovação", "Aprovado pelo cliente", "Designado", "Em atendimento", "Concluído", "Cancelado", "Recusado pelo cliente"]
        status_atual = chamado.get("status") if chamado.get("status") in status_opcoes else "Novo"
        novo_status = s1.selectbox("Status:", status_opcoes, index=status_opcoes.index(status_atual), key=f"ch_status_{id_ed}")
        label_atual = next((f["label"] for f in funcionarios if f["username"] == chamado.get("funcionario_designado")), "-- Sem funcionário --")
        funcionario_label = s2.selectbox("Funcionário designado:", labels_func, index=labels_func.index(label_atual) if label_atual in labels_func else 0, key=f"ch_func_{id_ed}")
        novo_tipo = s3.selectbox("Tipo ajustado:", ["Remoto", "Presencial", "Presencial ou remoto"], index=["Remoto", "Presencial", "Presencial ou remoto"].index(tipo_ch) if tipo_ch in ["Remoto", "Presencial", "Presencial ou remoto"] else 0, key=f"ch_tipo_{id_ed}")
        area_atual = chamado.get("area_destino") if chamado.get("area_destino") in AREAS_CHAMADO else "Suporte"
        nova_area = s4.selectbox("Área:", AREAS_CHAMADO, index=AREAS_CHAMADO.index(area_atual), key=f"ch_area_{id_ed}")

        d1, d2, d3 = st.columns(3)
        try:
            data_default = datetime.strptime(data_ch, "%Y-%m-%d").date()
        except Exception:
            data_default = date.today()
        nova_data = d1.date_input("Data ajustada:", value=data_default, key=f"ch_data_{id_ed}")
        try:
            inicio_default = datetime.strptime(inicio_ch, "%H:%M").time() if inicio_ch else None
        except Exception:
            inicio_default = None
        try:
            fim_default = datetime.strptime(fim_ch, "%H:%M").time() if fim_ch else None
        except Exception:
            fim_default = None
        nova_hora_inicio = d2.time_input("Hora início ajustada:", value=inicio_default, key=f"ch_ini_{id_ed}", step=1800)
        nova_hora_fim = d3.time_input("Hora fim ajustada:", value=fim_default, key=f"ch_fim_{id_ed}", step=1800)
        novo_titulo = st.text_input("Assunto:", value=chamado.get("titulo") or "", key=f"ch_titulo_{id_ed}")
        nova_descricao = st.text_area("Descrição/ajuste para o cliente:", value=descricao_ch, height=120, key=f"ch_desc_{id_ed}")

        if st.button("Salvar gestão do chamado", type="primary", width="stretch", key=f"ch_salvar_{id_ed}"):
            funcionario = mapa_func.get(funcionario_label, "")
            if not funcionario and nova_area in {"Gerente", "Compras"}:
                funcionario = responsavel_area_chamado(nova_area)
            h_ini = nova_hora_inicio.strftime("%H:%M") if nova_hora_inicio else ""
            h_fim = nova_hora_fim.strftime("%H:%M") if nova_hora_fim else ""
            erros = []
            if not novo_titulo.strip():
                erros.append("Informe o assunto do chamado.")
            if not h_ini or not h_fim:
                erros.append("Informe o horário de início e término.")
            elif h_fim <= h_ini:
                erros.append("A hora de término precisa ser maior que a hora de início.")
            if funcionario:
                conflito = conflito_agenda_funcionario(funcionario, nova_data.strftime("%Y-%m-%d"), h_ini, h_fim, chamado_ignorar=id_ed)
                if conflito:
                    erros.append(conflito)
            if erros:
                for erro in erros:
                    st.error(erro)
                return

            conn_up = conectar_banco()
            cup = conn_up.cursor()
            cup.execute(
                """UPDATE chamados_cliente SET titulo=?, status=?, funcionario_designado=?, area_destino=?,
                   ajuste_tipo_atendimento=?, ajuste_data=?, ajuste_hora_inicio=?, ajuste_hora_fim=?,
                   ajuste_descricao=?, atualizado_em=? WHERE id=?""",
                (
                    novo_titulo,
                    novo_status,
                    funcionario,
                    nova_area,
                    novo_tipo,
                    nova_data.strftime("%Y-%m-%d"),
                    h_ini,
                    h_fim,
                    nova_descricao,
                    datetime.now().strftime("%d/%m/%Y %H:%M"),
                    id_ed,
                ),
            )
            conn_up.commit()
            conn_up.close()
            st.success("Chamado atualizado.")
            st.rerun()

def renderizar_chamados_funcionario(ctx=None):
    if ctx is not None:
        aplicar_contexto_pagina(ctx, globals())
    funcionario = st.session_state.get("username", "")
    if not funcionario:
        return
    conn = conectar_banco()
    c = conn.cursor()
    eh_daniel = funcionario.strip().lower() == "daniel.fabio"
    c.execute(
        """SELECT * FROM chamados_cliente
           WHERE (funcionario_designado=%s
                  OR (%s=0 AND COALESCE(funcionario_designado, '')='' AND COALESCE(area_destino, 'Suporte')='Suporte'))
             AND status NOT IN ('Concluído', 'Cancelado', 'Recusado pelo cliente')
           ORDER BY ajuste_data ASC, data_solicitada ASC, hora_inicio ASC""",
        (funcionario, int(eh_daniel)),
    )
    chamados = c.fetchall()
    conn.close()
    if not chamados:
        st.info("Nenhum chamado atribuído a você.")
        return
    st.subheader("Chamados atribuídos a mim")
    for chamado in chamados:
        data_ch, inicio_ch, fim_ch, tipo_ch, descricao_ch = periodo_chamado(chamado)
        with st.expander(f"#{chamado['id']} - {chamado.get('cliente_nome')} - {texto_data_br(data_ch)} {inicio_ch}", expanded=False):
            st.write(f"**Área:** {chamado.get('area_destino') or 'Suporte'}")
            st.write(f"**Status:** {chamado.get('status')}")
            st.write(f"**Tipo:** {tipo_ch}")
            st.write(f"**Horário:** {texto_data_br(data_ch)} das {inicio_ch} às {fim_ch}")
            st.write(f"**Descrição:** {descricao_ch}")

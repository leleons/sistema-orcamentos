from __future__ import annotations

from dsystem_erp.app_context import aplicar_contexto_pagina
from dsystem_erp.services.cobrancas_recorrentes import (
    criar_ou_atualizar_cobranca_contrato,
    sincronizar_lancamentos_recorrentes,
)
from dsystem_erp.ui_consulta import tabela_selecionavel_id
from dsystem_erp.services.permissions import usuario_eh_gerencial
from dsystem_erp.pages.contratos_download import renderizar_downloads


def renderizar_contratos(ctx: dict) -> None:
    aplicar_contexto_pagina(ctx, globals())
    if not tem_permissao("contratos.view"):
        st.error("Você não tem permissão para acessar contratos.")
        st.stop()

    st.title("Contratos")
    st.caption("Consulta central de contratos de clientes, fornecedores e funcionários.")
    from dsystem_erp.pages.contratos_gerar import renderizar_gerador
    renderizar_gerador(ctx)
    with st.expander('Contratos já anexados no portal / atendimento', expanded=False):
        conn_legado = conectar_banco()
        try:
            cur_legado = conn_legado.cursor()
            cur_legado.execute("SELECT * FROM propostas_contratos_cliente WHERE LOWER(tipo) LIKE '%contrato%' ORDER BY id DESC")
            legados = [dict(r) for r in cur_legado.fetchall()]
        finally:
            conn_legado.close()
        permitidos = buscar_clientes()
        ids_permitidos = {str(c['id']) for c in permitidos}
        nomes_permitidos = {str(c.get('nome') or '').strip().casefold() for c in permitidos}
        for legado in legados:
            autorizado = (str(legado.get('cliente_id')) in ids_permitidos if legado.get('cliente_id') else
                          str(legado.get('cliente_nome') or '').strip().casefold() in nomes_permitidos)
            if not autorizado:
                continue
            st.write(f"#{legado['id']} — {legado.get('cliente_nome')} — {legado.get('titulo') or legado.get('tipo')} — {legado.get('status')}")
            if legado.get('arquivo'):
                renderizar_downloads(st, legado, prefixo='contrato_legado')
        st.caption('Os arquivos são consultados na origem, sem duplicar ou alterar os contratos existentes.')
    if tem_permissao("contratos.edit"):
        with st.expander("Cadastrar contrato existente", expanded=False):
            with st.form("contrato_existente", clear_on_submit=True):
                uc1, uc2, uc3 = st.columns(3)
                novo_tipo = uc1.text_input("Tipo do contrato:")
                nova_classificacao = uc2.selectbox("Vinculado a:", ["Cliente", "Fornecedor", "Funcionário", "Outro"])
                nova_parte = uc3.text_input("Nome da parte:")
                uc4, uc5, uc6 = st.columns(3)
                novo_inicio = uc4.date_input("Data de início:", value=None)
                novo_vencimento = uc5.date_input("Data de vencimento:", value=None)
                novo_valor = uc6.text_input("Valor do contrato:")
                novo_arquivo = st.file_uploader("Arquivo do contrato:", type=["pdf", "doc", "docx", "jpg", "jpeg", "png"])
                nova_obs = st.text_area("Observações:")
                cadastrar = st.form_submit_button("Cadastrar contrato", type="primary", width="stretch")
            if cadastrar:
                if not novo_tipo.strip() or not nova_parte.strip() or not novo_arquivo:
                    st.error("Informe tipo, nome da parte e arquivo.")
                elif not upload_dentro_limite(novo_arquivo):
                    erro_upload_grande("contrato")
                else:
                    dados, nome, mime = dados_upload(novo_arquivo)
                    conn_novo = conectar_banco(); cn = conn_novo.cursor()
                    cn.execute("""INSERT INTO contratos
                               (tipo, parte_tipo, parte_nome, nome_arquivo, mime_type, arquivo, status,
                                valor, data_inicio, data_vencimento, observacoes, criado_por, criado_em)
                               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                               (novo_tipo.strip(), nova_classificacao, nova_parte.strip(), nome, mime, dados, "Ativo",
                                novo_valor, data_para_banco_br(novo_inicio) if novo_inicio else "",
                                data_para_banco_br(novo_vencimento) if novo_vencimento else "", nova_obs,
                                st.session_state.get("username", ""), agora_br()))
                    conn_novo.commit(); conn_novo.close(); st.success("Contrato cadastrado."); st.rerun()
    conn = conectar_banco(); c = conn.cursor()
    c.execute("SELECT * FROM contratos ORDER BY id DESC")
    contratos = [dict(item) for item in c.fetchall()]
    conn.close()
    if not usuario_eh_gerencial(st.session_state):
        contratos = [item for item in contratos if item.get('parte_tipo') != 'Funcionário']

    f1, f2, f3 = st.columns(3)
    busca = f1.text_input("Buscar nome, tipo ou arquivo:", key="contratos_busca").strip().casefold()
    tipos = sorted({item.get("tipo") or "Sem tipo" for item in contratos})
    tipo_filtro = f2.selectbox("Tipo:", ["Todos"] + tipos, key="contratos_tipo")
    status_filtro = f3.selectbox("Status:", ["Todos", "Ativo", "Assinado", "Encerrado", "Cancelado", "Em renovação"], key="contratos_status")
    filtrados = contratos
    if busca:
        filtrados = [x for x in filtrados if busca in f"{x.get('parte_nome','')} {x.get('tipo','')} {x.get('nome_arquivo','')}".casefold()]
    if tipo_filtro != "Todos":
        filtrados = [x for x in filtrados if (x.get("tipo") or "Sem tipo") == tipo_filtro]
    if status_filtro != "Todos":
        filtrados = [x for x in filtrados if (x.get("status") or "Ativo") == status_filtro]

    linhas = [{
        "ID": x.get("id"), "Tipo": x.get("tipo"), "Vinculado a": x.get("parte_nome"),
        "Classificação": x.get("parte_tipo"), "Início": data_para_br(x.get("data_inicio")),
        "Vencimento": data_para_br(x.get("data_vencimento")), "Valor": x.get("valor") or "",
        "Status": x.get("status") or "Ativo", "Assinado": x.get("assinado") or "Não",
        "Cobrança recorrente": x.get("cobranca_recorrente_id") or "", "Arquivo": x.get("nome_arquivo"),
    } for x in filtrados]
    selecionado_id = tabela_selecionavel_id(st, linhas, "contratos_grade", "ID") if linhas else None
    if not linhas:
        st.info("Nenhum contrato encontrado. Os próximos contratos gerados serão arquivados aqui automaticamente.")
        return
    st.caption("Clique na linha do contrato para abrir a consulta e edição abaixo.")
    if selecionado_id:
        st.session_state["contrato_aberto_id"] = int(selecionado_id)
    contrato_id = st.session_state.get("contrato_aberto_id")
    contrato = next((x for x in contratos if int(x.get("id") or 0) == int(contrato_id or 0)), None)
    if not contrato:
        return

    st.divider()
    st.subheader(f"Contrato #{contrato['id']} — {contrato.get('parte_nome') or ''}")
    ce1, ce2, ce3 = st.columns(3)
    tipo_edit = ce1.text_input("Tipo do contrato:", value=contrato.get("tipo") or "", disabled=not tem_permissao("contratos.edit"), key=f"contrato_tipo_{contrato['id']}")
    parte_edit = ce2.text_input("Cliente/fornecedor/funcionário:", value=contrato.get("parte_nome") or "", disabled=not tem_permissao("contratos.edit"), key=f"contrato_parte_{contrato['id']}")
    status_contrato_opcoes = ["Ativo", "Assinado", "Em renovação", "Encerrado", "Cancelado"]
    status_edit = ce3.selectbox("Status:", status_contrato_opcoes, index=status_contrato_opcoes.index(contrato.get("status") if contrato.get("status") in status_contrato_opcoes else "Ativo"), disabled=not tem_permissao("contratos.edit"), key=f"contrato_status_{contrato['id']}")
    observacoes = st.text_area("Observações:", value=contrato.get("observacoes") or "", disabled=not tem_permissao("contratos.edit"), key=f"contrato_obs_{contrato['id']}")
    st.markdown("#### Assinatura e cobrança recorrente")
    cr1, cr2, cr3 = st.columns(3)
    assinado = cr1.checkbox(
        "Contrato assinado", value=str(contrato.get("assinado") or "Não").casefold() == "sim",
        disabled=not tem_permissao("contratos.edit"), key=f"contrato_assinado_{contrato['id']}",
    )
    data_assinatura = cr2.date_input(
        "Data da assinatura:", value=parse_data_flex(contrato.get("data_assinatura")) or date.today(),
        disabled=not assinado or not tem_permissao("contratos.edit"), key=f"contrato_data_assinatura_{contrato['id']}",
    )
    gerar_recorrencia = cr3.checkbox(
        "Gerar cobranças conforme o contrato",
        value=str(contrato.get("gerar_recorrencia") or "Não").casefold() == "sim",
        disabled=not tem_permissao("contratos.edit"), key=f"contrato_gerar_rec_{contrato['id']}",
    )
    rr1, rr2, rr3 = st.columns(3)
    recorrencia_tipo = rr1.text_input(
        "Descrição da cobrança:", value=contrato.get("recorrencia_tipo") or contrato.get("tipo") or "Contrato",
        disabled=not gerar_recorrencia or not tem_permissao("contratos.edit"), key=f"contrato_rec_tipo_{contrato['id']}",
    )
    opcoes_periodicidade = ["Diária", "Semanal", "Mensal", "Anual"]
    periodicidade_atual = contrato.get("recorrencia_periodicidade") or "Mensal"
    recorrencia_periodicidade = rr2.selectbox(
        "Periodicidade:", opcoes_periodicidade,
        index=opcoes_periodicidade.index(periodicidade_atual) if periodicidade_atual in opcoes_periodicidade else 2,
        disabled=not gerar_recorrencia or not tem_permissao("contratos.edit"), key=f"contrato_rec_periodo_{contrato['id']}",
    )
    recorrencia_valor = rr3.number_input(
        "Valor recorrente R$:", min_value=0.0, value=float(contrato.get("recorrencia_valor") or 0),
        step=0.01, format="%.2f", disabled=not gerar_recorrencia or not tem_permissao("contratos.edit"),
        key=f"contrato_rec_valor_{contrato['id']}",
    )
    rr4, rr5, rr6 = st.columns(3)
    recorrencia_primeiro = rr4.date_input(
        "Primeiro vencimento:",
        value=parse_data_flex(contrato.get("recorrencia_primeiro_vencimento")) or date.today(),
        disabled=not gerar_recorrencia or not tem_permissao("contratos.edit"), key=f"contrato_rec_primeiro_{contrato['id']}",
    )
    recorrencia_fim = rr5.date_input(
        "Fim da recorrência:",
        value=parse_data_flex(contrato.get("recorrencia_fim") or contrato.get("data_vencimento")) or date.today(),
        disabled=not gerar_recorrencia or not tem_permissao("contratos.edit"), key=f"contrato_rec_fim_{contrato['id']}",
    )
    opcoes_pagamento_recorrencia = ["Faturamento via D-System", "Boleto", "PIX", "Cartão", "Transferência"]
    pagamento_recorrencia_atual = contrato.get("recorrencia_pagamento") or "Faturamento via D-System"
    recorrencia_pagamento = rr6.selectbox(
        "Forma de cobrança:", opcoes_pagamento_recorrencia,
        index=(opcoes_pagamento_recorrencia.index(pagamento_recorrencia_atual)
               if pagamento_recorrencia_atual in opcoes_pagamento_recorrencia else 0),
        disabled=not gerar_recorrencia or not tem_permissao("contratos.edit"),
        key=f"contrato_rec_pagamento_{contrato['id']}",
    )
    if gerar_recorrencia and not assinado:
        st.warning("A recorrência ficará configurada, mas só será gerada depois que o contrato for marcado como assinado.")
    if contrato.get("cobranca_recorrente_id"):
        st.info(f"Cobrança recorrente vinculada: #{contrato.get('cobranca_recorrente_id')}")
    renderizar_downloads(st, contrato)
    if tem_permissao("contratos.edit"):
        if st.button("Salvar alterações do contrato", type="primary", width="stretch", key=f"contrato_salvar_{contrato['id']}"):
            conn = conectar_banco(); c = conn.cursor()
            usuario = st.session_state.get("username", "")
            agora = agora_br()
            try:
                c.execute(
                    """UPDATE contratos SET tipo=?, parte_nome=?, status=?, observacoes=?,
                       assinado=?, data_assinatura=?, gerar_recorrencia=?, recorrencia_tipo=?,
                       recorrencia_periodicidade=?, recorrencia_primeiro_vencimento=?, recorrencia_fim=?,
                       recorrencia_valor=?, recorrencia_pagamento=?, alterado_por=?, alterado_em=? WHERE id=?""",
                    (tipo_edit, parte_edit, "Assinado" if assinado else status_edit, observacoes,
                     "Sim" if assinado else "Não", data_para_banco_br(data_assinatura) if assinado else "",
                     "Sim" if gerar_recorrencia else "Não", recorrencia_tipo,
                     recorrencia_periodicidade, data_para_banco_br(recorrencia_primeiro),
                     data_para_banco_br(recorrencia_fim), recorrencia_valor, recorrencia_pagamento,
                     usuario, agora, contrato["id"]),
                )
                contrato_atualizado = dict(contrato)
                contrato_atualizado.update({
                    "tipo": tipo_edit, "parte_nome": parte_edit,
                    "assinado": "Sim" if assinado else "Não",
                    "gerar_recorrencia": "Sim" if gerar_recorrencia else "Não",
                    "recorrencia_tipo": recorrencia_tipo,
                    "recorrencia_periodicidade": recorrencia_periodicidade,
                    "recorrencia_primeiro_vencimento": data_para_banco_br(recorrencia_primeiro),
                    "recorrencia_fim": data_para_banco_br(recorrencia_fim),
                    "recorrencia_valor": recorrencia_valor,
                    "recorrencia_pagamento": recorrencia_pagamento,
                })
                titulos_gerados = 0
                if assinado and gerar_recorrencia:
                    cobranca_id, _ = criar_ou_atualizar_cobranca_contrato(conn, contrato_atualizado, usuario, agora)
                    titulos_gerados = sincronizar_lancamentos_recorrentes(
                        conn, date.today(), usuario, horizonte_dias=35
                    )
                elif contrato.get("cobranca_recorrente_id"):
                    c.execute(
                        "UPDATE cobrancas_recorrentes SET status='Encerrada' WHERE id=?",
                        (contrato.get("cobranca_recorrente_id"),),
                    )
                    conn.commit()
                else:
                    conn.commit()
            except Exception as erro_contrato:
                conn.rollback()
                st.error(f"Não foi possível atualizar o contrato: {erro_contrato}")
            else:
                mensagem = "Contrato atualizado."
                if assinado and gerar_recorrencia:
                    mensagem += f" Cobrança #{cobranca_id} vinculada; {titulos_gerados} lançamento(s) gerado(s)."
                st.success(mensagem)
                st.rerun()
            finally:
                conn.close()
    if tem_permissao("contratos.delete"):
        with st.expander("Excluir contrato"):
            confirmar = st.checkbox("Confirmo a exclusão do contrato e do arquivo armazenado.", key=f"contrato_confirmar_exclusao_{contrato['id']}")
            if st.button("Excluir contrato", disabled=not confirmar, key=f"contrato_excluir_{contrato['id']}"):
                deletar_registro("contratos", "id", contrato["id"]); st.session_state.pop("contrato_aberto_id", None); st.rerun()

"""Central de documentos do faturamento para download e envio ao cliente."""

from __future__ import annotations

import hashlib

from dsystem_erp.app_context import aplicar_contexto_pagina
from dsystem_erp.services.faturamento_espelho import gerar_pdf_espelho_faturamento
from dsystem_erp.services.fiscal_automatico import listar_emissoes, processar_emissoes, tipos_fiscais, recuperar_pdfs, permite_correcao, liberar_correcao
from dsystem_erp.services.fiscal_documentos import consultar_documentos_fiscais
from dsystem_erp.services.pacote_faturamento import (
    DocumentoFaturamento,
    juntar_documentos_pdf,
    nome_pacote_faturamento,
    pdf_de_referencia,
)


def _bytes(valor) -> bytes:
    if isinstance(valor, memoryview):
        return valor.tobytes()
    return bytes(valor or b"")


def _contato_cliente(faturamento: dict) -> dict:
    conn = conectar_banco()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """SELECT email, emails_cobranca, telefone
               FROM clientes
               WHERE documento_chave=? OR cnpj=? OR nome=?
               ORDER BY CASE WHEN nome=? THEN 0 ELSE 1 END, id DESC LIMIT 1""",
            (
                faturamento.get("cnpj") or "",
                faturamento.get("cnpj") or "",
                faturamento.get("cliente") or "",
                faturamento.get("cliente") or "",
            ),
        )
        return dict(cursor.fetchone() or {})
    finally:
        conn.close()


def _grupo_orcamento(faturamento, faturamentos):
    """Agrupa dentro dos registros já autorizados para o usuário da tela."""
    referencia = str(faturamento.get('orc_ref') or '').strip()
    documento = ''.join(filter(str.isdigit, str(faturamento.get('cnpj') or '')))
    if not referencia or not documento:
        return [faturamento]
    grupo = [dict(r) for r in faturamentos if r.get('status') == 'Faturado'
             and str(r.get('orc_ref') or '').strip() == referencia
             and ''.join(filter(str.isdigit, str(r.get('cnpj') or ''))) == documento]
    return sorted(grupo, key=lambda r: int(r['id'])) or [faturamento]


def _documentos_disponiveis(faturamento: dict) -> list[DocumentoFaturamento]:
    faturamento_id = int(faturamento["id"])
    documentos: list[DocumentoFaturamento] = [DocumentoFaturamento(
        codigo=f"espelho:{faturamento_id}", titulo=f"Espelho #{faturamento_id}", categoria="Espelho",
        arquivo=gerar_pdf_espelho_faturamento(faturamento), nome_arquivo=f"espelho_{faturamento_id}.pdf")]
    documentos.extend(consultar_documentos_fiscais(conectar_banco, faturamento_id)['documentos'])
    conn = conectar_banco()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """SELECT id, tipo, nome_arquivo, mime_type, arquivo
               FROM faturamento_anexos WHERE faturamento_id=? ORDER BY id DESC""",
            (faturamento_id,),
        )
        for anexo in cursor.fetchall():
            nome = anexo.get("nome_arquivo") or f"anexo_{anexo.get('id')}.pdf"
            tipo = str(anexo.get("tipo") or "Anexo")
            identificacao = f"{tipo} {nome}".casefold()
            if not (_bytes(anexo.get("arquivo")).startswith(b"%PDF")):
                continue
            if "boleto" in identificacao:
                categoria = "Boleto"
            elif any(marcador in identificacao for marcador in ("nota", "nf-e", "nfse", "nfs-e")):
                categoria = "Nota fiscal"
            elif "orç" in identificacao or "orc" in identificacao:
                categoria = "Orçamento"
            else:
                categoria = "Anexo"
            documentos.append(DocumentoFaturamento(
                codigo=f"anexo:{anexo.get('id')}", titulo=nome, categoria=categoria,
                arquivo=_bytes(anexo.get("arquivo")), nome_arquivo=nome,
            ))

        cursor.execute(
            """SELECT p.id, p.empresa, p.nome_arquivo, p.mime_type, p.arquivo,
                      o.orc_id, o.numero
               FROM orcamento_pdfs p
               INNER JOIN orcamentos o ON o.orc_id=p.orc_id
               WHERE o.faturamento_id=? OR (?<>'' AND o.numero=?)
               ORDER BY o.orc_id DESC, p.empresa""",
            (faturamento_id, str(faturamento.get("orc_ref") or ""), str(faturamento.get("orc_ref") or "")),
        )
        for orcamento in cursor.fetchall():
            arquivo = _bytes(orcamento.get("arquivo"))
            if not arquivo.startswith(b"%PDF"):
                continue
            numero = orcamento.get("numero") or orcamento.get("orc_id")
            empresa = orcamento.get("empresa") or "Dsystem"
            documentos.append(DocumentoFaturamento(
                codigo=f"orcamento:{orcamento.get('id')}",
                titulo=f"Orçamento #{numero} - {empresa}", categoria="Orçamento",
                arquivo=arquivo,
                nome_arquivo=orcamento.get("nome_arquivo") or f"orcamento_{numero}_{empresa}.pdf",
            ))
    finally:
        conn.close()

    codigos = {documento.codigo for documento in documentos}
    for campo, categoria, titulo in (
        ("nota_fiscal", "Nota fiscal", "Referência da nota fiscal"),
        ("boleto", "Boleto", "Boleto / segunda via"),
    ):
        referencia = str(faturamento.get(campo) or "").strip()
        if referencia and not any(documento.categoria == categoria for documento in documentos):
            codigo = f"referencia:{faturamento_id}:{campo}"
            if codigo not in codigos:
                documentos.append(DocumentoFaturamento(
                    codigo=codigo, titulo=titulo, categoria=categoria,
                    arquivo=pdf_de_referencia(titulo, "Referência registrada no faturamento:", referencia),
                    nome_arquivo=f"{campo}_referencia.pdf",
                ))
    return documentos


def _pendencias_notas(grupo):
    pendencias = []
    for fat in grupo:
        if tipos_fiscais(fat):
            estado = consultar_documentos_fiscais(conectar_banco, fat['id'])
            pendencias.extend(f"#{fat['id']} — {p}" for p in estado['pendencias'])
    return pendencias


def _salvar_pdf_anexo(faturamento_id: int, tipo: str, upload) -> None:
    if not upload:
        return
    if not upload_dentro_limite(upload):
        raise ValueError(f"O arquivo {upload.name} ultrapassa o limite permitido.")
    arquivo, nome, mime_type = dados_upload(upload)
    if not bytes(arquivo).startswith(b"%PDF"):
        raise ValueError(f"O arquivo {nome} não é um PDF válido.")
    conn = conectar_banco()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """INSERT INTO faturamento_anexos
               (faturamento_id, tipo, nome_arquivo, mime_type, arquivo, criado_por, criado_em)
               VALUES (?,?,?,?,?,?,?)""",
            (faturamento_id, tipo, nome, mime_type or "application/pdf", arquivo,
             st.session_state.get("username", ""), agora_br()),
        )
        conn.commit()
    finally:
        conn.close()


def renderizar_central_documentos_faturados(ctx: dict, faturamentos: list[dict]) -> None:
    aplicar_contexto_pagina(ctx, globals())
    st.subheader("Enviar documentos ao cliente")
    st.caption("Escolha o espelho, a nota fiscal ou ambos, junto dos demais documentos do faturamento.")

    faturados = [f for f in faturamentos if (f.get("status") or "Aberto") == "Faturado"]
    if not faturados:
        st.info("Nenhum faturamento com status Faturado está disponível.")
        return

    opcoes = [int(f["id"]) for f in faturados]
    selecionado_id = st.selectbox(
        "Faturamento:", opcoes,
        format_func=lambda item_id: next(
            f"#{item_id} - {f.get('cliente') or ''} - {formatar_moeda_br(f.get('valor_total'))}"
            for f in faturados if int(f["id"]) == int(item_id)
        ),
        key="faturado_documentos_id",
    )
    faturamento = next(f for f in faturados if int(f["id"]) == int(selecionado_id))
    from dsystem_erp.pages.banco_inter_operacoes import boletos_no_faturamento
    boletos_no_faturamento(conectar_banco, faturamento, dict(st.session_state))
    grupo = _grupo_orcamento(faturamento, faturados)
    if len(grupo) > 1:
        st.info('Documentos reunidos do orçamento ' + str(faturamento.get('orc_ref')) + ': faturamentos ' + ', '.join(f"#{f['id']}" for f in grupo))
    for fat_grupo in grupo:
        estados_auto = listar_emissoes(conectar_banco, fat_grupo['id'])
        if estados_auto:
            st.dataframe([{'Faturamento': fat_grupo['id'], 'Nota': r['tipo'], 'Situação': r['estado'], 'Mensagem': r.get('mensagem')} for r in estados_auto], hide_index=True)
            for envio in estados_auto:
                with st.expander(f"Detalhes / corrigir nota — {envio['tipo']} #{fat_grupo['id']}"):
                    st.write(envio.get('mensagem') or 'Sem mensagem de erro.')
                    if permite_correcao(envio):
                        st.caption('A correção não cria outro faturamento nem repete a baixa. Depois de corrigir em Emissão de Nota, salve a preparação e use Continuar notas preparadas nesta tela.')
                        confirmar_correcao = st.checkbox('Quero corrigir os dados desta nota, sem enviá-la agora.', key=f"auto_corrigir_conf_{envio['id']}")
                        if st.button('Corrigir esta nota', key=f"auto_corrigir_{envio['id']}", disabled=not confirmar_correcao or not (tem_permissao('faturamento.edit') or tem_permissao('faturamento.faturado.edit'))):
                            try:
                                liberar_correcao(conectar_banco, fat_grupo['id'], envio['tipo'], tem_permissao('faturamento.edit') or tem_permissao('faturamento.faturado.edit'))
                            except Exception as erro:
                                st.error(str(erro))
                            else:
                                st.session_state['auto_correcao_destino'] = fat_grupo['id']
                                st.session_state['auto_correcao_aviso'] = f"Nota de {envio['tipo']} do faturamento #{fat_grupo['id']} liberada para correção. Abra a aba Emissão de Nota, corrija os dados e salve a preparação automática. Depois volte em Enviar documentos e clique em Continuar notas preparadas."
                                st.rerun()
                    elif envio.get('estado') in ('Conferir', 'Transmitindo'):
                        st.warning('O resultado deste envio é incerto. A correção permanece bloqueada até consultar o resultado no governo, para evitar nota duplicada.')
                if envio.get('xml_envio'):
                    st.download_button(f"Baixar XML enviado — {envio['tipo']} #{fat_grupo['id']}",
                        data=envio['xml_envio'], file_name=f"xml_enviado_{fat_grupo['id']}_{envio['tipo']}.xml",
                        mime='application/xml', key=f"auto_xml_{envio['id']}")
        if fat_grupo.get('emitir_automaticamente') and (tem_permissao('faturamento.edit') or tem_permissao('faturamento.faturado.edit')):
            if st.button('Continuar notas preparadas (não reenvia notas autorizadas/em conferência)', key=f"continuar_auto_{fat_grupo['id']}"):
                try:
                    processar_emissoes(conectar_banco, fat_grupo['id'], config_sistema_val, salvar_retorno_nota_fiscal)
                    st.rerun()
                except Exception as erro:
                    st.error(str(erro))
        if tem_permissao('faturamento.edit') or tem_permissao('faturamento.faturado.edit'):
            if st.button(f"Gerar PDFs autorizados pendentes — #{fat_grupo['id']} (sem reemitir)", key=f"auto_pdf_{fat_grupo['id']}"):
                try:
                    recuperar_pdfs(conectar_banco, fat_grupo['id'])
                    st.rerun()
                except Exception as erro:
                    st.error(str(erro))

    if tem_permissao("faturamento.faturado.edit") or tem_permissao("faturamento.edit"):
        with st.expander("Adicionar nota fiscal ou boleto em PDF", expanded=False):
            up1, up2 = st.columns(2)
            nota_upload = up1.file_uploader("Nota fiscal (PDF):", type=["pdf"], key=f"doc_nota_{selecionado_id}")
            boleto_upload = up2.file_uploader("Boleto (PDF):", type=["pdf"], key=f"doc_boleto_{selecionado_id}")
            if st.button("Salvar documentos neste faturamento", width="stretch", key=f"salvar_docs_{selecionado_id}"):
                if not nota_upload and not boleto_upload:
                    st.warning("Selecione ao menos uma nota ou um boleto em PDF.")
                else:
                    try:
                        _salvar_pdf_anexo(selecionado_id, "Nota fiscal", nota_upload)
                        _salvar_pdf_anexo(selecionado_id, "Boleto", boleto_upload)
                        st.success("Documentos salvos no faturamento.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Não foi possível salvar: {exc}")

    try:
        documentos = list({doc.codigo: doc for fat in grupo for doc in _documentos_disponiveis(fat)}.values())
    except Exception as exc:
        st.error(f"Não foi possível carregar os documentos: {exc}")
        return
    if not documentos:
        st.warning("Este faturamento ainda não possui nota, boleto ou orçamento em PDF.")
        return

    por_codigo = {documento.codigo: documento for documento in documentos}
    codigos = list(por_codigo)
    opcoes_entrega = ["Somente espelho"] if faturamento.get("emite_nf") == "Não" else ["Nota e espelho", "Somente nota", "Somente espelho"]
    preferencia = faturamento.get("documentos_entrega") or "Nota e espelho"
    modo_entrega = st.radio("Conteúdo do envio:", opcoes_entrega,
        index=opcoes_entrega.index(preferencia) if preferencia in opcoes_entrega else 0,
        key=f"docs_modo_{selecionado_id}")
    pendencias_documentos = _pendencias_notas(grupo) if modo_entrega != 'Somente espelho' else []
    envio_parcial_confirmado = False
    if pendencias_documentos:
        st.warning('Pacote fiscal incompleto: ' + '; '.join(pendencias_documentos))
        envio_parcial_confirmado = st.checkbox('Quero enviar somente os documentos disponíveis, ciente das notas pendentes.', key=f'docs_parcial_{selecionado_id}')
    elif modo_entrega != 'Somente espelho' and any(tipos_fiscais(f) for f in grupo):
        st.success('Pacote fiscal pronto: todas as notas previstas estão autorizadas e têm PDF. Confira o ambiente das notas antes de enviar ao cliente.')
    codigos = [k for k in codigos if not (
        (modo_entrega == "Somente espelho" and por_codigo[k].categoria == "Nota fiscal") or
        (modo_entrega == "Somente nota" and por_codigo[k].categoria == "Espelho"))]
    if modo_entrega != "Somente espelho" and not any(por_codigo[k].categoria == "Nota fiscal" for k in codigos):
        st.warning("Não há nota fiscal disponível neste lançamento. O espelho não substitui a nota.")
    # Quando uma nova nota fica pronta, inclua-a no conjunto, mesmo se a tela
    # já estava aberta anteriormente mostrando somente o espelho.
    versao_documentos = hashlib.sha256('|'.join(sorted(codigos)).encode()).hexdigest()[:12]
    selecionados = st.multiselect(
        "Documentos que serao enviados:", codigos, default=codigos,
        format_func=lambda codigo: f"{por_codigo[codigo].categoria} - {por_codigo[codigo].titulo}",
        key=f"docs_selecionados_{selecionado_id}_{modo_entrega}_{versao_documentos}",
    )
    try:
        pacote = juntar_documentos_pdf(
            [por_codigo[codigo] for codigo in selecionados],
            selecionado_id,
            faturamento.get("cliente") or "",
        )
    except ValueError as exc:
        st.warning(str(exc))
        return

    nome_pacote = nome_pacote_faturamento(selecionado_id)
    st.download_button(
        "Baixar conjunto em um único PDF", data=pacote, file_name=nome_pacote,
        mime="application/pdf", type="primary", width="stretch",
        key=f"baixar_pacote_{selecionado_id}",
        disabled=bool(pendencias_documentos) and not envio_parcial_confirmado,
    )

    contato = _contato_cliente(faturamento)
    emails_cobranca = str(contato.get("emails_cobranca") or "").replace(";", ",").split(",")[0].strip()
    email_padrao = emails_cobranca or contato.get("email")
    telefone_padrao = contato.get("telefone") or ""
    assunto_padrao = f"Documentos do faturamento #{selecionado_id} - Dsystem"
    mensagem_padrao = (
        f"Olá, {faturamento.get('cliente') or 'cliente'}.\n\n"
        f"Seguem os documentos selecionados do faturamento #{selecionado_id}: "
        + ", ".join(por_codigo[codigo].categoria for codigo in selecionados)
        + ".\n\nAtenciosamente,\nDsystem Tecnologia"
    )

    st.markdown("#### Enviar por e-mail")
    email = st.text_input("E-mail do cliente:", value=email_padrao, key=f"docs_email_{selecionado_id}")
    assunto = st.text_input("Assunto:", value=assunto_padrao, key=f"docs_assunto_{selecionado_id}")
    mensagem = st.text_area("Mensagem:", value=mensagem_padrao, height=150, key=f"docs_mensagem_{selecionado_id}")
    if st.button("Enviar PDF por e-mail", type="primary", width="stretch", key=f"enviar_email_docs_{selecionado_id}", disabled=bool(pendencias_documentos) and not envio_parcial_confirmado):
        if not email.strip():
            st.error("Informe o e-mail do cliente.")
        else:
            try:
                enviar_email_com_anexo(email.strip(), assunto, mensagem, nome_pacote, pacote, "application/pdf")
                st.success("Conjunto enviado por e-mail.")
            except Exception as exc:
                st.error(f"Falha no envio por e-mail: {exc}")

    st.markdown("#### Enviar pelo WhatsApp")
    telefone = st.text_input("WhatsApp do cliente:", value=telefone_padrao, key=f"docs_whatsapp_{selecionado_id}")
    mensagem_whatsapp = mensagem.replace("\n", " ") + " Baixe o PDF nesta tela e anexe-o na conversa."
    if telefone.strip():
        st.link_button(
            "Abrir conversa no WhatsApp", url_whatsapp(telefone, mensagem_whatsapp),
            width="stretch", type="primary", disabled=bool(pendencias_documentos) and not envio_parcial_confirmado,
        )
        st.caption("Por segurança, o WhatsApp abre a conversa com a mensagem pronta; anexe nela o PDF baixado acima.")
    else:
        st.info("Informe o telefone para abrir a conversa no WhatsApp.")

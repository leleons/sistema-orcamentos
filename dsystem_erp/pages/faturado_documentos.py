"""Central de documentos do faturamento para download e envio ao cliente."""

from __future__ import annotations

from dsystem_erp.app_context import aplicar_contexto_pagina
from dsystem_erp.services.pacote_faturamento import (
    DocumentoFaturamento,
    decodificar_pdf_base64,
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


def _documentos_disponiveis(faturamento: dict) -> list[DocumentoFaturamento]:
    faturamento_id = int(faturamento["id"])
    documentos: list[DocumentoFaturamento] = []
    conn = conectar_banco()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """SELECT id, tipo_nota, numero_nota, status, pdf_base64, link_nota
               FROM notas_fiscais WHERE faturamento_id=? ORDER BY id DESC""",
            (faturamento_id,),
        )
        for nota in cursor.fetchall():
            numero = nota.get("numero_nota") or nota.get("id")
            titulo = f"Nota {nota.get('tipo_nota') or 'fiscal'} #{numero} ({nota.get('status') or 'Pendente'})"
            pdf_oficial_servico = (
                nota.get("tipo_nota") != "Serviço"
                or str(nota.get("link_nota") or "").startswith(
                    ("https://www.nfse.gov.br/ConsultaPublica/", "https://www.producaorestrita.nfse.gov.br/ConsultaPublica/")
                )
            )
            if nota.get("pdf_base64") and pdf_oficial_servico:
                arquivo = decodificar_pdf_base64(nota.get("pdf_base64"))
            elif nota.get("link_nota"):
                arquivo = pdf_de_referencia(titulo, "A nota fiscal está disponível no link abaixo:", nota.get("link_nota"))
            else:
                continue
            documentos.append(DocumentoFaturamento(
                codigo=f"nota:{nota.get('id')}", titulo=titulo, categoria="Nota fiscal",
                arquivo=arquivo, nome_arquivo=f"nota_fiscal_{numero}.pdf",
            ))

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
            codigo = f"referencia:{campo}"
            if codigo not in codigos:
                documentos.append(DocumentoFaturamento(
                    codigo=codigo, titulo=titulo, categoria=categoria,
                    arquivo=pdf_de_referencia(titulo, "Referência registrada no faturamento:", referencia),
                    nome_arquivo=f"{campo}_referencia.pdf",
                ))
    return documentos


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
    st.caption("Escolha a nota fiscal, o boleto e um ou mais orçamentos para formar um único PDF.")

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
        documentos = _documentos_disponiveis(faturamento)
    except Exception as exc:
        st.error(f"Não foi possível carregar os documentos: {exc}")
        return
    if not documentos:
        st.warning("Este faturamento ainda não possui nota, boleto ou orçamento em PDF.")
        return

    por_codigo = {documento.codigo: documento for documento in documentos}
    codigos = list(por_codigo)
    selecionados = st.multiselect(
        "Documentos que serao enviados:", codigos, default=codigos,
        format_func=lambda codigo: f"{por_codigo[codigo].categoria} - {por_codigo[codigo].titulo}",
        key=f"docs_selecionados_{selecionado_id}",
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
    if st.button("Enviar PDF por e-mail", type="primary", width="stretch", key=f"enviar_email_docs_{selecionado_id}"):
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
            width="stretch", type="primary",
        )
        st.caption("Por segurança, o WhatsApp abre a conversa com a mensagem pronta; anexe nela o PDF baixado acima.")
    else:
        st.info("Informe o telefone para abrir a conversa no WhatsApp.")

from __future__ import annotations

from dsystem_erp.app_context import aplicar_contexto_pagina
from dsystem_erp.ui_consulta import tabela_clicavel_id


def renderizar_acesso_softwares(ctx: dict, secao: str = "pasta") -> None:
    aplicar_contexto_pagina(ctx, globals())
    if secao == "pesquisa":
        st.title("Base de Pesquisa")
        _renderizar_base_pesquisa(exibir_titulo=False)
        return

    st.title("Acesso Softwares")
    renderizar_pasta_dsystem()


def _renderizar_base_pesquisa(exibir_titulo: bool = True) -> None:
    """Cadastro interno de problemas e soluções reutilizáveis."""
    if st.session_state.get("tipo_login") == "cliente":
        st.error("A Base de Pesquisa é de uso exclusivo da equipe interna.")
        return

    if exibir_titulo:
        st.subheader("Base de Pesquisa")
    st.caption("Registre soluções, procedimentos e informações difíceis de localizar para consultar novamente no futuro.")
    conn = conectar_banco()
    c = conn.cursor(dictionary=True)
    c.execute("SELECT * FROM base_pesquisa ORDER BY id DESC")
    registros = c.fetchall()
    conn.close()

    busca = st.text_input(
        "Pesquisar na base:",
        placeholder="Título, problema, solução, categoria ou palavra-chave",
        key="base_pesquisa_busca",
    ).strip().casefold()
    filtrados = [
        item for item in registros
        if not busca or busca in " ".join(str(item.get(campo) or "") for campo in (
            "titulo", "categoria", "palavras_chave", "problema", "solucao"
        )).casefold()
    ]

    if filtrados:
        tabela_base = [{
            "ID": item.get("id"), "Título": item.get("titulo"),
            "Categoria": item.get("categoria"), "Palavras-chave": item.get("palavras_chave"),
            "Atualizado em": item.get("alterado_em") or item.get("criado_em"),
        } for item in filtrados]
        id_clicado = tabela_clicavel_id(st, tabela_base, f"base_pesquisa_grade_{st.session_state.get('base_pesquisa_versao', 0)}", campo_id="ID")
        if id_clicado:
            st.session_state["base_pesquisa_id_ativo"] = int(id_clicado)
    else:
        st.info("Nenhum conteúdo encontrado.")

    novo_col, _ = st.columns([1, 3])
    if novo_col.button("Novo conteúdo", width="stretch", key="base_pesquisa_novo"):
        st.session_state.pop("base_pesquisa_id_ativo", None)
        st.session_state["base_pesquisa_versao"] = st.session_state.get("base_pesquisa_versao", 0) + 1
        st.rerun()
    selecionado = int(st.session_state.get("base_pesquisa_id_ativo") or 0)
    st.caption("Clique em qualquer informação da tabela para abrir o conteúdo completo e editar.")
    atual = next((item for item in registros if int(item.get("id") or 0) == int(selecionado or 0)), {})
    if selecionado:
        conn_anexos = conectar_banco()
        try:
            ca = conn_anexos.cursor(dictionary=True)
            ca.execute("SELECT * FROM base_pesquisa_anexos WHERE pesquisa_id=? ORDER BY id", (selecionado,))
            for anexo in ca.fetchall():
                st.download_button(anexo['nome'], data=bytes(anexo['arquivo']), file_name=anexo['nome'],
                                   mime=anexo['mime'] or 'application/octet-stream', key=f"pesquisa_anexo_{anexo['id']}")
        finally:
            conn_anexos.close()
    with st.form(f"base_pesquisa_form_{selecionado}_{st.session_state.get('base_pesquisa_versao', 0)}", clear_on_submit=False):
        b1, b2 = st.columns(2)
        titulo = b1.text_input("Título:", value=atual.get("titulo") or "")
        categoria = b2.text_input("Categoria:", value=atual.get("categoria") or "")
        palavras = st.text_input("Palavras-chave:", value=atual.get("palavras_chave") or "")
        problema = st.text_area("Problema ou informação encontrada:", value=atual.get("problema") or "", height=140)
        solucao = st.text_area("Solução, procedimento ou resposta:", value=atual.get("solucao") or "", height=190)
        anexos = st.file_uploader("Adicionar arquivos ou fotos (até 20 MB por arquivo):", accept_multiple_files=True)
        salvar = st.form_submit_button(
            "Salvar alterações" if selecionado else "Adicionar à Base de Pesquisa",
            type="primary", width="stretch",
        )
    if salvar:
        if any(arquivo.size > 20 * 1024 * 1024 for arquivo in anexos):
            st.error("Cada anexo deve ter no máximo 20 MB.")
            return
        if not titulo.strip() or not (problema.strip() or solucao.strip()):
            st.error("Informe o título e pelo menos o problema/informação ou a solução.")
        else:
            agora = datetime.now().strftime("%d/%m/%Y %H:%M")
            usuario = st.session_state.get("username") or ""
            conn_salvar = conectar_banco()
            cs = conn_salvar.cursor()
            if selecionado:
                cs.execute(
                    """UPDATE base_pesquisa SET titulo=?, categoria=?, palavras_chave=?, problema=?, solucao=?,
                       alterado_por=?, alterado_em=? WHERE id=?""",
                    (titulo.strip(), categoria.strip(), palavras.strip(), problema.strip(), solucao.strip(), usuario, agora, selecionado),
                )
            else:
                cs.execute(
                    """INSERT INTO base_pesquisa
                       (titulo, categoria, palavras_chave, problema, solucao, criado_por, criado_em)
                       VALUES (?,?,?,?,?,?,?)""",
                    (titulo.strip(), categoria.strip(), palavras.strip(), problema.strip(), solucao.strip(), usuario, agora),
                )
            pesquisa_id = selecionado or cs.lastrowid
            for arquivo in anexos:
                cs.execute("INSERT INTO base_pesquisa_anexos (pesquisa_id,nome,mime,arquivo) VALUES (?,?,?,?)",
                           (pesquisa_id, arquivo.name, arquivo.type, arquivo.getvalue()))
            conn_salvar.commit()
            conn_salvar.close()
            st.session_state['base_pesquisa_id_ativo'] = pesquisa_id
            st.session_state['base_pesquisa_versao'] = st.session_state.get('base_pesquisa_versao', 0) + 1
            st.success("Base de Pesquisa atualizada.")
            st.rerun()


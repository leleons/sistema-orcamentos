"""Consulta do Simples reutilizada no cadastro e na emissão."""
from dsystem_erp.services.dados_publicos import consultar_cnpj, ConsultaDadosPublicosErro, somente_digitos
from dsystem_erp.services.simples import OPCOES_SIMPLES, optante_legado


def campo_simples(st, documento, chave, atual=""):
    documento = somente_digitos(documento)
    if len(documento) == 11:
        st.session_state[chave + "_documento"] = documento
        st.session_state.pop(chave, None)
        st.session_state.pop(chave + "_mensagem", None)
        st.caption("Simples Nacional: não se aplica ao CPF. Informe o CNPJ para consultar uma empresa.")
        return "NA"
    memo = chave + "_documento"
    recarregar = st.button("Consultar situação pelo CNPJ", key=chave + "_consultar", disabled=len(documento) != 14)
    if len(documento) != 14:
        st.session_state[memo] = documento
        st.session_state[chave] = ""
        st.session_state.pop(chave + "_mensagem", None)
    if len(documento) == 14 and (st.session_state.get(memo) != documento or recarregar):
        mudou = st.session_state.get(memo) not in (None, documento)
        st.session_state[memo] = documento
        st.session_state[chave] = "" if mudou else (atual if atual in OPCOES_SIMPLES else "")
        try:
            # Um valor já salvo/manual permanece até uma consulta explícita.
            dados = consultar_cnpj(documento) if (recarregar or mudou or not atual) else {}
            situacao = dados.get("situacao_simples_nacional", "")
            if situacao:
                st.session_state[chave] = situacao
                mensagem = "Situação consultada na BrasilAPI. Confira se corresponde à competência da nota."
            else:
                mensagem = "Situação salva no cadastro. Use a consulta para atualizar." if atual and not recarregar and not mudou else "A fonte não informou a situação completa. Confira e selecione manualmente."
        except ConsultaDadosPublicosErro as erro:
            mensagem = str(erro) + " Você pode informar a situação manualmente."
        st.session_state[chave + "_mensagem"] = mensagem
    if st.session_state.get(chave + "_mensagem"):
        st.caption(st.session_state[chave + "_mensagem"])
    opcoes = ["", "1", "2", "3"]
    if st.session_state.get(chave) not in opcoes:
        st.session_state[chave] = atual if atual in opcoes else ""
    return st.selectbox("Situação no Simples Nacional:", opcoes, format_func=OPCOES_SIMPLES.get, key=chave)


def atualizar_cadastros(st, conectar_banco, clientes):
    resultados, consultas = [], {}
    progresso = st.progress(0.0)
    for indice, cliente in enumerate(clientes):
        documento = somente_digitos(cliente.get("cnpj"))
        situacao = ""
        if len(documento) == 11:
            situacao, mensagem = "NA", "CPF: não se aplica"
        elif len(documento) == 14:
            if documento not in consultas:
                try:
                    consultas[documento] = (consultar_cnpj(documento).get("situacao_simples_nacional", ""), "")
                except ConsultaDadosPublicosErro as erro:
                    consultas[documento] = ("", str(erro))
            situacao, erro = consultas[documento]
            mensagem = OPCOES_SIMPLES.get(situacao) if situacao else (erro or "Não informado pela fonte; cadastro preservado")
        else:
            mensagem = "Documento inválido; cadastro preservado"
        if situacao:
            conn = conectar_banco()
            try:
                cursor = conn.cursor()
                cursor.execute("UPDATE clientes SET situacao_simples_nacional=?, optante_simples_nacional=? WHERE id=? AND cnpj=?",
                               (situacao, optante_legado(situacao), cliente["id"], cliente.get("cnpj")))
                conn.commit()
            finally:
                conn.close()
        resultados.append({"ID": cliente["id"], "Nome": cliente.get("nome"), "Resultado": mensagem})
        progresso.progress((indice + 1) / len(clientes))
    return resultados

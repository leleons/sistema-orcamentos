from __future__ import annotations

from dsystem_erp.app_context import aplicar_contexto_pagina
from dsystem_erp.services.dados_publicos import (
    ConsultaDadosPublicosErro,
    ConsultaDadosPublicosIndisponivel,
    consultar_cep,
    consultar_cnpj,
)
from dsystem_erp.ui_consulta import tabela_clicavel_id
from dsystem_erp.utils.formatadores import somente_digitos
from dsystem_erp.pages.simples import campo_simples, atualizar_cadastros
from dsystem_erp.services.simples import validar_situacao, optante_legado


def validar_redefinicao_senha_portal(senha, confirmacao):
    if not senha and not confirmacao:
        return
    if senha != confirmacao:
        raise ValueError("As senhas do portal não coincidem.")
    if len(senha) < 8 or not senha.strip():
        raise ValueError("A nova senha do portal deve ter pelo menos 8 caracteres.")


def filtrar_clientes_cadastrados(clientes, pesquisa):
    """Filtra por nome, código, CPF ou CNPJ, com ou sem pontuação."""
    termo = str(pesquisa or "").strip().casefold()
    if not termo:
        return list(clientes or [])
    documento = somente_digitos(termo)
    pesquisa_documento = bool(documento) and all(
        caractere.isdigit() or caractere in ".-/ ()"
        for caractere in termo
    )
    resultado = []
    for cliente in clientes or []:
        textos = (
            cliente.get("nome"), cliente.get("codigo_cliente"),
            cliente.get("cnpj"), cliente.get("documento_chave"),
            cliente.get("portal_username"),
        )
        encontrou_texto = any(termo in str(valor or "").casefold() for valor in textos)
        encontrou_documento = pesquisa_documento and any(
            documento in somente_digitos(valor)
            for valor in (cliente.get("cnpj"), cliente.get("documento_chave"), cliente.get("portal_username"))
        )
        if encontrou_texto or encontrou_documento:
            resultado.append(cliente)
    return resultado


def buscar_cliente_cadastrado_por_cpf(clientes, cpf):
    """Localiza somente CPF exato nos cadastros internos, sem confundir com CNPJ."""
    documento = somente_digitos(cpf)
    if len(documento) != 11:
        raise ValueError("Informe um CPF com 11 dígitos.")
    for cliente in clientes or []:
        documentos_cliente = (
            cliente.get("cnpj"), cliente.get("documento_chave"), cliente.get("portal_username"),
        )
        if any(somente_digitos(valor) == documento for valor in documentos_cliente):
            return cliente
    return None


def _preencher_campos(estado, dados: dict, campos: dict[str, str]) -> None:
    for origem, chave_widget in campos.items():
        valor = dados.get(origem)
        if valor not in (None, ""):
            estado[chave_widget] = valor


def _campos_novo_cliente() -> dict[str, str]:
    return {
        "cnpj": "cad_cli_cpf_cnpj", "nome": "cad_cli_nome", "fantasia": "cad_cli_rg",
        "telefone": "cad_cli_telefone", "telefone_secundario": "cad_cli_telefone_sec",
        "email": "cad_cli_email", "endereco": "cad_cli_endereco", "numero": "cad_cli_numero",
        "complemento": "cad_cli_complemento", "bairro": "cad_cli_bairro",
        "cidade_estado": "cad_cli_cidade_estado", "cep": "cad_cli_cep",
        "codigo_ibge": "cad_cli_codigo_ibge", "uf": "cad_cli_uf", "pessoa": "cad_cli_pessoa",
        "ramo_atividade": "cad_cli_ramo", "optante_simples_nacional": "cad_cli_simples",
    }


def _campos_edicao_cliente(cliente_id: int) -> dict[str, str]:
    sufixo = str(cliente_id)
    return {
        "cnpj": f"edit_cli_cnpj_{sufixo}", "nome": f"edit_cli_nome_{sufixo}",
        "fantasia": f"edit_cli_rg_{sufixo}", "telefone": f"edit_cli_tel_{sufixo}",
        "telefone_secundario": f"edit_cli_tel_sec_{sufixo}", "email": f"edit_cli_email_{sufixo}",
        "endereco": f"edit_cli_end_{sufixo}", "numero": f"edit_cli_num_{sufixo}",
        "complemento": f"edit_cli_comp_{sufixo}", "bairro": f"edit_cli_bai_{sufixo}",
        "cidade_estado": f"edit_cli_cid_{sufixo}", "cep": f"edit_cli_cep_{sufixo}",
        "codigo_ibge": f"edit_cli_ibge_{sufixo}", "uf": f"edit_cli_uf_{sufixo}",
        "pessoa": f"edit_cli_pessoa_{sufixo}", "ramo_atividade": f"edit_cli_ramo_{sufixo}",
        "optante_simples_nacional": f"edit_cli_simples_{sufixo}",
    }


def renderizar_cadastro_cliente_fornecedor(ctx: dict) -> None:
    aplicar_contexto_pagina(ctx, globals())
    for chave in st.session_state.pop("portal_senha_limpar_campos", []):
        st.session_state.pop(chave, None)
    st.title("Gestão e Cadastro de Cliente/Fornecedor")
    injetar_mascaras()
    aba1, aba2, aba3, aba4 = st.tabs(["Cadastrar Novo", "Base Cadastrada", "Importar Excel", "Contrato de Suporte"])

    with aba1:
        st.write("Preencha os dados abaixo. Eles ficarão disponíveis para puxar em Orçamentos, O.S. e Infraestrutura.")
        st.session_state.setdefault("cad_cli_cidade_estado", "BH / MG")

        st.markdown("**Preenchimento automático**")
        consulta1, acao1, consulta_cpf, acao_cpf, consulta2, acao2 = st.columns([3, 1, 3, 1, 3, 1])
        cnpj_consulta = consulta1.text_input(
            "Consultar CNPJ:", placeholder="00.000.000/0000-00", key="cad_cli_consulta_cnpj"
        )
        consulta1.caption("Dados públicos pela BrasilAPI, com CNPJ.ws como alternativa automática em caso de indisponibilidade.")
        consultar_cnpj_agora = acao1.button("Buscar CNPJ", width="stretch", key="btn_cad_buscar_cnpj")
        cpf_consulta = consulta_cpf.text_input(
            "Consultar CPF:", placeholder="000.000.000-00", key="cad_cli_consulta_cpf"
        )
        consulta_cpf.caption("Pesquisa segura nos clientes já cadastrados.")
        consultar_cpf_agora = acao_cpf.button("Buscar CPF", width="stretch", key="btn_cad_buscar_cpf")
        cep_consulta = consulta2.text_input(
            "Consultar CEP:", placeholder="00000-000", key="cad_cli_consulta_cep"
        )
        consulta2.caption("Endereço consultado no ViaCEP.")
        consultar_cep_agora = acao2.button("Buscar CEP", width="stretch", key="btn_cad_buscar_cep")
        if consultar_cnpj_agora:
            try:
                with st.spinner('Consultando CNPJ; em caso de falha temporária, tentaremos mais uma vez...'):
                    dados_cnpj = consultar_cnpj(cnpj_consulta)
                _preencher_campos(st.session_state, dados_cnpj, _campos_novo_cliente())
                situacao = dados_cnpj.get("situacao_cadastral") or "não informada"
                st.session_state["cad_cli_consulta_mensagem"] = f"CNPJ localizado. Situação cadastral: {situacao}."
                st.rerun()
            except ConsultaDadosPublicosIndisponivel as ex:
                st.warning(str(ex))
            except ConsultaDadosPublicosErro as ex:
                st.error(str(ex))
        if consultar_cpf_agora:
            try:
                cpf_documento = somente_digitos(cpf_consulta)
                cliente_cpf = buscar_cliente_cadastrado_por_cpf(buscar_clientes(), cpf_documento)
                if cliente_cpf:
                    st.session_state["cliente_edicao_selecionado"] = int(cliente_cpf["id"])
                    st.session_state["cad_cli_consulta_mensagem"] = (
                        f"CPF localizado: {cliente_cpf.get('nome') or 'cliente sem nome'}. "
                        "Abra a aba Base Cadastrada para consultar ou editar."
                    )
                else:
                    st.session_state["cad_cli_cpf_cnpj"] = cpf_documento
                    st.session_state["cad_cli_consulta_mensagem"] = (
                        "CPF não encontrado na base. O número foi preenchido no novo cadastro."
                    )
                st.rerun()
            except ValueError as ex:
                st.error(str(ex))
        if consultar_cep_agora:
            try:
                _preencher_campos(st.session_state, consultar_cep(cep_consulta), _campos_novo_cliente())
                st.session_state["cad_cli_consulta_mensagem"] = "CEP localizado e endereço preenchido."
                st.rerun()
            except ConsultaDadosPublicosErro as ex:
                st.error(str(ex))
        mensagem_consulta = st.session_state.pop("cad_cli_consulta_mensagem", None)
        if mensagem_consulta:
            st.success(mensagem_consulta)
        
        c_top1, c_top2 = st.columns(2)
        with c_top1: 
            c_tipo = st.radio("Classificação:", ["Cliente", "Fornecedor", "Ambos"], horizontal=True)
        with c_top2: 
            st.write("") 
            c_subst = st.checkbox("É Substituto Tributário?")

        c1, c2, c3 = st.columns(3)
        with c1: c_nome = st.text_input("Nome/Empresa (Obrigatório):", key="cad_cli_nome")
        with c2: c_cnpj = st.text_input("CPF/CNPJ (Obrigatório e único):", placeholder="Digite CPF ou CNPJ", key="cad_cli_cpf_cnpj")
        with c3: c_rg = st.text_input("RG/Fantasia:", key="cad_cli_rg")
        c_emite_nf = st.selectbox("Emite nota fiscal?", ["Não informado", "Sim", "Não"], key="cad_cli_emite_nf")
        c_situacao = campo_simples(st, c_cnpj, "cad_cli_situacao_sn")
            
        c_ie1, c_ie2 = st.columns(2)
        with c_ie1: c_ie = st.text_input("Inscrição Estadual (IE):", key="cad_cli_ie")
        with c_ie2: c_im = st.text_input("Inscrição Municipal (IM):", key="cad_cli_im")
            
        c4, c5, c5b = st.columns(3)
        with c4: c_tel = st.text_input("Telefone Principal:", placeholder="(31) 99999-9999", key="cad_cli_telefone")
        with c5: c_tel_sec = st.text_input("Telefone Secundário:", placeholder="(31) 99999-9999", key="cad_cli_telefone_sec")
        with c5b: c_email = st.text_input("E-mail:", key="cad_cli_email")
        c_emails_cobranca = st.text_area("E-mails de cobrança:", height=70, key="cad_cli_emails_cobranca", help="Separe mais de um e-mail por vírgula, ponto e vírgula ou quebra de linha.")
            
        c6, c7, c8 = st.columns([3,1,2])
        with c6: c_end = st.text_input("Endereço (Rua):", key="cad_cli_endereco")
        with c7: c_num = st.text_input("Número:", key="cad_cli_numero")
        with c8: c_comp = st.text_input("Complemento:", key="cad_cli_complemento")
            
        c9, c10, c11 = st.columns(3)
        with c9: c_bai = st.text_input("Bairro:", key="cad_cli_bairro")
        with c10: c_cid = st.text_input("Cidade/UF:", key="cad_cli_cidade_estado")
        with c11: c_cep = st.text_input("CEP:", placeholder="00000-000", key="cad_cli_cep")

        with st.expander("Dados complementares e faturamento", expanded=False):
            cc1, cc2, cc3 = st.columns(3)
            c_pessoa = cc1.selectbox("Pessoa:", ["", "Jurídica", "Física"], key="cad_cli_pessoa")
            c_endereco_padrao = cc2.selectbox("Endereço padrão:", ["", "SIM", "NÃO"], key="cad_cli_endereco_padrao")
            c_referencia = cc3.text_input("Referência:", key="cad_cli_referencia")
            cc4, cc5, cc6 = st.columns(3)
            c_codigo_ibge = cc4.text_input("Código IBGE / Cidade:", key="cad_cli_codigo_ibge")
            c_uf = cc5.text_input("UF / Estado:", key="cad_cli_uf")
            c_estado_ie = cc6.text_input("Estado da Inscrição Estadual:", key="cad_cli_estado_ie")
            cc7, cc8, cc9 = st.columns(3)
            c_contato = cc7.text_input("Contato:", key="cad_cli_contato")
            c_contato_padrao = cc8.selectbox("Contato padrão:", ["", "SIM", "NÃO"], key="cad_cli_contato_padrao")
            c_contato_cobranca = cc9.selectbox("Contato cobrança:", ["", "SIM", "NÃO"], key="cad_cli_contato_cobranca")
            cc10, cc11, cc12 = st.columns(3)
            c_data_nascimento = cc10.text_input("Data de nascimento:", key="cad_cli_data_nascimento")
            c_simples = optante_legado(c_situacao)
            c_ramo = cc12.text_input("Ramo de atividade:", key="cad_cli_ramo")
            cc13, cc14, cc15 = st.columns(3)
            c_dias_antecedencia = cc13.text_input("Dias antecedência faturamento:", key="cad_cli_dias_antecedencia")
            c_dia_faturamento = cc14.text_input("Dia de faturamento:", key="cad_cli_dia_faturamento")
            c_dia_vencimento = cc15.text_input("Dia de vencimento:", key="cad_cli_dia_vencimento")

        c_logo = st.file_uploader("Logo do cliente/fornecedor:", type=TIPOS_IMAGEM_UPLOAD, key="cad_cli_logo")

        st.write("---")
        st.markdown("**Redes Sociais**")
        qtd_redes = st.number_input("Quantidade de redes sociais:", min_value=0, max_value=10, value=0, key="cad_cli_qtd_redes")
        redes_sociais_lista = []
        for i in range(qtd_redes):
            rs1, rs2 = st.columns([1, 3])
            rede_nome = rs1.text_input(f"Rede {i+1}:", key=f"cad_cli_rede_nome_{i}", placeholder="Instagram, LinkedIn...")
            rede_url = rs2.text_input(f"Link/usuário {i+1}:", key=f"cad_cli_rede_url_{i}")
            if rede_nome or rede_url:
                redes_sociais_lista.append({"rede": rede_nome, "url": rede_url})
        redes_sociais_json = preparar_redes_sociais(redes_sociais_lista)

        st.write("---")
        st.markdown("**Login do Cliente no Portal**")
        st.info("O usuário será o CPF/CNPJ informado e a senha inicial será 1234. No primeiro acesso será obrigatório trocar a senha e configurar o autenticador.")
        c_portal_user = normalizar_documento_cliente(c_cnpj)
        c_portal_senha = "1234"
            
        st.write("---")
        is_empresa = st.checkbox("O cliente é uma Empresa? (Adicionar Funcionários)")
        lista_funcionarios = []
        funcionarios_sem_email = []
        
        if is_empresa:
            st.caption('Cada funcionário terá login pelo próprio e-mail, vinculado a esta empresa, e verá somente seus chamados e conversas. A D-System mantém a visão de todos. A senha inicial segue o primeiro acesso do portal, com troca obrigatória.')
            qtd_func = st.number_input("Quantidade de Funcionários:", min_value=1, max_value=50, value=1)
            for i in range(qtd_func):
                st.write(f"**Funcionário {i+1}**")
                f_col1, f_col2, f_col3, f_col4 = st.columns(4)
                f_nome = f_col1.text_input("Nome:", key=f"fnome_{i}")
                f_cargo = f_col2.text_input("Cargo/Setor:", key=f"fcargo_{i}")
                f_tel = f_col3.text_input("Telefone Direto:", key=f"ftel_{i}")
                f_email = f_col4.text_input("E-mail Direto:", key=f"femail_{i}")
                if f_nome:
                    lista_funcionarios.append({"codigo": f"FUN{i+1:03d}", "nome": f_nome, "cargo": f_cargo, "telefone": f_tel, "email": f_email})
                    if not f_email.strip():
                        funcionarios_sem_email.append(f_nome)
                    
        funcionarios_json = preparar_funcionarios(lista_funcionarios)

        if st.session_state.pop('cliente_salvo', None):
            st.toast("Cadastro salvo com sucesso!")
        
        if st.button("Salvar no Banco de Dados", type="primary", width="stretch"):
            if funcionarios_sem_email:
                st.error("Informe o e-mail dos funcionários para gerar os logins: " + ", ".join(funcionarios_sem_email))
            elif c_nome.strip() and normalizar_documento_cliente(c_cnpj):
                try:
                    validar_situacao(c_cnpj, c_emite_nf, c_situacao)
                    if c_logo and not upload_dentro_limite(c_logo):
                        erro_upload_grande("logo")
                        st.stop()
                    logo_dados, logo_nome, logo_mime = dados_upload(c_logo)
                    sub_str = "Sim" if c_subst else "Não"
                    dados_complementares = {
                        "emite_nota_fiscal": c_emite_nf,
                        "situacao_simples_nacional": c_situacao,
                        "pessoa": c_pessoa, "endereco_padrao": c_endereco_padrao, "referencia": c_referencia,
                        "codigo_ibge": c_codigo_ibge, "uf": c_uf, "contato_padrao": c_contato_padrao,
                        "contato_cobranca": c_contato_cobranca, "contato": c_contato,
                        "estado_insc_estadual": c_estado_ie, "data_nascimento": c_data_nascimento,
                        "optante_simples_nacional": c_simples, "ramo_atividade": c_ramo,
                        "dias_antecedencia_faturamento": c_dias_antecedencia,
                        "dia_faturamento": c_dia_faturamento, "dia_vencimento": c_dia_vencimento,
                    }
                    salvar_cliente(c_nome, c_tel, c_tel_sec, c_email, c_emails_cobranca, c_cnpj, c_rg, c_end, c_num, c_comp, c_bai, c_cid, c_cep, c_tipo, c_ie, c_im, sub_str, redes_sociais_json, funcionarios_json, c_portal_user, c_portal_senha, logo_dados, logo_nome, logo_mime, dados_complementares)
                    st.session_state['cliente_salvo'] = True
                    st.rerun()
                except Exception as ex:
                    st.error(f"Erro ao salvar cliente no banco: {ex}")
            else: 
                st.error("Informe o Nome/Empresa e um CPF/CNPJ válido e único.")

    with aba2:
        st.subheader("Base Cadastrada (Tabela Completa)")
        if tem_permissao("clientes.edit"):
            with st.expander("Atualizar Simples Nacional dos cadastros existentes"):
                st.caption("Consulta os CNPJs acessíveis ao seu usuário. CPF recebe 'Não se aplica'. Falhas ou informação ausente preservam o cadastro. A emissão de nota não é deduzida do CNPJ.")
                if st.button("Consultar e atualizar cadastros", key="clientes_atualizar_simples"):
                    st.session_state["clientes_resultado_simples"] = atualizar_cadastros(st, conectar_banco, buscar_clientes())
                    # Limpa valores anteriores dos formulários antes de renderizá-los.
                    for chave in list(st.session_state):
                        if str(chave).startswith("edit_cli_situacao_sn_"):
                            del st.session_state[chave]
                if st.session_state.get("clientes_resultado_simples"):
                    st.dataframe(st.session_state["clientes_resultado_simples"], hide_index=True)
        clientes_cadastrados = buscar_clientes()
        pesquisa_cliente = st.text_input(
            "Pesquisar por nome, código, CPF ou CNPJ:",
            key="pesquisa_base_clientes",
            placeholder="Ex.: Casa Verde, CLI00010, 123.456.789-00 ou CNPJ",
        )
        termo_cliente = pesquisa_cliente.strip().lower()
        clientes_cadastrados = filtrar_clientes_cadastrados(clientes_cadastrados, pesquisa_cliente)

        documentos_agrupados = {}
        for cli in buscar_clientes():
            chave_doc = normalizar_documento_cliente(cli.get("cnpj"))
            if chave_doc:
                documentos_agrupados.setdefault(chave_doc, []).append(cli)
        documentos_duplicados = [grupo for grupo in documentos_agrupados.values() if len(grupo) > 1]
        if documentos_duplicados:
            detalhes_duplicados = " | ".join(
                f"{grupo[0].get('cnpj')}: IDs {', '.join(str(item.get('id')) for item in grupo)}"
                for grupo in documentos_duplicados
            )
            st.warning(f"Cadastros antigos com CPF/CNPJ duplicado para revisão: {detalhes_duplicados}")
        
        if clientes_cadastrados:
            df_view = [{k: v for k, v in cli.items() if k not in ('funcionarios', 'portal_password', 'portal_2fa_secret', 'logo')} for cli in clientes_cadastrados]
            id_cliente_clicado = tabela_clicavel_id(st, df_view, "clientes_grade_consulta", "id")
            if id_cliente_clicado is not None:
                st.session_state["cliente_edicao_selecionado"] = int(id_cliente_clicado)
            id_cliente_selecionado = st.session_state.get("cliente_edicao_selecionado")
            ids_clientes_visiveis = {int(item.get("id") or 0) for item in clientes_cadastrados}
            if termo_cliente and int(id_cliente_selecionado or 0) not in ids_clientes_visiveis:
                st.session_state.pop("cliente_edicao_selecionado", None)
                id_cliente_selecionado = None
            st.caption("Clique em qualquer informação da linha para abrir automaticamente a edição.")

            with st.expander("Histórico de login dos clientes", expanded=False):
                conn_hist = conectar_banco()
                chist = conn_hist.cursor()
                chist.execute(
                    """SELECT cliente_nome, portal_username, evento, ip, criado_em
                       FROM clientes_portal_acessos
                       ORDER BY id DESC
                       LIMIT 100"""
                )
                acessos = chist.fetchall()
                conn_hist.close()
                if acessos:
                    st.dataframe(pd.DataFrame(acessos), width="stretch", hide_index=True)
                else:
                    st.info("Nenhum acesso de cliente registrado ainda.")
            
            st.write("---")
            act_cli = st.radio("Selecione a ação:", ["Editar Cadastro", "Excluir Cadastro"], horizontal=True)
            if id_cliente_selecionado:
                act_cli = "Editar Cadastro"
            
            if st.session_state.pop('cli_excluido', None): st.toast("Excluído!")
            if st.session_state.pop('cli_editado', None): st.toast("Cadastro atualizado!")

            if act_cli == "Excluir Cadastro":
                id_del_cli = st.number_input("ID para Excluir:", min_value=1, step=1)
                if st.button("Excluir Permanentemente"):
                    deletar_registro('clientes', 'id', id_del_cli)
                    st.session_state['cli_excluido'] = True
                    st.rerun()
                    
            elif act_cli == "Editar Cadastro":
                if not id_cliente_selecionado:
                    st.info("Clique em um cliente ou fornecedor na tabela para editar.")
                id_edit_cli = int(id_cliente_selecionado or 0)
                cliente_edit = next((c for c in clientes_cadastrados if c['id'] == id_edit_cli), None)
                
                if cliente_edit:
                    with st.expander(f"Editando: {cliente_edit['nome']}", expanded=True):
                        ecnpj1, ecnpj2, ecep1, ecep2 = st.columns([3, 1, 3, 1])
                        cnpj_edicao_consulta = ecnpj1.text_input(
                            "Atualizar pelo CNPJ:", value=cliente_edit.get("cnpj") or "",
                            key=f"edit_cli_consulta_cnpj_{id_edit_cli}",
                        )
                        buscar_cnpj_edicao = ecnpj2.button(
                            "Buscar CNPJ", width="stretch", key=f"btn_edit_cnpj_{id_edit_cli}"
                        )
                        cep_edicao_consulta = ecep1.text_input(
                            "Atualizar pelo CEP:", value=cliente_edit.get("cep") or "",
                            key=f"edit_cli_consulta_cep_{id_edit_cli}",
                        )
                        buscar_cep_edicao = ecep2.button(
                            "Buscar CEP", width="stretch", key=f"btn_edit_cep_{id_edit_cli}"
                        )
                        if buscar_cnpj_edicao:
                            try:
                                with st.spinner('Consultando CNPJ; em caso de falha temporária, tentaremos mais uma vez...'):
                                    dados_cnpj_edicao = consultar_cnpj(cnpj_edicao_consulta)
                                _preencher_campos(
                                    st.session_state, dados_cnpj_edicao,
                                    _campos_edicao_cliente(id_edit_cli),
                                )
                                st.session_state[f"edit_cli_consulta_ok_{id_edit_cli}"] = "Dados do CNPJ atualizados na tela."
                                st.rerun()
                            except ConsultaDadosPublicosIndisponivel as ex:
                                st.warning(str(ex))
                            except ConsultaDadosPublicosErro as ex:
                                st.error(str(ex))
                        if buscar_cep_edicao:
                            try:
                                _preencher_campos(
                                    st.session_state, consultar_cep(cep_edicao_consulta),
                                    _campos_edicao_cliente(id_edit_cli),
                                )
                                st.session_state[f"edit_cli_consulta_ok_{id_edit_cli}"] = "Endereço atualizado na tela."
                                st.rerun()
                            except ConsultaDadosPublicosErro as ex:
                                st.error(str(ex))
                        mensagem_edicao = st.session_state.pop(f"edit_cli_consulta_ok_{id_edit_cli}", None)
                        if mensagem_edicao:
                            st.success(mensagem_edicao)
                        
                        c_tp1, c_tp2 = st.columns(2)
                        def_tipo = cliente_edit.get('tipo', 'Cliente')
                        idx_tp = ["Cliente", "Fornecedor", "Ambos"].index(def_tipo) if def_tipo in ["Cliente", "Fornecedor", "Ambos"] else 0
                        e_tipo = c_tp1.radio("Classificação:", ["Cliente", "Fornecedor", "Ambos"], index=idx_tp, horizontal=True, key=f"etipo_{id_edit_cli}")
                        e_sub = c_tp2.checkbox("É Substituto Tributário?", value=(cliente_edit.get('substituto_tributario') == 'Sim'), key=f"esub_{id_edit_cli}")

                        e_nome = st.text_input("Nome/Empresa:", value=cliente_edit['nome'], key=f"edit_cli_nome_{id_edit_cli}")
                        e_cnpj = st.text_input("CPF/CNPJ:", value=cliente_edit['cnpj'] or "", key=f"edit_cli_cnpj_{id_edit_cli}")
                        opcoes_emite = ["Não informado", "Sim", "Não"]
                        e_emite_nf = st.selectbox("Emite nota fiscal?", opcoes_emite,
                            index=opcoes_emite.index(cliente_edit.get("emite_nota_fiscal")) if cliente_edit.get("emite_nota_fiscal") in opcoes_emite else 0,
                            key=f"edit_cli_emite_nf_{id_edit_cli}")
                        e_situacao = campo_simples(st, e_cnpj, f"edit_cli_situacao_sn_{id_edit_cli}", cliente_edit.get("situacao_simples_nacional") or "")
                        e_rg = st.text_input("RG/Fantasia:", value=cliente_edit['rg_mei'] or "", key=f"edit_cli_rg_{id_edit_cli}")
                        
                        c_ie1, c_ie2 = st.columns(2)
                        e_ie = c_ie1.text_input("Inscrição Estadual (IE):", value=cliente_edit.get('insc_estadual') or "", key=f"eie_{id_edit_cli}")
                        e_im = c_ie2.text_input("Inscrição Municipal (IM):", value=cliente_edit.get('insc_municipal') or "", key=f"eim_{id_edit_cli}")

                        et1, et2, et3 = st.columns(3)
                        e_tel = et1.text_input("Telefone Principal:", value=cliente_edit['telefone'] or "", key=f"edit_cli_tel_{id_edit_cli}")
                        e_tel_sec = et2.text_input("Telefone Secundário:", value=cliente_edit.get('telefone_secundario') or "", key=f"edit_cli_tel_sec_{id_edit_cli}")
                        e_email = et3.text_input("E-mail:", value=cliente_edit['email'] or "", key=f"edit_cli_email_{id_edit_cli}")
                        e_emails_cobranca = st.text_area("E-mails de cobrança:", value=cliente_edit.get("emails_cobranca") or "", height=70, key=f"edit_cli_emails_cobranca_{id_edit_cli}", help="Separe mais de um e-mail por vírgula, ponto e vírgula ou quebra de linha.")
                        e_end = st.text_input("Endereço:", value=cliente_edit['endereco'] or "", key=f"edit_cli_end_{id_edit_cli}")
                        e_num = st.text_input("Número:", value=cliente_edit['numero'] or "", key=f"edit_cli_num_{id_edit_cli}")
                        e_comp = st.text_input("Complemento:", value=cliente_edit['complemento'] or "", key=f"edit_cli_comp_{id_edit_cli}")
                        e_bai = st.text_input("Bairro:", value=cliente_edit['bairro'] or "", key=f"edit_cli_bai_{id_edit_cli}")
                        e_cid = st.text_input("Cidade/UF:", value=cliente_edit['cidade_estado'] or "", key=f"edit_cli_cid_{id_edit_cli}")
                        e_cep = st.text_input("CEP:", value=cliente_edit['cep'] or "", key=f"edit_cli_cep_{id_edit_cli}")

                        with st.expander("Dados complementares e faturamento", expanded=False):
                            ec1, ec2, ec3 = st.columns(3)
                            e_pessoa = ec1.text_input("Pessoa:", value=cliente_edit.get("pessoa") or "", key=f"edit_cli_pessoa_{id_edit_cli}")
                            e_endereco_padrao = ec2.text_input("Endereço padrão:", value=cliente_edit.get("endereco_padrao") or "", key=f"edit_cli_endpad_{id_edit_cli}")
                            e_referencia = ec3.text_input("Referência:", value=cliente_edit.get("referencia") or "", key=f"edit_cli_ref_{id_edit_cli}")
                            ec4, ec5, ec6 = st.columns(3)
                            e_codigo_ibge = ec4.text_input("Código IBGE / Cidade:", value=cliente_edit.get("codigo_ibge") or "", key=f"edit_cli_ibge_{id_edit_cli}")
                            e_uf = ec5.text_input("UF / Estado:", value=cliente_edit.get("uf") or "", key=f"edit_cli_uf_{id_edit_cli}")
                            e_estado_ie = ec6.text_input("Estado da Inscrição Estadual:", value=cliente_edit.get("estado_insc_estadual") or "", key=f"edit_cli_estadoie_{id_edit_cli}")
                            ec7, ec8, ec9 = st.columns(3)
                            e_contato = ec7.text_input("Contato:", value=cliente_edit.get("contato") or "", key=f"edit_cli_contato_{id_edit_cli}")
                            e_contato_padrao = ec8.text_input("Contato padrão:", value=cliente_edit.get("contato_padrao") or "", key=f"edit_cli_contatopad_{id_edit_cli}")
                            e_contato_cobranca = ec9.text_input("Contato cobrança:", value=cliente_edit.get("contato_cobranca") or "", key=f"edit_cli_contatocob_{id_edit_cli}")
                            ec10, ec11, ec12 = st.columns(3)
                            e_data_nascimento = ec10.text_input("Data de nascimento:", value=cliente_edit.get("data_nascimento") or "", key=f"edit_cli_nasc_{id_edit_cli}")
                            e_simples = optante_legado(e_situacao)
                            e_ramo = ec12.text_input("Ramo de atividade:", value=cliente_edit.get("ramo_atividade") or "", key=f"edit_cli_ramo_{id_edit_cli}")
                            ec13, ec14, ec15 = st.columns(3)
                            e_dias_antecedencia = ec13.text_input("Dias antecedência faturamento:", value=cliente_edit.get("dias_antecedencia_faturamento") or "", key=f"edit_cli_antecedencia_{id_edit_cli}")
                            e_dia_faturamento = ec14.text_input("Dia de faturamento:", value=cliente_edit.get("dia_faturamento") or "", key=f"edit_cli_diafat_{id_edit_cli}")
                            e_dia_vencimento = ec15.text_input("Dia de vencimento:", value=cliente_edit.get("dia_vencimento") or "", key=f"edit_cli_diavenc_{id_edit_cli}")

                        if cliente_edit.get("logo"):
                            st.image(cliente_edit.get("logo"), caption=cliente_edit.get("logo_nome") or "Logo cadastrada", width=160)
                        e_logo = st.file_uploader("Atualizar logo do cliente/fornecedor:", type=TIPOS_IMAGEM_UPLOAD, key=f"edit_cli_logo_{id_edit_cli}")

                        st.markdown("**Redes Sociais**")
                        redes_existentes = carregar_lista_json(cliente_edit.get("redes_sociais"))
                        qtd_redes_edit = st.number_input("Quantidade de redes sociais:", min_value=0, max_value=10, value=len(redes_existentes), key=f"edit_cli_qtd_redes_{id_edit_cli}")
                        redes_sociais_edit = []
                        for i in range(qtd_redes_edit):
                            rede_atual = redes_existentes[i] if i < len(redes_existentes) else {}
                            rs1, rs2 = st.columns([1, 3])
                            rede_nome = rs1.text_input(f"Rede {i+1}:", value=rede_atual.get("rede", ""), key=f"edit_cli_rede_nome_{id_edit_cli}_{i}")
                            rede_url = rs2.text_input(f"Link/usuário {i+1}:", value=rede_atual.get("url", ""), key=f"edit_cli_rede_url_{id_edit_cli}_{i}")
                            if rede_nome or rede_url:
                                redes_sociais_edit.append({"rede": rede_nome, "url": rede_url})
                        redes_sociais_json_edit = preparar_redes_sociais(redes_sociais_edit)

                        st.markdown("**Login do Cliente no Portal**")
                        e_portal_user = normalizar_documento_cliente(e_cnpj)
                        st.info(f"Usuário automático da empresa: {e_portal_user or 'informe o CPF/CNPJ'}")
                        senha_versao = st.session_state.get(f"portal_senha_versao_{id_edit_cli}", 0)
                        chave_senha = f"edit_cli_portal_senha_{id_edit_cli}_{senha_versao}"
                        chave_confirmacao = f"edit_cli_portal_confirmacao_{id_edit_cli}_{senha_versao}"
                        e_portal_senha = st.text_input("Nova senha do portal:", type="password", key=chave_senha)
                        e_portal_confirmacao = st.text_input("Confirmar nova senha do portal:", type="password", key=chave_confirmacao)
                        st.caption("Deixe os dois campos vazios para manter a senha atual. Para redefinir, use pelo menos 8 caracteres e clique em Guardar Alterações. O cliente deverá trocar essa senha no próximo acesso. Não altera as senhas dos funcionários.")
                        e_reset_2fa = st.checkbox("Resetar 2FA do cliente", help="Use se o cliente perdeu o celular/autenticador. No próximo login ele precisará configurar novamente.", key=f"edit_cli_reset_2fa_{id_edit_cli}")
                        
                        try: func_existentes = json.loads(cliente_edit.get('funcionarios', '[]'))
                        except: func_existentes = []
                        
                        is_empresa_edit = st.checkbox("É uma Empresa?", value=len(func_existentes) > 0, key=f"isemp_{id_edit_cli}")
                        lista_funcionarios_edit = []
                        funcionarios_edit_sem_email = []
                        
                        if is_empresa_edit:
                            st.caption('O e-mail de cada funcionário é seu login individual. Ele vê somente seus chamados; remover o funcionário desativa o acesso, sem apagar o histórico da D-System.')
                            qtd_func_edit = st.number_input("Quantidade de Funcionários:", min_value=1, max_value=50, value=max(1, len(func_existentes)), key=f"qf_{id_edit_cli}")
                            for i in range(qtd_func_edit):
                                default_fn = func_existentes[i].get('nome', '') if i < len(func_existentes) else ""
                                default_fc = func_existentes[i].get('cargo', '') if i < len(func_existentes) else ""
                                default_ft = func_existentes[i].get('telefone', '') if i < len(func_existentes) else ""
                                default_fe = func_existentes[i].get('email', '') if i < len(func_existentes) else ""
                                
                                st.write(f"**Funcionário {i+1}**")
                                f_col1, f_col2, f_col3, f_col4 = st.columns(4)
                                f_nome = f_col1.text_input("Nome:", value=default_fn, key=f"efnome_{id_edit_cli}_{i}")
                                f_cargo = f_col2.text_input("Cargo/Setor:", value=default_fc, key=f"efcargo_{id_edit_cli}_{i}")
                                f_tel = f_col3.text_input("Telefone Direto:", value=default_ft, key=f"eftel_{id_edit_cli}_{i}")
                                f_email = f_col4.text_input("E-mail Direto:", value=default_fe, key=f"efemail_{id_edit_cli}_{i}")
                                codigo_func = func_existentes[i].get('codigo', f"FUN{i+1:03d}") if i < len(func_existentes) else f"FUN{i+1:03d}"
                                if f_nome:
                                    lista_funcionarios_edit.append({"codigo": codigo_func, "nome": f_nome, "cargo": f_cargo, "telefone": f_tel, "email": f_email})
                                    if not f_email.strip():
                                        funcionarios_edit_sem_email.append(f_nome)
                                    
                        funcionarios_json_edit = preparar_funcionarios(lista_funcionarios_edit)
                        
                        if st.button("Guardar Alterações", type="primary", key=f"btn_save_cli_{id_edit_cli}"):
                            try:
                                validar_situacao(e_cnpj, e_emite_nf, e_situacao)
                                validar_redefinicao_senha_portal(e_portal_senha, e_portal_confirmacao)
                            except ValueError as erro_senha:
                                st.error(str(erro_senha))
                                st.stop()
                            if funcionarios_edit_sem_email:
                                st.error("Informe o e-mail dos funcionários para gerar os logins: " + ", ".join(funcionarios_edit_sem_email))
                                st.stop()
                            documento_edit_chave = normalizar_documento_cliente(e_cnpj)
                            if len(documento_edit_chave) not in (11, 14):
                                st.error("Informe um CPF com 11 dígitos ou CNPJ com 14 dígitos.")
                                st.stop()
                            if e_logo and not upload_dentro_limite(e_logo):
                                erro_upload_grande("logo")
                                st.stop()
                            logo_dados_edit, logo_nome_edit, logo_mime_edit = dados_upload(e_logo)
                            conn = conectar_banco()
                            c = conn.cursor()
                            ids_documento_edit = buscar_ids_cliente_por_documento(c, e_cnpj, ignorar_id=id_edit_cli)
                            if ids_documento_edit:
                                conn.close()
                                st.error("Este CPF/CNPJ já pertence a outro cadastro.")
                                st.stop()
                            sub_str = "Sim" if e_sub else "Não"
                            campos_logo = ", logo_nome=?, logo_mime=?, logo=?" if logo_dados_edit is not None else ""
                            if e_portal_senha:
                                campos_2fa = ", portal_2fa_secret=NULL, portal_2fa_ativo=0" if e_reset_2fa else ""
                                sql = f'''UPDATE clientes SET nome=?, documento_chave=?, telefone=?, telefone_secundario=?, email=?, emails_cobranca=?, cnpj=?, rg_mei=?, endereco=?, numero=?, complemento=?, bairro=?, cidade_estado=?, cep=?, tipo=?, insc_estadual=?, insc_municipal=?, substituto_tributario=?, redes_sociais=?, funcionarios=?, portal_username=?, portal_password=?, portal_trocar_senha=1{campos_2fa}{campos_logo} WHERE id=?'''
                                params = [e_nome, documento_edit_chave, e_tel, e_tel_sec, e_email, e_emails_cobranca, e_cnpj, e_rg, e_end, e_num, e_comp, e_bai, e_cid, e_cep, e_tipo, e_ie, e_im, sub_str, redes_sociais_json_edit, funcionarios_json_edit, e_portal_user, criar_hash_senha(e_portal_senha)]
                            elif e_reset_2fa:
                                sql = f'''UPDATE clientes SET nome=?, documento_chave=?, telefone=?, telefone_secundario=?, email=?, emails_cobranca=?, cnpj=?, rg_mei=?, endereco=?, numero=?, complemento=?, bairro=?, cidade_estado=?, cep=?, tipo=?, insc_estadual=?, insc_municipal=?, substituto_tributario=?, redes_sociais=?, funcionarios=?, portal_username=?, portal_2fa_secret=NULL, portal_2fa_ativo=0{campos_logo} WHERE id=?'''
                                params = [e_nome, documento_edit_chave, e_tel, e_tel_sec, e_email, e_emails_cobranca, e_cnpj, e_rg, e_end, e_num, e_comp, e_bai, e_cid, e_cep, e_tipo, e_ie, e_im, sub_str, redes_sociais_json_edit, funcionarios_json_edit, e_portal_user]
                            else:
                                sql = f'''UPDATE clientes SET nome=?, documento_chave=?, telefone=?, telefone_secundario=?, email=?, emails_cobranca=?, cnpj=?, rg_mei=?, endereco=?, numero=?, complemento=?, bairro=?, cidade_estado=?, cep=?, tipo=?, insc_estadual=?, insc_municipal=?, substituto_tributario=?, redes_sociais=?, funcionarios=?, portal_username=?{campos_logo} WHERE id=?'''
                                params = [e_nome, documento_edit_chave, e_tel, e_tel_sec, e_email, e_emails_cobranca, e_cnpj, e_rg, e_end, e_num, e_comp, e_bai, e_cid, e_cep, e_tipo, e_ie, e_im, sub_str, redes_sociais_json_edit, funcionarios_json_edit, e_portal_user]
                            if logo_dados_edit is not None:
                                params.extend([logo_nome_edit, logo_mime_edit, logo_dados_edit])
                            params.append(id_edit_cli)
                            c.execute(sql, tuple(params))
                            c.execute("UPDATE clientes SET emite_nota_fiscal=?, situacao_simples_nacional=? WHERE id=?", (e_emite_nf, e_situacao, id_edit_cli))
                            c.execute(
                                """UPDATE clientes SET pessoa=?, endereco_padrao=?, referencia=?, codigo_ibge=?, uf=?,
                                   contato_padrao=?, contato_cobranca=?, contato=?, estado_insc_estadual=?,
                                   data_nascimento=?, optante_simples_nacional=?, ramo_atividade=?,
                                   dias_antecedencia_faturamento=?, dia_faturamento=?, dia_vencimento=? WHERE id=?""",
                                (e_pessoa, e_endereco_padrao, e_referencia, e_codigo_ibge, e_uf,
                                 e_contato_padrao, e_contato_cobranca, e_contato, e_estado_ie,
                                 e_data_nascimento, e_simples, e_ramo, e_dias_antecedencia,
                                 e_dia_faturamento, e_dia_vencimento, id_edit_cli),
                            )
                            sincronizar_logins_portal_cliente(
                                c, id_edit_cli, e_nome, e_cnpj, funcionarios_json_edit
                            )
                            conn.commit()
                            conn.close()
                            st.session_state[f"portal_senha_versao_{id_edit_cli}"] = senha_versao + 1
                            st.session_state["portal_senha_limpar_campos"] = [chave_senha, chave_confirmacao]
                            st.session_state['cli_editado'] = True
                            st.rerun()

    with aba3:
        st.subheader("Preparar Importação de Clientes por Excel")
        st.caption("A planilha será analisada primeiro. Os clientes somente serão cadastrados após a confirmação no final da tela.")
        arquivo_excel_clientes = st.file_uploader(
            "Selecionar planilha de clientes:",
            type=["xls", "xlsx"],
            key="clientes_preparar_importacao_excel",
        )

        if arquivo_excel_clientes:
            try:
                cabecalhos_clientes, linhas_clientes = ler_planilha_importacao(arquivo_excel_clientes)
            except Exception as ex:
                st.error(f"Não foi possível ler a planilha: {ex}")
                cabecalhos_clientes, linhas_clientes = [], []

            if linhas_clientes:
                st.success(f"Planilha lida: {len(linhas_clientes)} linhas encontradas.")
                st.write("**Prévia das primeiras linhas:**")
                st.dataframe(linhas_clientes[:10], width="stretch", hide_index=True)

                st.write("**Relacionamento preliminar com o cadastro atual:**")
                opcoes_clientes = ["-- Não relacionar --"] + cabecalhos_clientes
                relacionadas_clientes = set()
                colunas_mapa_clientes = st.columns(3)
                for idx, (campo, rotulo) in enumerate(COLUNAS_CLIENTES_IMPORTACAO.items()):
                    sugestao = sugerir_coluna_cliente(campo, cabecalhos_clientes)
                    indice = opcoes_clientes.index(sugestao) if sugestao in opcoes_clientes else 0
                    selecionada = colunas_mapa_clientes[idx % 3].selectbox(
                        rotulo,
                        opcoes_clientes,
                        index=indice,
                        key=f"mapa_cliente_preparo_{campo}",
                    )
                    if selecionada != "-- Não relacionar --":
                        relacionadas_clientes.add(selecionada)

                colunas_novas = [coluna for coluna in cabecalhos_clientes if coluna not in relacionadas_clientes]
                st.write("**Colunas da planilha ainda sem campo correspondente no site:**")
                if colunas_novas:
                    st.dataframe(
                        [{"Coluna a analisar/adicionar": coluna} for coluna in colunas_novas],
                        width="stretch",
                        hide_index=True,
                    )
                else:
                    st.success("Todas as colunas da planilha foram relacionadas com campos existentes.")

                modo_clientes = st.radio(
                    "Quando o mesmo CPF/CNPJ já existir:",
                    ["Atualizar cliente existente", "Ignorar cliente repetido"],
                    horizontal=True,
                    key="modo_importacao_clientes",
                )
                confirmar_clientes = st.checkbox(
                    "Revisei a prévia e o relacionamento das colunas. Confirmo a importação para o banco.",
                    key="confirmar_importacao_clientes",
                )

                if st.button("Importar clientes para o banco", type="primary", width="stretch", disabled=not confirmar_clientes, key="btn_importar_clientes"):
                    mapeamento_clientes = {
                        campo: st.session_state.get(f"mapa_cliente_preparo_{campo}", "-- Não relacionar --")
                        for campo in COLUNAS_CLIENTES_IMPORTACAO
                    }
                    if mapeamento_clientes["nome"] == "-- Não relacionar --":
                        st.error("Relacione a coluna Nome / Empresa antes de importar.")
                    else:
                        conn_cli_imp = conectar_banco()
                        c_cli_imp = conn_cli_imp.cursor()
                        novos_cli, atualizados_cli, ignorados_cli = 0, 0, 0
                        erro_cli = None
                        try:
                            for linha in linhas_clientes:
                                dados_cli = {
                                    campo: texto_importacao(linha.get(coluna)) if coluna != "-- Não relacionar --" else ""
                                    for campo, coluna in mapeamento_clientes.items()
                                }
                                nome_cli = dados_cli.get("nome", "").strip()
                                if not nome_cli:
                                    ignorados_cli += 1
                                    continue
                                if not dados_cli.get("tipo"):
                                    dados_cli["tipo"] = "Cliente"
                                if not dados_cli.get("substituto_tributario"):
                                    dados_cli["substituto_tributario"] = "Não"

                                cnpj_cli = dados_cli.get("cnpj", "").strip()
                                documento_chave_cli = normalizar_documento_cliente(cnpj_cli)
                                if len(documento_chave_cli) not in (11, 14):
                                    ignorados_cli += 1
                                    continue
                                ids_existentes_cli = buscar_ids_cliente_por_documento(c_cli_imp, cnpj_cli)
                                existente_cli = {"id": ids_existentes_cli[0]} if len(ids_existentes_cli) == 1 else None
                                if len(ids_existentes_cli) > 1:
                                    ignorados_cli += 1
                                    continue

                                campos_cli = [
                                    campo for campo, coluna in mapeamento_clientes.items()
                                    if coluna != "-- Não relacionar --"
                                ]
                                if "tipo" not in campos_cli:
                                    campos_cli.append("tipo")
                                if "substituto_tributario" not in campos_cli:
                                    campos_cli.append("substituto_tributario")

                                if existente_cli and modo_clientes == "Ignorar cliente repetido":
                                    ignorados_cli += 1
                                elif existente_cli:
                                    atribuicoes_cli = ", ".join(f"{campo}=?" for campo in campos_cli)
                                    c_cli_imp.execute(
                                        f"UPDATE clientes SET {atribuicoes_cli} WHERE id=?",
                                        tuple(dados_cli.get(campo, "") for campo in campos_cli) + (existente_cli["id"],),
                                    )
                                    atualizados_cli += 1
                                else:
                                    if not dados_cli.get("codigo_cliente"):
                                        dados_cli["codigo_cliente"] = proximo_codigo_cliente(c_cli_imp)
                                    if "codigo_cliente" not in campos_cli:
                                        campos_cli.insert(0, "codigo_cliente")
                                    dados_cli["documento_chave"] = documento_chave_cli
                                    if "documento_chave" not in campos_cli:
                                        campos_cli.insert(1, "documento_chave")
                                    campos_novo_cli = campos_cli + ["redes_sociais", "funcionarios"]
                                    valores_novo_cli = [dados_cli.get(campo, "") for campo in campos_cli] + ["[]", "[]"]
                                    marcadores_cli = ",".join("?" for _ in campos_novo_cli)
                                    c_cli_imp.execute(
                                        f"INSERT INTO clientes ({','.join(campos_novo_cli)}) VALUES ({marcadores_cli})",
                                        tuple(valores_novo_cli),
                                    )
                                    novos_cli += 1
                            conn_cli_imp.commit()
                        except Exception as ex:
                            conn_cli_imp.rollback()
                            erro_cli = str(ex)
                        finally:
                            conn_cli_imp.close()

                        if erro_cli:
                            st.error(f"A importação foi cancelada sem alterar o banco: {erro_cli}")
                        else:
                            st.success(f"Importação concluída: {novos_cli} novos, {atualizados_cli} atualizados e {ignorados_cli} ignorados.")
                            st.rerun()
            elif cabecalhos_clientes:
                st.warning("A planilha não possui clientes abaixo do cabeçalho.")

    with aba4:
        st.subheader("Gerar contrato de suporte tecnológico")
        st.caption("O contrato de locação será adicionado quando o modelo jurídico correspondente estiver disponível.")
        clientes_suporte = buscar_clientes()
        nome_cliente_suporte = st.selectbox(
            "Cliente:", ["-- Selecionar --"] + [item.get("nome") or "" for item in clientes_suporte],
            key="suporte_contrato_cliente",
        )
        cliente_suporte = next((item for item in clientes_suporte if item.get("nome") == nome_cliente_suporte), None)
        if cliente_suporte:
            sc1, sc2, sc3 = st.columns(3)
            responsavel_suporte = sc1.text_input("Responsável legal:", value=cliente_suporte.get("contato") or "", key="suporte_responsavel")
            cpf_responsavel_suporte = sc2.text_input("CPF do responsável:", key="suporte_cpf_responsavel")
            data_suporte = sc3.date_input("Data de início:", value=date.today(), key="suporte_data")
            sc4, sc5, sc6 = st.columns(3)
            valor_suporte_num = sc4.number_input("Valor mensal R$:", min_value=0.0, step=0.01, format="%.2f", key="suporte_valor")
            dia_suporte = sc5.text_input("Dia do vencimento:", value=cliente_suporte.get("dia_vencimento") or "", key="suporte_vencimento")
            forma_suporte = sc6.selectbox("Forma de pagamento:", ["Boleto bancário", "PIX", "Transferência bancária"], key="suporte_pagamento")

            conn_clausulas_suporte = conectar_banco()
            c_clausulas_suporte = conn_clausulas_suporte.cursor()
            c_clausulas_suporte.execute("SELECT * FROM contrato_clausulas WHERE tipo_contrato='Suporte Tecnológico' ORDER BY id")
            clausulas_suporte = [dict(item) for item in c_clausulas_suporte.fetchall()]
            conn_clausulas_suporte.close()
            with st.expander("Biblioteca de cláusulas do suporte", expanded=False):
                with st.form("nova_clausula_suporte", clear_on_submit=True):
                    titulo_nova_suporte = st.text_input("Título da nova cláusula:")
                    texto_nova_suporte = st.text_area("Texto da nova cláusula:", height=120)
                    if st.form_submit_button("Salvar cláusula", type="primary", width="stretch"):
                        if titulo_nova_suporte.strip() and texto_nova_suporte.strip():
                            conn_ncs = conectar_banco(); cncs = conn_ncs.cursor()
                            cncs.execute(
                                """INSERT INTO contrato_clausulas
                                   (tipo_contrato, titulo, texto, ativo, criado_por, criado_em) VALUES (?,?,?,?,?,?)""",
                                ("Suporte Tecnológico", titulo_nova_suporte.strip(), texto_nova_suporte.strip(), "Sim",
                                 st.session_state.get("username", ""), datetime.now().strftime("%d/%m/%Y %H:%M")),
                            )
                            conn_ncs.commit(); conn_ncs.close(); st.success("Cláusula salva."); st.rerun()
                        else:
                            st.error("Informe título e texto.")
                if clausulas_suporte:
                    id_clausula_suporte = st.selectbox(
                        "Cláusula para editar/excluir:", ["-- Selecionar --"] + [f"{item['id']} - {item.get('titulo')}" for item in clausulas_suporte],
                        key="editar_clausula_suporte",
                    )
                    if id_clausula_suporte != "-- Selecionar --":
                        id_cs = int(id_clausula_suporte.split(" - ", 1)[0])
                        item_cs = next(item for item in clausulas_suporte if int(item.get("id")) == id_cs)
                        titulo_cs = st.text_input("Título:", value=item_cs.get("titulo") or "", key=f"titulo_cs_{id_cs}")
                        texto_cs = st.text_area("Texto:", value=item_cs.get("texto") or "", height=130, key=f"texto_cs_{id_cs}")
                        cs1, cs2 = st.columns(2)
                        if cs1.button("Salvar alteração", type="primary", width="stretch", key=f"salvar_cs_{id_cs}"):
                            conn_ecs = conectar_banco(); cecs = conn_ecs.cursor()
                            cecs.execute("UPDATE contrato_clausulas SET titulo=?, texto=?, alterado_por=?, alterado_em=? WHERE id=?",
                                         (titulo_cs.strip(), texto_cs.strip(), st.session_state.get("username", ""), datetime.now().strftime("%d/%m/%Y %H:%M"), id_cs))
                            conn_ecs.commit(); conn_ecs.close(); st.success("Cláusula atualizada."); st.rerun()
                        if cs2.button("Excluir cláusula", width="stretch", key=f"excluir_cs_{id_cs}"):
                            deletar_registro("contrato_clausulas", "id", id_cs); st.success("Cláusula excluída."); st.rerun()

            clausulas_suporte_ativas = [item for item in clausulas_suporte if (item.get("ativo") or "Sim") == "Sim"]
            opcoes_clausulas_suporte = [f"{item['id']} - {item.get('titulo')}" for item in clausulas_suporte_ativas]
            selecionadas_suporte = st.multiselect("Cláusulas adicionais:", opcoes_clausulas_suporte, default=opcoes_clausulas_suporte, key="clausulas_suporte_atual")
            clausulas_suporte_atual = []
            for opcao in selecionadas_suporte:
                id_item = int(opcao.split(" - ", 1)[0]); base_item = next(item for item in clausulas_suporte_ativas if int(item["id"]) == id_item)
                texto_item = st.text_area(base_item.get("titulo") or "Cláusula", value=base_item.get("texto") or "", height=100, key=f"texto_suporte_atual_{id_item}")
                clausulas_suporte_atual.append({"titulo": base_item.get("titulo") or "", "texto": texto_item})

            dados_suporte = {
                **dict(cliente_suporte), "responsavel_legal": responsavel_suporte, "cpf_responsavel": cpf_responsavel_suporte,
                "data_contrato": data_suporte.strftime("%d/%m/%Y"), "valor_contrato": formatar_moeda_br(valor_suporte_num),
                "dia_vencimento": dia_suporte, "forma_pagamento": forma_suporte, "clausulas": clausulas_suporte_atual,
            }
            faltantes_suporte = [rotulo for rotulo, valor in {
                "Nome": dados_suporte.get("nome"), "CPF/CNPJ": dados_suporte.get("cnpj"), "Endereço": dados_suporte.get("endereco"),
                "Responsável legal": responsavel_suporte, "CPF do responsável": cpf_responsavel_suporte,
                "Valor mensal": valor_suporte_num if valor_suporte_num > 0 else "", "Dia do vencimento": dia_suporte,
            }.items() if not str(valor or "").strip()]
            if faltantes_suporte:
                st.warning("Preencha antes de gerar: " + ", ".join(faltantes_suporte) + ".")
            if st.button("Gerar contrato de suporte", type="primary", width="stretch", disabled=bool(faltantes_suporte), key="gerar_suporte_cliente"):
                try:
                    pdf_suporte = gerar_contrato_pdf("Suporte Tecnológico", dados_suporte)
                    nome_suporte = re.sub(r"[^A-Za-z0-9_-]+", "_", nome_cliente_suporte).strip("_") or "cliente"
                    arquivo_suporte = f"Contrato_Suporte_{nome_suporte}.pdf"
                    conn_contrato = conectar_banco()
                    salvar_contrato_gerado(
                        conn_contrato, tipo="Suporte Tecnológico", parte_tipo="Cliente",
                        parte_id=cliente_suporte.get("id"), parte_nome=nome_cliente_suporte,
                        nome_arquivo=arquivo_suporte, arquivo=pdf_suporte,
                        valor=formatar_moeda_br(valor_suporte_num), inicio=data_suporte.strftime("%d/%m/%Y"),
                        criado_por=st.session_state.get("username", ""), criado_em=datetime.now().strftime("%d/%m/%Y %H:%M"),
                    )
                    conn_contrato.close()
                    st.session_state["contrato_suporte_gerado"] = {"dados": pdf_suporte, "nome": arquivo_suporte}
                    st.success("Contrato de suporte gerado.")
                except Exception as ex:
                    st.error(f"Não foi possível gerar o contrato: {ex}")
            if st.session_state.get("contrato_suporte_gerado"):
                st.download_button("Baixar contrato de suporte", data=st.session_state["contrato_suporte_gerado"]["dados"],
                                   file_name=st.session_state["contrato_suporte_gerado"]["nome"], mime="application/pdf",
                                   type="primary", width="stretch", key="baixar_suporte_cliente")
        else:
            st.info("Selecione um cliente para gerar o contrato.")


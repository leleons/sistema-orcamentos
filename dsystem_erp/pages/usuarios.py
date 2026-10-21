from __future__ import annotations

from dsystem_erp.app_context import aplicar_contexto_pagina
from dsystem_erp.services.usuarios import cpf_em_uso, cpf_usuario_valido, filtrar_usuarios
from dsystem_erp.ui_consulta import tabela_clicavel_id
from dsystem_erp.services.contratos_pj import eh_pj, tipos_contrato_funcionario, salvar_empresa_pj
from dsystem_erp.pages.funcionario_pj import campos_empresa_pj


def renderizar_gerenciador_usuarios(ctx: dict) -> None:
    aplicar_contexto_pagina(ctx, globals())
    st.title("Controle de Acessos")

    if (st.session_state.get("username") or "").strip().lower() == "daniel.fabio":
        with st.expander("Alterar minha senha de Administrador Master", expanded=False):
            senha_atual_master = st.text_input("Senha atual:", type="password", key="master_senha_atual")
            nova_senha_master = st.text_input("Nova senha:", type="password", key="master_nova_senha")
            confirma_senha_master = st.text_input("Confirmar nova senha:", type="password", key="master_confirma_senha")
            if st.button("Atualizar minha senha master", type="primary", width="stretch", key="btn_trocar_senha_master"):
                conn_master = conectar_banco()
                cmaster = conn_master.cursor()
                cmaster.execute("SELECT id, password FROM usuarios WHERE LOWER(username)=?", ("daniel.fabio",))
                usuario_master = cmaster.fetchone()
                if not usuario_master:
                    st.error("Usuário Daniel.fabio não encontrado.")
                elif not verificar_senha(senha_atual_master, usuario_master.get("password")):
                    st.error("Senha atual incorreta.")
                elif len(nova_senha_master or "") < 6:
                    st.error("A nova senha precisa ter pelo menos 6 caracteres.")
                elif nova_senha_master != confirma_senha_master:
                    st.error("A confirmação não confere com a nova senha.")
                else:
                    cmaster.execute(
                        "UPDATE usuarios SET password=? WHERE id=?",
                        (criar_hash_senha(nova_senha_master), usuario_master.get("id")),
                    )
                    conn_master.commit()
                    registrar_evento_sistema("senha_master_alterada", "usuarios", usuario_master.get("id"), "Daniel.fabio")
                    st.success("Senha do Administrador Master atualizada com sucesso.")
                conn_master.close()

    with st.expander("Criar Novo Usuário / Funcionário", expanded=True):
        st.subheader("Dados do Funcionário")
        f1, f2, f3 = st.columns(3)
        funcionario_nome = f1.text_input("Nome:")
        funcionario_cpf = f2.text_input("CPF:")
        funcionario_rj = f3.text_input("RG / identificação adicional:")

        f4, f5 = st.columns(2)
        funcionario_dados_bancarios = f4.text_area("Dados Bancários (Ag, conta, banco, pix):", height=90)
        funcionario_endereco = f5.text_area("Endereço:", height=90)

        f6, f7, f8 = st.columns(3)
        funcionario_telefone = f6.text_input("Telefone:")
        funcionario_email = f7.text_input("E-mail:")
        funcionario_tipo_contrato = f8.selectbox("Tipo de Contrato:", tipos_contrato_funcionario())
        empresa_pj_nova = campos_empresa_pj(st,funcionario_tipo_contrato,'novo_usuario')

        f9, f10 = st.columns(2)
        funcionario_forma_pagamento = f9.selectbox("Forma de pagamento:", ["PIX", "Transferência", "Boleto"])
        funcionario_emite_nf = f10.selectbox("Emite nota fiscal?", ["Não", "Sim"])
        funcionario_deslocamento = st.multiselect("Deslocamento:", ["Próprio", "Ônibus", "Metrô", "A pé"])

        st.subheader("Login e Acesso")
        u_nome = st.text_input("Login:")
        u_senha = st.text_input("Senha:", type="password")
        clientes_para_acesso = buscar_clientes(aplicar_permissao=False)
        nomes_empresas_acesso = [cli["nome"] for cli in clientes_para_acesso]
        empresas_permitidas_novo = st.multiselect(
            "Empresas que este funcionário pode acessar/alterar:",
            nomes_empresas_acesso,
            help="Deixe vazio para permitir todas as empresas.",
            key="novo_usuario_empresas",
        )
        st.write("Defina os módulos, submódulos e funções deste usuário:")
        p_adm = st.checkbox("Administrador", value=False, key="novo_usuario_admin")
        p_gerencial = st.checkbox(
            "Login gerencial — visualizar informações internas da Dsystem",
            value=False,
            key="novo_usuario_gerencial",
            help="Libera os cadastros e dados que pertencem à própria Dsystem.",
        )
        permissoes_novo_usuario = editor_permissoes("novo_usuario")
        flags_novo_usuario = flags_legadas(permissoes_novo_usuario)

        if st.button("Criar Usuário no Sistema", type="primary"):
            if not cpf_usuario_valido(funcionario_cpf):
                st.warning("Informe um CPF com 11 dígitos. Ele será o identificador único do funcionário.")
            elif u_nome and u_senha:
                conn = conectar_banco()
                c = conn.cursor()
                try:
                    c.execute("SELECT id, funcionario_cpf FROM usuarios")
                    if cpf_em_uso([dict(item) for item in c.fetchall()], funcionario_cpf):
                        st.error("Este CPF já pertence a outro usuário.")
                        st.stop()
                    c.execute('''INSERT INTO usuarios (username, password, is_admin, modulo_gerencial, perm_orcamentos, perm_os,
                                 perm_del_orc, perm_del_os, perm_edit_os, perm_emails, perm_edit_em,
                                 perm_del_em, perm_infra, perm_edit_infra, perm_del_infra, perm_clientes,
                                 perm_estoque, perm_faturamento, perm_atendimentos, perm_edit_atendimentos, submodulos, empresas_permitidas,
                                 funcionario_nome, funcionario_cpf, funcionario_rj, funcionario_dados_bancarios,
                                 funcionario_telefone, funcionario_email, funcionario_endereco,
                                 funcionario_tipo_contrato, funcionario_forma_pagamento, funcionario_emite_nf,
                                 funcionario_deslocamento)
                                 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                              (u_nome, criar_hash_senha(u_senha), int(p_adm), int(p_gerencial), flags_novo_usuario.get("perm_orcamentos", 0), flags_novo_usuario.get("perm_os", 0), flags_novo_usuario.get("perm_del_orc", 0), flags_novo_usuario.get("perm_del_os", 0),
                               flags_novo_usuario.get("perm_edit_os", 0), flags_novo_usuario.get("perm_emails", 0), flags_novo_usuario.get("perm_edit_em", 0), flags_novo_usuario.get("perm_del_em", 0), flags_novo_usuario.get("perm_infra", 0), flags_novo_usuario.get("perm_edit_infra", 0),
                               flags_novo_usuario.get("perm_del_infra", 0), flags_novo_usuario.get("perm_clientes", 0), flags_novo_usuario.get("perm_estoque", 0), flags_novo_usuario.get("perm_faturamento", 0), flags_novo_usuario.get("perm_atendimentos", 0), flags_novo_usuario.get("perm_edit_atendimentos", 0), json.dumps(sorted(permissoes_novo_usuario), ensure_ascii=False), json.dumps(empresas_permitidas_novo, ensure_ascii=False),
                               funcionario_nome, funcionario_cpf, funcionario_rj, funcionario_dados_bancarios,
                               funcionario_telefone, funcionario_email, funcionario_endereco,
                               funcionario_tipo_contrato, funcionario_forma_pagamento, funcionario_emite_nf,
                               json.dumps(funcionario_deslocamento, ensure_ascii=False)))
                    salvar_empresa_pj(c, c.lastrowid, empresa_pj_nova)
                    conn.commit()
                    st.success(f"Usuário {u_nome} criado!")
                    st.rerun()
                except mysql.connector.IntegrityError: 
                    st.error("O login já existe no sistema.")
                finally:
                    conn.close()
            else: 
                st.warning("Login e Senha são obrigatórios.")

    st.subheader("Base de Usuários Ativos")
    conn = conectar_banco()
    conn.row_factory = None
    c = conn.cursor()
    c.execute('SELECT id, username, funcionario_nome, funcionario_cpf, funcionario_telefone, funcionario_email, funcionario_tipo_contrato, modulo_gerencial, is_admin FROM usuarios ORDER BY id ASC')
    u_rows = c.fetchall()
    conn.close()

    if u_rows: 
        usuarios_view = [dict(u) for u in u_rows]
        pesquisa_usuario = st.text_input(
            "Pesquisar usuário por nome, CPF ou login:",
            key="pesquisa_base_usuarios",
            placeholder="Ex.: Maria, 123.456.789-00 ou maria.silva",
        )
        usuarios_view = filtrar_usuarios(usuarios_view, pesquisa_usuario)
        st.caption(f"{len(usuarios_view)} usuário(s) encontrado(s).")
        id_usuario_clicado = tabela_clicavel_id(st, usuarios_view, "usuarios_grade_consulta", "id")
        if id_usuario_clicado is not None:
            st.session_state["usuario_edicao_selecionado"] = int(id_usuario_clicado)
        id_usuario_selecionado = st.session_state.get("usuario_edicao_selecionado")
        ids_usuarios_visiveis = {int(item.get("id") or 0) for item in usuarios_view}
        if pesquisa_usuario.strip() and int(id_usuario_selecionado or 0) not in ids_usuarios_visiveis:
            st.session_state.pop("usuario_edicao_selecionado", None)
            id_usuario_selecionado = None
        st.caption("Clique em qualquer informação da linha para abrir automaticamente a edição.")

        with st.expander("Gerar contrato do funcionário", expanded=False):
            conn_contrato_func = conectar_banco()
            c_contrato_func = conn_contrato_func.cursor()
            c_contrato_func.execute("SELECT * FROM usuarios ORDER BY funcionario_nome, username")
            usuarios_contrato = [dict(usuario) for usuario in c_contrato_func.fetchall()]
            conn_contrato_func.close()

            opcoes_funcionarios = ["-- Selecionar --"] + [
                f"{usuario.get('id')} - {usuario.get('funcionario_nome') or usuario.get('username')}"
                for usuario in usuarios_contrato
            ]
            funcionario_escolhido = st.selectbox("Funcionário:", opcoes_funcionarios, key="contrato_funcionario")
            funcionario_contrato = None
            if funcionario_escolhido != "-- Selecionar --":
                funcionario_id_contrato = int(funcionario_escolhido.split(" - ", 1)[0])
                funcionario_contrato = next((usuario for usuario in usuarios_contrato if int(usuario.get("id") or 0) == funcionario_id_contrato), None)

            if funcionario_contrato:
                tipo_cadastrado = funcionario_contrato.get("funcionario_tipo_contrato") or ""
                tipo_modelo_funcionario = "Corporativo CLT" if tipo_cadastrado == "CLT" else "Estágio" if tipo_cadastrado == "Estágio" else ""
                st.info(
                    f"**Tipo cadastrado:** {tipo_cadastrado or 'não informado'}  \n"
                    f"**CPF:** {funcionario_contrato.get('funcionario_cpf') or 'não informado'}  \n"
                    f"**Contato:** {funcionario_contrato.get('funcionario_telefone') or 'não informado'} | "
                    f"{funcionario_contrato.get('funcionario_email') or 'não informado'}"
                )

                if eh_pj(tipo_cadastrado):
                    from dsystem_erp.pages.contratos_gerar import renderizar_gerador
                    renderizar_gerador(ctx, prestador_pj=funcionario_contrato)
                elif not tipo_modelo_funcionario:
                    st.warning("O fluxo da empresa utiliza PJ ou Estágio. Confira o tipo do cadastro antes de gerar o contrato.")
                else:
                    conn_clausulas = conectar_banco()
                    c_clausulas = conn_clausulas.cursor()
                    c_clausulas.execute(
                        "SELECT * FROM contrato_clausulas WHERE tipo_contrato=? ORDER BY id",
                        (tipo_modelo_funcionario,),
                    )
                    clausulas_salvas = [dict(item) for item in c_clausulas.fetchall()]
                    conn_clausulas.close()

                    with st.expander("Biblioteca de cláusulas", expanded=False):
                        st.caption("As cláusulas salvas ficam disponíveis nos próximos contratos deste mesmo tipo.")
                        with st.form(f"form_nova_clausula_{tipo_modelo_funcionario}", clear_on_submit=True):
                            nova_clausula_titulo = st.text_input("Título da nova cláusula:")
                            nova_clausula_texto = st.text_area("Texto da nova cláusula:", height=130)
                            if st.form_submit_button("Salvar nova cláusula", type="primary", width="stretch"):
                                if not nova_clausula_titulo.strip() or not nova_clausula_texto.strip():
                                    st.error("Informe título e texto da cláusula.")
                                else:
                                    agora_clausula = datetime.now().strftime("%d/%m/%Y %H:%M")
                                    usuario_clausula = st.session_state.get("username", "")
                                    conn_nova_clausula = conectar_banco()
                                    c_nova_clausula = conn_nova_clausula.cursor()
                                    c_nova_clausula.execute(
                                        """INSERT INTO contrato_clausulas
                                           (tipo_contrato, titulo, texto, ativo, criado_por, criado_em)
                                           VALUES (?,?,?,?,?,?)""",
                                        (tipo_modelo_funcionario, nova_clausula_titulo.strip(), nova_clausula_texto.strip(),
                                         "Sim", usuario_clausula, agora_clausula),
                                    )
                                    conn_nova_clausula.commit()
                                    conn_nova_clausula.close()
                                    st.success("Cláusula salva para os próximos contratos.")
                                    st.rerun()

                        if clausulas_salvas:
                            opcoes_editar_clausula = ["-- Selecionar --"] + [
                                f"{item.get('id')} - {item.get('titulo')}" for item in clausulas_salvas
                            ]
                            clausula_edicao_escolhida = st.selectbox(
                                "Editar cláusula salva:", opcoes_editar_clausula,
                                key=f"editar_clausula_salva_{tipo_modelo_funcionario}",
                            )
                            if clausula_edicao_escolhida != "-- Selecionar --":
                                clausula_edicao_id = int(clausula_edicao_escolhida.split(" - ", 1)[0])
                                clausula_edicao = next(
                                    item for item in clausulas_salvas if int(item.get("id") or 0) == clausula_edicao_id
                                )
                                edit_clausula_titulo = st.text_input(
                                    "Título:", value=clausula_edicao.get("titulo") or "",
                                    key=f"edit_clausula_titulo_{clausula_edicao_id}",
                                )
                                edit_clausula_texto = st.text_area(
                                    "Texto:", value=clausula_edicao.get("texto") or "", height=150,
                                    key=f"edit_clausula_texto_{clausula_edicao_id}",
                                )
                                edit_clausula_ativa = st.checkbox(
                                    "Disponível para novos contratos",
                                    value=(clausula_edicao.get("ativo") or "Sim") == "Sim",
                                    key=f"edit_clausula_ativa_{clausula_edicao_id}",
                                )
                                ec1, ec2 = st.columns(2)
                                if ec1.button("Salvar alteração", type="primary", width="stretch", key=f"salvar_clausula_{clausula_edicao_id}"):
                                    conn_edit_clausula = conectar_banco()
                                    c_edit_clausula = conn_edit_clausula.cursor()
                                    c_edit_clausula.execute(
                                        """UPDATE contrato_clausulas SET titulo=?, texto=?, ativo=?,
                                           alterado_por=?, alterado_em=? WHERE id=?""",
                                        (edit_clausula_titulo.strip(), edit_clausula_texto.strip(),
                                         "Sim" if edit_clausula_ativa else "Não",
                                         st.session_state.get("username", ""),
                                         datetime.now().strftime("%d/%m/%Y %H:%M"), clausula_edicao_id),
                                    )
                                    conn_edit_clausula.commit()
                                    conn_edit_clausula.close()
                                    st.success("Cláusula atualizada.")
                                    st.rerun()
                                if ec2.button("Excluir cláusula", width="stretch", key=f"excluir_clausula_{clausula_edicao_id}"):
                                    deletar_registro("contrato_clausulas", "id", clausula_edicao_id)
                                    st.success("Cláusula excluída.")
                                    st.rerun()
                        else:
                            st.info("Nenhuma cláusula adicional salva para este tipo de contrato.")

                    clausulas_disponiveis = [item for item in clausulas_salvas if (item.get("ativo") or "Sim") == "Sim"]
                    titulos_clausulas = [f"{item.get('id')} - {item.get('titulo')}" for item in clausulas_disponiveis]
                    clausulas_selecionadas = st.multiselect(
                        "Cláusulas adicionais deste contrato:",
                        titulos_clausulas,
                        default=titulos_clausulas,
                        help="Desmarque uma cláusula para não incluí-la somente neste contrato.",
                        key=f"clausulas_contrato_{funcionario_contrato.get('id')}_{tipo_modelo_funcionario}",
                    )
                    clausulas_contrato_editadas = []
                    if clausulas_selecionadas:
                        st.caption("Você pode editar os textos abaixo somente para este contrato. As cláusulas salvas não serão alteradas.")
                        for opcao_clausula in clausulas_selecionadas:
                            clausula_id = int(opcao_clausula.split(" - ", 1)[0])
                            clausula_base = next(item for item in clausulas_disponiveis if int(item.get("id") or 0) == clausula_id)
                            texto_contrato = st.text_area(
                                clausula_base.get("titulo") or "Cláusula",
                                value=clausula_base.get("texto") or "",
                                height=120,
                                key=f"texto_clausula_contrato_{funcionario_contrato.get('id')}_{clausula_id}",
                            )
                            clausulas_contrato_editadas.append({
                                "titulo": clausula_base.get("titulo") or "",
                                "texto": texto_contrato,
                            })

                    cf1, cf2, cf3 = st.columns(3)
                    rg_funcionario = cf1.text_input("RG:", key="contrato_func_rg")
                    cargo_funcionario = cf2.text_input("Cargo / função:", key="contrato_func_cargo")
                    data_contrato_funcionario = cf3.date_input("Data do contrato:", value=date.today(), key="contrato_func_data")
                    from dsystem_erp.pages.contratos_gerar import escolher_data_assinatura
                    data_assinatura_funcionario = escolher_data_assinatura(st, data_contrato_funcionario, f"contrato_func_{funcionario_contrato['id']}")

                    salario_funcionario = 0.0
                    instituicao_funcionario = ""
                    curso_funcionario = ""
                    jornada_funcionario = ""
                    if tipo_modelo_funcionario == "Corporativo CLT":
                        salario_funcionario = st.number_input(
                            "Salário R$:", min_value=0.0, step=0.01, format="%.2f", key="contrato_func_salario"
                        )
                    else:
                        ce1, ce2, ce3 = st.columns(3)
                        instituicao_funcionario = ce1.text_input("Instituição de ensino:", key="contrato_func_instituicao")
                        curso_funcionario = ce2.text_input("Curso:", key="contrato_func_curso")
                        jornada_funcionario = ce3.selectbox(
                            "Jornada:",
                            ["20 horas semanais (4h/dia)", "30 horas semanais (6h/dia)"],
                            key="contrato_func_jornada",
                        )

                    dados_contrato_funcionario = {
                        "nome": funcionario_contrato.get("funcionario_nome") or funcionario_contrato.get("username"),
                        "cnpj": funcionario_contrato.get("funcionario_cpf") or "",
                        "rg_mei": rg_funcionario,
                        "endereco": funcionario_contrato.get("funcionario_endereco") or "",
                        "numero": "", "complemento": "", "bairro": "", "cidade_estado": "", "cep": "",
                        "telefone": funcionario_contrato.get("funcionario_telefone") or "",
                        "email": funcionario_contrato.get("funcionario_email") or "",
                        "data_contrato": data_contrato_funcionario.strftime("%d/%m/%Y"),
                        "data_assinatura": data_assinatura_funcionario.strftime("%d/%m/%Y"),
                        "cargo": cargo_funcionario,
                        "valor_contrato": formatar_moeda_br(salario_funcionario) if salario_funcionario > 0 else "",
                        "instituicao_ensino": instituicao_funcionario,
                        "curso": curso_funcionario,
                        "jornada": jornada_funcionario,
                        "clausulas": clausulas_contrato_editadas,
                    }
                    obrigatorios_funcionario = {
                        "Nome": dados_contrato_funcionario["nome"],
                        "CPF": dados_contrato_funcionario["cnpj"],
                        "RG": rg_funcionario,
                        "Endereço": dados_contrato_funcionario["endereco"],
                        "Telefone": dados_contrato_funcionario["telefone"],
                        "E-mail": dados_contrato_funcionario["email"],
                    }
                    if tipo_modelo_funcionario == "Corporativo CLT":
                        obrigatorios_funcionario.update({
                            "Cargo / função": cargo_funcionario,
                            "Salário": salario_funcionario if salario_funcionario > 0 else "",
                        })
                    else:
                        obrigatorios_funcionario.update({
                            "Instituição de ensino": instituicao_funcionario,
                            "Curso": curso_funcionario,
                            "Jornada": jornada_funcionario,
                        })

                    faltantes_funcionario = [
                        rotulo for rotulo, valor in obrigatorios_funcionario.items() if not str(valor or "").strip()
                    ]
                    if faltantes_funcionario:
                        st.warning("Preencha antes de gerar: " + ", ".join(faltantes_funcionario) + ".")

                    if st.button(
                        "Gerar contrato do funcionário",
                        type="primary",
                        width="stretch",
                        disabled=bool(faltantes_funcionario),
                        key="btn_gerar_contrato_funcionario",
                    ):
                        try:
                            bytes_contrato_funcionario = gerar_contrato_pdf(tipo_modelo_funcionario, dados_contrato_funcionario)
                            from dsystem_erp.services.contratos_word import gerar_contrato_word, nome_word, MIME_WORD
                            word_contrato_funcionario = gerar_contrato_word(tipo_modelo_funcionario, dados_contrato_funcionario, pdf=bytes_contrato_funcionario)
                            nome_funcionario_limpo = re.sub(
                                r"[^A-Za-z0-9_-]+", "_", dados_contrato_funcionario["nome"]
                            ).strip("_") or "funcionario"
                            arquivo_contrato_funcionario = f"{tipo_modelo_funcionario.replace(' ', '_')}_{nome_funcionario_limpo}.pdf"
                            conn_contrato_func = conectar_banco()
                            salvar_contrato_gerado(
                                conn_contrato_func, tipo=tipo_modelo_funcionario, parte_tipo="Funcionário",
                                parte_id=funcionario_contrato.get("id"), parte_nome=dados_contrato_funcionario["nome"],
                                nome_arquivo=arquivo_contrato_funcionario, arquivo=bytes_contrato_funcionario,
                                arquivo_word=word_contrato_funcionario, nome_arquivo_word=nome_word(arquivo_contrato_funcionario),
                                valor=dados_contrato_funcionario.get("valor_contrato") or "",
                                inicio=dados_contrato_funcionario.get("data_contrato") or "",
                                criado_por=st.session_state.get("username", ""), criado_em=datetime.now().strftime("%d/%m/%Y %H:%M"),
                            )
                            conn_contrato_func.close()
                            st.session_state["contrato_funcionario_gerado"] = {
                                "dados": bytes_contrato_funcionario,
                                "nome": arquivo_contrato_funcionario,
                                "word": word_contrato_funcionario,
                                "formulario": dict(dados_contrato_funcionario),
                                "funcionario_id": funcionario_contrato['id'],
                            }
                            st.success("Contrato do funcionário gerado com sucesso.")
                        except Exception as ex:
                            st.error(f"Não foi possível gerar o contrato: {ex}")

                    contrato_funcionario_gerado = st.session_state.get("contrato_funcionario_gerado")
                    if (contrato_funcionario_gerado
                        and contrato_funcionario_gerado.get('formulario') == dados_contrato_funcionario
                        and contrato_funcionario_gerado.get('funcionario_id') == funcionario_contrato['id']):
                        st.download_button(
                            "Baixar contrato do funcionário em PDF",
                            data=contrato_funcionario_gerado["dados"],
                            file_name=contrato_funcionario_gerado["nome"],
                            mime="application/pdf",
                            type="primary",
                            width="stretch",
                            key="download_contrato_funcionario",
                        )
                        if contrato_funcionario_gerado.get('word'):
                            from dsystem_erp.services.contratos_word import nome_word, MIME_WORD
                            st.download_button('Baixar contrato do funcionário em Word (.docx)',
                                contrato_funcionario_gerado['word'], file_name=nome_word(contrato_funcionario_gerado['nome']),
                                mime=MIME_WORD, key='download_contrato_funcionario_word')

        st.write("---")
        act_u = st.radio("Ação (Usuários):", ["Editar Usuário", "Excluir Usuário"], horizontal=True)
        if id_usuario_selecionado:
            act_u = "Editar Usuário"

        if act_u == "Excluir Usuário":
            id_del_u = st.number_input("ID Usuário para excluir", min_value=1, step=1, key="del_u_id")
            if st.button("Excluir Permanentemente", key="btn_del_user"):
                conn = conectar_banco()
                conn.row_factory = None
                c = conn.cursor()
                c.execute('SELECT is_admin FROM usuarios WHERE id=?', (id_del_u,))
                ud = c.fetchone()
                if ud and ud['is_admin']: 
                    st.error("Proteção de Segurança: Não pode excluir o Admin Master.")
                else: 
                    c.execute('DELETE FROM usuarios WHERE id=?', (id_del_u,))
                    conn.commit()
                    st.success("Usuário Removido.")
                    st.rerun()
                conn.close()
            
        elif act_u == "Editar Usuário":
            if not id_usuario_selecionado:
                st.info("Clique em um usuário na tabela para editar seus dados e permissões.")
            id_ed_u = int(id_usuario_selecionado or 0)
            conn = conectar_banco()
            conn.row_factory = None
            c = conn.cursor()
            c.execute('SELECT * FROM usuarios WHERE id=?', (id_ed_u,))
            ud = c.fetchone()
            conn.close()

            if ud:
                ud = dict(ud)
                if ud['is_admin']: 
                    st.error("Permissões do Admin Master não podem ser limitadas.")
                else:
                    with st.expander(f"Editando permissões de: {ud['username']}", expanded=True):
                        st.subheader("Dados do Funcionário")
                        ef1, ef2, ef3 = st.columns(3)
                        e_funcionario_nome = ef1.text_input("Nome:", value=ud.get("funcionario_nome") or "", key=f"ef_nome_{id_ed_u}")
                        e_funcionario_cpf = ef2.text_input("CPF:", value=ud.get("funcionario_cpf") or "", key=f"ef_cpf_{id_ed_u}")
                        e_funcionario_rj = ef3.text_input("RG / identificação adicional:", value=ud.get("funcionario_rj") or "", key=f"ef_rj_{id_ed_u}")

                        ef4, ef5 = st.columns(2)
                        e_funcionario_dados_bancarios = ef4.text_area("Dados Bancários (Ag, conta, banco, pix):", value=ud.get("funcionario_dados_bancarios") or "", height=90, key=f"ef_banco_{id_ed_u}")
                        e_funcionario_endereco = ef5.text_area("Endereço:", value=ud.get("funcionario_endereco") or "", height=90, key=f"ef_end_{id_ed_u}")

                        ef6, ef7, ef8 = st.columns(3)
                        e_funcionario_telefone = ef6.text_input("Telefone:", value=ud.get("funcionario_telefone") or "", key=f"ef_tel_{id_ed_u}")
                        e_funcionario_email = ef7.text_input("E-mail:", value=ud.get("funcionario_email") or "", key=f"ef_email_{id_ed_u}")
                        tipo_atual = ud.get("funcionario_tipo_contrato") or "PJ"
                        tipos_contrato = tipos_contrato_funcionario(tipo_atual)
                        e_funcionario_tipo_contrato = ef8.selectbox("Tipo de Contrato:", tipos_contrato, index=tipos_contrato.index(tipo_atual) if tipo_atual in tipos_contrato else 1, key=f"ef_tipo_{id_ed_u}")
                        empresa_pj_edicao = campos_empresa_pj(st,e_funcionario_tipo_contrato,f'edit_usuario_{id_ed_u}',ud)

                        ef9, ef10 = st.columns(2)
                        formas_pagamento = ["PIX", "Transferência", "Boleto"]
                        forma_atual = ud.get("funcionario_forma_pagamento") or "PIX"
                        e_funcionario_forma_pagamento = ef9.selectbox("Forma de pagamento:", formas_pagamento, index=formas_pagamento.index(forma_atual) if forma_atual in formas_pagamento else 0, key=f"ef_forma_{id_ed_u}")
                        emite_atual = ud.get("funcionario_emite_nf") or "Não"
                        e_funcionario_emite_nf = ef10.selectbox("Emite nota fiscal?", ["Não", "Sim"], index=1 if emite_atual == "Sim" else 0, key=f"ef_nf_{id_ed_u}")
                        deslocamentos_opcoes = ["Próprio", "Ônibus", "Metrô", "A pé"]
                        deslocamentos_atuais = [d for d in carregar_submodulos(ud.get("funcionario_deslocamento")) if d in deslocamentos_opcoes]
                        e_funcionario_deslocamento = st.multiselect("Deslocamento:", deslocamentos_opcoes, default=deslocamentos_atuais, key=f"ef_desloc_{id_ed_u}")

                        st.subheader("Login e Permissões")
                        eu_n = st.text_input("Login:", value=ud['username'], key=f"eu_n_{id_ed_u}")
                        eu_s = st.text_input("Nova senha (deixe em branco para manter):", type="password", key=f"eu_s_{id_ed_u}")
                        e_modulo_gerencial = st.checkbox(
                            "Login gerencial — visualizar informações internas da Dsystem",
                            value=bool(ud.get("modulo_gerencial", 0)),
                            key=f"eu_gerencial_{id_ed_u}",
                            help="Libera os cadastros e dados que pertencem à própria Dsystem.",
                        )
                        clientes_para_acesso_edit = buscar_clientes(aplicar_permissao=False)
                        nomes_empresas_acesso_edit = [cli["nome"] for cli in clientes_para_acesso_edit]
                        empresas_atuais = [empresa for empresa in carregar_submodulos(ud.get("empresas_permitidas")) if empresa in nomes_empresas_acesso_edit]
                        e_empresas_permitidas = st.multiselect(
                            "Empresas que este funcionário pode acessar/alterar:",
                            nomes_empresas_acesso_edit,
                            default=empresas_atuais,
                            help="Deixe vazio para permitir todas as empresas.",
                            key=f"edit_usuario_empresas_{id_ed_u}",
                        )
                        permissoes_usuario = editor_permissoes(f"edit_usuario_{id_ed_u}", ud)
                        flags_usuario = flags_legadas(permissoes_usuario)
                            
                        if st.button("Guardar Edição de Usuário", type="primary", key=f"btn_save_u_{id_ed_u}"):
                            conn = conectar_banco()
                            c = conn.cursor()
                            c.execute("SELECT id, funcionario_cpf FROM usuarios")
                            usuarios_cpf = [dict(item) for item in c.fetchall()]
                            if not cpf_usuario_valido(e_funcionario_cpf):
                                conn.close()
                                st.error("Informe um CPF com 11 dígitos. Ele é o identificador único do funcionário.")
                                st.stop()
                            if cpf_em_uso(usuarios_cpf, e_funcionario_cpf, ignorar_id=id_ed_u):
                                conn.close()
                                st.error("Este CPF já pertence a outro usuário.")
                                st.stop()
                            senha_para_salvar = criar_hash_senha(eu_s) if eu_s else ud["password"]
                            c.execute('''UPDATE usuarios SET username=?, password=?, modulo_gerencial=?, perm_orcamentos=?, perm_del_orc=?, perm_infra=?, perm_edit_infra=?, perm_os=?, perm_edit_os=?, perm_del_os=?, perm_del_infra=?, perm_emails=?, perm_edit_em=?, perm_del_em=?, perm_clientes=?, perm_estoque=?, perm_faturamento=?, perm_atendimentos=?, perm_edit_atendimentos=?, submodulos=?, empresas_permitidas=?, funcionario_nome=?, funcionario_cpf=?, funcionario_rj=?, funcionario_dados_bancarios=?, funcionario_telefone=?, funcionario_email=?, funcionario_endereco=?, funcionario_tipo_contrato=?, funcionario_forma_pagamento=?, funcionario_emite_nf=?, funcionario_deslocamento=? WHERE id=?''', (eu_n, senha_para_salvar, int(e_modulo_gerencial), flags_usuario.get("perm_orcamentos", 0), flags_usuario.get("perm_del_orc", 0), flags_usuario.get("perm_infra", 0), flags_usuario.get("perm_edit_infra", 0), flags_usuario.get("perm_os", 0), flags_usuario.get("perm_edit_os", 0), flags_usuario.get("perm_del_os", 0), flags_usuario.get("perm_del_infra", 0), flags_usuario.get("perm_emails", 0), flags_usuario.get("perm_edit_em", 0), flags_usuario.get("perm_del_em", 0), flags_usuario.get("perm_clientes", 0), flags_usuario.get("perm_estoque", 0), flags_usuario.get("perm_faturamento", 0), flags_usuario.get("perm_atendimentos", 0), flags_usuario.get("perm_edit_atendimentos", 0), json.dumps(sorted(permissoes_usuario), ensure_ascii=False), json.dumps(e_empresas_permitidas, ensure_ascii=False), e_funcionario_nome, e_funcionario_cpf, e_funcionario_rj, e_funcionario_dados_bancarios, e_funcionario_telefone, e_funcionario_email, e_funcionario_endereco, e_funcionario_tipo_contrato, e_funcionario_forma_pagamento, e_funcionario_emite_nf, json.dumps(e_funcionario_deslocamento, ensure_ascii=False), id_ed_u))
                            salvar_empresa_pj(c,id_ed_u,empresa_pj_edicao)
                            conn.commit()
                            conn.close()
                            if (st.session_state.get("username") or "") == (ud.get("username") or ""):
                                st.session_state["username"] = eu_n
                                st.session_state["modulo_gerencial"] = int(e_modulo_gerencial)
                                st.session_state["submodulos"] = json.dumps(sorted(permissoes_usuario), ensure_ascii=False)
                                for nome_flag, valor_flag in flags_usuario.items():
                                    st.session_state[nome_flag] = valor_flag
                            st.success("Permissões atualizadas com sucesso!")
                            st.rerun()
    else:
        st.info("Nenhum usuário encontrado no banco de dados.")


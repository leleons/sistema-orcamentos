"""Tela e fluxo de autenticação de usuários e clientes."""

from __future__ import annotations

from dsystem_erp.app_context import aplicar_contexto_pagina
from dsystem_erp.services.session import preencher_sessao


def renderizar_login(ctx) -> None:
    aplicar_contexto_pagina(ctx, globals())

    usuario_troca = st.session_state.get("usuario_troca_senha_pendente")
    if usuario_troca:
        exibir_logo_dsystem("190")
        st.title("Definir nova senha")
        st.info(
            f"Primeiro acesso do usuário {usuario_troca.get('username')}. "
            "Troque a senha temporária para continuar."
        )
        nova_senha = st.text_input("Nova senha:", type="password", key="usuario_nova_senha")
        confirmar_nova = st.text_input(
            "Confirmar nova senha:", type="password", key="usuario_confirmar_nova_senha"
        )
        if st.button("Salvar nova senha e entrar", type="primary", width="stretch"):
            if len(nova_senha) < 6:
                st.error("A nova senha precisa ter pelo menos 6 caracteres.")
            elif nova_senha != confirmar_nova:
                st.error("As senhas não conferem.")
            elif nova_senha == "1234":
                st.error("Escolha uma senha diferente da senha temporária.")
            else:
                conn_troca = conectar_banco()
                cursor_troca = conn_troca.cursor()
                cursor_troca.execute(
                    "UPDATE usuarios SET password=?, trocar_senha=0 WHERE id=?",
                    (criar_hash_senha(nova_senha), usuario_troca.get("id")),
                )
                conn_troca.commit()
                conn_troca.close()
                preencher_sessao(st.session_state, usuario_troca)
                st.session_state["trocar_senha"] = 0
                st.session_state["autenticado"] = True
                st.session_state.pop("usuario_troca_senha_pendente", None)
                registrar_evento_sistema(
                    "update",
                    "usuarios",
                    usuario_troca.get("id"),
                    "",
                    {"evento": "Senha temporária alterada"},
                )
                st.rerun()
        return

    cliente_pendente = st.session_state.get("cliente_login_pendente")
    if cliente_pendente:
        exibir_logo_dsystem("190")
        if int(cliente_pendente.get("portal_trocar_senha") or 0) or not int(
            cliente_pendente.get("portal_2fa_ativo") or 0
        ):
            renderizar_primeiro_acesso_cliente(cliente_pendente)
        else:
            renderizar_2fa_cliente(cliente_pendente)
        return

    exibir_logo_dsystem("210")
    st.title("Acesso ao Sistema Dsystem ERP")
    with st.container():
        user = st.text_input("Usuário")
        password = st.text_input("Senha", type="password")

        if not st.button("Entrar no Sistema", type="primary"):
            return

        conn = conectar_banco()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM usuarios WHERE username=%s", (user,))
        usuario = cursor.fetchone()

        if usuario is not None and verificar_senha(password, usuario.get("password", "")):
            if not senha_esta_com_hash(usuario.get("password", "")):
                cursor.execute(
                    "UPDATE usuarios SET password=%s WHERE id=%s",
                    (criar_hash_senha(password), usuario["id"]),
                )
                conn.commit()
                usuario["password"] = ""
            if int(usuario.get("trocar_senha") or 0):
                conn.close()
                st.session_state["usuario_troca_senha_pendente"] = dict(usuario)
                st.rerun()
                return
            conn.close()
            preencher_sessao(st.session_state, usuario)
            st.session_state["autenticado"] = True
            registrar_tentativa_login(user, "usuario", True, "Login do sistema autorizado")
            registrar_evento_sistema(
                "insert", "sistema", usuario.get("id"), "", {"evento": "Entrada no sistema"}
            )
            st.rerun()
            return

        usuario_portal_busca = user.strip().lower()
        documento_login = normalizar_documento_cliente(user)
        if len(documento_login) in (11, 14):
            usuario_portal_busca = documento_login
        cursor.execute("SELECT * FROM clientes WHERE LOWER(portal_username)=%s", (usuario_portal_busca,))
        cliente = cursor.fetchone()
        if cliente is None:
            cursor.execute(
                """SELECT p.id AS portal_conta_id, p.username, p.nome AS portal_usuario_nome,
                          p.tipo AS portal_tipo_usuario, p.password AS conta_password,
                          p.trocar_senha, p.twofa_secret, p.twofa_ativo, c.*
                   FROM clientes_portal_usuarios p
                   INNER JOIN clientes c ON c.id=p.cliente_id
                   WHERE LOWER(p.username)=%s AND p.ativo=1 LIMIT 1""",
                (usuario_portal_busca,),
            )
            conta_funcionario = cursor.fetchone()
            if conta_funcionario is not None:
                cliente = dict(conta_funcionario)
                cliente["portal_username"] = conta_funcionario.get("username")
                cliente["portal_password"] = conta_funcionario.get("conta_password")
                cliente["portal_trocar_senha"] = conta_funcionario.get("trocar_senha")
                cliente["portal_2fa_secret"] = conta_funcionario.get("twofa_secret")
                cliente["portal_2fa_ativo"] = conta_funcionario.get("twofa_ativo")

        if cliente is not None and verificar_senha(password, cliente.get("portal_password", "")):
            if not senha_esta_com_hash(cliente.get("portal_password", "")):
                if cliente.get("portal_conta_id"):
                    cursor.execute(
                        "UPDATE clientes_portal_usuarios SET password=%s WHERE id=%s",
                        (criar_hash_senha(password), cliente["portal_conta_id"]),
                    )
                else:
                    cursor.execute(
                        "UPDATE clientes SET portal_password=%s WHERE id=%s",
                        (criar_hash_senha(password), cliente["id"]),
                    )
                conn.commit()
                cliente["portal_trocar_senha"] = 1
            conn.close()
            registrar_tentativa_login(user, "cliente", True, "Login do portal autorizado")
            st.session_state["cliente_login_pendente"] = dict(cliente)
            st.rerun()
            return

        if cliente is not None:
            registrar_acesso_cliente(cliente, "senha_invalida")
        registrar_tentativa_login(
            user,
            "usuario" if usuario is not None else "cliente",
            False,
            "Usuário ou senha incorretos",
        )
        conn.close()
        st.error("Usuário ou senha incorretos.")

from __future__ import annotations

import json

from dsystem_erp.app_context import aplicar_contexto_pagina
from dsystem_erp.migrations import garantir_coluna
from dsystem_erp.ui_consulta import tabela_clicavel_id


COLUNAS_INFRA_ACESSO_REMOTO = (
    "serv_anydesk", "serv_radmin", "serv_google_remote",
    "serv_info_gerais", "impressoras_acessos",
)


# Alguns blocos antigos são armazenados em uma única coluna por compatibilidade
# com o banco existente. Esta definição permite apresentá-los como formulários
# de verdade, sem obrigar o usuário a editar a linha serializada manualmente.
CAMPOS_COMPOSTOS_INFRA = {
    "faixas_ip": [
        {"chave": "faixa", "rotulo": "Faixa de IP", "marcador": "Faixa"},
        {"chave": "informacao", "rotulo": "Informação da faixa", "marcador": "Informação", "multilinha": True},
    ],
    "dvr_acessos": [
        {"chave": "nome", "rotulo": "DVR / Nome", "marcador": "Nome", "posicional": True},
        {"chave": "serial", "rotulo": "Serial", "marcador": "Serial"},
        {"chave": "ip", "rotulo": "IP / DDNS", "marcador": "IP/DDNS"},
        {"chave": "porta", "rotulo": "Porta de serviço", "marcador": "Porta serviço"},
        {"chave": "login", "rotulo": "Login", "marcador": "Login"},
        {"chave": "senha", "rotulo": "Senha", "marcador": "Senha", "sensivel": True},
    ],
    "cameras_acessos": [
        {"chave": "nome", "rotulo": "Câmera / Local", "marcador": "Nome", "posicional": True},
        {"chave": "serial", "rotulo": "Serial", "marcador": "Serial"},
        {"chave": "ip", "rotulo": "IP", "marcador": "IP"},
        {"chave": "login", "rotulo": "Login", "marcador": "Login"},
        {"chave": "senha", "rotulo": "Senha", "marcador": "Senha", "sensivel": True},
        {"chave": "email", "rotulo": "E-mail", "marcador": "E-mail"},
        {"chave": "observacao", "rotulo": "Observação", "marcador": "Obs", "multilinha": True},
    ],
    "alarmes_acessos": [
        {"chave": "nome", "rotulo": "Alarme / Local", "marcador": "Nome", "posicional": True},
        {"chave": "serial", "rotulo": "Serial", "marcador": "Serial"},
        {"chave": "central", "rotulo": "Central / Modelo", "marcador": "Central"},
        {"chave": "login", "rotulo": "Login / Usuário", "marcador": "Login"},
        {"chave": "senha", "rotulo": "Senha", "marcador": "Senha", "sensivel": True},
    ],
    "serv_anydesk": [
        {"chave": "numero", "rotulo": "AnyDesk — Número", "marcador": "Número"},
        {"chave": "senha", "rotulo": "AnyDesk — Senha", "marcador": "Senha", "sensivel": True},
    ],
    "serv_radmin": [
        {"chave": "nome", "rotulo": "Radmin — Nome", "marcador": "Nome"},
        {"chave": "senha", "rotulo": "Radmin — Senha", "marcador": "Senha", "sensivel": True},
        {"chave": "ip", "rotulo": "Radmin — IP de acesso", "marcador": "IP"},
    ],
    "cert_log": [
        {"chave": "dhcp", "rotulo": "Gerencia DHCP?", "marcador": "Gerencia DHCP", "opcoes": ["Não", "Sim"]},
    ],
    "pfsense_acessos": [
        {"chave": "nome", "rotulo": "Nome PfSense", "marcador": "Nome"},
        {"chave": "login", "rotulo": "Login de acesso", "marcador": "Login"},
        {"chave": "senha", "rotulo": "Senha de acesso", "marcador": "Senha", "sensivel": True},
        {"chave": "acesso_fora", "rotulo": "Acesso fora da rede", "marcador": "Acesso fora da rede"},
        {"chave": "senha_fora", "rotulo": "Senha do acesso externo", "marcador": "Senha acesso fora", "sensivel": True},
        {"chave": "dhcp", "rotulo": "Gerencia DHCP?", "marcador": "Gerencia DHCP", "opcoes": ["Não", "Sim"]},
    ],
    "vpn_acessos": [
        {"chave": "nome", "rotulo": "VPN / Nome", "marcador": "VPN"},
        {"chave": "login", "rotulo": "Login", "marcador": "Login"},
        {"chave": "senha", "rotulo": "Senha de autenticação", "marcador": "Senha de autenticação", "sensivel": True},
        {"chave": "dois_fatores", "rotulo": "Autenticação em 2 fatores?", "marcador": "2FA", "opcoes": ["Não", "Sim"]},
        {"chave": "local_dois_fatores", "rotulo": "Local da autenticação em 2 fatores", "marcador": "Local 2FA"},
    ],
    "impressoras_acessos": [
        {"chave": "modelo", "rotulo": "Modelo", "marcador": "Modelo"},
        {"chave": "toners", "rotulo": "Tipos de toner", "marcador": "Toners"},
        {"chave": "ip", "rotulo": "IP", "marcador": "IP"},
        {"chave": "driver", "rotulo": "Link para baixar o driver", "marcador": "Driver"},
        {"chave": "setor", "rotulo": "Setor", "marcador": "Setor"},
    ],
    "antivirus_acessos": [
        {"chave": "tipo", "rotulo": "Tipo do antivírus", "marcador": "Tipo"},
        {"chave": "nome", "rotulo": "Nome do antivírus", "marcador": "Nome"},
        {"chave": "login", "rotulo": "Login de acesso", "marcador": "Login"},
        {"chave": "senha", "rotulo": "Senha", "marcador": "Senha", "sensivel": True},
        {"chave": "email", "rotulo": "E-mail", "marcador": "E-mail"},
        {"chave": "plataforma", "rotulo": "Plataforma", "marcador": "Plataforma"},
        {"chave": "compra", "rotulo": "Data de compra", "marcador": "Compra"},
        {"chave": "vencimento", "rotulo": "Data de vencimento", "marcador": "Vencimento"},
    ],
    "pcs_acessos": [
        {"chave": "tipo", "rotulo": "Tipo", "marcador": "Tipo", "posicional": True, "opcoes": ["Desktop", "Notebook", "Servidor"]},
        {"chave": "nome", "rotulo": "Nome / Setor", "marcador": "Nome/Setor", "posicional": True},
        {"chave": "anydesk", "rotulo": "AnyDesk / Senha", "marcador": "AnyDesk", "sensivel": True},
        {"chave": "remote_email", "rotulo": "Remote — E-mail", "marcador": "Remote e-mail"},
        {"chave": "remote_nome", "rotulo": "Remote — Nome da máquina", "marcador": "Remote nome máquina"},
    ],
    "hospedagem_acessos": [
        {"chave": "provedor", "rotulo": "Nome do provedor", "marcador": "Provedor"},
        {"chave": "site_provedor", "rotulo": "Site do provedor", "marcador": "Site Provedor"},
        {"chave": "login_hospedagem", "rotulo": "Login da hospedagem", "marcador": "Login Hospedagem"},
        {"chave": "senha_hospedagem", "rotulo": "Senha da hospedagem", "marcador": "Senha Hospedagem", "sensivel": True},
        {"chave": "dois_fatores_hospedagem", "rotulo": "Hospedagem pede 2FA?", "marcador": "2FA Hospedagem", "opcoes": ["Não", "Sim"]},
        {"chave": "local_dois_fatores_hospedagem", "rotulo": "Local do 2FA da hospedagem", "marcador": "Local 2FA Hospedagem"},
        {"chave": "dominio", "rotulo": "Domínio", "marcador": "Domínio"},
        {"chave": "registrado_em", "rotulo": "Onde está registrado", "marcador": "Registrado em"},
        {"chave": "site_registro", "rotulo": "Site do registro do domínio", "marcador": "Site Registro Domínio"},
        {"chave": "login_dominio", "rotulo": "Login do domínio", "marcador": "Login Domínio"},
        {"chave": "senha_dominio", "rotulo": "Senha do domínio", "marcador": "Senha Domínio", "sensivel": True},
        {"chave": "dois_fatores_dominio", "rotulo": "Domínio pede 2FA?", "marcador": "2FA Domínio", "opcoes": ["Não", "Sim"]},
        {"chave": "local_dois_fatores_dominio", "rotulo": "Local do 2FA do domínio", "marcador": "Local 2FA Domínio"},
    ],
    "aplicativos_acessos": [
        {"chave": "sistema", "rotulo": "Sistema / Aplicativo", "marcador": "Sistema"},
        {"chave": "operador", "rotulo": "Operador", "marcador": "Operador"},
        {"chave": "email", "rotulo": "E-mail", "marcador": "E-mail"},
        {"chave": "login", "rotulo": "Login", "marcador": "Login"},
        {"chave": "senha", "rotulo": "Senha", "marcador": "Senha", "sensivel": True},
    ],
}


def decompor_item_composto_infra(campo, valor):
    """Converte uma linha legada da infraestrutura em valores editáveis separados."""
    definicoes = CAMPOS_COMPOSTOS_INFRA.get(campo, [])
    resultado = {definicao["chave"]: "" for definicao in definicoes}
    texto = str(valor or "")
    if campo == "pcs_acessos" and " | Remote: " in texto:
        inicio, remoto = texto.split(" | Remote: ", 1)
        remote_email, _, remote_nome = remoto.partition(" / ")
        texto = f"{inicio} | Remote e-mail: {remote_email} | Remote nome máquina: {remote_nome}"
    partes = [parte.strip() for parte in texto.split(" | ")]
    posicionais = [definicao for definicao in definicoes if definicao.get("posicional")]
    proximo_posicional = 0
    ultima_chave = None
    for parte in partes:
        encontrado = None
        conteudo = ""
        for definicao in definicoes:
            prefixo = f'{definicao["marcador"]}:'
            if parte.casefold().startswith(prefixo.casefold()):
                encontrado = definicao
                conteudo = parte[len(prefixo):].strip()
                break
        if encontrado is None and proximo_posicional < len(posicionais):
            encontrado = posicionais[proximo_posicional]
            proximo_posicional += 1
            conteudo = parte
        elif encontrado is None and ultima_chave:
            resultado[ultima_chave] = f'{resultado[ultima_chave]} | {parte}'.strip(" |")
            continue
        if encontrado:
            resultado[encontrado["chave"]] = conteudo
            ultima_chave = encontrado["chave"]
            if encontrado.get("posicional"):
                proximo_posicional = max(proximo_posicional, posicionais.index(encontrado) + 1)

    return resultado


def compor_item_composto_infra(campo, valores):
    """Grava novamente a linha compatível com o banco, agora com marcadores estáveis."""
    return " | ".join(
        f'{definicao["marcador"]}: {str(valores.get(definicao["chave"], "") or "").strip()}'
        for definicao in CAMPOS_COMPOSTOS_INFRA.get(campo, [])
    )


def separar_itens_infra(valor, separador="||"):
    """Lê o formato legado sem remover posições vazias entre itens relacionados."""
    if valor in (None, ""):
        return []
    return [str(parte).strip() for parte in str(valor).split(separador)]


def anexar_itens_infra(valor_atual, novos, separador="||"):
    """Acrescenta novos registros sem substituir os que já estavam salvos."""
    atuais = separar_itens_infra(valor_atual, separador)
    adicionais = [str(valor or "").strip() for valor in (novos or []) if str(valor or "").strip()]
    return separador.join(atuais + adicionais)


def anexar_grupo_infra(ficha, novos_por_campo, separadores=None):
    """Anexa linhas paralelas, preservando o alinhamento entre campos do mesmo item."""
    ficha = ficha or {}
    separadores = separadores or {}
    campos = list(novos_por_campo)
    quantidade_nova = max((len(novos_por_campo[campo]) for campo in campos), default=0)
    indices_novos = [
        indice for indice in range(quantidade_nova)
        if any(
            str(novos_por_campo[campo][indice] if indice < len(novos_por_campo[campo]) else "").strip()
            for campo in campos
        )
    ]
    listas = {
        campo: separar_itens_infra(ficha.get(campo), separadores.get(campo, "|"))
        for campo in campos
    }
    quantidade_atual = max((len(lista) for lista in listas.values()), default=0)
    resultado = {}
    for campo in campos:
        valores = listas[campo] + [""] * (quantidade_atual - len(listas[campo]))
        valores.extend(
            str(novos_por_campo[campo][indice] if indice < len(novos_por_campo[campo]) else "").strip()
            for indice in indices_novos
        )
        resultado[campo] = separadores.get(campo, "|").join(valores)
    return resultado


def anexar_setores_infra(valor_atual, setores_novos):
    try:
        atuais = json.loads(valor_atual or "[]")
    except (TypeError, ValueError):
        atuais = []
    if not isinstance(atuais, list):
        atuais = []
    return json.dumps(atuais + list(setores_novos or []), ensure_ascii=False)


def garantir_colunas_infra_acesso_remoto(conectar_banco_func) -> None:
    """Mantém bancos antigos compatíveis antes de a tela consultar a ficha."""
    conn = conectar_banco_func()
    try:
        cursor = conn.cursor()
        for coluna in COLUNAS_INFRA_ACESSO_REMOTO:
            garantir_coluna(cursor, "infra_v4", coluna, "LONGTEXT")
        conn.commit()
    finally:
        conn.close()


def abrir_ficha_infraestrutura(estado, ficha_id):
    """Sincroniza a ficha clicada e consome a seleção antiga da grade."""
    ficha_id = int(ficha_id)
    estado["infra_item_editar_id"] = ficha_id
    estado["infra_editar_id"] = ficha_id
    estado["edit_inf_id_selecao"] = ficha_id
    estado["infra_acao_ficha"] = "Editar Ficha Completa"
    estado["infra_grade_versao"] = estado.get("infra_grade_versao", 0) + 1


def abrir_email_infraestrutura(estado, email_id):
    """Abre o e-mail e troca a grade para consumir o clique selecionado."""
    anterior = estado.get("infra_email_editar_id")
    if anterior and int(anterior) != int(email_id):
        estado.pop(f"infra_email_senha_liberada_{anterior}", None)
        estado.pop(f"infra_email_senha_valor_{anterior}", None)
        estado.setdefault("_infra_widgets_para_limpar", []).extend([
            f"infra_edit_em_senha_{anterior}", f"infra_edit_em_senha_visivel_{anterior}",
            f"infra_email_confirmar_senha_{anterior}",
        ])
    estado["infra_email_editar_id"] = int(email_id)
    estado["infra_email_grade_versao"] = estado.get("infra_email_grade_versao", 0) + 1


def buscar_senha_email_selecionado(conectar_banco_func, email, permitido):
    """Carrega o segredo somente do registro selecionado e autorizado."""
    if not permitido or not email or not email.get("id"):
        return ""
    conn = conectar_banco_func()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT senha FROM emails_clientes WHERE id=?", (int(email["id"]),))
        registro = cursor.fetchone()
        return (registro or {}).get("senha") or ""
    finally:
        conn.close()


def fechar_email_infraestrutura(estado):
    """Fecha a edição sem reaproveitar a seleção antiga da tabela."""
    email_id = estado.pop("infra_email_editar_id", None)
    if email_id:
        estado.setdefault("_infra_widgets_para_limpar", []).extend(
            chave for chave in list(estado)
            if str(chave).startswith(f"infra_edit_em_senha_carregada_{email_id}_")
        )
        estado.pop(f"infra_email_senha_liberada_{email_id}", None)
        estado.pop(f"infra_email_senha_valor_{email_id}", None)
        estado.setdefault("_infra_widgets_para_limpar", []).extend([
            f"infra_edit_em_senha_{email_id}", f"infra_edit_em_senha_visivel_{email_id}",
            f"infra_email_confirmar_senha_{email_id}",
        ])
    estado["infra_email_grade_versao"] = estado.get("infra_email_grade_versao", 0) + 1


def fechar_novos_emails_infraestrutura(estado):
    """Fecha o cadastro de novas contas e cria widgets vazios na próxima abertura."""
    estado["infra_novos_emails_versao"] = estado.get("infra_novos_emails_versao", 0) + 1


def ids_emails_cadastrados(registros):
    """Retorna somente IDs válidos e únicos apresentados na gestão de e-mails."""
    ids = []
    vistos = set()
    for registro in registros or []:
        try:
            email_id = int(registro.get("id") or 0)
        except (AttributeError, TypeError, ValueError):
            continue
        if email_id > 0 and email_id not in vistos:
            vistos.add(email_id)
            ids.append(email_id)
    return ids


def renderizar_infraestrutura_ti(ctx: dict) -> None:
    aplicar_contexto_pagina(ctx, globals())
    garantir_colunas_infra_acesso_remoto(conectar_banco)
    pode_visualizar_senhas_infra = tem_permissao("infra.senhas.view")

    def campo_secreto_infra(rotulo, valor, chave, altura=90):
        """Preserva o segredo quando o usuário não pode visualizá-lo."""
        if pode_visualizar_senhas_infra:
            return st.text_area(rotulo, value=valor or "", height=altura, key=chave)
        st.text_area(
            rotulo, value="••••••" if valor else "", height=altura, key=f"{chave}_bloqueado",
            disabled=True, help="Somente usuários com a permissão Visualizar senhas salvas podem acessar este conteúdo.",
        )
        return valor or ""
    for chave_widget in st.session_state.pop("_infra_widgets_para_limpar", []):
        st.session_state.pop(chave_widget, None)
    st.title("Infraestrutura e Acessos de TI")
    infra_edit_id_ativo = st.session_state.get("infra_editar_id")
    infra_editando = None
    if infra_edit_id_ativo:
        conn_inf_edit = conectar_banco()
        cinf_edit = conn_inf_edit.cursor(dictionary=True)
        cinf_edit.execute("SELECT * FROM infra_v4 WHERE id=?", (infra_edit_id_ativo,))
        infra_editando = cinf_edit.fetchone()
        conn_inf_edit.close()
        if not infra_editando:
            st.session_state.pop("infra_editar_id", None)
            infra_edit_id_ativo = None
    aba1, aba2 = st.tabs(["Cadastrar Ficha Completa", "Histórico de Fichas"])

    with aba1:
        if infra_editando:
            st.info(f"Modo edição ativo para a ficha #{infra_edit_id_ativo}. Ajuste os campos nesta tela e salve as alterações.")
            if st.button("Cancelar edição e voltar para novo cadastro", key="infra_cancelar_edicao"):
                st.session_state.pop("infra_editar_id", None)
                st.rerun()
        else:
            st.write("Preencha a ficha com os dados do cliente.")
        clientes_db = buscar_clientes()
        n_clis = ["-- Selecionar Cliente Existente --"] + [x['nome'] for x in clientes_db]
        idx_cli_infra = 0
        if infra_editando and infra_editando.get("cliente_vinc") in n_clis:
            idx_cli_infra = n_clis.index(infra_editando.get("cliente_vinc"))
        inf_vinc = st.selectbox("Vincular ao Cadastro de Cliente:", n_clis, index=idx_cli_infra, key=f"infra_vinc_{infra_edit_id_ativo or 'novo'}")
        cliente_infra = next((x for x in clientes_db if x["nome"] == inf_vinc), None)
        infra_historico_ficha = infra_editando
        if not infra_historico_ficha and inf_vinc != "-- Selecionar Cliente Existente --":
            conn_hist_cliente = conectar_banco()
            chist_cliente = conn_hist_cliente.cursor(dictionary=True)
            chist_cliente.execute(
                """SELECT * FROM infra_v4
                   WHERE cliente_vinc=? OR fantasia=? OR razao=?
                   ORDER BY id DESC LIMIT 1""",
                (inf_vinc, inf_vinc, inf_vinc),
            )
            infra_historico_ficha = chist_cliente.fetchone()
            conn_hist_cliente.close()
        infra_cliente_key = f"{infra_edit_id_ativo or 'novo'}_{cliente_infra.get('id') if cliente_infra else 'sem_cliente'}"
        puxar_cliente_selecionado = bool(cliente_infra) and (
            not infra_editando or inf_vinc != (infra_editando.get("cliente_vinc") or "")
        )

        def valor_cliente_infra(*campos):
            if not cliente_infra:
                return ""
            for campo in campos:
                valor = cliente_infra.get(campo)
                if valor not in (None, ""):
                    return str(valor)
            return ""

        def valor_infra(campo_infra, *campos_cliente):
            if infra_editando and not puxar_cliente_selecionado:
                return infra_editando.get(campo_infra) or ""
            return valor_cliente_infra(*campos_cliente)

        endereco_partes = []
        if cliente_infra:
            endereco_partes.append(valor_cliente_infra("endereco"))
            numero_cliente = valor_cliente_infra("numero")
            if numero_cliente:
                endereco_partes.append(f"Nº {numero_cliente}")
            complemento_cliente = valor_cliente_infra("complemento")
            if complemento_cliente:
                endereco_partes.append(complemento_cliente)
            bairro_cliente = valor_cliente_infra("bairro")
            if bairro_cliente:
                endereco_partes.append(bairro_cliente)
            cidade_cliente = valor_cliente_infra("cidade_estado")
            if cidade_cliente:
                endereco_partes.append(cidade_cliente)
            cep_cliente = valor_cliente_infra("cep")
            if cep_cliente:
                endereco_partes.append(f"CEP: {cep_cliente}")
        endereco_infra = " - ".join([parte for parte in endereco_partes if parte])
        
        st.subheader("1. Identificação da Empresa")
        c1, c2 = st.columns(2)
        with c1: inf_fan = st.text_input("Nome Fantasia:", value=valor_infra("fantasia", "nome"), key=f"infra_fan_{infra_cliente_key}")
        with c2: inf_emp = st.text_input("Razão Social / Nome da Empresa:", value=valor_infra("razao", "razao", "nome"), key=f"infra_emp_{infra_cliente_key}")
            
        c3, c4, c5 = st.columns([2,3,2])
        with c3: inf_cnpj = st.text_input("CNPJ / CPF:", value=valor_infra("cnpj", "cnpj", "cpf"), key=f"infra_cnpj_{infra_cliente_key}")
        with c4: inf_end = st.text_input("Endereço Completo:", value=(infra_editando.get("endereco") or "") if infra_editando and not puxar_cliente_selecionado else endereco_infra, key=f"infra_end_{infra_cliente_key}")
        with c5: inf_cont = st.text_input("Nome do Contato:", value=valor_infra("contato", "contato_padrao", "contato", "nome"), key=f"infra_cont_{infra_cliente_key}")
            
        c6, c7, c8 = st.columns(3)
        with c6: inf_email = st.text_input("E-mail Principal:", value=valor_infra("email_prin", "email", "emails_cobranca"), key=f"infra_email_{infra_cliente_key}")
        with c7: inf_t1 = st.text_input("Telefone Principal:", value=valor_infra("tel_prin", "telefone", "telefone_secundario"), key=f"infra_t1_{infra_cliente_key}")
        with c8: inf_t2 = st.text_input("Telefone Provedor:", value=(infra_editando.get("tel_prov") or "") if infra_editando and not puxar_cliente_selecionado else "", key=f"infra_t2_{infra_cliente_key}")

        c9, c10, c11 = st.columns(3)
        with c9: inf_contr = st.text_input("Data Assinatura Contrato:", value=(infra_editando.get("contrato_data") or "") if infra_editando and not puxar_cliente_selecionado else "", key=f"infra_contr_{infra_cliente_key}")
        with c10: inf_pag = st.text_input("Forma Pagto:", value=(infra_editando.get("pagto") or "") if infra_editando and not puxar_cliente_selecionado else "", key=f"infra_pag_{infra_cliente_key}")
        with c11: inf_venc = st.text_input("Dia de Vencimento:", value=valor_infra("venc", "dia_vencimento"), key=f"infra_venc_{infra_cliente_key}")

        st.subheader("2. Detalhamento Técnico")
        abas_infra = ["Sistemas", "Rede", "DVR", "Câmeras", "Alarme", "Wi-Fi", "Servidor", "Impressoras", "Antivírus", "Financeiro", "PCs e Acessos", "Setores", "Equipamentos", "Hospedagem"]
        if tem_permissao("infra.emails") or tem_permissao("emails.view"):
            abas_infra.append("Gestão de E-mails")
        if tem_permissao("infra.aplicativos"):
            abas_infra.append("Aplicativos")
        tabs_infra = dict(zip(abas_infra, st.tabs(abas_infra)))
        t_sys = tabs_infra["Sistemas"]
        t_rede = tabs_infra["Rede"]
        t_dvr = tabs_infra["DVR"]
        t_cam = tabs_infra["Câmeras"]
        t_alarme = tabs_infra["Alarme"]
        t_wifi = tabs_infra["Wi-Fi"]
        t_serv = tabs_infra["Servidor"]
        t_impressoras = tabs_infra["Impressoras"]
        t_antivirus = tabs_infra["Antivírus"]
        t_fin = tabs_infra["Financeiro"]
        t_pcs = tabs_infra["PCs e Acessos"]
        t_setores = tabs_infra.get("Setores")
        t_equipamentos = tabs_infra.get("Equipamentos")
        t_hospedagem = tabs_infra.get("Hospedagem")
        t_emails_infra = tabs_infra.get("Gestão de E-mails")
        t_apps = tabs_infra.get("Aplicativos")

        def renderizar_historico_tecnico(slug, titulo, campos, ficha=None):
            """Lista e edita os itens serializados da ficha escolhida."""
            ficha_ref = ficha or infra_historico_ficha
            st.markdown(f"#### Histórico de {titulo}")
            if not ficha_ref:
                st.info("Selecione um cliente que já possua uma ficha salva para consultar o histórico.")
                return
            listas = {}
            campos_sensiveis = {
                "sys_senha", "rede_sen", "rede_dsen", "rede_wsen", "serv_sen", "serv_anydesk",
                "serv_radmin", "dvr_acessos", "cameras_acessos", "alarmes_acessos",
                "pfsense_acessos", "vpn_acessos", "antivirus_acessos", "hospedagem_acessos",
                "aplicativos_acessos", "fin_b1", "fin_b2", "fin_b3", "pcs_acessos",
            }
            for campo, _, separador in campos:
                listas[campo] = [
                    parte.strip() for parte in str(ficha_ref.get(campo) or "").split(separador)
                ] if ficha_ref.get(campo) else []
            quantidade = max((len(valores) for valores in listas.values()), default=0)
            linhas = []
            for indice in range(quantidade):
                linha = {"ID": indice + 1}
                possui_dados = False
                for campo, rotulo, _ in campos:
                    valor = listas[campo][indice] if indice < len(listas[campo]) else ""
                    possui_dados = possui_dados or bool(valor.strip())
                    definicoes_compostas = CAMPOS_COMPOSTOS_INFRA.get(campo)
                    if definicoes_compostas:
                        valores_compostos = decompor_item_composto_infra(campo, valor)
                        for definicao in definicoes_compostas:
                            valor_campo = valores_compostos.get(definicao["chave"], "")
                            linha[definicao["rotulo"]] = (
                                "••••••" if definicao.get("sensivel") and valor_campo else valor_campo
                            )
                    else:
                        linha[rotulo] = "••••••" if campo in campos_sensiveis and valor else valor
                if possui_dados:
                    linha["_indice"] = indice
                    linhas.append(linha)
            if not linhas:
                st.info(f"Nenhum item de {titulo.lower()} salvo para este cliente.")
                return

            pesquisa = st.text_input(
                f"Pesquisar em {titulo.lower()}:",
                key=f"infra_hist_busca_{slug}_{ficha_ref.get('id')}",
            ).strip().casefold()
            filtradas = [
                linha for linha in linhas
                if not pesquisa or pesquisa in " ".join(
                    str(valor or "") for chave, valor in linha.items() if chave != "_indice"
                ).casefold()
            ]
            tabela = [{chave: valor for chave, valor in linha.items() if chave != "_indice"} for linha in filtradas]
            clicado = tabela_clicavel_id(
                st, tabela,
                f"infra_hist_grade_{slug}_{ficha_ref.get('id')}_{st.session_state.get(f'infra_hist_versao_{slug}', 0)}",
                campo_id="ID",
            ) if tabela else None
            if clicado:
                linha_clicada = next((linha for linha in filtradas if int(linha["ID"]) == int(clicado)), None)
                if linha_clicada:
                    st.session_state[f"infra_hist_item_{slug}_{ficha_ref.get('id')}"] = int(linha_clicada["_indice"])
            chave_item_ativo = f"infra_hist_item_{slug}_{ficha_ref.get('id')}"
            indice_ativo = st.session_state.get(chave_item_ativo)
            if indice_ativo is None or not any(linha["_indice"] == int(indice_ativo) for linha in linhas):
                st.caption("Clique em qualquer informação da tabela para abrir a edição.")
                return

            with st.expander(f"Editando item {int(indice_ativo) + 1} de {titulo}", expanded=True):
                valores_editados = {}
                colunas_campos_simples = st.columns(3)
                posicao_campo_simples = 0
                campos_multilinha = {"sys_dados", "serv_info_gerais", "fin_b1", "fin_b2", "fin_b3"}
                for campo, rotulo, _ in campos:
                    atual = listas[campo][int(indice_ativo)] if int(indice_ativo) < len(listas[campo]) else ""
                    definicoes_compostas = CAMPOS_COMPOSTOS_INFRA.get(campo)
                    if definicoes_compostas:
                        atuais_compostos = decompor_item_composto_infra(campo, atual)
                        editados_compostos = {}
                        colunas_campos = st.columns(3)
                        for posicao, definicao in enumerate(definicoes_compostas):
                            chave_widget = (
                                f"infra_hist_edit_{slug}_{campo}_{definicao['chave']}_"
                                f"{ficha_ref.get('id')}_{indice_ativo}"
                            )
                            valor_campo = atuais_compostos.get(definicao["chave"], "")
                            with colunas_campos[posicao % 3]:
                                if definicao.get("sensivel") and not pode_visualizar_senhas_infra:
                                    st.text_input(
                                        definicao["rotulo"], value="••••••", type="password", disabled=True,
                                        help="Seu usuário não possui a permissão Visualizar senhas salvas.",
                                        key=f"{chave_widget}_bloqueado",
                                    )
                                    editados_compostos[definicao["chave"]] = valor_campo
                                elif definicao.get("opcoes"):
                                    opcoes = list(definicao["opcoes"])
                                    if valor_campo and valor_campo not in opcoes:
                                        opcoes.insert(0, valor_campo)
                                    editados_compostos[definicao["chave"]] = st.selectbox(
                                        definicao["rotulo"], opcoes,
                                        index=opcoes.index(valor_campo) if valor_campo in opcoes else 0,
                                        key=chave_widget,
                                    )
                                elif definicao.get("multilinha"):
                                    editados_compostos[definicao["chave"]] = st.text_area(
                                        definicao["rotulo"], value=valor_campo, height=80, key=chave_widget,
                                    )
                                else:
                                    editados_compostos[definicao["chave"]] = st.text_input(
                                        definicao["rotulo"], value=valor_campo,
                                        type="password" if definicao.get("sensivel") else "default",
                                        key=chave_widget,
                                    )
                        valores_editados[campo] = compor_item_composto_infra(campo, editados_compostos)
                    else:
                        chave_simples = f"infra_hist_edit_{slug}_{campo}_{ficha_ref.get('id')}_{indice_ativo}"
                        with colunas_campos_simples[posicao_campo_simples % 3]:
                            if campo in campos_sensiveis and not pode_visualizar_senhas_infra:
                                st.text_input(
                                    rotulo, value="••••••", type="password", disabled=True,
                                    help="Seu usuário não possui a permissão Visualizar senhas salvas.",
                                    key=f"{chave_simples}_bloqueado",
                                )
                                valores_editados[campo] = atual
                            elif campo in campos_sensiveis:
                                valores_editados[campo] = st.text_input(
                                    rotulo, value=atual, type="password", key=chave_simples,
                                )
                            elif campo in campos_multilinha:
                                valores_editados[campo] = st.text_area(
                                    rotulo, value=atual, height=80, key=chave_simples,
                                )
                            else:
                                valores_editados[campo] = st.text_input(
                                    rotulo, value=atual, key=chave_simples,
                                )
                        posicao_campo_simples += 1
                salvar_col, cancelar_col = st.columns(2)
                if salvar_col.button("Salvar somente este item", type="primary", width="stretch", key=f"infra_hist_salvar_{slug}_{ficha_ref.get('id')}_{indice_ativo}"):
                    atualizacoes = {}
                    for campo, _, separador in campos:
                        valores = list(listas[campo])
                        while len(valores) <= int(indice_ativo):
                            valores.append("")
                        valores[int(indice_ativo)] = valores_editados[campo].strip()
                        atualizacoes[campo] = separador.join(valores)
                    conn_hist_save = conectar_banco()
                    chist_save = conn_hist_save.cursor()
                    set_sql = ", ".join(f"{campo}=?" for campo in atualizacoes)
                    chist_save.execute(
                        f"UPDATE infra_v4 SET {set_sql} WHERE id=?",
                        tuple(atualizacoes.values()) + (ficha_ref.get("id"),),
                    )
                    conn_hist_save.commit()
                    conn_hist_save.close()
                    st.session_state.pop(chave_item_ativo, None)
                    st.session_state[f"infra_hist_versao_{slug}"] = st.session_state.get(f"infra_hist_versao_{slug}", 0) + 1
                    st.success(f"{titulo} atualizado com sucesso.")
                    st.rerun()
                if cancelar_col.button("Cancelar edição", width="stretch", key=f"infra_hist_cancelar_{slug}_{ficha_ref.get('id')}_{indice_ativo}"):
                    st.session_state.pop(chave_item_ativo, None)
                    st.session_state[f"infra_hist_versao_{slug}"] = st.session_state.get(f"infra_hist_versao_{slug}", 0) + 1
                    st.rerun()

        def renderizar_historico_setores(ficha=None):
            ficha_ref = ficha or infra_historico_ficha
            st.markdown("#### Histórico de Setores")
            if not ficha_ref:
                st.info("Selecione um cliente que já possua uma ficha salva para consultar o histórico.")
                return
            try:
                setores_salvos = json.loads(ficha_ref.get("setores") or "[]")
            except (TypeError, ValueError):
                setores_salvos = []
            if not setores_salvos:
                st.info("Nenhum setor salvo para este cliente.")
                return
            pesquisa_setor = st.text_input(
                "Pesquisar setor:", key=f"infra_hist_setor_busca_{ficha_ref.get('id')}"
            ).strip().casefold()
            tabela_setores = [{
                "ID": indice + 1,
                "Setor": setor.get("nome") or "",
                "Informações": setor.get("informacoes") or "",
                "Softwares": len(setor.get("softwares") or []),
            } for indice, setor in enumerate(setores_salvos) if not pesquisa_setor or pesquisa_setor in " ".join([
                str(setor.get("nome") or ""), str(setor.get("informacoes") or ""),
                json.dumps(setor.get("softwares") or [], ensure_ascii=False),
            ]).casefold()]
            setor_clicado = tabela_clicavel_id(
                st, tabela_setores, f"infra_hist_setores_{ficha_ref.get('id')}", campo_id="ID"
            ) if tabela_setores else None
            if pesquisa_setor and not tabela_setores:
                st.info("Nenhum setor encontrado nessa pesquisa.")
            if setor_clicado:
                st.session_state[f"infra_hist_setor_item_{ficha_ref.get('id')}"] = int(setor_clicado) - 1
            chave_setor_ativo = f"infra_hist_setor_item_{ficha_ref.get('id')}"
            indice_setor = st.session_state.get(chave_setor_ativo)
            if indice_setor is None or not (0 <= int(indice_setor) < len(setores_salvos)):
                st.caption("Clique em qualquer informação do setor para abrir a edição.")
                return
            setor = setores_salvos[int(indice_setor)]
            with st.expander(f"Editando setor: {setor.get('nome') or int(indice_setor) + 1}", expanded=True):
                nome_setor = st.text_input("Nome do setor:", value=setor.get("nome") or "", key=f"infra_hist_setor_nome_{ficha_ref.get('id')}_{indice_setor}")
                info_setor = st.text_area("Informações gerais:", value=setor.get("informacoes") or "", height=110, key=f"infra_hist_setor_info_{ficha_ref.get('id')}_{indice_setor}")
                st.caption(f"Softwares vinculados preservados: {len(setor.get('softwares') or [])}")
                salvar_setor, cancelar_setor = st.columns(2)
                if salvar_setor.button("Salvar alterações do setor", type="primary", width="stretch", key=f"infra_hist_setor_salvar_{ficha_ref.get('id')}_{indice_setor}"):
                    setores_salvos[int(indice_setor)]["nome"] = nome_setor.strip()
                    setores_salvos[int(indice_setor)]["informacoes"] = info_setor.strip()
                    conn_setor = conectar_banco()
                    csetor = conn_setor.cursor()
                    csetor.execute(
                        "UPDATE infra_v4 SET setores=? WHERE id=?",
                        (json.dumps(setores_salvos, ensure_ascii=False), ficha_ref.get("id")),
                    )
                    conn_setor.commit()
                    conn_setor.close()
                    st.session_state.pop(chave_setor_ativo, None)
                    st.success("Setor atualizado sem alterar seus softwares vinculados.")
                    st.rerun()
                if cancelar_setor.button("Cancelar edição", width="stretch", key=f"infra_hist_setor_cancelar_{ficha_ref.get('id')}_{indice_setor}"):
                    st.session_state.pop(chave_setor_ativo, None)
                    st.rerun()
        
        with t_sys:
            qtd_sys = st.number_input("Qtd Sistemas:", min_value=1, max_value=10, value=1)
            sys_dados_l, sys_ser_l, sys_cod_l, sys_adm_l, sys_sen_l, sys_sec_l = [], [], [], [], [], []
            for i in range(qtd_sys):
                cs1, cs2, cs3 = st.columns(3)
                s_dados = cs1.text_input(f"Dados Sistema {i+1}:", key=f"sdados_{i}")
                s_ser = cs2.text_input(f"Serial Sistema {i+1}:", key=f"sser_{i}")
                s_cod = cs3.text_input(f"Cód. Cliente {i+1}:", key=f"scod_{i}")
                cs4, cs5, cs6 = st.columns(3)
                s_adm = cs4.text_area(f"Logins Administrativos {i+1}:", height=80, key=f"sadm_{i}")
                s_sen = cs5.text_area(f"Senhas Administrativas {i+1}:", height=80, key=f"ssen_{i}")
                s_sec = cs6.text_area(f"Logins Secundários {i+1}:", height=80, key=f"ssec_{i}")
                sys_dados_l.append(s_dados); sys_ser_l.append(s_ser); sys_cod_l.append(s_cod)
                sys_adm_l.append(s_adm); sys_sen_l.append(s_sen); sys_sec_l.append(s_sec)
            
        with t_rede:
            qtd_rede = st.number_input("Qtd Redes/Modems:", min_value=1, max_value=10, value=1)
            r_pro_l, r_ip_l, r_log_l, r_sen_l, r_ddns_l, r_dsen_l, r_wir_l, r_wsen_l = [], [], [], [], [], [], [], []
            faixas_ip_l = []
            for i in range(qtd_rede):
                cr1, cr2 = st.columns(2)
                r_pro = cr1.text_input(f"Provedor {i+1}:", key=f"rpro_{i}")
                r_ip = cr2.text_input(f"IP Provedor {i+1}:", key=f"rip_{i}")
                cr3, cr4 = st.columns(2)
                r_log = cr3.text_area(f"Logins Modem {i+1}:", height=80, key=f"rlog_{i}")
                r_sen = cr4.text_area(f"Senhas Modem {i+1}:", height=80, key=f"rsen_{i}")
                r_pro_l.append(r_pro); r_ip_l.append(r_ip); r_log_l.append(r_log); r_sen_l.append(r_sen)

            st.write("---")
            st.markdown("**Faixas de IP**")
            qtd_faixas_ip = st.number_input("Qtd Faixas de IP:", min_value=0, max_value=30, value=0, key="qtd_faixas_ip")
            for i in range(qtd_faixas_ip):
                fi1, fi2 = st.columns([1, 2])
                faixa_ip = fi1.text_input(f"Faixa de IP {i+1}:", placeholder="Ex: 192.168.0.0/24", key=f"faixa_ip_{i}")
                info_faixa = fi2.text_area(f"Informação da Faixa de IP {i+1}:", height=80, key=f"info_faixa_ip_{i}")
                if faixa_ip or info_faixa:
                    faixas_ip_l.append(f"Faixa: {faixa_ip} | Informação: {info_faixa}")
            
        with t_dvr:
            qtd_dvr = st.number_input("Qtd DVRs:", min_value=0, max_value=30, value=0)
            dvr_l = []
            fotos_infra_itens = []
            for i in range(qtd_dvr):
                cd1, cd2, cd3 = st.columns(3)
                d_nome = cd1.text_input(f"DVR/Nome {i+1}:", key=f"dvrnome_{i}")
                d_serial = cd2.text_input(f"Serial DVR {i+1}:", key=f"dvrserial_{i}")
                d_ip = cd3.text_input(f"IP/DDNS DVR {i+1}:", key=f"dvrip_{i}")
                cd4, cd5, cd6 = st.columns(3)
                d_login = cd4.text_area(f"Login DVR {i+1}:", height=80, key=f"dvrlogin_{i}")
                d_senha = cd5.text_area(f"Senha DVR {i+1}:", height=80, key=f"dvrsenha_{i}")
                d_porta = cd6.text_input(f"Porta serviço DVR {i+1}:", key=f"dvrporta_{i}")
                foto_dvr = st.file_uploader(f"Foto do DVR {i+1}:", type=TIPOS_IMAGEM_UPLOAD, key=f"dvrfoto_{i}")
                if foto_dvr:
                    fotos_infra_itens.append({"tipo": "DVR", "indice": i + 1, "nome": d_nome or f"DVR {i+1}", "arquivo": foto_dvr})
                if d_nome or d_serial or d_ip or d_login or d_senha or d_porta:
                    dvr_l.append(f"{d_nome} | Serial: {d_serial} | IP/DDNS: {d_ip} | Porta serviço: {d_porta} | Login: {d_login} | Senha: {d_senha}")
            r_ddns_l = dvr_l
            r_dsen_l = []

        with t_cam:
            qtd_cam = st.number_input("Qtd Câmeras:", min_value=0, max_value=100, value=0)
            cameras_l = []
            for i in range(qtd_cam):
                cc1, cc2, cc3, cc4 = st.columns(4)
                cam_nome = cc1.text_input(f"Câmera/Local {i+1}:", key=f"camnome_{i}")
                cam_serial = cc2.text_input(f"Serial Câmera {i+1}:", key=f"camserial_{i}")
                cam_ip = cc3.text_input(f"IP Câmera {i+1}:", key=f"camip_{i}")
                cam_obs = cc4.text_input(f"Obs Câmera {i+1}:", key=f"camobs_{i}")
                cc5, cc6, cc7 = st.columns(3)
                cam_login = cc5.text_input(f"Login Câmera {i+1}:", key=f"camlogin_{i}")
                cam_senha = cc6.text_input(f"Senha Câmera {i+1}:", key=f"camsenha_{i}")
                cam_email = cc7.text_input(f"E-mail Câmera {i+1}:", key=f"camemail_{i}")
                foto_cam = st.file_uploader(f"Foto da câmera {i+1}:", type=TIPOS_IMAGEM_UPLOAD, key=f"camfoto_{i}")
                if foto_cam:
                    fotos_infra_itens.append({"tipo": "Câmera", "indice": i + 1, "nome": cam_nome or f"Câmera {i+1}", "arquivo": foto_cam})
                if cam_nome or cam_serial or cam_ip or cam_obs or cam_login or cam_senha or cam_email:
                    cameras_l.append(f"{cam_nome} | Serial: {cam_serial} | IP: {cam_ip} | Login: {cam_login} | Senha: {cam_senha} | E-mail: {cam_email} | Obs: {cam_obs}")

        with t_alarme:
            qtd_alarme = st.number_input("Qtd Alarmes:", min_value=0, max_value=30, value=0)
            alarmes_l = []
            for i in range(qtd_alarme):
                ca1, ca2, ca3 = st.columns(3)
                al_nome = ca1.text_input(f"Alarme/Local {i+1}:", key=f"alnome_{i}")
                al_serial = ca2.text_input(f"Serial Alarme {i+1}:", key=f"alserial_{i}")
                al_central = ca3.text_input(f"Central/Modelo {i+1}:", key=f"alcentral_{i}")
                ca4, ca5 = st.columns(2)
                al_login = ca4.text_area(f"Login/Usuário Alarme {i+1}:", height=80, key=f"allogin_{i}")
                al_senha = ca5.text_area(f"Senha Alarme {i+1}:", height=80, key=f"alsenha_{i}")
                foto_alarme = st.file_uploader(f"Foto do alarme {i+1}:", type=TIPOS_IMAGEM_UPLOAD, key=f"alfoto_{i}")
                if foto_alarme:
                    fotos_infra_itens.append({"tipo": "Alarme", "indice": i + 1, "nome": al_nome or f"Alarme {i+1}", "arquivo": foto_alarme})
                if al_nome or al_serial or al_central or al_login or al_senha:
                    alarmes_l.append(f"{al_nome} | Serial: {al_serial} | Central: {al_central} | Login: {al_login} | Senha: {al_senha}")

        with t_wifi:
            qtd_wifi = st.number_input("Qtd Redes Wi-Fi:", min_value=0, max_value=30, value=0)
            for i in range(qtd_wifi):
                cw1, cw2 = st.columns(2)
                r_wir = cw1.text_area(f"SSID Wi-Fi {i+1}:", height=80, key=f"rwir_{i}")
                r_wsen = cw2.text_area(f"Senha Wi-Fi {i+1}:", height=80, key=f"rwsen_{i}")
                r_wir_l.append(r_wir); r_wsen_l.append(r_wsen)

        with t_serv:
            qtd_serv = st.number_input("Qtd Servidores:", min_value=1, max_value=10, value=1)
            sv_nom_l, sv_ip_l, sv_link_l, sv_log_l, sv_sen_l, ct_log_l, ct_sen_l = [], [], [], [], [], [], []
            sv_anydesk_l, sv_radmin_l, sv_google_remote_l, sv_info_gerais_l = [], [], [], []
            for i in range(qtd_serv):
                cv1, cv2, cv3 = st.columns(3)
                sv_nom = cv1.text_input(f"Nome da rede {i+1}:", key=f"svnom_{i}")
                sv_ip = cv2.text_input(f"IP do servidor {i+1}:", key=f"svip_{i}")
                sv_link = cv3.text_input(f"No-IP {i+1}:", key=f"svlink_{i}")
                cv4, cv5, cv6 = st.columns(3)
                sv_log = cv4.text_input(f"Login {i+1}:", key=f"svlog_{i}")
                sv_sen = cv5.text_input(f"Senha {i+1}:", type="password", key=f"svsen_{i}")
                sv_dhcp = cv6.selectbox(f"Gerencia DHCP? {i+1}:", ["Não", "Sim"], key=f"svdhcp_{i}")
                sv_nom_l.append(sv_nom); sv_ip_l.append(sv_ip); sv_link_l.append(sv_link)
                sv_log_l.append(sv_log); sv_sen_l.append(sv_sen)
                ct_log_l.append(f"Gerencia DHCP: {sv_dhcp}"); ct_sen_l.append("")
                ca1, ca2 = st.columns(2)
                anydesk_numero = ca1.text_input(f"AnyDesk - número {i+1}:", key=f"sv_anydesk_num_{i}")
                anydesk_senha = ca2.text_input(f"AnyDesk - senha {i+1}:", type="password", key=f"sv_anydesk_senha_{i}")
                cr1, cr2, cr3 = st.columns(3)
                radmin_nome = cr1.text_input(f"Radmin - nome {i+1}:", key=f"sv_radmin_nome_{i}")
                radmin_senha = cr2.text_input(f"Radmin - senha {i+1}:", type="password", key=f"sv_radmin_senha_{i}")
                radmin_ip = cr3.text_input(f"Radmin - IP de acesso {i+1}:", key=f"sv_radmin_ip_{i}")
                google_remote = st.text_input(f"Nome Google Remote {i+1}:", key=f"sv_google_remote_{i}")
                info_gerais = st.text_area(f"Informações gerais do servidor {i+1}:", height=90, key=f"sv_info_gerais_{i}")
                sv_anydesk_l.append(f"Número: {anydesk_numero} | Senha: {anydesk_senha}" if anydesk_numero or anydesk_senha else "")
                sv_radmin_l.append(f"Nome: {radmin_nome} | Senha: {radmin_senha} | IP: {radmin_ip}" if radmin_nome or radmin_senha or radmin_ip else "")
                sv_google_remote_l.append(google_remote)
                sv_info_gerais_l.append(info_gerais)

            st.write("---")
            st.markdown("**Dados do PfSense**")
            qtd_pfsense = st.number_input("Qtd PfSense:", min_value=0, max_value=20, value=0)
            pfsense_l = []
            for i in range(qtd_pfsense):
                pf1, pf2, pf3 = st.columns(3)
                pf_nome = pf1.text_input(f"Nome PfSense {i+1}:", key=f"pfnome_{i}")
                pf_login = pf2.text_input(f"Login de acesso {i+1}:", key=f"pflogin_{i}")
                pf_senha = pf3.text_input(f"Senha de acesso {i+1}:", type="password", key=f"pfsenha_{i}")
                pf4, pf5, pf6 = st.columns(3)
                pf_acesso_fora = pf4.text_input(f"Acesso fora da rede {i+1}:", key=f"pfacessofora_{i}")
                pf_senha_fora = pf5.text_input(f"Senha acesso fora {i+1}:", type="password", key=f"pfsenhafora_{i}")
                pf_dhcp = pf6.selectbox(f"Gerencia DHCP? {i+1}:", ["Não", "Sim"], key=f"pfdhcp_{i}")
                if pf_nome or pf_login or pf_senha or pf_acesso_fora or pf_senha_fora:
                    pfsense_l.append(f"Nome: {pf_nome} | Login: {pf_login} | Senha: {pf_senha} | Acesso fora da rede: {pf_acesso_fora} | Senha acesso fora: {pf_senha_fora} | Gerencia DHCP: {pf_dhcp}")

            st.write("---")
            st.markdown("**VPN**")
            qtd_vpn = st.number_input("Qtd VPN:", min_value=0, max_value=30, value=0, key="qtd_vpn")
            vpn_l = []
            for i in range(qtd_vpn):
                vpn1, vpn2, vpn3 = st.columns(3)
                vpn_nome = vpn1.text_input(f"VPN/Nome {i+1}:", key=f"vpn_nome_{i}")
                vpn_login = vpn2.text_input(f"Login VPN {i+1}:", key=f"vpn_login_{i}")
                vpn_senha = vpn3.text_input(f"Senha de autenticação {i+1}:", type="password", key=f"vpn_senha_{i}")
                vpn4, vpn5 = st.columns([1, 2])
                vpn_2fa = vpn4.selectbox(f"Autenticação 2 Fatores? {i+1}:", ["Não", "Sim"], key=f"vpn_2fa_{i}")
                vpn_local_2fa = vpn5.text_input(f"Local de Autenticação 2 Fatores {i+1}:", key=f"vpn_local_2fa_{i}")
                if vpn_nome or vpn_login or vpn_senha or vpn_local_2fa:
                    vpn_l.append(f"VPN: {vpn_nome} | Login: {vpn_login} | Senha de autenticação: {vpn_senha} | 2FA: {vpn_2fa} | Local 2FA: {vpn_local_2fa}")

        with t_impressoras:
            qtd_impressoras = st.number_input("Qtd Impressoras:", min_value=0, max_value=100, value=0, key="infra_qtd_impressoras")
            impressoras_l = []
            for i in range(qtd_impressoras):
                ip1, ip2, ip3 = st.columns(3)
                imp_modelo = ip1.text_input(f"Modelo da impressora {i+1}:", key=f"infra_imp_modelo_{i}")
                imp_toners = ip2.text_input(f"Tipos de toner {i+1}:", key=f"infra_imp_toners_{i}")
                imp_ip = ip3.text_input(f"IP {i+1}:", key=f"infra_imp_ip_{i}")
                ip4, ip5 = st.columns(2)
                imp_driver = ip4.text_input(f"Link para baixar o driver {i+1}:", key=f"infra_imp_driver_{i}")
                imp_setor = ip5.text_input(f"Setor {i+1}:", key=f"infra_imp_setor_{i}")
                if imp_modelo or imp_toners or imp_ip or imp_driver or imp_setor:
                    impressoras_l.append(
                        f"Modelo: {imp_modelo} | Toners: {imp_toners} | IP: {imp_ip} | Driver: {imp_driver} | Setor: {imp_setor}"
                    )

        with t_antivirus:
            qtd_antivirus = st.number_input("Qtd Antivírus:", min_value=0, max_value=50, value=0)
            antivirus_l = []
            for i in range(qtd_antivirus):
                av1, av2, av3, av4 = st.columns(4)
                av_tipo = av1.text_input(f"Tipo do antivírus {i+1}:", key=f"avtipo_{i}")
                av_nome = av2.text_input(f"Nome do antivírus {i+1}:", key=f"avnome_{i}")
                av_login = av3.text_input(f"Login de acesso {i+1}:", key=f"avlogin_{i}")
                av_senha = av4.text_input(f"Senha {i+1}:", type="password", key=f"avsenha_{i}")
                av5, av6, av7, av8 = st.columns(4)
                av_email = av5.text_input(f"E-mail {i+1}:", key=f"avemail_{i}")
                av_plataforma = av6.text_input(f"Plataforma {i+1}:", key=f"avplataforma_{i}")
                av_compra = av7.date_input(f"Data de compra {i+1}:", value=None, key=f"avcompra_{i}")
                av_venc = av8.date_input(f"Data de vencimento {i+1}:", value=None, key=f"avvenc_{i}")
                if av_tipo or av_nome or av_login or av_senha or av_email or av_plataforma:
                    antivirus_l.append(f"Tipo: {av_tipo} | Nome: {av_nome} | Login: {av_login} | Senha: {av_senha} | E-mail: {av_email} | Plataforma: {av_plataforma} | Compra: {av_compra or ''} | Vencimento: {av_venc or ''}")

        with t_fin:
            qtd_fin = st.number_input("Qtd Blocos Bancários:", min_value=1, max_value=3, value=1)
            fin_l = ["", "", ""]
            for i in range(qtd_fin):
                fin_l[i] = st.text_area(f"Banco {i+1} (Ex: Ag, Conta, Op, Chave, Senhas):", height=150, key=f"finb_{i}")

        with t_pcs:
            qtd_pcs = st.number_input("Qtd de Computadores:", min_value=1, max_value=50, value=1)
            pcs_l = []
            for i in range(qtd_pcs):
                c_pc1, c_pc2, c_pc3 = st.columns(3)
                p_tipo = c_pc1.selectbox(f"Tipo {i+1}:", ["Desktop", "Notebook", "Servidor"], key=f"ptipo_{i}")
                p_nome = c_pc2.text_input(f"Nome/Setor {i+1}:", key=f"pnome_{i}")
                p_aces = c_pc3.text_input(f"AnyDesk/Senha {i+1}:", key=f"paces_{i}")
                c_pc4, c_pc5 = st.columns(2)
                p_remote_email = c_pc4.text_input(f"Remote e-mail {i+1}:", key=f"premail_{i}")
                p_remote_nome = c_pc5.text_input(f"Remote nome máquina {i+1}:", key=f"prnome_{i}")
                if p_nome or p_aces or p_remote_email or p_remote_nome:
                    pcs_l.append(f"{p_tipo} | {p_nome} | AnyDesk: {p_aces} | Remote: {p_remote_email} / {p_remote_nome}")

        setores_l = []
        if t_setores:
            with t_setores:
                qtd_setores = st.number_input("Qtd Setores:", min_value=0, max_value=50, value=0, key="qtd_setores_infra")
                for i in range(qtd_setores):
                    st.markdown(f"**Setor {i+1}**")
                    st1, st2 = st.columns([1, 2])
                    setor_nome = st1.text_input(f"Nome do setor {i+1}:", key=f"setor_nome_{i}")
                    setor_info = st2.text_area(f"Informações Gerais {i+1}:", height=80, key=f"setor_info_{i}")
                    qtd_soft_setor = st.number_input(
                        f"Qtd softwares padrão do setor {i+1}:",
                        min_value=0,
                        max_value=30,
                        value=0,
                        key=f"setor_qtd_soft_{i}",
                    )
                    softwares_setor = []
                    for j in range(qtd_soft_setor):
                        sw1, sw2, sw3 = st.columns(3)
                        sw_nome = sw1.text_input(f"Software {j+1}:", key=f"setor_{i}_soft_nome_{j}")
                        sw_caminho_usado = sw2.text_input(f"Caminho utilizado {j+1}:", key=f"setor_{i}_soft_caminho_usado_{j}")
                        sw_caminho_sugerido = sw3.text_input(f"Caminho sugerido {j+1}:", key=f"setor_{i}_soft_caminho_sugerido_{j}")
                        sw4, sw5, sw6 = st.columns(3)
                        sw_config = sw4.text_area(f"Configuração de instalação {j+1}:", height=80, key=f"setor_{i}_soft_config_{j}")
                        sw_periodo = sw5.text_input(f"Período de atualização {j+1}:", key=f"setor_{i}_soft_periodo_{j}")
                        sw_site = sw6.text_input(f"Site de download {j+1}:", key=f"setor_{i}_soft_site_{j}")
                        if sw_nome or sw_caminho_usado or sw_caminho_sugerido or sw_config or sw_periodo or sw_site:
                            softwares_setor.append({
                                "software": sw_nome,
                                "caminho_utilizado": sw_caminho_usado,
                                "caminho_sugerido": sw_caminho_sugerido,
                                "configuracao_instalacao": sw_config,
                                "periodo_atualizacao": sw_periodo,
                                "site_download": sw_site,
                            })
                    if setor_nome or setor_info or softwares_setor:
                        setores_l.append({"nome": setor_nome, "informacoes": setor_info, "softwares": softwares_setor})

        if t_equipamentos:
            with t_equipamentos:
                st.subheader("Cadastro de Equipamentos")
                clientes_equip = buscar_clientes()
                nomes_equip = [cli["nome"] for cli in clientes_equip]
                funcionarios_equip = listar_funcionarios_sistema()
                origem_equip = st.radio("Origem do equipamento:", ["Empresa/cliente cadastrado", "Funcionário cadastrado"], horizontal=True, key="infra_eq_origem")
                cliente_eq_nome = ""
                cliente_eq_id = None
                funcionario_eq_usuario = ""
                funcionario_eq_nome = ""
                if origem_equip == "Empresa/cliente cadastrado":
                    cliente_eq_nome = st.selectbox("Cliente/empresa:", nomes_equip, key="infra_eq_cliente") if nomes_equip else ""
                    cliente_eq_id = next((cli.get("id") for cli in clientes_equip if cli.get("nome") == cliente_eq_nome), None)
                else:
                    labels_func = [f["label"] for f in funcionarios_equip]
                    funcionario_label = st.selectbox("Funcionário:", labels_func, key="infra_eq_funcionario") if labels_func else ""
                    funcionario_sel = next((f for f in funcionarios_equip if f["label"] == funcionario_label), None)
                    funcionario_eq_usuario = funcionario_sel.get("username", "") if funcionario_sel else ""
                    funcionario_eq_nome = funcionario_sel.get("nome", "") if funcionario_sel else ""

                eq1, eq2, eq3 = st.columns(3)
                tipo_eq = eq1.selectbox("Tipo de equipamento:", ["Desktop", "Notebook", "Impressora", "Servidor", "Roteador", "Switch", "DVR", "Câmera", "Outro"], key="infra_eq_tipo")
                nome_eq = eq2.text_input("Nome/modelo do equipamento:", key="infra_eq_nome")
                ip_eq = eq3.text_input("IP do equipamento:", key="infra_eq_ip")
                eq4, eq5 = st.columns([1, 2])
                quem_usa_eq = eq4.text_input("Quem usa o equipamento:", key="infra_eq_quem_usa")
                info_eq = eq5.text_area("Informações Gerais:", height=100, key="infra_eq_info")
                fotos_eq = st.file_uploader("Adicionar fotos do equipamento:", type=TIPOS_IMAGEM_UPLOAD, accept_multiple_files=True, key="infra_eq_fotos")

                if st.button("Salvar Equipamento", type="primary", width="stretch", key="btn_salvar_infra_eq"):
                    if not nome_eq.strip() and not ip_eq.strip():
                        st.error("Informe ao menos o nome/modelo ou o IP do equipamento.")
                    elif origem_equip == "Empresa/cliente cadastrado" and not cliente_eq_nome:
                        st.error("Selecione um cliente/empresa.")
                    elif origem_equip == "Funcionário cadastrado" and not funcionario_eq_usuario:
                        st.error("Selecione um funcionário.")
                    else:
                        arquivos_validos = True
                        for foto in fotos_eq or []:
                            if not upload_dentro_limite(foto):
                                erro_upload_grande("foto")
                                arquivos_validos = False
                                break
                        if arquivos_validos:
                            conn_eq = conectar_banco()
                            ceq = conn_eq.cursor()
                            agora_eq = datetime.now().strftime("%d/%m/%Y %H:%M")
                            ceq.execute(
                                """INSERT INTO infra_equipamentos
                                   (cliente_id, cliente_nome, funcionario_usuario, funcionario_nome, origem, tipo_equipamento, nome_equipamento, ip_equipamento, quem_usa, informacoes, criado_por, criado_em)
                                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                                (cliente_eq_id, cliente_eq_nome, funcionario_eq_usuario, funcionario_eq_nome, origem_equip, tipo_eq, nome_eq, ip_eq, quem_usa_eq, info_eq, st.session_state.get("username", ""), agora_eq),
                            )
                            equipamento_id = ceq.lastrowid
                            for foto in fotos_eq or []:
                                foto_dados, foto_nome, foto_mime = dados_upload(foto)
                                ceq.execute(
                                    """INSERT INTO infra_equipamentos_fotos
                                       (equipamento_id, foto_nome, foto_mime, foto, criado_em)
                                       VALUES (?,?,?,?,?)""",
                                    (equipamento_id, foto_nome, foto_mime, foto_dados, agora_eq),
                                )
                            conn_eq.commit()
                            conn_eq.close()
                            st.success("Equipamento salvo com sucesso.")
                            st.rerun()

                st.write("---")
                st.subheader("Equipamentos cadastrados")
                conn_eq = conectar_banco()
                ceq = conn_eq.cursor()
                ceq.execute("SELECT * FROM infra_equipamentos ORDER BY id DESC")
                equipamentos_rows = filtrar_registros_por_empresa(ceq.fetchall(), "cliente_nome")
                conn_eq.close()
                if equipamentos_rows:
                    clientes_filtro_eq = ["Todos"] + sorted({r.get("cliente_nome") or "" for r in equipamentos_rows if r.get("cliente_nome")})
                    filtro_eq_cliente = st.selectbox("Filtrar por cliente/empresa:", clientes_filtro_eq, key="infra_eq_filtro_cliente")
                    termo_eq = st.text_input("Buscar por equipamento/IP/usuário:", key="infra_eq_busca")
                    filtrados_eq = equipamentos_rows
                    if filtro_eq_cliente != "Todos":
                        filtrados_eq = [r for r in filtrados_eq if r.get("cliente_nome") == filtro_eq_cliente]
                    if termo_eq.strip():
                        termo = termo_eq.strip().lower()
                        filtrados_eq = [
                            r for r in filtrados_eq
                            if termo in " ".join(str(r.get(c) or "") for c in ["tipo_equipamento", "nome_equipamento", "ip_equipamento", "quem_usa", "informacoes"]).lower()
                        ]
                    linhas_equipamentos = [
                        {k: v for k, v in dict(eq).items() if k not in ("informacoes",)} for eq in filtrados_eq
                    ]
                    id_eq_clicado = tabela_clicavel_id(
                        st, linhas_equipamentos, "infra_equipamentos_grade", campo_id="id"
                    ) if linhas_equipamentos else None
                    if id_eq_clicado:
                        st.session_state["infra_eq_id_ativo"] = int(id_eq_clicado)
                    id_eq_ver = int(st.session_state.get("infra_eq_id_ativo") or 0)
                    eq_sel = next((dict(eq) for eq in equipamentos_rows if int(eq.get("id") or 0) == int(id_eq_ver)), None)
                    if eq_sel:
                        with st.expander(f"Consultar/editar equipamento #{id_eq_ver}", expanded=True):
                            eqe1, eqe2 = st.columns(2)
                            edit_eq_cliente = eqe1.text_input("Cliente/empresa:", value=eq_sel.get("cliente_nome") or "", key=f"infra_eq_edit_cliente_{id_eq_ver}")
                            edit_eq_funcionario = eqe2.text_input("Funcionário:", value=eq_sel.get("funcionario_nome") or eq_sel.get("funcionario_usuario") or "", key=f"infra_eq_edit_func_{id_eq_ver}")
                            eqe3, eqe4, eqe5 = st.columns(3)
                            edit_eq_tipo = eqe3.text_input("Tipo:", value=eq_sel.get("tipo_equipamento") or "", key=f"infra_eq_edit_tipo_{id_eq_ver}")
                            edit_eq_nome = eqe4.text_input("Equipamento:", value=eq_sel.get("nome_equipamento") or "", key=f"infra_eq_edit_nome_{id_eq_ver}")
                            edit_eq_ip = eqe5.text_input("IP:", value=eq_sel.get("ip_equipamento") or "", key=f"infra_eq_edit_ip_{id_eq_ver}")
                            edit_eq_quem_usa = st.text_input("Quem usa:", value=eq_sel.get("quem_usa") or "", key=f"infra_eq_edit_usa_{id_eq_ver}")
                            edit_eq_info = st.text_area("Informações Gerais:", value=eq_sel.get("informacoes") or "", key=f"infra_eq_edit_info_{id_eq_ver}")
                            if st.button("Salvar alterações do equipamento", type="primary", width="stretch", key=f"infra_eq_salvar_{id_eq_ver}"):
                                conn_edit_eq = conectar_banco()
                                cedit_eq = conn_edit_eq.cursor()
                                cedit_eq.execute(
                                    """UPDATE infra_equipamentos SET cliente_nome=?, funcionario_nome=?, tipo_equipamento=?,
                                       nome_equipamento=?, ip_equipamento=?, quem_usa=?, informacoes=? WHERE id=?""",
                                    (edit_eq_cliente, edit_eq_funcionario, edit_eq_tipo, edit_eq_nome,
                                     edit_eq_ip, edit_eq_quem_usa, edit_eq_info, id_eq_ver),
                                )
                                conn_edit_eq.commit()
                                conn_edit_eq.close()
                                st.success("Equipamento atualizado.")
                                st.rerun()
                            conn_feq = conectar_banco()
                            cfeq = conn_feq.cursor()
                            cfeq.execute("SELECT foto_nome, foto FROM infra_equipamentos_fotos WHERE equipamento_id=? ORDER BY id", (id_eq_ver,))
                            fotos_salvas = cfeq.fetchall()
                            conn_feq.close()
                            if fotos_salvas:
                                cols_fotos = st.columns(3)
                                for idx_foto, foto in enumerate(fotos_salvas):
                                    with cols_fotos[idx_foto % 3]:
                                        st.image(foto.get("foto"), caption=foto.get("foto_nome") or "Foto", width=220)
                            else:
                                st.info("Nenhuma foto cadastrada para este equipamento.")
                    else:
                        st.caption("Clique em qualquer informação do equipamento para consultar ou editar.")
                    if tem_permissao("infra.delete") and eq_sel:
                        if st.button("Excluir Equipamento", key="infra_eq_excluir"):
                            conn_del_eq = conectar_banco()
                            cdel_eq = conn_del_eq.cursor()
                            cdel_eq.execute("DELETE FROM infra_equipamentos_fotos WHERE equipamento_id=?", (id_eq_ver,))
                            cdel_eq.execute("DELETE FROM infra_equipamentos WHERE id=?", (id_eq_ver,))
                            conn_del_eq.commit()
                            conn_del_eq.close()
                            st.success("Equipamento excluído.")
                            st.rerun()
                else:
                    st.info("Nenhum equipamento cadastrado.")

        hospedagem_l = []
        if t_hospedagem:
            with t_hospedagem:
                st.subheader("Hospedagem e Domínio")
                qtd_hospedagem = st.number_input("Qtd Hospedagens/Domínios:", min_value=0, max_value=30, value=0, key="qtd_hospedagem")
                for i in range(qtd_hospedagem):
                    st.markdown(f"**Hospedagem/Domínio {i+1}**")
                    hp1, hp2 = st.columns(2)
                    hosp_provedor = hp1.text_input(f"Nome do Provedor {i+1}:", key=f"hosp_provedor_{i}")
                    hosp_site = hp2.text_input(f"Site do Provedor {i+1}:", key=f"hosp_site_{i}")
                    hp3, hp4 = st.columns(2)
                    hosp_login = hp3.text_input(f"Login Hospedagem {i+1}:", key=f"hosp_login_{i}")
                    hosp_senha = hp4.text_input(f"Senha Hospedagem {i+1}:", type="password", key=f"hosp_senha_{i}")
                    hp5, hp6 = st.columns([1, 2])
                    hosp_2fa = hp5.selectbox(f"Autenticação 2 Fatores? {i+1}:", ["Não", "Sim"], key=f"hosp_2fa_{i}")
                    hosp_local_2fa = hp6.text_input(f"Local de Autenticação 2 Fatores {i+1}:", key=f"hosp_local_2fa_{i}")

                    st.markdown("**Dados do Domínio**")
                    dominio_registro_opts = ["Registro.br", "Outro"]
                    hd1, hd2, hd3 = st.columns(3)
                    dominio_registro_tipo = hd1.selectbox(f"Onde está registrado {i+1}:", dominio_registro_opts, key=f"dom_registro_tipo_{i}")
                    dominio_registro_outro = ""
                    if dominio_registro_tipo == "Outro":
                        dominio_registro_outro = hd1.text_input(f"Outro registro {i+1}:", key=f"dom_registro_outro_{i}")
                    dominio_registro = dominio_registro_outro or dominio_registro_tipo
                    dominio_site = hd2.text_input(f"Site onde está registrado {i+1}:", key=f"dom_site_{i}")
                    dominio_nome = hd3.text_input(f"Domínio {i+1}:", key=f"dom_nome_{i}")
                    hd4, hd5 = st.columns(2)
                    dominio_login = hd4.text_input(f"Login Domínio {i+1}:", key=f"dom_login_{i}")
                    dominio_senha = hd5.text_input(f"Senha Domínio {i+1}:", type="password", key=f"dom_senha_{i}")
                    hd6, hd7 = st.columns([1, 2])
                    dominio_2fa = hd6.selectbox(f"Domínio pede 2FA? {i+1}:", ["Não", "Sim"], key=f"dom_2fa_{i}")
                    dominio_local_2fa = hd7.text_input(f"Local de Autenticação 2 Fatores do Domínio {i+1}:", key=f"dom_local_2fa_{i}")

                    if any([
                        hosp_provedor, hosp_site, hosp_login, hosp_senha, hosp_local_2fa,
                        dominio_nome, dominio_registro, dominio_site, dominio_login, dominio_senha, dominio_local_2fa,
                    ]):
                        hospedagem_l.append(
                            " | ".join([
                                f"Provedor: {hosp_provedor}",
                                f"Site Provedor: {hosp_site}",
                                f"Login Hospedagem: {hosp_login}",
                                f"Senha Hospedagem: {hosp_senha}",
                                f"2FA Hospedagem: {hosp_2fa}",
                                f"Local 2FA Hospedagem: {hosp_local_2fa}",
                                f"Domínio: {dominio_nome}",
                                f"Registrado em: {dominio_registro}",
                                f"Site Registro Domínio: {dominio_site}",
                                f"Login Domínio: {dominio_login}",
                                f"Senha Domínio: {dominio_senha}",
                                f"2FA Domínio: {dominio_2fa}",
                                f"Local 2FA Domínio: {dominio_local_2fa}",
                            ])
                        )

        aplicativos_l = []
        emails_infra_para_salvar = []
        if t_emails_infra:
            with t_emails_infra:
                st.subheader("Gestão de E-mails")
                mensagem_email = st.session_state.pop("infra_email_mensagem", None)
                if mensagem_email:
                    st.success(mensagem_email)
                cliente_email_infra = inf_vinc if inf_vinc != "-- Selecionar Cliente Existente --" else (inf_fan or inf_emp or "-- Avulso --")
                st.caption(f"As contas salvas aqui ficam vinculadas a: {cliente_email_infra}")
                emails_existentes_infra = buscar_emails_para_empresa(cliente_email_infra, inf_fan, inf_emp, inf_email)
                if emails_existentes_infra:
                    st.markdown("**E-mails já cadastrados para este cliente**")
                    pesquisa_email_infra = st.text_input(
                        "Pesquisar e-mail salvo:",
                        placeholder="E-mail, funcionário, provedor, alias ou configuração",
                        key=f"infra_pesquisa_email_{infra_cliente_key}",
                    ).strip().casefold()
                    emails_filtrados_infra = [
                        email_item for email_item in emails_existentes_infra
                        if not pesquisa_email_infra or pesquisa_email_infra in " ".join(
                            str(valor or "") for valor in email_item.values()
                        ).casefold()
                    ]
                    linhas_email_infra = [
                        {
                            "ID": email_item.get("id"),
                            "Funcionário": email_item.get("funcionario"),
                            "E-mail": email_item.get("email"),
                            "Aliases": email_item.get("aliases"),
                            "Provedor": email_item.get("provedor"),
                            "Entrada": email_item.get("config_entrada"),
                            "Saída": email_item.get("config_saida"),
                            "Capacidade": email_item.get("capacidade"),
                        }
                        for email_item in emails_filtrados_infra
                    ]
                    email_clicado_id = tabela_clicavel_id(
                        st, linhas_email_infra,
                        f"infra_grade_emails_{infra_cliente_key}_{st.session_state.get('infra_email_grade_versao', 0)}",
                        campo_id="ID",
                    ) if linhas_email_infra else None
                    if email_clicado_id:
                        abrir_email_infraestrutura(st.session_state, email_clicado_id)
                        st.rerun()

                    ids_email_infra = ids_emails_cadastrados(emails_existentes_infra)
                    if ids_email_infra and tem_permissao("emails.delete"):
                        with st.expander("Apagar todos os e-mails cadastrados deste cliente", expanded=False):
                            st.warning(
                                f"Esta ação apagará permanentemente {len(ids_email_infra)} conta(s) de e-mail "
                                f"encontrada(s) para {cliente_email_infra}. Os demais dados da infraestrutura não serão alterados."
                            )
                            confirmar_exclusao_emails = st.checkbox(
                                "Confirmo que desejo apagar todas essas contas de e-mail.",
                                key=f"infra_confirmar_excluir_emails_{infra_cliente_key}",
                            )
                            if st.button(
                                "Apagar todos os e-mails deste cliente",
                                type="primary",
                                width="stretch",
                                disabled=not confirmar_exclusao_emails,
                                key=f"infra_excluir_todos_emails_{infra_cliente_key}",
                            ):
                                conn_excluir_emails = conectar_banco()
                                try:
                                    cursor_excluir_emails = conn_excluir_emails.cursor()
                                    placeholders_exclusao = ",".join(["?"] * len(ids_email_infra))
                                    cursor_excluir_emails.execute(
                                        f"DELETE FROM emails_clientes WHERE id IN ({placeholders_exclusao})",
                                        tuple(ids_email_infra),
                                    )
                                    conn_excluir_emails.commit()
                                finally:
                                    conn_excluir_emails.close()
                                registrar_evento_sistema(
                                    "delete", "emails_clientes", ",".join(map(str, ids_email_infra)),
                                    cliente_email_infra,
                                    {"evento": "Exclusão de todos os e-mails do cliente", "quantidade": len(ids_email_infra)},
                                )
                                fechar_email_infraestrutura(st.session_state)
                                st.session_state["infra_email_mensagem"] = (
                                    f"{len(ids_email_infra)} conta(s) de e-mail apagada(s). "
                                    "As demais informações da infraestrutura foram mantidas."
                                )
                                st.rerun()

                    email_editar_id = st.session_state.get("infra_email_editar_id")
                    email_editar = next(
                        (item for item in emails_existentes_infra if int(item.get("id") or 0) == int(email_editar_id or 0)),
                        None,
                    )
                    if email_editar:
                        with st.expander(f"Editando: {email_editar.get('email')}", expanded=True):
                            ee1, ee2, ee3 = st.columns(3)
                            edit_em_func = ee1.text_input("Usuário / Funcionário:", value=email_editar.get("funcionario") or "", key=f"infra_edit_em_func_{email_editar_id}")
                            edit_em_email = ee2.text_input("E-mail:", value=email_editar.get("email") or "", key=f"infra_edit_em_email_{email_editar_id}")
                            if pode_visualizar_senhas_infra:
                                senha_email_salva = buscar_senha_email_selecionado(
                                    conectar_banco, email_editar, pode_visualizar_senhas_infra
                                )
                                edit_em_senha = ee3.text_input(
                                    "Senha cadastrada (use o olho para visualizar):",
                                    value=senha_email_salva,
                                    type="password",
                                    key=f"infra_edit_em_senha_carregada_{email_editar_id}_{st.session_state.get('infra_email_grade_versao', 0)}",
                                )
                                if not senha_email_salva:
                                    ee3.caption("Este registro está sem senha salva. Informe a senha e salve as alterações.")
                            else:
                                edit_em_senha = ee3.text_input(
                                    "Nova senha (vazio mantém a atual):",
                                    type="password",
                                    key=f"infra_edit_em_senha_{email_editar_id}",
                                )
                                ee3.caption("Visualização bloqueada pela permissão do usuário. É possível definir uma nova senha sem ver a atual.")
                            ee4, ee5, ee6 = st.columns(3)
                            edit_em_aliases = ee4.text_input("Aliases:", value=email_editar.get("aliases") or "", key=f"infra_edit_em_aliases_{email_editar_id}")
                            edit_em_provedor = ee5.text_input("Provedor:", value=email_editar.get("provedor") or "", key=f"infra_edit_em_provedor_{email_editar_id}")
                            edit_em_capacidade = ee6.text_input("Capacidade:", value=email_editar.get("capacidade") or "", key=f"infra_edit_em_capacidade_{email_editar_id}")
                            ee7, ee8 = st.columns(2)
                            edit_em_entrada = ee7.text_input("Entrada (IMAP/POP):", value=email_editar.get("config_entrada") or "", key=f"infra_edit_em_entrada_{email_editar_id}")
                            edit_em_saida = ee8.text_input("Saída (SMTP):", value=email_editar.get("config_saida") or "", key=f"infra_edit_em_saida_{email_editar_id}")
                            salvar_email_col, cancelar_email_col = st.columns(2)
                            if salvar_email_col.button("Salvar alterações do e-mail", type="primary", width="stretch", key=f"infra_salvar_email_{email_editar_id}"):
                                if not edit_em_email.strip():
                                    st.error("Informe o endereço de e-mail.")
                                else:
                                    conn_edit_em = conectar_banco()
                                    cedit_em = conn_edit_em.cursor()
                                    if edit_em_senha:
                                        cedit_em.execute(
                                            """UPDATE emails_clientes SET funcionario=?, email=?, senha=?, aliases=?, provedor=?,
                                               config_entrada=?, config_saida=?, capacidade=? WHERE id=?""",
                                            (edit_em_func, edit_em_email, edit_em_senha, edit_em_aliases, edit_em_provedor,
                                             edit_em_entrada, edit_em_saida, edit_em_capacidade, email_editar_id),
                                        )
                                    else:
                                        cedit_em.execute(
                                            """UPDATE emails_clientes SET funcionario=?, email=?, aliases=?, provedor=?,
                                               config_entrada=?, config_saida=?, capacidade=? WHERE id=?""",
                                            (edit_em_func, edit_em_email, edit_em_aliases, edit_em_provedor,
                                             edit_em_entrada, edit_em_saida, edit_em_capacidade, email_editar_id),
                                        )
                                    conn_edit_em.commit()
                                    conn_edit_em.close()
                                    fechar_email_infraestrutura(st.session_state)
                                    st.session_state["infra_email_mensagem"] = "E-mail atualizado com sucesso."
                                    st.rerun()
                            if cancelar_email_col.button("Cancelar edição", width="stretch", key=f"infra_cancelar_email_{email_editar_id}"):
                                fechar_email_infraestrutura(st.session_state)
                                st.rerun()
                    fora_do_vinculo = [e for e in emails_existentes_infra if (e.get("cliente_vinculado") or "") != cliente_email_infra]
                    if fora_do_vinculo and cliente_email_infra != "-- Avulso --":
                        st.warning("Alguns e-mails foram encontrados pelo domínio ou outro nome, mas ainda não estão vinculados a esta empresa.")
                        if st.button("Vincular e-mails encontrados a esta empresa", width="stretch", key="infra_vincular_emails_empresa"):
                            conn_vinc_em = conectar_banco()
                            cvinc_em = conn_vinc_em.cursor()
                            placeholders = ",".join(["?"] * len(ids_email_infra))
                            cvinc_em.execute(
                                f"UPDATE emails_clientes SET cliente_vinculado=? WHERE id IN ({placeholders})",
                                tuple([cliente_email_infra] + ids_email_infra),
                            )
                            conn_vinc_em.commit()
                            conn_vinc_em.close()
                            st.success("E-mails vinculados à empresa.")
                            st.rerun()
                else:
                    st.info("Nenhum e-mail cadastrado para este cliente ainda.")

                versao_novos_emails = st.session_state.get("infra_novos_emails_versao", 0)
                mostrar_novos_emails = st.toggle(
                    "Adicionar novas contas de e-mail",
                    key=f"infra_adicionar_emails_{versao_novos_emails}",
                )
                if mostrar_novos_emails:
                    with st.container(border=True):
                        qtd_emails_infra = st.number_input(
                            "Qtd contas de e-mail:", min_value=1, max_value=30, value=1,
                            key=f"infra_qtd_emails_{versao_novos_emails}",
                        )
                        for i in range(qtd_emails_infra):
                            st.markdown(f"**Conta de E-mail {i+1}**")
                            em1, em2, em3 = st.columns(3)
                            em_func = em1.text_input(f"Usuário / Funcionário {i+1}:", key=f"infra_em_func_{versao_novos_emails}_{i}")
                            em_email = em2.text_input(f"E-mail {i+1}:", key=f"infra_em_email_{versao_novos_emails}_{i}")
                            em_senha = em3.text_input(f"Senha {i+1}:", type="password", key=f"infra_em_senha_{versao_novos_emails}_{i}")
                            em4, em5, em6 = st.columns(3)
                            em_aliases = em4.text_input(f"Aliases {i+1}:", key=f"infra_em_aliases_{versao_novos_emails}_{i}")
                            em_provedor = em5.text_input(f"Provedor {i+1}:", key=f"infra_em_provedor_{versao_novos_emails}_{i}")
                            em_capacidade = em6.text_input(f"Capacidade {i+1}:", key=f"infra_em_capacidade_{versao_novos_emails}_{i}")
                            em7, em8 = st.columns(2)
                            em_entrada = em7.text_input(f"Entrada (IMAP/POP) {i+1}:", key=f"infra_em_entrada_{versao_novos_emails}_{i}")
                            em_saida = em8.text_input(f"Saída (SMTP) {i+1}:", key=f"infra_em_saida_{versao_novos_emails}_{i}")
                            if em_email:
                                emails_infra_para_salvar.append(
                                    (cliente_email_infra, em_func, em_email, em_senha, em_aliases, em_provedor, em_entrada, em_saida, em_capacidade)
                                )

        if t_apps:
            with t_apps:
                qtd_apps = st.number_input("Qtd Aplicativos/Sistemas:", min_value=0, max_value=50, value=0)
                for i in range(qtd_apps):
                    ca1, ca2, ca3 = st.columns(3)
                    app_nome = ca1.text_input(f"Nome do sistema {i+1}:", key=f"appnome_{i}")
                    app_operador = ca2.text_input(f"Operador {i+1}:", key=f"appoperador_{i}")
                    app_email = ca3.text_input(f"E-mail {i+1}:", key=f"appemail_{i}")
                    ca4, ca5 = st.columns(2)
                    app_login = ca4.text_input(f"Login {i+1}:", key=f"applogin_{i}")
                    app_senha = ca5.text_input(f"Senha {i+1}:", type="password", key=f"appsenha_{i}")
                    if app_nome or app_operador or app_email or app_login or app_senha:
                        aplicativos_l.append(f"Sistema: {app_nome} | Operador: {app_operador} | E-mail: {app_email} | Login: {app_login} | Senha: {app_senha}")

        with t_sys:
            st.divider()
            renderizar_historico_tecnico("sistemas", "Sistemas", [
                ("sys_dados", "Dados", "|"), ("sys_serial", "Serial", "|"),
                ("sys_cod", "Código do cliente", "|"), ("sys_adm", "Login administrativo", "|"),
                ("sys_senha", "Senha administrativa", "|"), ("sys_sec", "Login secundário", "|"),
            ])
        with t_rede:
            st.divider()
            renderizar_historico_tecnico("rede", "Redes", [
                ("rede_prov", "Provedor", "|"), ("rede_ip", "IP", "|"),
                ("rede_log", "Login", "|"), ("rede_sen", "Senha", "|"),
            ])
            renderizar_historico_tecnico("faixas_ip", "Faixas de IP", [("faixas_ip", "Informações", "||")])
        with t_dvr:
            st.divider()
            renderizar_historico_tecnico("dvrs", "DVRs", [("dvr_acessos", "Informações", "||")])
        with t_cam:
            st.divider()
            renderizar_historico_tecnico("cameras", "Câmeras", [("cameras_acessos", "Informações", "||")])
        with t_alarme:
            st.divider()
            renderizar_historico_tecnico("alarmes", "Alarmes", [("alarmes_acessos", "Informações", "||")])
        with t_wifi:
            st.divider()
            renderizar_historico_tecnico("wifi", "Redes Wi-Fi", [
                ("rede_wire", "SSID", "|"), ("rede_wsen", "Senha", "|"),
            ])
        with t_serv:
            st.divider()
            renderizar_historico_tecnico("servidores", "Servidores", [
                ("serv_nome", "Nome", "|"), ("serv_ip", "IP", "|"),
                ("serv_link", "No-IP", "|"), ("serv_log", "Login", "|"),
                ("serv_sen", "Senha", "|"), ("serv_anydesk", "AnyDesk", "||"),
                ("serv_radmin", "Radmin", "||"), ("serv_google_remote", "Google Remote", "|"),
                ("serv_info_gerais", "Informações gerais", "||"), ("cert_log", "Gerencia DHCP", "|"),
            ])
            renderizar_historico_tecnico("pfsense", "PfSense", [("pfsense_acessos", "Informações", "||")])
            renderizar_historico_tecnico("vpn", "VPN", [("vpn_acessos", "Informações", "||")])
        with t_impressoras:
            st.divider()
            renderizar_historico_tecnico("impressoras", "Impressoras", [("impressoras_acessos", "Informações", "||")])
        with t_antivirus:
            st.divider()
            renderizar_historico_tecnico("antivirus", "Antivírus", [("antivirus_acessos", "Informações", "||")])
        with t_fin:
            st.divider()
            renderizar_historico_tecnico("financeiro", "Acessos financeiros", [
                ("fin_b1", "Banco 1", "||"), ("fin_b2", "Banco 2", "||"), ("fin_b3", "Banco 3", "||"),
            ])
        with t_pcs:
            st.divider()
            renderizar_historico_tecnico("pcs", "PCs e Acessos", [("pcs_acessos", "Informações", "||")])
        if t_setores:
            with t_setores:
                st.divider()
                renderizar_historico_setores()
        if t_hospedagem:
            with t_hospedagem:
                st.divider()
                renderizar_historico_tecnico("hospedagem", "Hospedagens e Domínios", [("hospedagem_acessos", "Informações", "||")])
        if t_apps:
            with t_apps:
                st.divider()
                renderizar_historico_tecnico("aplicativos", "Aplicativos", [("aplicativos_acessos", "Informações", "||")])

        ficha_base_salvar = infra_editando or infra_historico_ficha
        rotulo_salvar_infra = "Salvar alterações da ficha" if ficha_base_salvar else "Salvar Ficha de Infraestrutura"
        if st.button(rotulo_salvar_infra, type="primary", width="stretch"):
            if inf_vinc != "-- Selecionar Cliente Existente --" or inf_fan:
                for foto_item in fotos_infra_itens:
                    if not upload_dentro_limite(foto_item["arquivo"]):
                        erro_upload_grande("foto")
                        st.stop()
                conn = conectar_banco()
                c = conn.cursor()
                dados_infra_salvar = {
                    "cliente_vinc": inf_vinc,
                    "fantasia": inf_fan,
                    "razao": inf_emp,
                    "cnpj": inf_cnpj,
                    "endereco": inf_end,
                    "contato": inf_cont,
                    "email_prin": inf_email,
                    "tel_prin": inf_t1,
                    "tel_prov": inf_t2,
                    "contrato_data": inf_contr,
                    "pagto": inf_pag,
                    "venc": inf_venc,
                    "sys_dados": "|".join(sys_dados_l),
                    "sys_serial": "|".join(sys_ser_l),
                    "sys_cod": "|".join(sys_cod_l),
                    "sys_adm": "|".join(sys_adm_l),
                    "sys_senha": "|".join(sys_sen_l),
                    "sys_sec": "|".join(sys_sec_l),
                    "rede_prov": "|".join(r_pro_l),
                    "rede_ip": "|".join(r_ip_l),
                    "rede_log": "|".join(r_log_l),
                    "rede_sen": "|".join(r_sen_l),
                    "rede_ddns": "|".join(r_ddns_l),
                    "rede_dsen": "|".join(r_dsen_l),
                    "rede_wire": "|".join(r_wir_l),
                    "rede_wsen": "|".join(r_wsen_l),
                    "serv_nome": "|".join(sv_nom_l),
                    "serv_ip": "|".join(sv_ip_l),
                    "serv_link": "|".join(sv_link_l),
                    "serv_log": "|".join(sv_log_l),
                    "serv_sen": "|".join(sv_sen_l),
                    "serv_anydesk": "||".join(sv_anydesk_l),
                    "serv_radmin": "||".join(sv_radmin_l),
                    "serv_google_remote": "|".join(sv_google_remote_l),
                    "serv_info_gerais": "||".join(sv_info_gerais_l),
                    "impressoras_acessos": "||".join(impressoras_l),
                    "cert_log": "|".join(ct_log_l),
                    "cert_sen": "|".join(ct_sen_l),
                    "fin_b1": fin_l[0],
                    "fin_b2": fin_l[1],
                    "fin_b3": fin_l[2],
                    "pcs_acessos": "||".join(pcs_l),
                    "dvr_acessos": "||".join(dvr_l),
                    "cameras_acessos": "||".join(cameras_l),
                    "alarmes_acessos": "||".join(alarmes_l),
                    "aplicativos_acessos": "||".join(aplicativos_l),
                    "pfsense_acessos": "||".join(pfsense_l),
                    "antivirus_acessos": "||".join(antivirus_l),
                    "faixas_ip": "||".join(faixas_ip_l),
                    "vpn_acessos": "||".join(vpn_l),
                    "hospedagem_acessos": "||".join(hospedagem_l),
                    "setores": preparar_setores(setores_l),
                }
                colunas_infra_salvar = list(dados_infra_salvar.keys())
                if ficha_base_salvar:
                    # Os campos técnicos desta tela são para adicionar registros. Nunca
                    # substituímos o histórico existente ao preencher apenas um novo item.
                    dados_infra_salvar.update(anexar_grupo_infra(ficha_base_salvar, {
                        "sys_dados": sys_dados_l, "sys_serial": sys_ser_l, "sys_cod": sys_cod_l,
                        "sys_adm": sys_adm_l, "sys_senha": sys_sen_l, "sys_sec": sys_sec_l,
                    }))
                    dados_infra_salvar.update(anexar_grupo_infra(ficha_base_salvar, {
                        "rede_prov": r_pro_l, "rede_ip": r_ip_l,
                        "rede_log": r_log_l, "rede_sen": r_sen_l,
                    }))
                    dados_infra_salvar.update(anexar_grupo_infra(ficha_base_salvar, {
                        "rede_wire": r_wir_l, "rede_wsen": r_wsen_l,
                    }))
                    dados_infra_salvar.update(anexar_grupo_infra(
                        ficha_base_salvar,
                        {
                            "serv_nome": sv_nom_l, "serv_ip": sv_ip_l, "serv_link": sv_link_l,
                            "serv_log": sv_log_l, "serv_sen": sv_sen_l,
                            "serv_anydesk": sv_anydesk_l, "serv_radmin": sv_radmin_l,
                            "serv_google_remote": sv_google_remote_l,
                            "serv_info_gerais": sv_info_gerais_l,
                            "cert_log": ct_log_l, "cert_sen": ct_sen_l,
                        },
                        {"serv_anydesk": "||", "serv_radmin": "||", "serv_info_gerais": "||"},
                    ))
                    for coluna, novos, separador in (
                        ("dvr_acessos", dvr_l, "||"), ("cameras_acessos", cameras_l, "||"),
                        ("alarmes_acessos", alarmes_l, "||"), ("impressoras_acessos", impressoras_l, "||"),
                        ("pcs_acessos", pcs_l, "||"), ("aplicativos_acessos", aplicativos_l, "||"),
                        ("pfsense_acessos", pfsense_l, "||"), ("antivirus_acessos", antivirus_l, "||"),
                        ("faixas_ip", faixas_ip_l, "||"), ("vpn_acessos", vpn_l, "||"),
                        ("hospedagem_acessos", hospedagem_l, "||"),
                    ):
                        dados_infra_salvar[coluna] = anexar_itens_infra(
                            ficha_base_salvar.get(coluna), novos, separador
                        )
                    # Campos legados de DVR não podem ser remontados a partir do novo formulário.
                    dados_infra_salvar["rede_ddns"] = ficha_base_salvar.get("rede_ddns") or ""
                    dados_infra_salvar["rede_dsen"] = ficha_base_salvar.get("rede_dsen") or ""
                    bancos_existentes = [
                        str(ficha_base_salvar.get(campo) or "").strip()
                        for campo in ("fin_b1", "fin_b2", "fin_b3")
                        if str(ficha_base_salvar.get(campo) or "").strip()
                    ]
                    bancos_mesclados = (bancos_existentes + [str(valor).strip() for valor in fin_l if str(valor).strip()])[:3]
                    for indice, campo in enumerate(("fin_b1", "fin_b2", "fin_b3")):
                        dados_infra_salvar[campo] = bancos_mesclados[indice] if indice < len(bancos_mesclados) else ""
                    dados_infra_salvar["setores"] = anexar_setores_infra(
                        ficha_base_salvar.get("setores"), setores_l
                    )
                    campos_identificacao = {
                        "cliente_vinc", "fantasia", "razao", "cnpj", "endereco", "contato",
                        "email_prin", "tel_prin", "tel_prov", "contrato_data", "pagto", "venc",
                    }
                    for coluna in campos_identificacao:
                        if dados_infra_salvar[coluna] in (None, "", "-- Selecionar Cliente Existente --"):
                            dados_infra_salvar[coluna] = ficha_base_salvar.get(coluna) or ""
                    set_sql_infra = ", ".join([f"{col}=?" for col in colunas_infra_salvar])
                    c.execute(
                        f"UPDATE infra_v4 SET {set_sql_infra} WHERE id=?",
                        tuple(dados_infra_salvar[col] for col in colunas_infra_salvar) + (ficha_base_salvar.get("id"),),
                    )
                    ficha_id = ficha_base_salvar.get("id")
                else:
                    placeholders_infra = ",".join(["?"] * len(colunas_infra_salvar))
                    c.execute(
                        f"INSERT INTO infra_v4 ({','.join(colunas_infra_salvar)}) VALUES ({placeholders_infra})",
                        tuple(dados_infra_salvar[col] for col in colunas_infra_salvar),
                    )
                    ficha_id = c.lastrowid
                for foto_item in fotos_infra_itens:
                    foto_dados, foto_nome, foto_mime = dados_upload(foto_item["arquivo"])
                    c.execute(
                        """INSERT INTO infra_item_fotos
                           (ficha_id, tipo_item, item_indice, item_nome, foto_nome, foto_mime, foto, criado_em)
                           VALUES (?,?,?,?,?,?,?,?)""",
                        (ficha_id, foto_item["tipo"], foto_item["indice"], foto_item["nome"], foto_nome,
                         foto_mime, foto_dados, datetime.now().strftime("%d/%m/%Y %H:%M")),
                    )
                for conta_email in emails_infra_para_salvar:
                    c.execute(
                        """INSERT INTO emails_clientes
                           (cliente_vinculado, funcionario, email, senha, aliases, provedor, config_entrada, config_saida, capacidade)
                           VALUES (?,?,?,?,?,?,?,?,?)""",
                        conta_email,
                    )
                conn.commit()
                conn.close()
                fechar_novos_emails_infraestrutura(st.session_state)
                if ficha_base_salvar:
                    st.session_state.pop("infra_editar_id", None)
                    st.success("Ficha atualizada com sucesso!")
                else:
                    st.success("Ficha Salva com Sucesso!")
                st.rerun()
            else: 
                st.error("Insira ao menos a Razão Social/Fantasia ou vincule um cliente.")

    with aba2:
        st.subheader("Base de Infraestrutura Cadastrada")
        conn = conectar_banco()
        c = conn.cursor(dictionary=True)
        c.execute('SELECT * FROM infra_v4 ORDER BY id DESC')
        rows = c.fetchall()
        conn.close()
        rows = filtrar_registros_por_empresa(rows, "cliente_vinc", "fantasia", "razao")

        pesquisa_infra = st.text_input(
            "Pesquisar em toda a infraestrutura:",
            placeholder="Cliente, equipamento, IP, sistema, e-mail, servidor, setor ou qualquer informação salva",
            key="infra_pesquisa_geral",
        ).strip().casefold()
        rows_filtradas = [
            row for row in rows
            if not pesquisa_infra or pesquisa_infra in " ".join(
                str(valor or "") for chave, valor in row.items()
                if chave not in {"foto"}
            ).casefold()
        ]
        linhas_infra = [
            {
                "ID": row.get("id"),
                "Cliente": row.get("cliente_vinc") or row.get("fantasia") or row.get("razao"),
                "Fantasia": row.get("fantasia"),
                "Razão social": row.get("razao"),
                "Contato": row.get("contato"),
                "Telefone": row.get("tel_prin"),
                "E-mail": row.get("email_prin"),
            }
            for row in rows_filtradas
        ]
        ficha_clicada_id = tabela_clicavel_id(
            st, linhas_infra,
            f"infra_historico_grade_{st.session_state.get('infra_grade_versao', 0)}",
            campo_id="ID"
        ) if linhas_infra else None
        if ficha_clicada_id:
            if tem_permissao("infra.edit"):
                abrir_ficha_infraestrutura(st.session_state, ficha_clicada_id)
                st.rerun()
            else:
                ficha_consulta = next(
                    (row for row in rows_filtradas if int(row.get("id") or 0) == int(ficha_clicada_id)),
                    None,
                )
                if ficha_consulta:
                    with st.expander(f"Ficha #{ficha_clicada_id} — Identificação", expanded=True):
                        for campo, titulo in (
                            ("cliente_vinc", "Cliente"), ("fantasia", "Fantasia"),
                            ("razao", "Razão social"), ("cnpj", "CNPJ/CPF"),
                            ("endereco", "Endereço"), ("contato", "Contato"),
                            ("tel_prin", "Telefone"), ("email_prin", "E-mail"),
                        ):
                            st.write(f"**{titulo}:** {ficha_consulta.get(campo) or 'Não informado'}")
        if not rows:
            st.info("Nenhuma ficha encontrada.")
        elif not linhas_infra:
            st.warning("Nenhuma ficha contém o texto pesquisado.")
        else:
            st.caption("Clique em qualquer informação da ficha para abrir a edição completa.")
        
        acoes_inf = []
        if tem_permissao("infra.edit"): acoes_inf.append("Editar Ficha Completa")
        if tem_permissao("infra.delete"): acoes_inf.append("Excluir Ficha")
        
        if acoes_inf:
            st.write("---")
            a_inf = st.radio("Ação:", acoes_inf, horizontal=True, key="infra_acao_ficha")
            if ficha_clicada_id and tem_permissao("infra.edit"):
                a_inf = "Editar Ficha Completa"
            elif a_inf == "Editar Ficha Completa" and not st.session_state.get("infra_item_editar_id"):
                # A consulta deve permanecer limpa até o usuário escolher uma ficha.
                a_inf = ""
            if a_inf == "Excluir Ficha":
                id_di = st.number_input("ID para excluir:", min_value=1, step=1, key="del_inf_id")
                if st.button("Excluir Definitivamente", key="btn_d_inf"): 
                    conn_del_fotos = conectar_banco()
                    cdel_fotos = conn_del_fotos.cursor()
                    cdel_fotos.execute("DELETE FROM infra_item_fotos WHERE ficha_id=?", (id_di,))
                    conn_del_fotos.commit()
                    conn_del_fotos.close()
                    deletar_registro('infra_v4', 'id', id_di)
                    st.success("Ficha excluída com sucesso.")
                    st.rerun()
                    
            elif a_inf == "Editar Ficha Completa":
                ids_infra_disponiveis = [int(row.get("id")) for row in rows_filtradas if row.get("id")]
                id_salvo_edicao = int(st.session_state.get("infra_item_editar_id") or 0)
                if id_salvo_edicao not in ids_infra_disponiveis and ids_infra_disponiveis:
                    id_salvo_edicao = ids_infra_disponiveis[0]
                if not ids_infra_disponiveis:
                    st.stop()
                id_ei = st.selectbox(
                    "Ficha selecionada para edição:",
                    ids_infra_disponiveis,
                    index=ids_infra_disponiveis.index(id_salvo_edicao),
                    format_func=lambda ficha_id: next(
                        (
                            f"#{ficha_id} — {row.get('cliente_vinc') or row.get('fantasia') or row.get('razao') or 'Sem nome'}"
                            for row in rows_filtradas if int(row.get("id") or 0) == ficha_id
                        ),
                        f"#{ficha_id}",
                    ),
                    key="edit_inf_id_selecao",
                )
                st.session_state["infra_item_editar_id"] = int(id_ei)
                conn = conectar_banco()
                conn.row_factory = None
                c = conn.cursor()
                c.execute('SELECT * FROM infra_v4 WHERE id=?', (id_ei,))
                idata = c.fetchone()
                conn.close()
                
                if idata:
                    idata = dict(idata) 
                    with st.container(border=True):
                        st.subheader(f"Editando a ficha de: {idata.get('fantasia', '')} {idata.get('razao', '')}")
                        st.markdown("**1. Identificação da Empresa**")
                        st.caption("Informe o ID do cliente cadastrado para puxar os dados para esta ficha. Depois disso, pode alterar qualquer campo e salvar.")
                        puxar1, puxar2 = st.columns([1, 3])
                        id_cliente_puxar = puxar1.number_input("ID do cliente:", min_value=0, step=1, key=f"inf_edit_cliente_id_puxar_{id_ei}")
                        if puxar2.button("Puxar dados do cliente para esta ficha", width="stretch", key=f"inf_edit_btn_puxar_cliente_{id_ei}"):
                            if id_cliente_puxar <= 0:
                                st.error("Informe um ID de cliente válido.")
                            else:
                                conn_cli_inf = conectar_banco()
                                ccli_inf = conn_cli_inf.cursor(dictionary=True)
                                ccli_inf.execute("SELECT * FROM clientes WHERE id=?", (id_cliente_puxar,))
                                cliente_puxado_inf = ccli_inf.fetchone()
                                conn_cli_inf.close()
                                if cliente_puxado_inf:
                                    st.session_state[f"inf_edit_cliente_{id_ei}"] = cliente_puxado_inf.get("nome") or ""
                                    st.session_state[f"inf_edit_fantasia_{id_ei}"] = cliente_puxado_inf.get("rg_mei") or cliente_puxado_inf.get("nome") or ""
                                    st.session_state[f"inf_edit_razao_{id_ei}"] = cliente_puxado_inf.get("nome") or ""
                                    st.session_state[f"inf_edit_cnpj_{id_ei}"] = cliente_puxado_inf.get("cnpj") or ""
                                    st.session_state[f"inf_edit_end_{id_ei}"] = montar_endereco_cliente(cliente_puxado_inf)
                                    st.session_state[f"inf_edit_contato_{id_ei}"] = cliente_puxado_inf.get("nome") or ""
                                    st.session_state[f"inf_edit_email_{id_ei}"] = cliente_puxado_inf.get("email") or ""
                                    st.session_state[f"inf_edit_tel_{id_ei}"] = cliente_puxado_inf.get("telefone") or ""
                                    st.success("Dados do cliente carregados. Confira e salve a ficha.")
                                    st.rerun()
                                else:
                                    st.error("Cliente não encontrado com esse ID.")

                        ei1, ei2 = st.columns(2)
                        edit_fantasia = ei1.text_input("Nome Fantasia:", value=idata.get("fantasia") or "", key=f"inf_edit_fantasia_{id_ei}")
                        edit_razao = ei2.text_input("Razão Social / Nome da Empresa:", value=idata.get("razao") or "", key=f"inf_edit_razao_{id_ei}")
                        ei3, ei4, ei5 = st.columns([2, 3, 2])
                        edit_cnpj = ei3.text_input("CNPJ / CPF:", value=idata.get("cnpj") or "", key=f"inf_edit_cnpj_{id_ei}")
                        edit_endereco = ei4.text_input("Endereço Completo:", value=idata.get("endereco") or "", key=f"inf_edit_end_{id_ei}")
                        edit_contato = ei5.text_input("Nome do Contato:", value=idata.get("contato") or "", key=f"inf_edit_contato_{id_ei}")
                        ei6, ei7, ei8 = st.columns(3)
                        edit_email = ei6.text_input("E-mail Principal:", value=idata.get("email_prin") or "", key=f"inf_edit_email_{id_ei}")
                        edit_tel_prin = ei7.text_input("Telefone Principal:", value=idata.get("tel_prin") or "", key=f"inf_edit_tel_{id_ei}")
                        edit_tel_prov = ei8.text_input("Telefone Provedor:", value=idata.get("tel_prov") or "", key=f"inf_edit_telprov_{id_ei}")
                        ei9, ei10, ei11 = st.columns(3)
                        edit_contrato = ei9.text_input("Data Assinatura Contrato:", value=idata.get("contrato_data") or "", key=f"inf_edit_contrato_{id_ei}")
                        edit_pagto = ei10.text_input("Forma Pagto:", value=idata.get("pagto") or "", key=f"inf_edit_pagto_{id_ei}")
                        edit_venc = ei11.text_input("Dia de Vencimento:", value=idata.get("venc") or "", key=f"inf_edit_venc_{id_ei}")
                        edit_cliente_vinc = st.text_input("Cliente vinculado:", value=idata.get("cliente_vinc") or "", key=f"inf_edit_cliente_{id_ei}")

                        with st.expander("Gestão de E-mails deste cliente", expanded=False):
                            empresa_email_ficha = edit_cliente_vinc or edit_fantasia or edit_razao or "-- Avulso --"
                            emails_ficha = buscar_emails_para_empresa(empresa_email_ficha, edit_fantasia, edit_razao, edit_email)
                            if emails_ficha:
                                st.dataframe(emails_ficha, width="stretch", hide_index=True)
                                ids_email_ficha = [int(e.get("id")) for e in emails_ficha if e.get("id")]
                                fora_do_vinculo_ficha = [e for e in emails_ficha if (e.get("cliente_vinculado") or "") != empresa_email_ficha]
                                if fora_do_vinculo_ficha and empresa_email_ficha != "-- Avulso --":
                                    st.warning("Alguns e-mails foram encontrados, mas ainda não estão vinculados a esta empresa.")
                                    if st.button("Vincular e-mails encontrados a esta empresa", width="stretch", key=f"inf_edit_vinc_emails_{id_ei}"):
                                        conn_vinc_ficha = conectar_banco()
                                        cvinc_ficha = conn_vinc_ficha.cursor()
                                        placeholders = ",".join(["?"] * len(ids_email_ficha))
                                        cvinc_ficha.execute(
                                            f"UPDATE emails_clientes SET cliente_vinculado=? WHERE id IN ({placeholders})",
                                            tuple([empresa_email_ficha] + ids_email_ficha),
                                        )
                                        conn_vinc_ficha.commit()
                                        conn_vinc_ficha.close()
                                        st.success("E-mails vinculados à empresa.")
                                        st.rerun()
                            else:
                                st.info("Nenhum e-mail vinculado a esta ficha ainda.")

                            st.markdown("**Adicionar nova conta de e-mail**")
                            emn1, emn2, emn3 = st.columns(3)
                            novo_em_func = emn1.text_input("Usuário / Funcionário:", key=f"inf_edit_em_func_{id_ei}")
                            novo_em_email = emn2.text_input("E-mail:", key=f"inf_edit_em_email_{id_ei}")
                            novo_em_senha = emn3.text_input("Senha:", type="password", key=f"inf_edit_em_senha_{id_ei}")
                            emn4, emn5, emn6 = st.columns(3)
                            novo_em_aliases = emn4.text_input("Aliases:", key=f"inf_edit_em_aliases_{id_ei}")
                            novo_em_provedor = emn5.text_input("Provedor:", key=f"inf_edit_em_prov_{id_ei}")
                            novo_em_capacidade = emn6.text_input("Capacidade:", key=f"inf_edit_em_cap_{id_ei}")
                            emn7, emn8 = st.columns(2)
                            novo_em_entrada = emn7.text_input("Entrada (IMAP/POP):", key=f"inf_edit_em_entrada_{id_ei}")
                            novo_em_saida = emn8.text_input("Saída (SMTP):", key=f"inf_edit_em_saida_{id_ei}")
                            if st.button("Salvar e-mail nesta ficha", type="primary", key=f"inf_edit_em_btn_{id_ei}"):
                                if not novo_em_email.strip():
                                    st.error("Informe o endereço de e-mail.")
                                else:
                                    conn_salva_email = conectar_banco()
                                    csalva_email = conn_salva_email.cursor()
                                    csalva_email.execute(
                                        """INSERT INTO emails_clientes
                                           (cliente_vinculado, funcionario, email, senha, aliases, provedor, config_entrada, config_saida, capacidade)
                                           VALUES (?,?,?,?,?,?,?,?,?)""",
                                        (empresa_email_ficha, novo_em_func, novo_em_email, novo_em_senha, novo_em_aliases, novo_em_provedor, novo_em_entrada, novo_em_saida, novo_em_capacidade),
                                    )
                                    conn_salva_email.commit()
                                    conn_salva_email.close()
                                    st.success("E-mail salvo e vinculado à ficha.")
                                    st.rerun()

                        st.markdown("**2. Registros técnicos — edição individual**")
                        st.caption("Escolha a aba, clique no registro e salve somente aquele item. Os demais registros não serão alterados.")
                        abas_edicao_itens = st.tabs([
                            "Sistemas", "Rede", "Wi-Fi", "Servidor", "DVR", "Câmeras", "Alarme",
                            "Impressoras", "Antivírus", "Financeiro", "PCs", "PfSense", "VPN",
                            "Hospedagem", "Aplicativos", "Faixas de IP", "Setores",
                        ])
                        edicoes_infra = [
                            ("sistemas", "Sistemas", [("sys_dados", "Dados", "|"), ("sys_serial", "Serial", "|"), ("sys_cod", "Código do cliente", "|"), ("sys_adm", "Login administrativo", "|"), ("sys_senha", "Senha administrativa", "|"), ("sys_sec", "Login secundário", "|")]),
                            ("rede", "Redes", [("rede_prov", "Provedor", "|"), ("rede_ip", "IP", "|"), ("rede_log", "Login", "|"), ("rede_sen", "Senha", "|")]),
                            ("wifi", "Redes Wi-Fi", [("rede_wire", "SSID", "|"), ("rede_wsen", "Senha", "|")]),
                            ("servidores", "Servidores", [("serv_nome", "Nome", "|"), ("serv_ip", "IP", "|"), ("serv_link", "No-IP", "|"), ("serv_log", "Login", "|"), ("serv_sen", "Senha", "|"), ("serv_anydesk", "AnyDesk", "||"), ("serv_radmin", "Radmin", "||"), ("serv_google_remote", "Google Remote", "|"), ("serv_info_gerais", "Informações gerais", "||"), ("cert_log", "Gerencia DHCP", "|")]),
                            ("dvrs", "DVRs", [("dvr_acessos", "Informações", "||")]),
                            ("cameras", "Câmeras", [("cameras_acessos", "Informações", "||")]),
                            ("alarmes", "Alarmes", [("alarmes_acessos", "Informações", "||")]),
                            ("impressoras", "Impressoras", [("impressoras_acessos", "Informações", "||")]),
                            ("antivirus", "Antivírus", [("antivirus_acessos", "Informações", "||")]),
                            ("financeiro", "Acessos financeiros", [("fin_b1", "Banco 1", "||"), ("fin_b2", "Banco 2", "||"), ("fin_b3", "Banco 3", "||")]),
                            ("pcs", "PCs e Acessos", [("pcs_acessos", "Informações", "||")]),
                            ("pfsense", "PfSense", [("pfsense_acessos", "Informações", "||")]),
                            ("vpn", "VPN", [("vpn_acessos", "Informações", "||")]),
                            ("hospedagem", "Hospedagens e Domínios", [("hospedagem_acessos", "Informações", "||")]),
                            ("aplicativos", "Aplicativos", [("aplicativos_acessos", "Informações", "||")]),
                            ("faixas_ip", "Faixas de IP", [("faixas_ip", "Informações", "||")]),
                        ]
                        for aba_item, (slug_item, titulo_item, campos_item) in zip(abas_edicao_itens, edicoes_infra):
                            with aba_item:
                                renderizar_historico_tecnico(slug_item, titulo_item, campos_item, ficha=idata)
                        with abas_edicao_itens[-1]:
                            renderizar_historico_setores(ficha=idata)

                        st.markdown("**Fotos de DVR, câmeras e alarmes**")
                        conn_fotos_item = conectar_banco()
                        cfotos_item = conn_fotos_item.cursor()
                        cfotos_item.execute(
                            """SELECT id, ficha_id, tipo_item, item_indice, item_nome, foto_nome, foto_mime, criado_em
                               FROM infra_item_fotos WHERE ficha_id=? ORDER BY tipo_item, item_indice, id""",
                            (id_ei,),
                        )
                        fotos_item_salvas = [dict(r) for r in cfotos_item.fetchall()]
                        conn_fotos_item.close()

                        if fotos_item_salvas:
                            foto_item_clicada = tabela_clicavel_id(
                                st, fotos_item_salvas, f"infra_fotos_grade_{id_ei}", campo_id="id"
                            )
                            if foto_item_clicada:
                                st.session_state[f"infra_foto_ativa_{id_ei}"] = int(foto_item_clicada)
                            id_foto_ativa = int(st.session_state.get(f"infra_foto_ativa_{id_ei}") or 0)
                            foto_meta = next((foto for foto in fotos_item_salvas if int(foto.get("id") or 0) == id_foto_ativa), None)
                            if foto_meta:
                                conn_foto_blob = conectar_banco()
                                cfoto_blob = conn_foto_blob.cursor()
                                cfoto_blob.execute("SELECT foto FROM infra_item_fotos WHERE id=? AND ficha_id=?", (id_foto_ativa, id_ei))
                                foto_blob = cfoto_blob.fetchone()
                                conn_foto_blob.close()
                                if foto_blob and foto_blob.get("foto"):
                                    st.image(foto_blob.get("foto"), caption=foto_meta.get("foto_nome") or "Foto", width=240)
                            else:
                                st.caption("Clique em uma foto para visualizar, trocar ou excluir.")
                            if foto_meta and st.button("Excluir foto selecionada", key=f"infra_item_foto_btn_del_{id_ei}"):
                                conn_del_item_foto = conectar_banco()
                                cdel_item_foto = conn_del_item_foto.cursor()
                                cdel_item_foto.execute("DELETE FROM infra_item_fotos WHERE id=? AND ficha_id=?", (id_foto_ativa, id_ei))
                                conn_del_item_foto.commit()
                                conn_del_item_foto.close()
                                st.success("Foto excluída. Você pode enviar outra abaixo.")
                                st.rerun()
                        else:
                            st.info("Nenhuma foto individual cadastrada nesta ficha.")

                        fi1, fi2, fi3 = st.columns(3)
                        novo_tipo_foto = fi1.selectbox("Tipo do item:", ["DVR", "Câmera", "Alarme"], key=f"infra_item_foto_tipo_{id_ei}")
                        novo_indice_foto = fi2.number_input("Número do item:", min_value=1, step=1, key=f"infra_item_foto_indice_{id_ei}")
                        novo_nome_foto = fi3.text_input("Nome/local do item:", key=f"infra_item_foto_nome_{id_ei}")
                        nova_foto_item = st.file_uploader("Adicionar nova foto para este item:", type=TIPOS_IMAGEM_UPLOAD, key=f"infra_item_foto_nova_{id_ei}")
                        if st.button("Salvar nova foto do item", type="primary", key=f"infra_item_foto_btn_nova_{id_ei}"):
                            if not nova_foto_item:
                                st.error("Selecione uma foto.")
                            elif not upload_dentro_limite(nova_foto_item):
                                erro_upload_grande("foto")
                            else:
                                foto_dados, foto_nome, foto_mime = dados_upload(nova_foto_item)
                                conn_nova_item_foto = conectar_banco()
                                cnova_item_foto = conn_nova_item_foto.cursor()
                                cnova_item_foto.execute(
                                    """INSERT INTO infra_item_fotos
                                       (ficha_id, tipo_item, item_indice, item_nome, foto_nome, foto_mime, foto, criado_em)
                                       VALUES (?,?,?,?,?,?,?,?)""",
                                    (id_ei, novo_tipo_foto, novo_indice_foto, novo_nome_foto, foto_nome, foto_mime,
                                     foto_dados, datetime.now().strftime("%d/%m/%Y %H:%M")),
                                )
                                conn_nova_item_foto.commit()
                                conn_nova_item_foto.close()
                                st.success("Foto salva.")
                                st.rerun()
                        
                        if st.button("Guardar dados da empresa", type="primary", key=f"btn_save_inf_{id_ei}"):
                            conn_save_inf = conectar_banco()
                            csave_inf = conn_save_inf.cursor()
                            csave_inf.execute(
                                """UPDATE infra_v4 SET cliente_vinc=?, fantasia=?, razao=?, cnpj=?, endereco=?,
                                   contato=?, email_prin=?, tel_prin=?, tel_prov=?, contrato_data=?, pagto=?, venc=?
                                   WHERE id=?""",
                                (
                                    edit_cliente_vinc, edit_fantasia, edit_razao, edit_cnpj, edit_endereco,
                                    edit_contato, edit_email, edit_tel_prin, edit_tel_prov,
                                    edit_contrato, edit_pagto, edit_venc, id_ei,
                                ),
                            )
                            conn_save_inf.commit()
                            conn_save_inf.close()
                            st.session_state.pop("infra_item_editar_id", None)
                            st.session_state.setdefault("_infra_widgets_para_limpar", []).extend(
                                ["infra_historico_grade", "edit_inf_id_selecao"]
                            )
                            st.success("Ficha atualizada.")
                            st.rerun()


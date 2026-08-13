from __future__ import annotations

from dsystem_erp.app_context import aplicar_contexto_pagina


def renderizar_infraestrutura_ti(ctx: dict) -> None:
    aplicar_contexto_pagina(ctx, globals())
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
        abas_infra = ["Sistemas", "Rede", "DVR", "Câmeras", "Alarme", "Wi-Fi", "Servidor", "Antivírus", "Financeiro", "PCs e Acessos", "Setores", "Equipamentos", "Hospedagem"]
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
        t_antivirus = tabs_infra["Antivírus"]
        t_fin = tabs_infra["Financeiro"]
        t_pcs = tabs_infra["PCs e Acessos"]
        t_setores = tabs_infra.get("Setores")
        t_equipamentos = tabs_infra.get("Equipamentos")
        t_hospedagem = tabs_infra.get("Hospedagem")
        t_emails_infra = tabs_infra.get("Gestão de E-mails")
        t_apps = tabs_infra.get("Aplicativos")
        
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
                    st.dataframe(
                        [{k: v for k, v in dict(eq).items() if k not in ("informacoes",)} for eq in filtrados_eq],
                        width="stretch",
                        hide_index=True,
                    )
                    id_eq_ver = st.number_input("ID para ver fotos/detalhes:", min_value=1, step=1, key="infra_eq_id_ver")
                    eq_sel = next((dict(eq) for eq in equipamentos_rows if int(eq.get("id") or 0) == int(id_eq_ver)), None)
                    if eq_sel:
                        with st.expander(f"Detalhes do equipamento #{id_eq_ver}", expanded=True):
                            st.write(f"**Cliente/empresa:** {eq_sel.get('cliente_nome') or ''}")
                            st.write(f"**Funcionário:** {eq_sel.get('funcionario_nome') or eq_sel.get('funcionario_usuario') or ''}")
                            st.write(f"**Tipo:** {eq_sel.get('tipo_equipamento') or ''}")
                            st.write(f"**Equipamento:** {eq_sel.get('nome_equipamento') or ''}")
                            st.write(f"**IP:** {eq_sel.get('ip_equipamento') or ''}")
                            st.write(f"**Quem usa:** {eq_sel.get('quem_usa') or ''}")
                            st.write(f"**Informações Gerais:** {eq_sel.get('informacoes') or ''}")
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
                    if tem_permissao("infra.delete"):
                        id_eq_del = st.number_input("ID para excluir equipamento:", min_value=1, step=1, key="infra_eq_id_del")
                        if st.button("Excluir Equipamento", key="infra_eq_excluir"):
                            conn_del_eq = conectar_banco()
                            cdel_eq = conn_del_eq.cursor()
                            cdel_eq.execute("DELETE FROM infra_equipamentos_fotos WHERE equipamento_id=?", (id_eq_del,))
                            cdel_eq.execute("DELETE FROM infra_equipamentos WHERE id=?", (id_eq_del,))
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
                cliente_email_infra = inf_vinc if inf_vinc != "-- Selecionar Cliente Existente --" else (inf_fan or inf_emp or "-- Avulso --")
                st.caption(f"As contas salvas aqui ficam vinculadas a: {cliente_email_infra}")
                qtd_emails_infra = st.number_input("Qtd contas de e-mail:", min_value=0, max_value=30, value=0, key="infra_qtd_emails")
                for i in range(qtd_emails_infra):
                    st.markdown(f"**Conta de E-mail {i+1}**")
                    em1, em2, em3 = st.columns(3)
                    em_func = em1.text_input(f"Usuário / Funcionário {i+1}:", key=f"infra_em_func_{i}")
                    em_email = em2.text_input(f"E-mail {i+1}:", key=f"infra_em_email_{i}")
                    em_senha = em3.text_input(f"Senha {i+1}:", type="password", key=f"infra_em_senha_{i}")
                    em4, em5, em6 = st.columns(3)
                    em_aliases = em4.text_input(f"Aliases {i+1}:", key=f"infra_em_aliases_{i}")
                    em_provedor = em5.text_input(f"Provedor {i+1}:", key=f"infra_em_provedor_{i}")
                    em_capacidade = em6.text_input(f"Capacidade {i+1}:", key=f"infra_em_capacidade_{i}")
                    em7, em8 = st.columns(2)
                    em_entrada = em7.text_input(f"Entrada (IMAP/POP) {i+1}:", key=f"infra_em_entrada_{i}")
                    em_saida = em8.text_input(f"Saída (SMTP) {i+1}:", key=f"infra_em_saida_{i}")
                    if em_email:
                        emails_infra_para_salvar.append(
                            (cliente_email_infra, em_func, em_email, em_senha, em_aliases, em_provedor, em_entrada, em_saida, em_capacidade)
                        )

                emails_existentes_infra = buscar_emails_para_empresa(cliente_email_infra, inf_fan, inf_emp, inf_email)
                if emails_existentes_infra:
                    st.markdown("**E-mails já cadastrados para este cliente**")
                    st.dataframe(emails_existentes_infra, width="stretch", hide_index=True)
                    ids_email_infra = [int(e.get("id")) for e in emails_existentes_infra if e.get("id")]
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

        rotulo_salvar_infra = "Salvar alterações da ficha" if infra_editando else "Salvar Ficha de Infraestrutura"
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
                if infra_editando:
                    for coluna in colunas_infra_salvar:
                        if dados_infra_salvar[coluna] in (None, "", "-- Selecionar Cliente Existente --"):
                            dados_infra_salvar[coluna] = infra_editando.get(coluna) or ""
                    set_sql_infra = ", ".join([f"{col}=?" for col in colunas_infra_salvar])
                    c.execute(
                        f"UPDATE infra_v4 SET {set_sql_infra} WHERE id=?",
                        tuple(dados_infra_salvar[col] for col in colunas_infra_salvar) + (infra_edit_id_ativo,),
                    )
                    ficha_id = infra_edit_id_ativo
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
                if infra_editando:
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
        c.execute('SELECT id, fantasia, razao, contato, tel_prin FROM infra_v4 ORDER BY id DESC')
        rows = c.fetchall()
        conn.close()
        rows = filtrar_registros_por_empresa(rows, "cliente_vinc", "fantasia", "razao")
        
        if rows: st.dataframe(rows, width="stretch", hide_index=True)
        else: st.info("Nenhuma ficha encontrada.")
        
        acoes_inf = []
        if tem_permissao("infra.edit"): acoes_inf.append("Editar Ficha Completa")
        if tem_permissao("infra.delete"): acoes_inf.append("Excluir Ficha")
        
        if acoes_inf:
            st.write("---")
            a_inf = st.radio("Ação:", acoes_inf, horizontal=True)
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
                id_ei = st.number_input("ID para editar:", min_value=1, step=1, key="edit_inf_id")
                if st.button("Abrir ficha na tela principal para editar", type="primary", width="stretch", key="btn_abrir_inf_na_tela_principal"):
                    st.session_state["infra_editar_id"] = int(id_ei)
                    st.rerun()
                st.info("Clique no botão acima para carregar essa ficha na aba 'Cadastrar Ficha Completa' em modo edição.")
                st.stop()
                conn = conectar_banco()
                conn.row_factory = None
                c = conn.cursor()
                c.execute('SELECT * FROM infra_v4 WHERE id=?', (id_ei,))
                idata = c.fetchone()
                conn.close()
                
                if idata:
                    idata = dict(idata) 
                    with st.expander(f"Editando a Ficha de: {idata.get('fantasia', '')} {idata.get('razao', '')}", expanded=True):
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

                        st.markdown("**2. Detalhamento Técnico**")
                        st.caption("Edite um item por linha. Campos antigos separados por | foram mantidos para não perder dados.")
                        edit_dvr = st.text_area("DVRs:", value=texto_lista_infra(idata.get("dvr_acessos")), height=120, key=f"inf_edit_dvr_{id_ei}")
                        edit_cameras = st.text_area("Câmeras:", value=texto_lista_infra(idata.get("cameras_acessos")), height=120, key=f"inf_edit_cameras_{id_ei}")
                        edit_alarmes = st.text_area("Alarmes:", value=texto_lista_infra(idata.get("alarmes_acessos")), height=120, key=f"inf_edit_alarmes_{id_ei}")

                        with st.expander("Editar demais blocos técnicos", expanded=False):
                            edit_sys_dados = st.text_area("Sistemas - dados:", value=texto_lista_infra(idata.get("sys_dados"), "|"), height=90, key=f"inf_edit_sysdados_{id_ei}")
                            edit_sys_serial = st.text_area("Sistemas - serial:", value=texto_lista_infra(idata.get("sys_serial"), "|"), height=90, key=f"inf_edit_sysserial_{id_ei}")
                            edit_sys_cod = st.text_area("Sistemas - código cliente:", value=texto_lista_infra(idata.get("sys_cod"), "|"), height=90, key=f"inf_edit_syscod_{id_ei}")
                            edit_sys_adm = st.text_area("Sistemas - logins administrativos:", value=texto_lista_infra(idata.get("sys_adm"), "|"), height=90, key=f"inf_edit_sysadm_{id_ei}")
                            edit_sys_senha = st.text_area("Sistemas - senhas administrativas:", value=texto_lista_infra(idata.get("sys_senha"), "|"), height=90, key=f"inf_edit_syssen_{id_ei}")
                            edit_sys_sec = st.text_area("Sistemas - logins secundários:", value=texto_lista_infra(idata.get("sys_sec"), "|"), height=90, key=f"inf_edit_syssec_{id_ei}")
                            edit_rede_prov = st.text_area("Rede - provedor:", value=texto_lista_infra(idata.get("rede_prov"), "|"), height=90, key=f"inf_edit_redeprov_{id_ei}")
                            edit_rede_ip = st.text_area("Rede - IP:", value=texto_lista_infra(idata.get("rede_ip"), "|"), height=90, key=f"inf_edit_redeip_{id_ei}")
                            edit_rede_log = st.text_area("Rede - logins modem:", value=texto_lista_infra(idata.get("rede_log"), "|"), height=90, key=f"inf_edit_redelog_{id_ei}")
                            edit_rede_sen = st.text_area("Rede - senhas modem:", value=texto_lista_infra(idata.get("rede_sen"), "|"), height=90, key=f"inf_edit_redesen_{id_ei}")
                            edit_wifi = st.text_area("Wi-Fi SSID:", value=texto_lista_infra(idata.get("rede_wire"), "|"), height=90, key=f"inf_edit_wifi_{id_ei}")
                            edit_wifi_senha = st.text_area("Wi-Fi senha:", value=texto_lista_infra(idata.get("rede_wsen"), "|"), height=90, key=f"inf_edit_wifisen_{id_ei}")
                            edit_serv_nome = st.text_area("Servidor - nome:", value=texto_lista_infra(idata.get("serv_nome"), "|"), height=90, key=f"inf_edit_servnome_{id_ei}")
                            edit_serv_ip = st.text_area("Servidor - IP:", value=texto_lista_infra(idata.get("serv_ip"), "|"), height=90, key=f"inf_edit_servip_{id_ei}")
                            edit_serv_link = st.text_area("Servidor - link/no-ip:", value=texto_lista_infra(idata.get("serv_link"), "|"), height=90, key=f"inf_edit_servlink_{id_ei}")
                            edit_serv_log = st.text_area("Servidor - login:", value=texto_lista_infra(idata.get("serv_log"), "|"), height=90, key=f"inf_edit_servlog_{id_ei}")
                            edit_serv_sen = st.text_area("Servidor - senha:", value=texto_lista_infra(idata.get("serv_sen"), "|"), height=90, key=f"inf_edit_servsen_{id_ei}")
                            edit_fin_b1 = st.text_area("Financeiro/Banco 1:", value=idata.get("fin_b1") or "", height=90, key=f"inf_edit_fin1_{id_ei}")
                            edit_fin_b2 = st.text_area("Financeiro/Banco 2:", value=idata.get("fin_b2") or "", height=90, key=f"inf_edit_fin2_{id_ei}")
                            edit_fin_b3 = st.text_area("Financeiro/Banco 3:", value=idata.get("fin_b3") or "", height=90, key=f"inf_edit_fin3_{id_ei}")
                            edit_pcs = st.text_area("PCs e acessos:", value=texto_lista_infra(idata.get("pcs_acessos")), height=120, key=f"inf_edit_pcs_{id_ei}")
                            edit_apps = st.text_area("Aplicativos:", value=texto_lista_infra(idata.get("aplicativos_acessos")), height=120, key=f"inf_edit_apps_{id_ei}")
                            edit_pfsense = st.text_area("PfSense:", value=texto_lista_infra(idata.get("pfsense_acessos")), height=120, key=f"inf_edit_pfsense_{id_ei}")
                            edit_antivirus = st.text_area("Antivírus:", value=texto_lista_infra(idata.get("antivirus_acessos")), height=120, key=f"inf_edit_antivirus_{id_ei}")
                            edit_faixas_ip = st.text_area("Faixas de IP:", value=texto_lista_infra(idata.get("faixas_ip")), height=120, key=f"inf_edit_faixas_{id_ei}")
                            edit_vpn = st.text_area("VPN:", value=texto_lista_infra(idata.get("vpn_acessos")), height=120, key=f"inf_edit_vpn_{id_ei}")
                            edit_hospedagem = st.text_area("Hospedagem/domínios:", value=texto_lista_infra(idata.get("hospedagem_acessos")), height=120, key=f"inf_edit_hosp_{id_ei}")
                            edit_setores = st.text_area("Setores:", value=idata.get("setores") or "", height=120, key=f"inf_edit_setores_{id_ei}")

                        st.markdown("**Fotos de DVR, câmeras e alarmes**")
                        conn_fotos_item = conectar_banco()
                        cfotos_item = conn_fotos_item.cursor()
                        cfotos_item.execute("SELECT * FROM infra_item_fotos WHERE ficha_id=? ORDER BY tipo_item, item_indice, id", (id_ei,))
                        fotos_item_salvas = [dict(r) for r in cfotos_item.fetchall()]
                        conn_fotos_item.close()

                        if fotos_item_salvas:
                            for foto_salva in fotos_item_salvas:
                                st.write(f"**ID {foto_salva.get('id')} - {foto_salva.get('tipo_item')} {foto_salva.get('item_indice')}: {foto_salva.get('item_nome') or ''}**")
                                st.image(foto_salva.get("foto"), caption=foto_salva.get("foto_nome") or "Foto", width=240)
                            id_foto_excluir = st.number_input("ID da foto para excluir/trocar:", min_value=1, step=1, key=f"infra_item_foto_del_{id_ei}")
                            if st.button("Excluir foto selecionada", key=f"infra_item_foto_btn_del_{id_ei}"):
                                conn_del_item_foto = conectar_banco()
                                cdel_item_foto = conn_del_item_foto.cursor()
                                cdel_item_foto.execute("DELETE FROM infra_item_fotos WHERE id=? AND ficha_id=?", (id_foto_excluir, id_ei))
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
                        
                        if st.button("Guardar Edição Completa da Ficha", type="primary", key=f"btn_save_inf_{id_ei}"):
                            conn_save_inf = conectar_banco()
                            csave_inf = conn_save_inf.cursor()
                            csave_inf.execute(
                                """UPDATE infra_v4 SET cliente_vinc=?, fantasia=?, razao=?, cnpj=?, endereco=?,
                                   contato=?, email_prin=?, tel_prin=?, tel_prov=?, contrato_data=?, pagto=?, venc=?,
                                   sys_dados=?, sys_serial=?, sys_cod=?, sys_adm=?, sys_senha=?, sys_sec=?,
                                   rede_prov=?, rede_ip=?, rede_log=?, rede_sen=?, rede_wire=?, rede_wsen=?,
                                   serv_nome=?, serv_ip=?, serv_link=?, serv_log=?, serv_sen=?,
                                   fin_b1=?, fin_b2=?, fin_b3=?, pcs_acessos=?, dvr_acessos=?, cameras_acessos=?,
                                   alarmes_acessos=?, aplicativos_acessos=?, pfsense_acessos=?, antivirus_acessos=?,
                                   faixas_ip=?, vpn_acessos=?, hospedagem_acessos=?, setores=? WHERE id=?""",
                                (
                                    edit_cliente_vinc, edit_fantasia, edit_razao, edit_cnpj, edit_endereco,
                                    edit_contato, edit_email, edit_tel_prin, edit_tel_prov, edit_contrato, edit_pagto, edit_venc,
                                    lista_texto_infra(edit_sys_dados, "|"), lista_texto_infra(edit_sys_serial, "|"),
                                    lista_texto_infra(edit_sys_cod, "|"), lista_texto_infra(edit_sys_adm, "|"),
                                    lista_texto_infra(edit_sys_senha, "|"), lista_texto_infra(edit_sys_sec, "|"),
                                    lista_texto_infra(edit_rede_prov, "|"), lista_texto_infra(edit_rede_ip, "|"),
                                    lista_texto_infra(edit_rede_log, "|"), lista_texto_infra(edit_rede_sen, "|"),
                                    lista_texto_infra(edit_wifi, "|"), lista_texto_infra(edit_wifi_senha, "|"),
                                    lista_texto_infra(edit_serv_nome, "|"), lista_texto_infra(edit_serv_ip, "|"),
                                    lista_texto_infra(edit_serv_link, "|"), lista_texto_infra(edit_serv_log, "|"),
                                    lista_texto_infra(edit_serv_sen, "|"), edit_fin_b1, edit_fin_b2, edit_fin_b3,
                                    lista_texto_infra(edit_pcs), lista_texto_infra(edit_dvr), lista_texto_infra(edit_cameras),
                                    lista_texto_infra(edit_alarmes), lista_texto_infra(edit_apps), lista_texto_infra(edit_pfsense),
                                    lista_texto_infra(edit_antivirus), lista_texto_infra(edit_faixas_ip),
                                    lista_texto_infra(edit_vpn), lista_texto_infra(edit_hospedagem), edit_setores, id_ei,
                                ),
                            )
                            conn_save_inf.commit()
                            conn_save_inf.close()
                            st.success("Ficha atualizada.")
                            st.rerun()


from __future__ import annotations

from dsystem_erp.app_context import aplicar_contexto_pagina
from dsystem_erp.services.precificacao_estoque import preco_revenda_produto


def renderizar_gerador_orcamentos(ctx: dict) -> None:
    aplicar_contexto_pagina(ctx, globals())
    st.title("Gerador de Orçamentos")
    aba1, aba2 = st.tabs(["Gerar/Editar Orçamento", "Histórico de Orçamentos"])

    if 'orc_em_edicao' not in st.session_state:
        st.session_state['orc_em_edicao'] = None
    if "orc_form_reset" not in st.session_state:
        st.session_state["orc_form_reset"] = 0

    def resetar_formulario_orcamento():
        st.session_state["orc_form_reset"] = st.session_state.get("orc_form_reset", 0) + 1

    with aba1:
        edicao = st.session_state['orc_em_edicao']
        id_orcamento_tela = edicao.get("orc_id") if edicao else "novo"
        prefixo_orc = f"orc_{id_orcamento_tela}_{st.session_state.get('orc_form_reset', 0)}"
        
        if edicao:
            st.warning(f"MODO DE EDIÇÃO: Você está alterando o Orçamento Nº {edicao['numero']}")
            if st.button("Cancelar Edição e Limpar Tela", key="btn_canc_ed"):
                st.session_state['orc_em_edicao'] = None
                resetar_formulario_orcamento()
                st.rerun()

        try:
            conn = conectar_banco()
            c = conn.cursor()
            c.execute("SELECT numero FROM orcamentos ORDER BY orc_id DESC LIMIT 1")
            last_orc = c.fetchone()
            conn.close()
            sugestao_num = str(int(last_orc[0]) + 1) if (last_orc and str(last_orc[0]).isdigit()) else "441"
        except:
            sugestao_num = "441"

        def_num = edicao['numero'] if edicao else sugestao_num
        def_fpag = edicao['forma_pagamento'] if edicao else "Boleto Bancário"
        def_opag = edicao['obs_pag'] if edicao else ""
        def_oger = edicao['obs_geral'] if edicao else ""
        def_status = (edicao.get('status') or "Aberto") if edicao else "Aberto"
        def_validade = parse_data_flex(edicao.get('data_validade')) if edicao else None
        if not def_validade:
            def_validade = (parse_data_flex(edicao.get('data_orc')) if edicao else date.today()) or date.today()
            def_validade += timedelta(days=10)

        c1, c2 = st.columns(2)
        with c1: 
            n_orc = st.text_input("Número do Orçamento:", value=def_num, key=f"{prefixo_orc}_numero")
        with c2: 
            opts_pag = ["Boleto Bancário", "PIX", "Cartão de Crédito", "A vista", "A Combinar"]
            idx_pag = opts_pag.index(def_fpag) if def_fpag in opts_pag else 0
            f_pag = st.selectbox("Forma de Pagamento:", opts_pag, index=idx_pag, key=f"{prefixo_orc}_forma_pag")
            
        c3, c4 = st.columns(2)
        with c3: o_pag = st.text_input("Observação do Pagamento:", value=def_opag, key=f"{prefixo_orc}_obs_pag")
        with c4: o_ger = st.text_input("Observações Gerais:", value=def_oger, key=f"{prefixo_orc}_obs_geral")

        c_status, c_validade = st.columns(2)
        status_opcoes = ["Aberto", "Em negociação", "Vencido", "Aprovado", "Cancelado", "Aprovado e lançado"]
        if def_status not in status_opcoes:
            status_opcoes.append(def_status)
        status_orcamento = c_status.selectbox(
            "Status do orçamento:", status_opcoes,
            index=status_opcoes.index(def_status), key=f"{prefixo_orc}_status",
        )
        data_validade = c_validade.date_input(
            "Validade do orçamento:", value=def_validade,
            min_value=date.today() if not edicao else None,
            key=f"{prefixo_orc}_validade",
            help="Se não for aprovado até esta data, o orçamento será marcado como Vencido.",
        )
            
        cdb = buscar_clientes()
        nclis = ["-- Preencher Manualmente --"] + [c['nome'] for c in cdb]
        
        def_cli_nome = edicao['cliente'] if edicao else ""
        idx_cli = nclis.index(def_cli_nome) if def_cli_nome in nclis else 0
        c_sel = st.selectbox("Buscar Cliente Cadastrado:", nclis, index=idx_cli, key=f"{prefixo_orc}_cliente_cadastrado")
        if edicao and c_sel != "-- Preencher Manualmente --" and c_sel != def_cli_nome:
            st.info("Cliente selecionado diferente do orçamento original. Os dados abaixo foram puxados do cadastro selecionado; confira e salve para atualizar.")
        sufixo_cliente_orc = re.sub(r"[^A-Za-z0-9_-]+", "_", c_sel or "manual")[:40]
        prefixo_cliente_orc = f"{prefixo_orc}_{sufixo_cliente_orc}"
        
        if c_sel != "-- Preencher Manualmente --":
            dc = next((c for c in cdb if c['nome'] == c_sel), {})
        else:
            dc = {'nome': edicao['cliente'] if edicao else '', 'cnpj': edicao['cpf_cnpj'] if edicao else '', 'telefone':'','email':'','rg_mei':'','endereco':'','numero':'','complemento':'','bairro':'','cidade_estado':'BH / MG','cep':''}
        
        c5, c6, c7 = st.columns(3)
        with c5: nm = st.text_input("Nome/Empresa:", value=dc.get('nome',''), key=f"{prefixo_cliente_orc}_nome")
        with c6: t = st.text_input("Telefone:", value=dc.get('telefone',''), key=f"{prefixo_cliente_orc}_telefone")
        with c7: em = st.text_input("E-mail:", value=dc.get('email',''), key=f"{prefixo_cliente_orc}_email")
            
        c8, c9 = st.columns(2)
        with c8: cnj = st.text_input("CNPJ/CPF:", value=dc.get('cnpj',''), key=f"{prefixo_cliente_orc}_cnpj")
        with c9: rg = st.text_input("Fantasia/RG:", value=dc.get('rg_mei',''), key=f"{prefixo_cliente_orc}_rg")
            
        c10, c11, c12 = st.columns([3,1,2])
        with c10: end = st.text_input("Rua:", value=dc.get('endereco',''), key=f"{prefixo_cliente_orc}_endereco")
        with c11: num = st.text_input("Nº:", value=dc.get('numero',''), key=f"{prefixo_cliente_orc}_numero_end")
        with c12: comp = st.text_input("Comp:", value=dc.get('complemento',''), key=f"{prefixo_cliente_orc}_complemento")
            
        c13, c14, c15 = st.columns([2,2,2])
        with c13: bai = st.text_input("Bairro:", value=dc.get('bairro',''), key=f"{prefixo_cliente_orc}_bairro")
        with c14: cid = st.text_input("Cidade/UF:", value=dc.get('cidade_estado','BH / MG'), key=f"{prefixo_cliente_orc}_cidade")
        with c15: cep = st.text_input("CEP:", value=dc.get('cep',''), key=f"{prefixo_cliente_orc}_cep")

        st.divider()
        
        if edicao and edicao['itens']:
            try: itens_carregados = json.loads(edicao['itens'])
            except: itens_carregados = []
        else:
            itens_carregados = []

        ns = st.number_input("Quantidade de Itens Diferentes:", min_value=1, max_value=20, value=max(1, len(itens_carregados)), key=f"{prefixo_orc}_qtd_itens")
        produtos_estoque_orc = repo_listar_estoque(conectar_banco)
        opcoes_produto_orc = ["-- Selecionar produto do estoque --"] + [
            f"{p['id']} - {p.get('produto') or p.get('codigo_entrada')} — {p.get('situacao_nota') or 'Comprado com nota'} (Estoque: {p.get('quantidade') or 0})"
            for p in produtos_estoque_orc
        ]
        srvs = []
        vt = 0.0
        
        for i in range(ns):
            cc1, cc2, cc3, cc4, cc5 = st.columns([4, 1.5, 2, 1, 1.8])
            item_carregado = itens_carregados[i] if i < len(itens_carregados) and isinstance(itens_carregados[i], dict) else {}
            def_d = item_carregado.get('d') or item_carregado.get('desc') or ""
            def_tipo_item = item_carregado.get("tipo_item") or item_carregado.get("tipo") or item_carregado.get("tipo_nota") or "Serviço"
            if item_carregado.get("estoque_id"):
                def_tipo_item = "Produto"
            if def_tipo_item not in ["Produto", "Serviço"]:
                def_tipo_item = "Serviço"
            try:
                def_v = float(item_carregado.get('v', item_carregado.get('vunit', 0)) or 0)
            except Exception:
                def_v = 0.0
            try:
                def_q = int(item_carregado.get('q', item_carregado.get('qtd', 1)) or 1)
            except Exception:
                def_q = 1

            d = cc1.text_input(f"Descrição do Item {i+1}:", value=def_d, key=f"{prefixo_orc}_oi_{i}")
            tipo_item_orc = cc2.selectbox(f"Tipo {i+1}:", ["Serviço", "Produto"], index=["Serviço", "Produto"].index(def_tipo_item), key=f"{prefixo_orc}_tipo_item_{i}")
            produto_orc = None
            tipo_item_fiscal_orc = tipo_item_orc
            situacao_nota_orc = ""
            ajuste_orc = 0.0
            if tipo_item_orc == "Produto":
                produto_salvo_id = item_carregado.get("estoque_id")
                indice_produto = next((idx for idx, opcao in enumerate(opcoes_produto_orc) if produto_salvo_id and opcao.startswith(f"{produto_salvo_id} - ")), 0)
                produto_escolhido = st.selectbox(f"Produto do estoque {i+1}:", opcoes_produto_orc, index=indice_produto, key=f"{prefixo_orc}_produto_estoque_{i}")
                if produto_escolhido != opcoes_produto_orc[0]:
                    produto_id = int(produto_escolhido.split(" - ", 1)[0])
                    produto_orc = next((p for p in produtos_estoque_orc if int(p["id"]) == produto_id), None)
                    if produto_orc:
                        situacao_nota_orc = produto_orc.get("situacao_nota") or "Comprado com nota"
                        tipo_item_fiscal_orc = "Serviço" if situacao_nota_orc == "Comprado sem nota" else "Produto"
                        d = produto_orc.get("produto") or produto_orc.get("codigo_entrada") or d
                        if produto_orc.get("permitir_ajuste_preco"):
                            ajuste_orc = st.number_input(f"Ajuste comercial do produto {i+1} (%):", min_value=-100.0, value=float(item_carregado.get("ajuste_preco_percentual") or 0), step=0.1, key=f"{prefixo_orc}_ajuste_produto_{i}")
                        def_v = float(preco_revenda_produto(produto_orc, ajuste_orc))
                        st.caption(f"Preço do estoque aplicado ao item {i+1}: {formatar_moeda_br(def_v)} — {situacao_nota_orc}")
                        if situacao_nota_orc == "Comprado sem nota":
                            st.warning(f"Item {i+1}: será lançado fiscalmente como Serviço e continuará vinculado à baixa do estoque.")
            chave_preco_orc = f"{prefixo_orc}_ov_{i}_{produto_orc.get('id') if produto_orc else 'manual'}_{ajuste_orc:.2f}"
            v = cc3.number_input(f"Valor Unit. R$ {i+1}:", value=def_v, min_value=0.0, format="%.2f", key=chave_preco_orc, disabled=bool(produto_orc))
            q = cc4.number_input(f"Qtd {i+1}:", value=def_q, min_value=1, step=1, key=f"{prefixo_orc}_oq_{i}")
            total_item = total_item_orcamento(v, q)
            cc5.metric(f"Total item {i+1}", formatar_moeda_br(total_item))
            
            if d: 
                srvs.append({"d": d, "tipo_item": tipo_item_fiscal_orc, "v": v, "q": q, "t": total_item,
                             "estoque_id": produto_orc.get("id") if produto_orc else None,
                             "origem_item": "Produto do estoque" if produto_orc else tipo_item_orc,
                             "situacao_nota": situacao_nota_orc,
                             "ajuste_preco_percentual": ajuste_orc if produto_orc else 0})
                vt += total_item

        st.metric("Total geral do orçamento", formatar_moeda_br(vt))

        empesc = st.radio("Selecione a unidade para Preview:", ["Dsystem Tecnologia", "LC Printer", "GT Solutions"], horizontal=True, key=f"{prefixo_orc}_empresa_preview")
        
        cb1, cb2, cb3, cb4 = st.columns(4)
        bp = cb1.button("Visualizar na Tela", width="stretch")
        
        label_btn_salvar = "Atualizar e Gerar PDF" if edicao else "Salvar e Gerar PDF Múltiplo"
        bpa = cb2.button(label_btn_salvar, type="primary", width="stretch")
        bimp = cb3.button("Imprimir Orçamento", width="stretch", disabled=not bool(edicao))
        limpar_tela = cb4.button("Limpar tela", width="stretch", key=f"limpar_{prefixo_orc}")
        if limpar_tela:
            st.session_state['orc_em_edicao'] = None
            resetar_formulario_orcamento()
            st.rerun()

        if vt > 0 and nm:
            st.markdown("#### Imprimir / salvar PDF individual")
            st.caption("Abre a impressão com o mesmo layout antigo. Na janela de impressão, escolha 'Salvar como PDF'.")
            pds1, pds2, pds3 = st.columns(3)
            bpdf_ds = pds1.button("PDF Dsystem", width="stretch", key=f"print_pdf_ds_{prefixo_orc}")
            bpdf_nc = pds2.button("PDF LC Printer", width="stretch", key=f"print_pdf_lc_{prefixo_orc}")
            bpdf_gt = pds3.button("PDF GT Solutions", width="stretch", key=f"print_pdf_gt_{prefixo_orc}")
        else:
            bpdf_ds = bpdf_nc = bpdf_gt = False

        if bp or bpa or bimp or bpdf_ds or bpdf_nc or bpdf_gt:
            if vt > 0 and nm:
                dtc = date.today().strftime("%d/%m/%Y")
                dtv = data_validade.strftime("%d/%m/%Y")
                cfmt = f" - {comp}" if comp else ""
                cepfmt = f" - CEP: {cep}" if cep else ""
                
                if bpa:
                    salvar_cliente_simples(nm, cnj, end, t, cep)
                    import json as _json
                    json_itens = _json.dumps(srvs, ensure_ascii=False)
                    
                    conn = conectar_banco()
                    c = conn.cursor()
                    if edicao:
                        c.execute('''UPDATE orcamentos SET numero=?, cliente=?, cpf_cnpj=?, valor_total=?, forma_pagamento=?, obs_pag=?, obs_geral=?, itens=?, status=?, data_validade=?, alterado_em=?, alterado_por=? WHERE orc_id=?''', (n_orc, nm, cnj, formata_moeda(vt), f_pag, o_pag, o_ger, json_itens, status_orcamento, dtv, agora_br(), st.session_state.get("username", ""), edicao['orc_id']))
                        orc_id_salvo = edicao['orc_id']
                        st.success("Orçamento atualizado com sucesso!")
                    else:
                        c.execute('INSERT INTO orcamentos (numero, data_orc, cliente, cpf_cnpj, valor_total, forma_pagamento, obs_pag, obs_geral, itens, status, data_validade, versao) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', (n_orc, dtc, nm, cnj, formata_moeda(vt), f_pag, o_pag, o_ger, json_itens, status_orcamento, dtv, 1))
                        orc_id_salvo = c.lastrowid
                        st.success("Orçamento salvo com sucesso!")
                    dados_pdf_salvar = dados_orcamento_base(
                        n_orc, nm, cnj, srvs, f_pag, o_pag, o_ger, dtc,
                        telefone=t, email=em,
                        endereco=f"{end}, {num}{cfmt} - {bai} - {cid}{cepfmt}",
                        data_validade=dtv,
                    )
                    salvar_pdfs_orcamento(c, orc_id_salvo, dados_pdf_salvar)
                    conn.commit()
                    conn.close()
                    st.session_state['orc_em_edicao'] = None
                    resetar_formulario_orcamento()

                lds = "".join([f"<tr><td style='padding:6px; border-bottom:1px solid #ddd;'>{s['d']}</td><td align='center' style='padding:6px; border-bottom:1px solid #ddd;'>{s['q']}</td><td align='right' style='padding:6px; border-bottom:1px solid #ddd;'>{formata_moeda(s['v']).replace('R$ ','')}</td><td align='right' style='padding:6px; border-bottom:1px solid #ddd;'>0,00</td><td align='right' style='padding:6px; border-bottom:1px solid #ddd;'>{formata_moeda(s['t']).replace('R$ ','')}</td></tr>" for s in srvs])
                
                hds = f"""
                <div class="folha-a4" style="background:white; color:black; padding:20px; font-family:Arial, sans-serif; font-size:12px; width:100%; max-width:21cm; margin:0 auto; box-sizing: border-box;">
                    <div style="display:flex; justify-content:space-between; margin-bottom:10px; border-bottom:3px solid #004488; padding-bottom:10px;">
                        <div style="width:50%;">
                            {carrega_logo("logo_dsystem.png","SYSTEM TECNOLOGIA","#004488","140")}<br>
                            <span style="color:#004488; font-size:10px; font-weight:bold;">PARCEIRA DA SUA EMPRESA</span><br><br>
                            <b style="font-size:12px;">D F Pereira Informática</b><br>
                            Rua Gl&oacute;ria, 25<br>
                            Sabará MG 34700-150
                        </div>
                        <div style="width:40%; text-align:right;">
                            <table style="width:100%; border-collapse:collapse; margin-bottom:5px; text-align:center;">
                                <tr>
                                    <td style="border:1px solid #ccc; padding:3px; font-weight:bold; background:#f4f4f4;">Criação:</td>
                                    <td style="border:1px solid #ccc; padding:3px;">{dtc}</td>
                                </tr>
                                <tr>
                                    <td style="border:1px solid #ccc; padding:3px; font-weight:bold; background:#f4f4f4;">Validade:</td>
                                    <td style="border:1px solid #ccc; padding:3px;">{dtv}</td>
                                </tr>
                            </table>
                            <h3 style="margin:5px 0; color:#004488;">Orçamento # {n_orc}</h3>
                            <p style="margin:0;">23.524.449/0001-54<br>adm@dsystemtecnologia.com.br<br>(31) 97117-7190</p>
                        </div>
                    </div>
                    <div style="margin-bottom:10px;">
                        <h4 style="color:#004488; border-bottom:1px solid #004488; margin-bottom:5px;">Cliente</h4>
                        <table style="width:100%; border:none; font-size:11px;">
                            <tr><td style="width:50%;"><b>Nome:</b> {nm}</td><td><b>CPF/CNPJ:</b> {cnj}</td></tr>
                            <tr><td><b>Endereço:</b> {end}, {num}{cfmt} - {bai} - {cid}{cepfmt}</td><td><b>Telefone:</b> {t}</td></tr>
                        </table>
                    </div>
                    <h4 style="color:#004488; border-bottom:1px solid #004488; margin-bottom:5px;">Itens</h4>
                    <table style="width:100%; border-collapse:collapse; margin-bottom:10px; font-size:11px;">
                        <tr style="background:#f4f4f4;">
                            <th style="padding:5px; border:1px solid #ccc; text-align:left;">Descrição</th>
                            <th style="padding:5px; border:1px solid #ccc;">Qtd</th>
                            <th style="padding:5px; border:1px solid #ccc; text-align:right;">Unit (R$)</th>
                            <th style="padding:5px; border:1px solid #ccc; text-align:right;">Desc (R$)</th>
                            <th style="padding:5px; border:1px solid #ccc; text-align:right;">Total (R$)</th>
                        </tr>
                        {lds}
                    </table>
                    <div style="display:flex; justify-content:flex-end; margin-bottom:15px;">
                        <table style="width:60%; border-collapse:collapse; text-align:right; font-size:11px;">
                            <tr style="background:#f4f4f4;">
                                <th style="padding:5px; border:1px solid #ccc; text-align:center;">Valor Total</th>
                                <th style="padding:5px; border:1px solid #ccc; text-align:center;">Total Liquido</th>
                            </tr>
                            <tr>
                                <td style="padding:5px; border:1px solid #ccc; text-align:center;">{formata_moeda(vt).replace('R$ ','')}</td>
                                <td style="padding:5px; border:1px solid #ccc; font-weight:bold; text-align:center;">{formata_moeda(vt).replace('R$ ','')}</td>
                            </tr>
                        </table>
                    </div>
                    <h4 style="color:#004488; border-bottom:1px solid #004488; margin-bottom:5px;">Pagamento</h4>
                    <p style="font-size:11px;"><b>{f_pag}</b> - {o_pag}</p>
                    <h4 style="color:#004488; border-bottom:1px solid #004488; margin-bottom:5px;">Obs:</h4>
                    <p style="font-size:11px;">{o_ger}</p>
                </div>
                """
                
                vnc = vt * 1.30
                lnc = "".join([f"<tr><td style='border:1px solid #222; padding:5px; text-align:center; width:7%;'>{idx+1}</td><td style='border:1px solid #222; padding:5px; width:48%;'>{s['d']}</td><td style='border:1px solid #222; padding:5px; text-align:center; width:12%;'>{s['q']}</td><td style='border:1px solid #222; padding:5px; text-align:right; width:16%;'>{formata_moeda(s['v']*1.30)}</td><td style='border:1px solid #222; padding:5px; text-align:right; width:17%;'>{formata_moeda(s['t']*1.30)}</td></tr>" for idx, s in enumerate(srvs)])
                linhas_vazias_nc = "".join(["<tr><td style='border:1px solid #222; padding:7px;'>&nbsp;</td><td style='border:1px solid #222; padding:7px;'>&nbsp;</td><td style='border:1px solid #222; padding:7px;'>&nbsp;</td><td style='border:1px solid #222; padding:7px;'>&nbsp;</td><td style='border:1px solid #222; padding:7px;'>&nbsp;</td></tr>" for _ in range(max(0, 18 - len(srvs)))])
                
                hnc = f"""
                <div class="folha-a4" style="background:white; color:black; padding:24px 28px; font-family:Arial, sans-serif; font-size:10px; width:100%; max-width:21cm; margin:0 auto; box-sizing:border-box;">
                    
                    <div style="text-align:center; margin-bottom:15px;">
                        <div style="margin-bottom:4px;">{carrega_logo("logo_lc_printer.jpg","LC Printer","#1c1762","125")}</div>
                        <div style="font-size:10px; line-height:1.4; font-weight:bold;">
                            Luiz Cl&aacute;udio da Silveira-ME - CNPJ 11.024.413/0001-22<br>
                            R. Geralda Martins de Miranda, 244 - Maria Goretti - Belo Horizonte/MG - CEP 31.930-450<br>
                            EMAIL: lc_printer@hotmail.com&nbsp;&nbsp;&nbsp;TELEFONES: (31) 3432-3593 / 9 8500-2691
                        </div>
                    </div>

                    <table style="width:100%; border-top:1px solid #111; border-bottom:1px solid #111; margin-bottom:12px; font-size:10px; line-height:1.4; border-collapse:collapse;">
                        <tr>
                            <td style="padding:4px 0; width:60%;"><b>NOME:</b> {nm}</td>
                            <td style="padding:4px 0; width:40%;"><b>EMAIL:</b> {em}</td>
                        </tr>
                        <tr>
                            <td style="padding:4px 0;"><b>TELEFONE:</b> {t}</td>
                            <td style="padding:4px 0;"><b>CPF/CNPJ:</b> {cnj} &nbsp;&nbsp; <b>RG/MEI:</b> {rg}</td>
                        </tr>
                        <tr>
                            <td colspan="2" style="padding:4px 0;"><b>ENDERE&Ccedil;O:</b> {end}{(', ' + num) if num else ''}{cfmt}</td>
                        </tr>
                        <tr>
                            <td colspan="2" style="padding:4px 0; padding-bottom:6px;"><b>BAIRRO:</b> {bai} &nbsp;&nbsp; <b>CIDADE:</b> {cid.replace(' / ', ' ')} &nbsp;&nbsp; <b>UF:</b> MG &nbsp;&nbsp; <b>CEP:</b> {cep}</td>
                        </tr>
                    </table>

                    <table style="width:100%; border-collapse:collapse; font-size:10px; margin-bottom:8px;">
                        <tr style="background:#efefef; font-weight:bold; text-align:center;">
                            <th style="border:1px solid #222; padding:5px;">ITEM</th>
                            <th style="border:1px solid #222; padding:5px;">PRODUTO/SERVI&Ccedil;O</th>
                            <th style="border:1px solid #222; padding:5px;">QUANT</th>
                            <th style="border:1px solid #222; padding:5px;">VALOR UNIDADE</th>
                            <th style="border:1px solid #222; padding:5px;">SUBTOTAL</th>
                        </tr>
                        {lnc}{linhas_vazias_nc}
                    </table>

                    <div style="display:flex; justify-content:flex-end; gap:34px; align-items:center; margin:8px 0 18px 0; font-size:12px; font-weight:bold;">
                        <span>DESCONTO: R$</span>
                        <span>ACR&Eacute;SCIMO: R$</span>
                        <span style="font-size:16px; letter-spacing:2px;">TOTAL: {formata_moeda(vnc)}</span>
                    </div>

                    <div style="display:flex; justify-content:flex-end; margin-top:18px; font-size:12px;">
                        <table style="width:42%; border-collapse:collapse;">
                            <tr><td colspan="2" style="font-weight:bold; font-size:15px; padding:3px 0;">OR&Ccedil;AMENTO n&deg; {n_orc}</td></tr>
                            <tr><td style="font-weight:bold; padding:3px 0;">DATA DE EMISS&Atilde;O:</td><td style="padding:3px 0;">{dtc}</td></tr>
                            <tr><td style="font-weight:bold; padding:3px 0;">VALIDO AT&Eacute;:</td><td style="padding:3px 0;">{dtv}</td></tr>
                        </table>
                    </div>
                </div>
                """

                vgt = vt * 1.45
                lgt = "".join([f"<tr><td style='border:1px solid #b8d5e3; padding:5px; text-align:center; width:8%;'>{idx+1}</td><td style='border:1px solid #b8d5e3; padding:5px; width:58%;'>{s['d']}</td><td style='border:1px solid #b8d5e3; padding:5px; text-align:center; width:12%;'>{s['q']}</td><td style='border:1px solid #b8d5e3; padding:5px; text-align:right; width:22%;'>{formata_moeda(s['t']*1.45)}</td></tr>" for idx, s in enumerate(srvs)])
                linhas_vazias_gt = "".join(["<tr><td style='border:1px solid #b8d5e3; padding:8px;'>&nbsp;</td><td style='border:1px solid #b8d5e3; padding:8px;'>&nbsp;</td><td style='border:1px solid #b8d5e3; padding:8px;'>&nbsp;</td><td style='border:1px solid #b8d5e3; padding:8px;'>&nbsp;</td></tr>" for _ in range(max(0, 5 - len(srvs)))])
                hgt = f"""
                <div class="folha-a4" style="background:white; color:#222; padding:24px 28px; font-family:Arial, sans-serif; font-size:10px; width:100%; max-width:21cm; margin:0 auto; box-sizing:border-box;">
                    <h1 style="font-size:30px; letter-spacing:0; color:#4ba3d5; margin:0 0 18px 0; font-weight:bold;">OR&Ccedil;AMENTO</h1>

                    <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:12px;">
                        <div style="width:26%;">
                            {carrega_logo("logo_gt.png","GT Solutions","#4ba3d5","120")}
                        </div>
                        <div style="width:50%; line-height:1.45; font-size:10px;">
                            <b>GT Solutions Eireli</b> CPF/CNPJ: 34.349.098/0001-09<br>
                            <b>ENDERE&Ccedil;O:</b> AV Alterosa 17, sala 6<br>
                            parque turista - contagem<br>
                            <b>TELEFONE:</b> (31) 9 8679-7785<br>
                            <b>EMAIL:</b> gustavo@gtimpressao.com.br<br>
                            <b>WEBSITE:</b> www.gtlmpressao.com.br
                        </div>
                        <div style="width:20%;"></div>
                    </div>

                    <table style="width:100%; border-collapse:collapse; margin-bottom:10px; font-size:10px;">
                        <tr style="background:#eaf6fb; color:#222; font-weight:bold;">
                            <td style="border:1px solid #8ec7df; padding:5px; width:34%;">OR&Ccedil;AMENTO N&deg;: {n_orc}</td>
                            <td style="border:1px solid #8ec7df; padding:5px; width:33%;">EMITIDO EM: {dtc}</td>
                            <td style="border:1px solid #8ec7df; padding:5px; width:33%;">VALIDO AT&Eacute;: {dtv}</td>
                        </tr>
                    </table>

                    <div style="background:#4ba3d5; color:white; font-weight:bold; padding:6px 8px; margin-bottom:0;">CLIENTE</div>
                    <table style="width:100%; border-collapse:collapse; font-size:10px; margin-bottom:12px;">
                        <tr><td style="border:1px solid #b8d5e3; padding:5px; width:50%;"><b>NOME</b> {nm}</td><td style="border:1px solid #b8d5e3; padding:5px;"><b>TELEFONE</b> {t} &nbsp;&nbsp; <b>EMAIL</b> {em}</td></tr>
                        <tr><td style="border:1px solid #b8d5e3; padding:5px;"><b>CPF/CNPJ</b> {cnj}</td><td style="border:1px solid #b8d5e3; padding:5px;"><b>RG/EI</b> {rg}</td></tr>
                        <tr><td colspan="2" style="border:1px solid #b8d5e3; padding:5px;"><b>ENDERE&Ccedil;O</b> {end}{(', ' + num) if num else ''}{cfmt}</td></tr>
                        <tr><td style="border:1px solid #b8d5e3; padding:5px;"><b>BAIRRO</b> {bai}</td><td style="border:1px solid #b8d5e3; padding:5px;"><b>CIDADE</b> {cid.replace(' / ', ' ')} &nbsp;&nbsp; <b>ESTADO</b> MG &nbsp;&nbsp; <b>CEP</b> {cep}</td></tr>
                    </table>

                    <div style="background:#4ba3d5; color:white; font-weight:bold; padding:6px 8px; margin-bottom:0;">OR&Ccedil;AMENTOS</div>
                    <table style="width:100%; border-collapse:collapse; font-size:10px; margin-bottom:8px;">
                        <tr style="background:#eaf6fb; font-weight:bold; text-align:center;">
                            <th style="border:1px solid #b8d5e3; padding:5px;">ITEM</th>
                            <th style="border:1px solid #b8d5e3; padding:5px;">PRODUTO/SERVI&Ccedil;O</th>
                            <th style="border:1px solid #b8d5e3; padding:5px;">QUANT</th>
                            <th style="border:1px solid #b8d5e3; padding:5px;">VALOR TOTAL</th>
                        </tr>
                        {lgt}{linhas_vazias_gt}
                    </table>

                    <div style="display:flex; justify-content:flex-end; gap:22px; font-size:11px; font-weight:bold; margin:8px 0 18px 0;">
                        <span>SUBTOTAL: {formata_moeda(vgt)}</span>
                        <span>DESCONTO: 0 R$</span>
                        <span>ACR&Eacute;SCIMO: 0 R$</span>
                        <span>TOTAL: {formata_moeda(vgt)}</span>
                    </div>

                    <div style="background:#4ba3d5; color:white; font-weight:bold; padding:6px 8px; margin-bottom:0;">OBSERVA&Ccedil;&Otilde;ES</div>
                    <div style="border:1px solid #b8d5e3; min-height:112px; padding:8px; font-size:10px; line-height:1.55;">
                        {o_ger}<br><br>
                        <b>FORMAS DE PAGAMENTO:</b><br>
                        - {f_pag}<br>
                        {('- ' + o_pag + '<br>') if o_pag else ''}
                        <br><b>OBS:</b> (12) MESES DE GARANTIA
                    </div>
                </div>
                """

                hds = limpar_html_impressao(hds)
                hnc = limpar_html_impressao(hnc)
                hgt = limpar_html_impressao(hgt)

                if bp:
                    if "Dsystem" in empesc: st.markdown(f'<div id="doc-impressao">{hds}</div>', unsafe_allow_html=True)
                    elif "LC" in empesc: st.markdown(f'<div id="doc-impressao">{hnc}</div>', unsafe_allow_html=True)
                    else: st.markdown(f'<div id="doc-impressao">{hgt}</div>', unsafe_allow_html=True)
                
                if bpa:
                    st.markdown(f'<div id="doc-impressao">{hds}<div class="quebra-pagina"></div>{hnc}<div class="quebra-pagina"></div>{hgt}</div>', unsafe_allow_html=True)
                    imprimir_html(f'{hds}<div class="quebra-pagina"></div>{hnc}<div class="quebra-pagina"></div>{hgt}', "Impressao Orcamento")

                if bimp:
                    html_imp = hds if "Dsystem" in empesc else hnc if "LC" in empesc else hgt
                    st.markdown(f'<div id="doc-impressao">{html_imp}</div>', unsafe_allow_html=True)
                    imprimir_html(html_imp, f"Orcamento {n_orc}")

                if bpdf_ds:
                    st.markdown(f'<div id="doc-impressao">{hds}</div>', unsafe_allow_html=True)
                    imprimir_html(hds, f"Orcamento {n_orc} Dsystem")
                if bpdf_nc:
                    st.markdown(f'<div id="doc-impressao">{hnc}</div>', unsafe_allow_html=True)
                    imprimir_html(hnc, f"Orcamento {n_orc} LC Printer")
                if bpdf_gt:
                    st.markdown(f'<div id="doc-impressao">{hgt}</div>', unsafe_allow_html=True)
                    imprimir_html(hgt, f"Orcamento {n_orc} GT")

    with aba2:
        st.subheader("Base de Orçamentos")
        conn = conectar_banco()
        conn.row_factory = None
        c = conn.cursor()
        c.execute('SELECT * FROM orcamentos ORDER BY orc_id DESC')
        df_orc = [dict(item) for item in c.fetchall()]
        ids_vencidos = []
        for item in df_orc:
            if orcamento_esta_vencido(item):
                item["status"] = "Vencido"
                ids_vencidos.append(int(item["orc_id"]))
        for orc_id_vencido in ids_vencidos:
            c.execute(
                "UPDATE orcamentos SET status=?, alterado_em=?, alterado_por=? WHERE orc_id=?",
                ("Vencido", agora_br(), "Vencimento automático", orc_id_vencido),
            )
        if ids_vencidos:
            conn.commit()
        conn.close()
        df_orc = filtrar_registros_por_empresa(df_orc, "cliente")
        
        if df_orc:
            df_orc_todos = [dict(o) for o in df_orc]
            st.markdown("#### Pesquisa e faturamento rápido")
            fo1, fo2, fo3, fo4 = st.columns(4)
            orc_hist_mes = fo1.date_input("Filtrar por mês:", value=None, key="orc_hist_mes")
            orc_hist_cliente = fo2.text_input("Pesquisar cliente/CPF/Nº:", key="orc_hist_cliente")
            status_orc_opts = ["Todos"] + sorted({(o.get("status") or "Aberto") for o in df_orc_todos})
            orc_hist_status = fo3.selectbox("Status:", status_orc_opts, key="orc_hist_status")
            orc_hist_lancamento = fo4.selectbox("Faturamento:", ["Todos", "A lançar", "Já lançado"], key="orc_hist_lancamento")

            df_orc_filtrado = list(df_orc_todos)
            if orc_hist_mes:
                df_orc_filtrado = [
                    o for o in df_orc_filtrado
                    if parse_data_flex(o.get("data_orc")) and parse_data_flex(o.get("data_orc")).strftime("%Y-%m") == orc_hist_mes.strftime("%Y-%m")
                ]
            termo_orc = orc_hist_cliente.strip().lower()
            if termo_orc:
                df_orc_filtrado = [
                    o for o in df_orc_filtrado
                    if termo_orc in str(o.get("cliente") or "").lower()
                    or termo_orc in str(o.get("cpf_cnpj") or "").lower()
                    or termo_orc in str(o.get("numero") or "").lower()
                    or termo_orc in str(o.get("orc_id") or "").lower()
                ]
            if orc_hist_status != "Todos":
                df_orc_filtrado = [o for o in df_orc_filtrado if (o.get("status") or "Aberto") == orc_hist_status]
            if orc_hist_lancamento != "Todos":
                if orc_hist_lancamento == "A lançar":
                    df_orc_filtrado = [o for o in df_orc_filtrado if not o.get("faturamento_id") and (o.get("status") or "Aberto") != "Aprovado e lançado"]
                else:
                    df_orc_filtrado = [o for o in df_orc_filtrado if o.get("faturamento_id") or (o.get("status") or "") == "Aprovado e lançado"]

            view_orc = []
            total_orc_filtrado = 0.0
            itens_orc_filtrados = 0
            for x in df_orc_filtrado:
                itens_x = itens_orcamento_normalizados(x.get("itens"))
                valor_x = sum(float(item.get("t") or 0) for item in itens_x)
                total_orc_filtrado += valor_x
                itens_orc_filtrados += len(itens_x)
                view_orc.append({
                    "ID": x.get("orc_id"),
                    "Número": x.get("numero"),
                    "Data": data_para_br(x.get("data_orc")),
                    "Validade": data_para_br(x.get("data_validade")) or data_para_br(data_validade_orcamento(x.get("data_orc"))),
                    "Cliente": x.get("cliente") or "",
                    "CPF/CNPJ": x.get("cpf_cnpj") or "",
                    "Tipo": tipo_nota_por_itens(itens_x),
                    "Valor Dsystem": formatar_moeda_br(valor_x),
                    "Forma": x.get("forma_pagamento") or "",
                    "Status": x.get("status") or "Aberto",
                    "Faturamento": f"#{x.get('faturamento_id')}" if x.get("faturamento_id") else "A lançar",
                })

            mo1, mo2, mo3 = st.columns(3)
            mo1.metric("Orçamentos filtrados", len(view_orc))
            mo2.metric("Total Dsystem", formatar_moeda_br(total_orc_filtrado))
            mo3.metric("Itens Dsystem", itens_orc_filtrados)

            if view_orc:
                st.dataframe(view_orc, width="stretch", hide_index=True)
            else:
                st.info("Nenhum orçamento encontrado com os filtros selecionados.")

            if tem_permissao("orcamentos.edit") or tem_permissao("faturamento.edit"):
                with st.expander("Aprovar rápido e lançar no faturamento", expanded=False):
                    st.caption("Cada botão lança somente o orçamento Dsystem no faturamento, mantendo Produto/Serviço por item.")
                    for orc_row in df_orc_filtrado:
                        status_orc = orc_row.get("status") or "Aberto"
                        ja_lancado = bool(orc_row.get("faturamento_id")) or status_orc == "Aprovado e lançado"
                        col_o1, col_o2, col_o3, col_o4, col_o5 = st.columns([0.7, 2.4, 1.2, 1.4, 1.6])
                        col_o1.write(f"#{orc_row.get('numero') or orc_row.get('orc_id')}")
                        col_o2.write(orc_row.get("cliente") or "")
                        col_o3.write(orc_row.get("valor_total") or "")
                        col_o4.write(status_orc)
                        if ja_lancado:
                            col_o5.caption(f"Faturamento #{orc_row.get('faturamento_id')}")
                        elif col_o5.button("Lançar no faturamento", key=f"orc_lancar_rapido_{orc_row.get('orc_id')}", width="stretch"):
                            fat_id, _, _ = lancar_orcamento_dsystem_no_faturamento(orc_row)
                            st.success(f"Faturamento #{fat_id} criado.")
                            st.rerun()
        else:
            st.info("Nenhum orçamento encontrado.")
            
        if df_orc:
            st.write("---")
            opcoes_acao_orc = [
                "Visualizar/Editar Orçamento",
                "Renegociar orçamento vencido",
                "Enviar por e-mail ou WhatsApp",
                "Lançar orçamento aprovado no faturamento",
            ]
            if tem_permissao("orcamentos.delete"):
                opcoes_acao_orc.append("Excluir Orçamento")
            act_orc = st.radio("Ação (Orçamentos):", opcoes_acao_orc, horizontal=True)
            
            if act_orc == "Excluir Orçamento":
                idd = st.number_input("ID do Orçamento para excluir", min_value=1, step=1, key="del_orc_id")
                if st.button("Excluir Orçamento", key="btn_del_orc"): 
                    deletar_registro('orcamentos', 'orc_id', idd)
                    st.success("Excluído com sucesso.")
                    st.rerun()
            elif act_orc == "Visualizar/Editar Orçamento":
                idd = st.number_input("ID do Orçamento para Carregar:", min_value=1, step=1, key="edit_orc_id")
                st.caption("Para gerar PDF com o layout correto, carregue o orçamento na edição e use os botões PDF Dsystem, PDF LC Printer ou PDF GT.")
                if st.button("Carregar na Tela de Edição", key="btn_edit_orc"):
                    orc_load = next((dict(o) for o in df_orc if o['orc_id'] == idd), None)
                    if orc_load:
                        st.session_state['orc_em_edicao'] = orc_load
                        resetar_formulario_orcamento()
                        st.rerun()
                    else:
                        st.error("ID não encontrado.")
            elif act_orc == "Renegociar orçamento vencido":
                id_reneg = st.number_input("ID do orçamento para renegociar:", min_value=1, step=1, key="reneg_orc_id")
                orc_reneg = next((dict(o) for o in df_orc if int(o['orc_id']) == int(id_reneg)), None)
                if orc_reneg:
                    st.info(
                        f"Será criada uma nova versão de {orc_reneg.get('numero')} para {orc_reneg.get('cliente')}. "
                        "O orçamento original permanecerá no histórico como Vencido."
                    )
                    enc1, enc2 = st.columns(2)
                    juros_reneg = enc1.number_input(
                        "Juros opcional (%):", min_value=0.0, max_value=100.0,
                        value=0.0, step=0.5, format="%.2f", key=f"juros_reneg_{id_reneg}",
                    )
                    taxa_reneg = enc2.number_input(
                        "Taxa fixa opcional (R$):", min_value=0.0,
                        value=0.0, step=10.0, format="%.2f", key=f"taxa_reneg_{id_reneg}",
                    )
                    itens_originais_reneg = itens_orcamento_normalizados(orc_reneg.get("itens"))
                    itens_ajustados_reneg = aplicar_encargos_renegociacao(itens_originais_reneg, juros_reneg, taxa_reneg)
                    total_original_reneg = total_geral_orcamento(itens_originais_reneg)
                    total_novo_reneg = total_geral_orcamento(itens_ajustados_reneg)
                    sim1, sim2, sim3 = st.columns(3)
                    sim1.metric("Valor original", formatar_moeda_br(total_original_reneg))
                    sim2.metric("Encargos", formatar_moeda_br(total_novo_reneg - total_original_reneg))
                    sim3.metric("Nova cotação", formatar_moeda_br(total_novo_reneg))
                    pode_renegociar = (orc_reneg.get("status") or "Aberto") == "Vencido"
                    if not pode_renegociar:
                        st.warning("A renegociação fica disponível quando o orçamento estiver com status Vencido.")
                    if st.button("Criar nova cotação para renegociação", type="primary", width="stretch", key="btn_reneg_orc", disabled=not pode_renegociar):
                        versao_nova = int(orc_reneg.get("versao") or 1) + 1
                        numero_novo = numero_renegociacao(orc_reneg.get("numero"), int(orc_reneg.get("versao") or 1))
                        origem_id = int(orc_reneg.get("orcamento_origem_id") or orc_reneg["orc_id"])
                        hoje_txt = date.today().strftime("%d/%m/%Y")
                        validade_txt = (date.today() + timedelta(days=10)).strftime("%d/%m/%Y")
                        conn_reneg = conectar_banco()
                        cr = conn_reneg.cursor()
                        itens_reneg_json = json.dumps(itens_ajustados_reneg, ensure_ascii=False)
                        cr.execute(
                            """INSERT INTO orcamentos
                               (numero, data_orc, cliente, cpf_cnpj, valor_total, forma_pagamento,
                                 obs_pag, obs_geral, itens, status, data_validade, orcamento_origem_id,
                                 versao, juros_percentual, taxa_renegociacao, alterado_em, alterado_por)
                               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (numero_novo, hoje_txt, orc_reneg.get("cliente"), orc_reneg.get("cpf_cnpj"),
                             formatar_moeda_br(total_novo_reneg), orc_reneg.get("forma_pagamento"),
                             orc_reneg.get("obs_pag"), orc_reneg.get("obs_geral"), itens_reneg_json,
                             "Em negociação", validade_txt, origem_id, versao_nova,
                             juros_reneg, taxa_reneg, agora_br(), st.session_state.get("username", "")),
                        )
                        novo_id = cr.lastrowid
                        cr.execute("UPDATE orcamentos SET status=? WHERE orc_id=?", ("Vencido", id_reneg))
                        conn_reneg.commit()
                        cr.execute("SELECT * FROM orcamentos WHERE orc_id=?", (novo_id,))
                        novo_orcamento = dict(cr.fetchone())
                        conn_reneg.close()
                        st.session_state['orc_em_edicao'] = novo_orcamento
                        resetar_formulario_orcamento()
                        st.success(f"Renegociação {numero_novo} criada.")
                        st.rerun()
                else:
                    st.warning("Informe um ID de orçamento válido.")
            elif act_orc == "Enviar por e-mail ou WhatsApp":
                id_envio = st.number_input("ID do orçamento para enviar:", min_value=1, step=1, key="env_orc_id")
                orc_envio = next((dict(o) for o in df_orc if int(o['orc_id']) == int(id_envio)), None)
                if orc_envio:
                    conn_env = conectar_banco()
                    ce = conn_env.cursor()
                    ce.execute("SELECT email, telefone FROM clientes WHERE nome=? LIMIT 1", (orc_envio.get("cliente"),))
                    contato_env = ce.fetchone() or {}
                    empresas_envio = ["Dsystem Tecnologia", "LC Printer", "GT Solutions"]
                    empresa_envio = st.selectbox("Modelo do orçamento:", empresas_envio, key=f"empresa_env_orc_{id_envio}")
                    ce.execute(
                        "SELECT nome_arquivo, mime_type, arquivo FROM orcamento_pdfs WHERE orc_id=? AND empresa=? ORDER BY id DESC LIMIT 1",
                        (id_envio, empresa_envio),
                    )
                    pdf_envio = ce.fetchone()
                    conn_env.close()
                    email_envio = st.text_input("E-mail do cliente:", value=contato_env.get("email") or "", key=f"email_env_orc_{id_envio}")
                    telefone_envio = st.text_input("WhatsApp do cliente:", value=contato_env.get("telefone") or "", key=f"whats_env_orc_{id_envio}")
                    assunto_envio = f"Orçamento {orc_envio.get('numero')} - Dsystem Tecnologia"
                    mensagem_envio = (
                        f"Olá, {orc_envio.get('cliente') or 'cliente'}. Segue o orçamento "
                        f"{orc_envio.get('numero')} no valor de {orc_envio.get('valor_total') or ''}, "
                        f"válido até {data_para_br(orc_envio.get('data_validade'))}."
                    )
                    if not pdf_envio:
                        st.warning("Este orçamento ainda não possui PDF salvo. Carregue-o na edição e salve novamente para gerar os PDFs.")
                    else:
                        e1, e2 = st.columns(2)
                        if e1.button("Enviar PDF por e-mail", type="primary", width="stretch", key=f"btn_email_orc_{id_envio}"):
                            if not email_envio.strip():
                                st.error("Informe o e-mail do cliente.")
                            else:
                                try:
                                    enviar_email_com_anexo(
                                        email_envio.strip(), assunto_envio, mensagem_envio,
                                        pdf_envio.get("nome_arquivo") or f"orcamento_{orc_envio.get('numero')}.pdf",
                                        pdf_envio.get("arquivo"), pdf_envio.get("mime_type") or "application/pdf",
                                    )
                                    conn_marca = conectar_banco()
                                    cm = conn_marca.cursor()
                                    cm.execute("UPDATE orcamentos SET enviado_email_em=? WHERE orc_id=?", (agora_br(), id_envio))
                                    conn_marca.commit()
                                    conn_marca.close()
                                    st.success("Orçamento enviado por e-mail.")
                                except Exception as ex:
                                    st.error(f"Não foi possível enviar o e-mail: {ex}")
                        if telefone_envio.strip():
                            e2.link_button(
                                "Abrir conversa no WhatsApp",
                                url_whatsapp(telefone_envio, mensagem_envio + " Vou enviar o PDF nesta conversa."),
                                width="stretch",
                            )
                        else:
                            e2.button("Abrir conversa no WhatsApp", disabled=True, width="stretch", key=f"whats_sem_tel_{id_envio}")
                        st.download_button(
                            "Baixar PDF para anexar no WhatsApp",
                            data=bytes(pdf_envio.get("arquivo")),
                            file_name=pdf_envio.get("nome_arquivo") or f"orcamento_{orc_envio.get('numero')}.pdf",
                            mime=pdf_envio.get("mime_type") or "application/pdf",
                            width="stretch",
                            key=f"download_whats_orc_{id_envio}",
                        )
                        st.caption("O WhatsApp abre com a mensagem pronta; anexe o PDF baixado antes de enviar.")
                else:
                    st.warning("Informe um ID de orçamento válido.")
            elif act_orc == "Lançar orçamento aprovado no faturamento":
                id_aprov = st.number_input("ID do orçamento aprovado:", min_value=1, step=1, key="orc_aprov_id")
                orc_aprov = next((dict(o) for o in df_orc if int(o['orc_id']) == int(id_aprov)), None)
                if orc_aprov:
                    itens_aprov = itens_orcamento_normalizados(orc_aprov.get("itens"))
                    valor_aprov = sum(float(item.get("t") or 0) for item in itens_aprov)
                    tipo_nota_aprov = tipo_nota_por_itens(itens_aprov)
                    st.info(f"Cliente: {orc_aprov.get('cliente')} | Orçamento aprovado: Dsystem Tecnologia | Tipo: {tipo_nota_aprov} | Valor: {formatar_moeda_br(valor_aprov)}")
                    if st.button("Aprovar Dsystem e lançar no faturamento", type="primary", width="stretch", key="btn_lancar_orc_faturamento"):
                        fat_id, _, _ = lancar_orcamento_dsystem_no_faturamento(orc_aprov)
                        st.success(f"Faturamento #{fat_id} criado com o orçamento Dsystem aprovado.")
                        st.rerun()
                else:
                    st.warning("Informe um ID de orçamento válido.")


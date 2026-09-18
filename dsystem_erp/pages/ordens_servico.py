from __future__ import annotations

from dsystem_erp.app_context import aplicar_contexto_pagina
from dsystem_erp.ui_consulta import tabela_selecionavel_id
from dsystem_erp.services.recepcao_kanban import gerar_etiqueta_equipamento


def renderizar_ordem_servico(ctx: dict) -> None:
    aplicar_contexto_pagina(ctx, globals())
    st.title("Ordens de Serviço")
    versao_nova_os = int(st.session_state.get("os_nova_versao", 0))
    funcionarios_os = listar_funcionarios_sistema()
    tecnicos_por_label = {
        item["label"]: (item.get("nome") or item.get("username") or "")
        for item in funcionarios_os
        if item.get("label")
    }

    def selecionar_tecnico(rotulo, valor_atual="", permitir_vazio=False, key=None):
        opcoes = (["-- Sem segundo técnico --"] if permitir_vazio else ["-- Selecionar técnico --"]) + list(tecnicos_por_label)
        valor_atual = str(valor_atual or "").strip()
        label_atual = next((label for label, valor in tecnicos_por_label.items() if valor == valor_atual), None)
        if valor_atual and not label_atual:
            label_atual = f"{valor_atual} (cadastro antigo)"
            opcoes.append(label_atual)
        indice = opcoes.index(label_atual) if label_atual in opcoes else 0
        escolhido = st.selectbox(rotulo, opcoes, index=indice, key=key)
        if escolhido.startswith("-- "):
            return ""
        return tecnicos_por_label.get(escolhido, valor_atual if escolhido == label_atual else escolhido)

    conn_tipos_os = conectar_banco()
    c_tipos_os = conn_tipos_os.cursor()
    c_tipos_os.execute("SELECT * FROM os_tipos_aparelhos ORDER BY nome")
    tipos_os_cadastrados = [dict(item) for item in c_tipos_os.fetchall()]
    conn_tipos_os.close()
    tipos_os_ativos = [item.get("nome") for item in tipos_os_cadastrados if item.get("ativo") != "Não"]
    if "Notebook" not in tipos_os_ativos:
        tipos_os_ativos.append("Notebook")
    if not tipos_os_ativos:
        tipos_os_ativos = ["Desktop", "Notebook", "Outro"]

    if not funcionarios_os:
        st.warning("Nenhum funcionário/técnico cadastrado. Cadastre o funcionário em Usuários para vinculá-lo à O.S.")
    aba1, aba2, aba3 = st.tabs(["Gerar Nova O.S.", "Histórico de Registros", "Tipos / Aparelhos"])
    with aba1:
        cdb = buscar_clientes()
        cn = ["-- Preencher Manualmente --"] + [c['nome'] for c in cdb]
        cs = st.selectbox("Buscar Cliente:", cn, key=f"os_novo_busca_{versao_nova_os}")
        dc = next((c for c in cdb if c['nome'] == cs), {})
        cliente_indice = cn.index(cs)
        endc = f"{dc.get('endereco','')}, {dc.get('numero','')}"
        
        c1, c2 = st.columns(2)
        with c1: 
            oc = st.text_input("Nome Cliente:", value=dc.get('nome',''), key=f"os_novo_nome_{versao_nova_os}_{cliente_indice}")
        with c2: 
            ocpf = st.text_input("CPF/CNPJ:", value=dc.get('cnpj',''), key=f"os_novo_cpf_{versao_nova_os}_{cliente_indice}")
            
        c3, c4, c5 = st.columns([3,1,1])
        with c3: 
            oend = st.text_input("Endereço Completo:", value=endc, key=f"os_novo_endereco_{versao_nova_os}_{cliente_indice}")
        with c4: 
            ocep = st.text_input("CEP:", value=dc.get('cep',''), key=f"os_novo_cep_{versao_nova_os}_{cliente_indice}")
        with c5: 
            otel = st.text_input("Telefone:", value=dc.get('telefone',''), key=f"os_novo_telefone_{versao_nova_os}_{cliente_indice}")

        conn_ch_os = conectar_banco(); c_ch_os = conn_ch_os.cursor()
        c_ch_os.execute("""SELECT id, titulo, status FROM chamados_cliente
                            WHERE cliente_nome=? AND COALESCE(status,'') NOT IN ('Concluído','Concluido','Fechado','Cancelado')
                            ORDER BY id DESC""", (oc,))
        chamados_abertos_os = [dict(item) for item in c_ch_os.fetchall()]
        conn_ch_os.close()
        opcoes_chamado_os = ["-- Entrada sem chamado anterior --"] + [
            f"#{item['id']} — {item.get('titulo') or 'Chamado'} ({item.get('status') or 'Aberto'})"
            for item in chamados_abertos_os
        ]
        chamado_os_label = st.selectbox("Vincular a um chamado aberto (opcional):", opcoes_chamado_os, key=f"os_novo_chamado_{versao_nova_os}")
        chamado_os_id = int(chamado_os_label.split(" — ", 1)[0].replace("#", "")) if chamado_os_label.startswith("#") else None
        
        st.write("---")
        st.subheader("Equipamentos da O.S.")

        if "os_itens_temp" not in st.session_state:
            st.session_state["os_itens_temp"] = []
        if "os_item_idx" not in st.session_state:
            st.session_state["os_item_idx"] = 0

        itens_temp = st.session_state["os_itens_temp"]
        item_idx = st.session_state["os_item_idx"]
        st.caption(f"Item atual: NOVA-{letra_equipamento(item_idx)}. A numeracao final sera gerada depois de salvar a O.S.")

        eqc1, eqc2, eqc3, eqc4 = st.columns([2, 2, 2, 1])
        tipo_eq = eqc1.selectbox("Tipo:", tipos_os_ativos, key=f"os_novo_{versao_nova_os}_tipo_{item_idx}")
        eq_nome = eqc2.text_input("Aparelho:", key=f"os_novo_{versao_nova_os}_equip_{item_idx}")
        eq_marca = eqc3.text_input("Marca/Modelo:", key=f"os_novo_{versao_nova_os}_marca_{item_idx}")
        eq_avaria = eqc4.selectbox("Avaria?", ["Nao", "Sim"], key=f"os_novo_{versao_nova_os}_avaria_{item_idx}")
        eq_serie = st.text_input("Numero de serie / patrimonio:", key=f"os_novo_{versao_nova_os}_serie_{item_idx}")
        eq_foto = st.file_uploader("Foto deste equipamento (opcional):", type=TIPOS_IMAGEM_UPLOAD, key=f"os_novo_{versao_nova_os}_foto_{item_idx}")

        st.write("**Configuracao do equipamento**")
        cfg1, cfg2, cfg3, cfg4 = st.columns(4)
        cfg_cpu = cfg1.text_input("CPU:", key=f"os_novo_{versao_nova_os}_cpu_{item_idx}")
        cfg_ram = cfg2.text_input("RAM:", key=f"os_novo_{versao_nova_os}_ram_{item_idx}")
        cfg_hd = cfg3.text_input("HD/SSD:", key=f"os_novo_{versao_nova_os}_hd_{item_idx}")
        cfg_gpu = cfg4.text_input("GPU:", key=f"os_novo_{versao_nova_os}_gpu_{item_idx}")
        cfg5, cfg6, cfg7 = st.columns([2, 1, 1])
        cfg_placa = cfg5.text_input("Placa mae:", key=f"os_novo_{versao_nova_os}_placa_{item_idx}")
        cfg_gab = cfg6.text_input("Gabinete/Carcaca:", key=f"os_novo_{versao_nova_os}_gab_{item_idx}")
        cfg_chave = cfg7.text_input("Chave S.O.:", key=f"os_novo_{versao_nova_os}_chave_{item_idx}")

        st.write("**Servico e checklist deste equipamento**")
        cf1, cf2, cf3, cf4, cf5 = st.columns(5)
        ofo = cf1.selectbox("Deixou Fonte?", ["Nao", "Sim"], key=f"os_novo_{versao_nova_os}_fonte_{item_idx}")
        ofmt = cf2.selectbox("Formatar?", ["Nao", "Sim"], key=f"os_novo_{versao_nova_os}_formatar_{item_idx}")
        obk = cf3.selectbox("Backup?", ["Nao", "Sim"], key=f"os_novo_{versao_nova_os}_backup_{item_idx}")
        oap = cf4.selectbox("Apps Padroes?", ["Nao", "Sim"], key=f"os_novo_{versao_nova_os}_apps_{item_idx}")
        oso = cf5.text_input("S.O.:", key=f"os_novo_{versao_nova_os}_so_{item_idx}")
        ca1, ca2 = st.columns([1, 4])
        oac = ca1.selectbox("App Especifico?", ["Nao", "Sim"], key=f"os_novo_{versao_nova_os}_app_chk_{item_idx}")
        oan = ca2.text_input("Qual App?", key=f"os_novo_{versao_nova_os}_app_nome_{item_idx}")
        osrv = st.text_area("Problema/servico relatado deste equipamento:", key=f"os_novo_{versao_nova_os}_servico_{item_idx}")

        col_tec1, col_tec2 = st.columns(2)
        with col_tec1:
            otec = selecionar_tecnico("Técnico responsável:", key=f"os_novo_tecnico_principal_{versao_nova_os}")
        with col_tec2:
            otec_extra = selecionar_tecnico("2º técnico / troca no processo:", permitir_vazio=True, key=f"os_novo_tecnico_extra_{versao_nova_os}")

        def montar_item_os():
            foto_item = {}
            if eq_foto:
                if not upload_dentro_limite(eq_foto):
                    erro_upload_grande("foto")
                    return None
                foto_dados, foto_nome, foto_mime = dados_upload(eq_foto)
                foto_item = {"dados": foto_dados, "nome": foto_nome, "mime": foto_mime}
            return {"tipo": tipo_eq, "equipamento": eq_nome, "marca": eq_marca, "serie": eq_serie, "avaria": eq_avaria, "defeito": osrv, "servico": osrv,
                    "foto": foto_item,
                    "config": {"tipo": tipo_eq, "so": oso, "cpu": cfg_cpu, "ram": cfg_ram, "hd": cfg_hd, "gpu": cfg_gpu, "placa": cfg_placa, "gabinete": cfg_gab, "chave_so": cfg_chave, "fonte": ofo, "formatar": ofmt, "backup": obk, "apps_padrao": oap, "app_especifico": oac, "app_especifico_nome": oan}}

        def guardar_item_atual(avancar=False):
            item = montar_item_os()
            if item is None:
                return False
            if not item["equipamento"].strip():
                st.error("Preencha o aparelho do item atual antes de salvar.")
                return False
            itens = st.session_state["os_itens_temp"]
            idx = st.session_state["os_item_idx"]
            if idx < len(itens): itens[idx] = item
            else: itens.append(item)
            st.session_state["os_itens_temp"] = itens
            if avancar: st.session_state["os_item_idx"] = len(itens)
            return True

        b_item1, b_item2, b_item3 = st.columns(3)
        if b_item1.button("Salvar este equipamento", width="stretch"):
            if guardar_item_atual(False): st.success(f"Equipamento {letra_equipamento(st.session_state['os_item_idx'])} salvo na lista.")
        if b_item2.button("Salvar e ir para proximo", width="stretch"):
            if guardar_item_atual(True): st.rerun()
        if b_item3.button("Limpar lista de equipamentos", width="stretch"):
            st.session_state["os_itens_temp"] = []; st.session_state["os_item_idx"] = 0; st.rerun()

        if itens_temp:
            st.write("**Equipamentos ja adicionados nesta O.S.:**")
            st.dataframe([{ "Item": letra_equipamento(i), "Tipo": it.get("tipo", ""), "Aparelho": it.get("equipamento", ""), "Marca": it.get("marca", ""), "Serie": it.get("serie", ""), "Configuracao": resumo_config_os(it)} for i, it in enumerate(itens_temp)], width="stretch", hide_index=True)
            for i, item_temp in enumerate(itens_temp):
                foto_temp = item_temp.get("foto") or {}
                if foto_temp.get("dados"):
                    st.image(foto_temp["dados"], caption=f"Foto do item {letra_equipamento(i)} - {foto_temp.get('nome') or ''}", width=220)

        if st.button("Salvar todos os equipamentos e gerar ficha", type="primary", width="stretch"):
            if eq_nome.strip():
                guardar_item_atual(False)
            eqs = st.session_state.get("os_itens_temp", [])
            if oc and eqs:
                endf = f"{oend} - CEP: {ocep}" if ocep else oend
                dt = date.today().strftime("%d/%m/%Y")
                salvar_cliente_simples(oc, ocpf, oend, otel, ocep)
                cliente_os_id = dc.get("id")
                if not cliente_os_id:
                    conn_cliente_os = conectar_banco(); c_cliente_os = conn_cliente_os.cursor()
                    c_cliente_os.execute(
                        "SELECT id FROM clientes WHERE documento_chave=? OR cnpj=? OR nome=? ORDER BY id DESC LIMIT 1",
                        (normalizar_documento_cliente(ocpf), ocpf, oc),
                    )
                    cliente_os_row = c_cliente_os.fetchone() or {}
                    cliente_os_id = cliente_os_row.get("id")
                    conn_cliente_os.close()
                if not cliente_os_id:
                    st.error(
                        "A O.S. precisa estar vinculada a um cliente cadastrado. "
                        "Selecione um cliente da lista ou informe um CPF/CNPJ válido para cadastrá-lo."
                    )
                    st.stop()
                primeiro = eqs[0]; cfg0 = primeiro.get("config", {})
                conn = conectar_banco(); c = conn.cursor()
                c.execute("""
                    INSERT INTO ordens_servico (
                        cliente_id, data_os, cliente, cpf_cnpj, endereco, equipamento, marca, avaria, servico, atendente,
                        so, formatar, backup, aplicativos, fonte, hd_ssd, ram, cpu, gpu, placa_mae, gabinete, chave_so, app_especifico_check, app_especifico_nome, tecnico_extra,
                        chamado_id, recebido_por, recebido_em
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (cliente_os_id, dt, oc, ocpf, endf, "|".join([x.get('equipamento','') for x in eqs]), "|".join([x.get('marca','') for x in eqs]), "|".join([x.get('avaria','') for x in eqs]), "|".join([x.get('servico','') for x in eqs]), otec, cfg0.get('so',''), cfg0.get('formatar',''), cfg0.get('backup',''), cfg0.get('apps_padrao',''), cfg0.get('fonte',''), cfg0.get('hd',''), cfg0.get('ram',''), cfg0.get('cpu',''), cfg0.get('gpu',''), cfg0.get('placa',''), cfg0.get('gabinete',''), cfg0.get('chave_so',''), cfg0.get('app_especifico',''), cfg0.get('app_especifico_nome',''), otec_extra, chamado_os_id, st.session_state.get("username", ""), agora_br()))
                oid = c.lastrowid
                salvar_equipamentos_os(c, oid, eqs)
                conn.commit(); conn.close()

                conn_et = conectar_banco(); cet = conn_et.cursor()
                cet.execute("""SELECT eo.*, os.cliente, os.cpf_cnpj, os.chamado_id
                               FROM equipamentos_os eo JOIN ordens_servico os ON os.os_id=eo.os_id
                               WHERE eo.os_id=? ORDER BY eo.id""", (oid,))
                equipamentos_etiqueta = [dict(item) for item in cet.fetchall()]
                conn_et.close()
                st.success("O.S. salva. Equipamentos enviados ao Kanban na etapa Recebido.")
                st.markdown("#### Etiquetas dos equipamentos")
                for item_etiqueta in equipamentos_etiqueta:
                    st.download_button(
                        f"Imprimir etiqueta {item_etiqueta.get('numero_item')}",
                        data=gerar_etiqueta_equipamento(item_etiqueta, APP_BASE_URL),
                        file_name=f"etiqueta_{item_etiqueta.get('numero_item')}.pdf",
                        mime="application/pdf", key=f"etiqueta_os_nova_{item_etiqueta.get('id')}",
                    )

                
                logo_html = carrega_logo("logo_dsystem.png","DSYSTEM","#004488","130")
                cabecalho_empresa = f'''<table style="width:100%; border:none; margin-bottom:8px;">
                  <tr>
                    <td style="width:50%;">{logo_html}</td>
                    <td style="width:50%; text-align:right; font-size:10px; line-height:1.5;">
                      <b style="font-size:12px; color:#004488;">D F Pereira Inform&aacute;tica</b><br>
                      adm@dsystemtecnologia.com.br<br>
                      (31) 97117-7190<br>
                      Rua Gl&oacute;ria, 25<br>
                      Sabará, MG - 34.700-150<br>
                      CNPJ: 23.524.449/0001-54
                    </td>
                  </tr>
                </table>'''

                folhas_html = []
                for idx, eq in enumerate(eqs):
                    letra = letra_equipamento(idx)
                    num_item = numero_item_os(oid, idx)
                    cfg = eq.get("config", {})

                    avaria_txt = eq.get('avaria','NAO').upper()
                    checklist_itens = [
                        ("Formatação", cfg.get('formatar','Nao')),
                        ("Backup", cfg.get('backup','Nao')),
                        ("Apps Padrão", cfg.get('apps_padrao','Nao')),
                        ("Deixou Fonte", cfg.get('fonte','Nao')),
                        ("S.O.", cfg.get('so','')),
                    ]
                    if cfg.get('app_especifico','Nao') == 'Sim':
                        checklist_itens.append(("App Específico", cfg.get('app_especifico_nome','')))

                    checklist_map = {k: v for k, v in checklist_itens}
                    hardware_itens = [
                        ("CPU", cfg.get('cpu', '')), ("RAM", cfg.get('ram', '')),
                        ("Disco", cfg.get('hd', '')), ("GPU", cfg.get('gpu', '')),
                        ("Placa Mãe", cfg.get('placa', '')), ("Gabinete", cfg.get('gabinete', '')),
                        ("Chave", cfg.get('chave_so', ''))
                    ]
                    hw_cells = "".join([
                        f'<td style="border:1px solid #333; padding:5px 6px; width:{100/4}%"><b>{h(k)}:</b> {h(v)}</td>'
                        for k, v in hardware_itens[:4]
                    ])
                    hw_cells2 = "".join([
                        f'<td style="border:1px solid #333; padding:5px 6px;" colspan="{2 if k == "Placa Mãe" else 1}"><b>{h(k)}:</b> {h(v)}</td>'
                        for k, v in hardware_itens[4:]
                    ])

                    folha = f'''
    <div class="folha-a4" style="font-family:Arial, sans-serif; font-size:10px; color:#111; background:#fff; width:210mm; min-height:297mm; margin:0 auto; padding:12mm 10mm; box-sizing:border-box; page-break-after: always;">
      {cabecalho_empresa}
      <div style="text-align:center; margin:8px 0 12px 0;">
    <span style="display:inline-block; border:1px solid #555; border-radius:16px; padding:5px 28px; font-size:13px; font-weight:bold; background:#f7f7f7;">
      Ordem de Servi&ccedil;o N&deg; {oid:05d}
    </span>
      </div>

      <table style="width:100%; border-collapse:collapse; margin-bottom:10px;">
    <tr>
      <td style="width:58%; padding-right:10px; vertical-align:top;">
        <div style="font-weight:bold; margin-bottom:3px;">Dados do Cliente</div>
        <div style="border:1px solid #333; padding:8px; min-height:44px; line-height:1.6;">
          <b>{h(oc)}</b><br>
          Tel: {h(otel)} &nbsp;|&nbsp; CPF/CNPJ: {h(ocpf)}<br>
          End: {h(endf)}
        </div>
      </td>
      <td style="width:42%; vertical-align:top;">
        <table style="width:100%; border-collapse:collapse; text-align:center; font-size:10px;">
          <tr>
            <td style="border:1px solid #333; padding:4px; font-weight:bold; background:#f4f4f4;">N&uacute;mero OS</td>
            <td style="border:1px solid #333; padding:4px; color:#1b4f8a; font-weight:bold;">{oid:05d}</td>
            <td style="border:1px solid #333; padding:4px; font-weight:bold; background:#f4f4f4;">Data</td>
            <td style="border:1px solid #333; padding:4px;">{dt}</td>
          </tr>
          <tr>
            <td style="border:1px solid #333; padding:4px; font-weight:bold; background:#f4f4f4;">Prazo</td>
            <td style="border:1px solid #333; padding:4px;">3 Dias Úteis</td>
          </tr>
          <tr>
            <td style="border:1px solid #333; padding:4px; font-weight:bold; background:#f4f4f4;">Status</td>
            <td style="border:1px solid #333; padding:4px; font-weight:bold; color:red;">Aberto</td>
          </tr>
        </table>
      </td>
    </tr>
      </table>

      <div style="font-weight:bold; margin:7px 0 4px 0;">Equipamentos</div>
      <table style="width:100%; border-collapse:collapse; margin-bottom:10px;">
    <tr style="background:#f4f4f4;">
      <th style="border:1px solid #333; padding:5px; text-align:left;">Item</th>
      <th style="border:1px solid #333; padding:4px;">Marca / S&eacute;rie</th>
      <th style="border:1px solid #333; padding:4px; width:12%; text-align:center;">Avaria?</th>
    </tr>
    <tr>
      <td style="border:1px solid #333; padding:6px;">{h(eq.get('equipamento',''))} <span style="color:#666;">({h(num_item)} / {h(eq.get('tipo',''))})</span></td>
      <td style="border:1px solid #333; padding:6px;">{h(eq.get('marca',''))} / {h(eq.get('serie',''))}</td>
      <td style="border:1px solid #333; padding:6px; text-align:center; font-weight:bold;">{h(avaria_txt)}</td>
    </tr>
      </table>

      <div style="font-weight:bold; margin:7px 0 4px 0;">Check-list e Manuten&ccedil;&atilde;o</div>
      <table style="width:100%; border-collapse:collapse; margin-bottom:8px; font-size:9.5px;">
    <tr>
      <td style="border:1px solid #333; padding:5px;"><b>Fonte:</b> {h(checklist_map.get('Deixou Fonte', 'Nao'))}</td>
      <td style="border:1px solid #333; padding:5px;"><b>Formatar:</b> {h(checklist_map.get('Formatação', 'Nao'))}</td>
      <td style="border:1px solid #333; padding:5px;"><b>Backup:</b> {h(checklist_map.get('Backup', 'Nao'))}</td>
      <td style="border:1px solid #333; padding:5px;"><b>Apps Padr&atilde;o:</b> {h(checklist_map.get('Apps Padrão', 'Nao'))}</td>
      <td style="border:1px solid #333; padding:5px;"><b>S.O.:</b> {h(checklist_map.get('S.O.', ''))}</td>
    </tr>
    <tr>
      <td colspan="5" style="border:1px solid #333; padding:5px;"><b>Apps Espec&iacute;ficos:</b> {h(cfg.get('app_especifico_nome','') if cfg.get('app_especifico','Nao') == 'Sim' else 'Não')}</td>
    </tr>
    <tr>
      <td colspan="5" style="border:1px solid #333; padding:5px;"><b>Recebido por (Nome Leg&iacute;vel):</b> ______________________________________________________________</td>
    </tr>
      </table>

      <div style="font-weight:bold; margin:7px 0 4px 0;">Hardware</div>
      <table style="width:100%; border-collapse:collapse; margin-bottom:12px; font-size:9.5px;">
    <tr>{hw_cells}</tr>
    <tr>{hw_cells2}</tr>
      </table>

      <div style="font-weight:bold; margin:7px 0 4px 0;">Problema Relatado</div>
      <div style="border:1px solid #333; padding:9px; min-height:36px; margin-bottom:14px; line-height:1.6;">{h(eq.get('servico',''))}</div>

      <div style="border:1px solid #555; padding:7px; font-size:8px; text-align:justify; margin-bottom:18px;">
    Informamos que ap&oacute;s o or&ccedil;amento, o cliente tem at&eacute; 90 dias para retirar o aparelho. Ap&oacute;s esse prazo, reservamo-nos o direito de dar destino conforme o artigo 1.275, III do C.C.
      </div>

      <p style="font-size:10px; margin-bottom:28px;">
    <b>Atendente:</b> {h(otec)}
    {f' &nbsp;&nbsp; <b>2&ordm; T&eacute;cnico / Troca:</b> {h(otec_extra)}' if otec_extra else ''}
      </p>

      <table style="width:100%; border:none;">
    <tr>
      <td style="width:38%; vertical-align:bottom;"><b>Data:</b> ___/___/_____</td>
      <td style="width:62%; text-align:center;">
        ___________________________________________________<br>
        <span style="font-size:8px;">Assinatura do Respons&aacute;vel</span>
      </td>
    </tr>
      </table>
    </div>'''
                    folhas_html.append(folha)

                    html_os = "\n".join(folhas_html)
                st.session_state["os_itens_temp"] = []
                st.session_state["os_item_idx"] = 0
                # A próxima renderização usa novas chaves de widgets, deixando
                # cliente, equipamentos e checklist prontos para uma nova O.S.
                st.session_state["os_nova_versao"] = versao_nova_os + 1
                
                js_print = f"""
                <script>
                    var iframe = window.parent.document.createElement('iframe');
                    iframe.style.position = 'absolute';
                    iframe.style.width = '0px';
                    iframe.style.height = '0px';
                    iframe.style.border = 'none';
                    window.parent.document.body.appendChild(iframe);
                    
                    var doc = iframe.contentWindow.document;
                    doc.open();
                    doc.write(`
                        <html>
                        <head>
                            <title>Impressão O.S.</title>
                            <style>
                                body {{ margin: 0; padding: 0; background: white; -webkit-print-color-adjust: exact; }}
                                @page {{ size: A4 portrait; margin: 5mm; }}
                                .quebra-pagina {{ page-break-before: always; }}
                            </style>
                        </head>
                        <body>
                            {html_os.replace('`', '\\`')}
                        </body>
                        </html>
                    `);
                    doc.close();
                    
                    setTimeout(function() {{
                        iframe.contentWindow.focus();
                        iframe.contentWindow.print();
                        setTimeout(function() {{
                            window.parent.location.reload();
                        }}, 250);
                    }}, 500);
                </script>
                """
                components.html(js_print, height=0)

    with aba2:
        st.subheader("Base de O.S. (Tabela Completa)")
        id_os_selecionada = None
        conn = conectar_banco()
        conn.row_factory = None
        c = conn.cursor()
        c.execute('SELECT * FROM ordens_servico ORDER BY os_id DESC')
        df_os = c.fetchall()
        conn.close()
        df_os = filtrar_registros_por_empresa(df_os, "cliente")
        filtro_os1, filtro_os2, filtro_os3 = st.columns(3)
        clientes_historico_os = sorted({item.get("cliente") or "" for item in df_os if item.get("cliente")})
        filtro_cliente_os = filtro_os1.selectbox(
            "Filtrar por cliente:", ["Todos"] + clientes_historico_os, key="os_hist_cliente"
        )
        filtro_inicio_os = filtro_os2.date_input(
            "Data inicial:", value=None, format="DD/MM/YYYY", key="os_hist_inicio"
        )
        filtro_fim_os = filtro_os3.date_input(
            "Data final:", value=None, format="DD/MM/YYYY", key="os_hist_fim"
        )
        if filtro_cliente_os != "Todos":
            df_os = [item for item in df_os if item.get("cliente") == filtro_cliente_os]
        if filtro_inicio_os or filtro_fim_os:
            df_os = [
                item for item in df_os
                if (parse_data_flex(item.get("data_os"))
                    and (not filtro_inicio_os or parse_data_flex(item.get("data_os")) >= filtro_inicio_os)
                    and (not filtro_fim_os or parse_data_flex(item.get("data_os")) <= filtro_fim_os))
            ]
        
        if df_os: 
            linhas_historico_os = []
            for registro_os in df_os:
                linha_os = dict(registro_os)
                linha_os["Vínculo no portal"] = (
                    "Vinculada" if registro_os.get("cliente_id") else "Revisar vínculo"
                )
                linhas_historico_os.append(linha_os)
            id_os_selecionada = tabela_selecionavel_id(
                st, linhas_historico_os, "os_grade_consulta", "os_id"
            )
            st.caption("Clique na O.S. para abrir automaticamente a consulta/edição.")
            conn_eq_hist = conectar_banco()
            conn_eq_hist.row_factory = None
            ceh = conn_eq_hist.cursor()
            try:
                ids_os_historico = [int(item.get("os_id")) for item in df_os]
                marcadores_os = ",".join("?" for _ in ids_os_historico)
                ceh.execute(f'SELECT os_id, numero_item, tipo_equipamento, equipamento, marca, numero_serie, avaria, configuracao, foto_nome FROM equipamentos_os WHERE os_id IN ({marcadores_os}) ORDER BY os_id DESC, id ASC', ids_os_historico)
                eq_hist = ceh.fetchall()
            except Exception:
                eq_hist = []
            conn_eq_hist.close()
            if eq_hist:
                st.write("**Equipamentos por O.S.**")
                st.dataframe([dict(x) for x in eq_hist], width="stretch", hide_index=True)
                with st.expander("Fotos dos equipamentos das O.S.", expanded=False):
                    conn_fotos = conectar_banco()
                    cfotos = conn_fotos.cursor()
                    cfotos.execute("""SELECT os_id, numero_item, equipamento, foto_nome, foto_mime, foto
                                      FROM equipamentos_os
                                      WHERE foto IS NOT NULL
                                      ORDER BY os_id DESC, id ASC""")
                    fotos_os = cfotos.fetchall()
                    conn_fotos.close()
                    if fotos_os:
                        for foto_os in fotos_os:
                            st.image(
                                foto_os.get("foto"),
                                caption=f"OS #{foto_os.get('os_id')} - {foto_os.get('numero_item')} - {foto_os.get('equipamento') or ''}",
                                width=260,
                            )
                    else:
                        st.info("Nenhuma foto salva em O.S.")
        else:
            st.info("Nenhuma O.S. encontrada.")
        
        aos = []
        if tem_permissao("os.edit"):
            aos.append("Editar O.S.")
        if tem_permissao("os.delete"):
            aos.append("Excluir O.S.")
            
        if aos:
            st.write("---")
            ac = st.radio("Ação (O.S.):", aos, horizontal=True)
            if id_os_selecionada and "Editar O.S." in aos:
                ac = "Editar O.S."
            
            if ac == "Excluir O.S.":
                idd = st.number_input("ID O.S. para Excluir", min_value=1, step=1, key="del_os_id")
                if st.button("Remover O.S.", key="btn_del_os"): 
                    deletar_registro('ordens_servico', 'os_id', idd)
                    st.success("O.S. excluída com sucesso.")
                    st.rerun()
                    
            elif ac == "Editar O.S.":
                ide = st.number_input("ID O.S. para Editar:", min_value=1, step=1, value=int(id_os_selecionada or 1), key=f"edit_os_id_{id_os_selecionada or 'manual'}")
                conn = conectar_banco()
                conn.row_factory = None
                c = conn.cursor()
                c.execute('SELECT * FROM ordens_servico WHERE os_id=?',(ide,))
                osdb = c.fetchone()
                conn.close()
                
                if osdb:
                    with st.expander(f"Editando O.S. Nº {ide}", expanded=True):
                        clientes_os_puxar, opcoes_os_puxar = opcoes_clientes_para_puxar()
                        escolha_os_puxar = st.selectbox("Puxar dados de outro cliente cadastrado:", opcoes_os_puxar, key=f"os_puxar_cliente_{ide}")
                        if st.button("Aplicar cliente nesta O.S.", width="stretch", key=f"os_btn_puxar_cliente_{ide}"):
                            cliente_os_sel = next((cli for cli in clientes_os_puxar if cli.get("nome") == escolha_os_puxar), None)
                            if not cliente_os_sel:
                                st.error("Selecione um cliente cadastrado para aplicar.")
                            else:
                                st.session_state[f"os_ecli_{ide}"] = cliente_os_sel.get("nome") or ""
                                st.session_state[f"os_ecpf_{ide}"] = cliente_os_sel.get("cnpj") or ""
                                st.session_state[f"os_eend_{ide}"] = montar_endereco_cliente(cliente_os_sel)
                                st.success("Dados do cliente carregados na O.S. Confira e salve.")
                                st.rerun()
                        e_cli1, e_cli2 = st.columns(2)
                        with e_cli1: 
                            e_cliente = st.text_input("Cliente:", value=osdb['cliente'], key=f"os_ecli_{ide}")
                        with e_cli2: 
                            e_cpf = st.text_input("CPF/CNPJ:", value=osdb['cpf_cnpj'], key=f"os_ecpf_{ide}")
                            
                        e_endereco = st.text_input("Endereço:", value=osdb['endereco'], key=f"os_eend_{ide}")
                        
                        lista_eq = osdb['equipamento'].split('|') if osdb['equipamento'] else []
                        lista_ma = osdb['marca'].split('|') if osdb['marca'] else []
                        lista_av = osdb['avaria'].split('|') if osdb['avaria'] else []
                        
                        qtd_eq_edit = st.number_input("Qtd Equipamentos:", min_value=1, max_value=10, value=max(1, len(lista_eq)), key=f"os_eqtd_{ide}")
                        equipamentos_edit = []
                        
                        for i in range(qtd_eq_edit):
                            c1, c2, c3 = st.columns(3)
                            def_eq = lista_eq[i] if i < len(lista_eq) else ""
                            def_ma = lista_ma[i] if i < len(lista_ma) else ""
                            def_av = lista_av[i] if i < len(lista_av) else "Não"
                            if def_av not in ["Sim", "Não"]: 
                                def_av = "Não"
                            
                            e = c1.text_input(f"Aparelho ({i+1})", value=def_eq, key=f"os_eeq_{ide}_{i}")
                            m = c2.text_input(f"Série/Marca ({i+1})", value=def_ma, key=f"os_ema_{ide}_{i}")
                            a = c3.selectbox(f"Avaria? ({i+1})", ["Não", "Sim"], index=["Não", "Sim"].index(def_av), key=f"os_eav_{ide}_{i}")
                            
                            if e: 
                                equipamentos_edit.append({"e": e, "m": m, "a": a})
                            
                        col_f1, col_f2, col_f3, col_f4, col_f5 = st.columns(5)
                        def idx(val, lst): return lst.index(val) if val in lst else 0
                        
                        with col_f1: 
                            e_fonte = st.selectbox("Fonte?", ["Não", "Sim"], index=idx(osdb['fonte'], ["Não", "Sim"]), key=f"os_efo_{ide}")
                        with col_f2: 
                            e_formatar = st.selectbox("Formatar?", ["Não", "Sim"], index=idx(osdb['formatar'], ["Não", "Sim"]), key=f"os_eform_{ide}")
                        with col_f3: 
                            e_backup = st.selectbox("Backup?", ["Não", "Sim"], index=idx(osdb['backup'], ["Não", "Sim"]), key=f"os_ebk_{ide}")
                        with col_f4: 
                            e_apps = st.selectbox("Apps?", ["Não", "Sim"], index=idx(osdb['aplicativos'], ["Não", "Sim"]), key=f"os_eap_{ide}")
                        with col_f5: 
                            e_so = st.text_input("S.O.:", value=osdb['so'] or "", key=f"os_eso_{ide}")

                        col_app1, col_app2 = st.columns([1, 4])
                        with col_app1: 
                            e_app_chk = st.selectbox("App Específico?", ["Não", "Sim"], index=idx(osdb['app_especifico_check'], ["Não", "Sim"]), key=f"os_eapc_{ide}")
                        with col_app2: 
                            e_app_nome = st.text_input("Qual App?", value=osdb['app_especifico_nome'] or "", key=f"os_eapn_{ide}")

                        col_h1, col_h2, col_h3, col_h4 = st.columns(4)
                        with col_h1: 
                            e_cpu = st.text_input("CPU:", value=osdb['cpu'] or "", key=f"os_ecpu_{ide}")
                        with col_h2: 
                            e_ram = st.text_input("RAM:", value=osdb['ram'] or "", key=f"os_eram_{ide}")
                        with col_h3: 
                            e_hd = st.text_input("HD/SSD:", value=osdb['hd_ssd'] or "", key=f"os_ehd_{ide}")
                        with col_h4: 
                            e_gpu = st.text_input("GPU:", value=osdb['gpu'] or "", key=f"os_egpu_{ide}")
                        
                        col_h5, col_h6, col_h7 = st.columns([2, 1, 1])
                        with col_h5: 
                            e_placa = st.text_input("Placa Mãe:", value=osdb['placa_mae'] or "", key=f"os_epl_{ide}")
                        with col_h6: 
                            e_gab = st.text_input("Gabinete:", value=osdb['gabinete'] or "", key=f"os_egab_{ide}")
                        with col_h7: 
                            e_chave = st.text_input("Chave S.O.:", value=osdb['chave_so'] or "", key=f"os_ech_{ide}")

                        e_servico = st.text_area("Problema:", value=osdb['servico'] or "", key=f"os_esrv_{ide}")
                        col_et1, col_et2 = st.columns(2)
                        with col_et1:
                            e_tec = selecionar_tecnico("Técnico:", osdb['atendente'] or "", key=f"os_etec_{ide}")
                        with col_et2:
                            e_tec_extra = selecionar_tecnico("2º Técnico / Troca:", osdb['tecnico_extra'] if 'tecnico_extra' in osdb.keys() else "", permitir_vazio=True, key=f"os_etec2_{ide}")

                        os_edit_rows = "".join([
                            f"<tr><td>{idx+1}</td><td>{item['e']}</td><td>{item['m']}</td><td>{item['a']}</td></tr>"
                            for idx, item in enumerate(equipamentos_edit)
                        ]) or "<tr><td colspan='4'>Sem equipamentos preenchidos.</td></tr>"
                        html_os_edit = f"""
                        <div class="folha-a4" style="font-family:Arial,sans-serif;color:#000;background:#fff;padding:18px 20px;max-width:21cm;margin:0 auto;">
                            <div style="display:flex;justify-content:space-between;border-bottom:3px solid #004488;padding-bottom:10px;margin-bottom:14px;">
                                <div>{carrega_logo("logo_dsystem.png","DSYSTEM","#004488","130")}</div>
                                <div style="text-align:right;font-size:11px;line-height:1.5;">
                                    <b style="font-size:14px;color:#004488;">Ordem de Serviço Nº {ide:05d}</b><br>
                                    Data: {osdb.get('data_os','')}<br>
                                    D F Pereira Informática
                                </div>
                            </div>
                            <h3 style="color:#004488;margin:0 0 8px 0;">Dados do Cliente</h3>
                            <table style="width:100%;border-collapse:collapse;font-size:11px;margin-bottom:12px;">
                                <tr><td style="border:1px solid #333;padding:6px;"><b>Cliente:</b> {e_cliente}</td><td style="border:1px solid #333;padding:6px;"><b>CPF/CNPJ:</b> {e_cpf}</td></tr>
                                <tr><td colspan="2" style="border:1px solid #333;padding:6px;"><b>Endereço:</b> {e_endereco}</td></tr>
                            </table>
                            <h3 style="color:#004488;margin:0 0 8px 0;">Equipamentos</h3>
                            <table style="width:100%;border-collapse:collapse;font-size:11px;margin-bottom:12px;">
                                <tr style="background:#f0f6ff;"><th style="border:1px solid #333;padding:6px;">Item</th><th style="border:1px solid #333;padding:6px;">Aparelho</th><th style="border:1px solid #333;padding:6px;">Série/Marca</th><th style="border:1px solid #333;padding:6px;">Avaria</th></tr>
                                {os_edit_rows}
                            </table>
                            <h3 style="color:#004488;margin:0 0 8px 0;">Checklist e Serviço</h3>
                            <table style="width:100%;border-collapse:collapse;font-size:11px;margin-bottom:12px;">
                                <tr><td style="border:1px solid #333;padding:6px;"><b>Fonte:</b> {e_fonte}</td><td style="border:1px solid #333;padding:6px;"><b>Formatar:</b> {e_formatar}</td><td style="border:1px solid #333;padding:6px;"><b>Backup:</b> {e_backup}</td><td style="border:1px solid #333;padding:6px;"><b>Apps:</b> {e_apps}</td></tr>
                                <tr><td colspan="4" style="border:1px solid #333;padding:6px;"><b>S.O.:</b> {e_so} &nbsp; <b>CPU:</b> {e_cpu} &nbsp; <b>RAM:</b> {e_ram} &nbsp; <b>HD/SSD:</b> {e_hd} &nbsp; <b>GPU:</b> {e_gpu}</td></tr>
                                <tr><td colspan="4" style="border:1px solid #333;padding:6px;"><b>Placa Mãe:</b> {e_placa} &nbsp; <b>Gabinete:</b> {e_gab} &nbsp; <b>Chave S.O.:</b> {e_chave}</td></tr>
                                <tr><td colspan="4" style="border:1px solid #333;padding:6px;"><b>App Específico:</b> {e_app_chk} {e_app_nome}</td></tr>
                            </table>
                            <h3 style="color:#004488;margin:0 0 8px 0;">Problema / Serviço</h3>
                            <div style="border:1px solid #333;padding:8px;min-height:60px;font-size:11px;margin-bottom:16px;">{e_servico}</div>
                            <p style="font-size:11px;"><b>Técnico:</b> {e_tec} &nbsp;&nbsp; <b>2º Técnico / Troca:</b> {e_tec_extra or "—"}</p>
                            <table style="width:100%;margin-top:28px;font-size:11px;"><tr><td><b>Data:</b> ___/___/_____</td><td style="text-align:center;">_________________________________________<br>Assinatura do Responsável</td></tr></table>
                        </div>
                        """

                        col_os_btn1, col_os_btn2 = st.columns(2)
                        if col_os_btn2.button("Imprimir O.S. Editada", key=f"os_btn_print_{ide}", width="stretch"):
                            st.markdown(f'<div id="doc-impressao">{html_os_edit}</div>', unsafe_allow_html=True)
                            imprimir_html(html_os_edit, f"OS {ide:05d}")

                        if col_os_btn1.button("Guardar Alterações da O.S.", type="primary", key=f"os_btn_s_{ide}", width="stretch"):
                            conn = conectar_banco()
                            c = conn.cursor()
                            c.execute(
                                "SELECT id FROM clientes WHERE nome=? OR cnpj=? ORDER BY id DESC LIMIT 1",
                                (e_cliente, e_cpf),
                            )
                            cliente_edicao_os = c.fetchone() or {}
                            if not cliente_edicao_os.get("id"):
                                conn.close()
                                st.error("Selecione um cliente cadastrado antes de salvar a O.S.")
                                st.stop()
                            c.execute('''
                                UPDATE ordens_servico SET
                                cliente_id=?,
                                cliente=?, cpf_cnpj=?, endereco=?, equipamento=?, marca=?, avaria=?, servico=?, 
                                atendente=?, so=?, formatar=?, backup=?, aplicativos=?, fonte=?, hd_ssd=?, 
                                ram=?, cpu=?, gpu=?, placa_mae=?, gabinete=?, chave_so=?, 
                                app_especifico_check=?, app_especifico_nome=?, tecnico_extra=? 
                                WHERE os_id=?
                            ''', (
                                 cliente_edicao_os.get("id"), e_cliente, e_cpf, e_endereco, "|".join([x['e'] for x in equipamentos_edit]),
                                 "|".join([x['m'] for x in equipamentos_edit]), "|".join([x['a'] for x in equipamentos_edit]), 
                                 e_servico, e_tec, e_so, e_formatar, e_backup, e_apps, e_fonte, e_hd, e_ram, 
                                 e_cpu, e_gpu, e_placa, e_gab, e_chave, e_app_chk, e_app_nome, e_tec_extra, ide
                            ))
                            conn.commit()
                            conn.close()
                            st.success("O.S. atualizada e salva no banco de dados!")
                            st.rerun()

    with aba3:
        st.subheader("Cadastro de tipos e aparelhos")
        st.caption("Os tipos ativos aparecem no campo Tipo ao lançar uma nova O.S.")
        novo_tipo_os = st.text_input("Novo tipo/aparelho:", key="os_tipo_novo")
        if st.button(
            "Cadastrar tipo", type="primary",
            disabled=not tem_permissao("os.edit") or not novo_tipo_os.strip(), key="os_tipo_salvar"
        ):
            conn_tipo = conectar_banco(); c_tipo = conn_tipo.cursor()
            try:
                c_tipo.execute(
                    "INSERT INTO os_tipos_aparelhos (nome, ativo, criado_por, criado_em) VALUES (?,?,?,?)",
                    (novo_tipo_os.strip(), "Sim", st.session_state.get("username", ""), agora_br()),
                )
                conn_tipo.commit()
            except Exception:
                conn_tipo.rollback()
                st.warning("Esse tipo/aparelho já está cadastrado.")
            else:
                st.success("Tipo/aparelho cadastrado.")
                st.rerun()
            finally:
                conn_tipo.close()
        if tipos_os_cadastrados:
            st.dataframe([
                {"ID": item.get("id"), "Tipo/aparelho": item.get("nome"), "Ativo": item.get("ativo") or "Sim"}
                for item in tipos_os_cadastrados
            ], width="stretch", hide_index=True)
            tipo_os_id = st.selectbox(
                "Tipo para ativar/desativar:", [int(item["id"]) for item in tipos_os_cadastrados],
                format_func=lambda valor: next(item.get("nome") for item in tipos_os_cadastrados if int(item["id"]) == valor),
                key="os_tipo_gerenciar",
            )
            tipo_os_atual = next(item for item in tipos_os_cadastrados if int(item["id"]) == tipo_os_id)
            nome_tipo_os_editado = st.text_input(
                "Nome do tipo/aparelho:", value=tipo_os_atual.get("nome") or "",
                key=f"os_tipo_nome_{tipo_os_id}",
            )
            novo_status_tipo = "Não" if tipo_os_atual.get("ativo") != "Não" else "Sim"
            bt_tipo_nome, bt_tipo_status = st.columns(2)
            if bt_tipo_nome.button(
                "Salvar nome", disabled=not tem_permissao("os.edit") or not nome_tipo_os_editado.strip(),
                key="os_tipo_salvar_nome", width="stretch",
            ):
                conn_tipo = conectar_banco(); c_tipo = conn_tipo.cursor()
                try:
                    c_tipo.execute(
                        "UPDATE os_tipos_aparelhos SET nome=? WHERE id=?",
                        (nome_tipo_os_editado.strip(), tipo_os_id),
                    )
                    conn_tipo.commit()
                except Exception:
                    conn_tipo.rollback(); st.warning("Já existe um tipo/aparelho com esse nome.")
                else:
                    st.success("Nome atualizado."); st.rerun()
                finally:
                    conn_tipo.close()
            if bt_tipo_status.button(
                "Desativar tipo" if novo_status_tipo == "Não" else "Reativar tipo",
                disabled=not tem_permissao("os.edit"), key="os_tipo_alterar_status", width="stretch",
            ):
                conn_tipo = conectar_banco(); c_tipo = conn_tipo.cursor()
                c_tipo.execute("UPDATE os_tipos_aparelhos SET ativo=? WHERE id=?", (novo_status_tipo, tipo_os_id))
                conn_tipo.commit(); conn_tipo.close(); st.rerun()


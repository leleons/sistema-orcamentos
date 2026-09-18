"""Componentes visuais e seções do Portal do Cliente."""

from __future__ import annotations

from dsystem_erp.app_context import aplicar_contexto_pagina
from dsystem_erp.services.faturamento_espelho import gerar_pdf_espelho_faturamento

def injetar_css_portal_cliente(ctx=None):
    if ctx is not None:
        aplicar_contexto_pagina(ctx, globals())
    st.markdown("""
<style>
body, .stApp {
    background: #070a0f;
}
.portal-shell {
    margin: -2rem -1rem 1.5rem -1rem;
    padding: 28px 34px 34px;
    min-height: 420px;
    color: #fff;
    background:
        linear-gradient(110deg, rgba(7,10,15,.94) 0%, rgba(13,19,31,.88) 45%, rgba(18,26,35,.78) 100%),
        radial-gradient(circle at 80% 20%, rgba(223,255,0,.22), transparent 26%),
        linear-gradient(135deg, #101722, #06080d);
    border-bottom: 8px solid #eaff00;
    position: relative;
    overflow: hidden;
}
.portal-shell:after {
    content: "";
    position: absolute;
    inset: 0;
    background-image: repeating-linear-gradient(135deg, rgba(255,255,255,.04) 0 1px, transparent 1px 8px);
    pointer-events: none;
}
.portal-top, .portal-hero, .portal-actions, .portal-grid {
    position: relative;
    z-index: 1;
}
.portal-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 18px;
    margin-bottom: 58px;
}
.portal-brand {
    display: flex;
    align-items: center;
    gap: 16px;
    font-size: 18px;
    font-weight: 800;
    letter-spacing: .3px;
}
.portal-brand img {
    height: 70px;
    max-width: 210px;
    object-fit: contain;
}
.portal-nav {
    display: flex;
    gap: 24px;
    font-size: 13px;
    font-weight: 800;
    text-transform: uppercase;
}
.portal-nav a {
    color: #eaff00;
    text-decoration: none;
}
.portal-nav span {
    color: #eaff00;
    text-decoration: none;
}
.portal-nav a:hover {
    color: #fff;
    text-decoration: underline;
    text-decoration-color: #eaff00;
    text-underline-offset: 8px;
}
.portal-nav span:hover {
    color: #fff;
}
.portal-hero {
    max-width: 980px;
    margin: 0 auto;
    text-align: center;
}
.portal-kicker {
    color: #eaff00;
    font-weight: 900;
    text-transform: uppercase;
    letter-spacing: .16em;
    font-size: 12px;
    margin-bottom: 18px;
}
.portal-title {
    font-size: clamp(34px, 5vw, 68px);
    line-height: 1.03;
    font-weight: 900;
    margin: 0;
}
.portal-title span {
    color: #eaff00;
}
.portal-subtitle {
    margin: 20px auto 0;
    max-width: 780px;
    color: rgba(255,255,255,.78);
    font-size: 18px;
    line-height: 1.55;
}
.portal-actions {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 18px 20px;
    margin: 28px auto 28px;
    max-width: 1400px;
    padding: 0 20px;
}
.portal-pill {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    min-height: 56px;
    border: 1px solid rgba(234,255,0,.65);
    color: #fff !important;
    padding: 14px 18px;
    border-radius: 999px;
    background: #005293;
    font-weight: 800;
    text-decoration: none !important;
    transition: .16s ease;
    box-shadow: inset 0 0 0 1px rgba(255,255,255,.04);
}
.portal-pill:hover {
    border-color: #eaff00;
    background: #0768b5;
    color: #fff;
    transform: translateY(-1px);
}
.portal-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 14px;
    margin-top: 28px;
}
.portal-card {
    background: linear-gradient(180deg, rgba(25,31,42,.96), rgba(13,17,24,.96));
    border: 1px solid rgba(255,255,255,.1);
    border-radius: 8px;
    padding: 18px;
    min-height: 128px;
    box-shadow: 0 14px 34px rgba(0,0,0,.35);
    transition: .16s ease;
}
.portal-card-link {
    display: block;
    color: inherit !important;
    text-decoration: none !important;
}
.portal-card-link:hover {
    border-color: rgba(234,255,0,.65);
    transform: translateY(-2px);
    box-shadow: 0 18px 42px rgba(0,0,0,.42);
}
.portal-card strong {
    display: block;
    color: #fff;
    font-size: 15px;
    margin-bottom: 10px;
}
.portal-number {
    font-size: 34px;
    font-weight: 900;
    color: #eaff00;
}
.portal-muted {
    color: rgba(255,255,255,.62);
    font-size: 13px;
}
.portal-section-title {
    margin: 28px 0 12px;
    color: #fff;
    font-size: 26px;
    font-weight: 900;
}
.portal-mini-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 14px;
    margin-bottom: 18px;
}
.portal-mini {
    border: 1px solid rgba(234,255,0,.22);
    background: rgba(16,22,31,.8);
    border-radius: 8px;
    padding: 16px;
}
.portal-mini b {
    color: #eaff00;
}
div[data-testid="stHorizontalBlock"] div[data-testid="stButton"] button[kind="secondary"],
div[data-testid="stHorizontalBlock"] div[data-testid="stButton"] button[kind="primary"] {
    border: 1px solid rgba(234,255,0,.55);
    color: #eaff00;
    background: rgba(234,255,0,.08);
    border-radius: 999px;
    font-weight: 900;
    min-height: 46px;
    transition: .16s ease;
}
div[data-testid="stHorizontalBlock"] div[data-testid="stButton"] button:hover {
    border-color: #eaff00;
    background: rgba(234,255,0,.18);
    color: #fff;
    transform: translateY(-1px);
}
.portal-whatsapp {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 56px;
    border-radius: 999px;
    background: #0877b8;
    border: 1px solid #2fb7ff;
    color: #fff !important;
    font-weight: 900;
    text-decoration: none !important;
    box-shadow: 0 10px 24px rgba(0, 99, 180, .24);
}
.portal-whatsapp:hover {
    background: #0a75c9;
    border-color: #79d7ff;
    color: #fff !important;
}
.portal-doc-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 14px;
    margin: 16px 0 20px;
}
.portal-doc-box {
    border: 1px solid rgba(234,255,0,.18);
    border-radius: 8px;
    padding: 16px;
    background: rgba(16,22,31,.82);
}
.portal-doc-box b {
    color: #eaff00;
}
.chat-bubble {
    max-width: 78%;
    margin: 10px 0;
    padding: 13px 15px;
    border-radius: 10px;
    border: 1px solid rgba(255,255,255,.12);
    box-shadow: 0 10px 26px rgba(0,0,0,.22);
}
.chat-bubble.cliente {
    margin-left: auto;
    background: linear-gradient(180deg, rgba(0,75,141,.95), rgba(0,56,105,.95));
}
.chat-bubble.equipe {
    margin-right: auto;
    background: linear-gradient(180deg, rgba(25,31,42,.98), rgba(14,18,26,.98));
    border-color: rgba(234,255,0,.22);
}
.chat-meta {
    color: #eaff00;
    font-size: 12px;
    font-weight: 800;
    margin-bottom: 6px;
}
.chat-text {
    color: #fff;
    line-height: 1.45;
}
@media (max-width: 900px) {
    .portal-top { align-items: flex-start; flex-direction: column; margin-bottom: 34px; }
    .portal-nav { flex-wrap: wrap; gap: 12px; }
    .portal-actions, .portal-grid, .portal-mini-grid, .portal-doc-grid { grid-template-columns: 1fr; }
}
</style>
""", unsafe_allow_html=True)


def portal_logo_src(ctx=None):
    if ctx is not None:
        aplicar_contexto_pagina(ctx, globals())
    try:
        with open("logo_dsystem.png", "rb") as f:
            return "data:image/png;base64," + base64.b64encode(f.read()).decode("ascii")
    except Exception:
        return ""

def contar_portal_cliente(cliente_portal, cliente_portal_id=None, ctx=None):
    if ctx is not None:
        aplicar_contexto_pagina(ctx, globals())
    dados = {"chamados_abertos": 0, "os": 0, "propostas": 0, "notas": 0, "financeiro": 0.0}
    conn = conectar_banco()
    c = conn.cursor(dictionary=True)
    try:
        c.execute("SELECT COUNT(*) AS total FROM chamados_cliente WHERE cliente_nome=%s AND COALESCE(status,'') NOT IN ('Concluído','Concluido','Fechado','Cancelado')", (cliente_portal,))
        dados["chamados_abertos"] = (c.fetchone() or {}).get("total") or 0
    except Exception:
        pass
    try:
        vinculo_os = "(os.cliente_id=%s OR (os.cliente_id IS NULL AND os.cliente=%s))" if cliente_portal_id else "os.cliente=%s"
        params_os = (cliente_portal_id, cliente_portal) if cliente_portal_id else (cliente_portal,)
        c.execute(
            f"""SELECT COUNT(DISTINCT os.os_id) AS total FROM ordens_servico os
                LEFT JOIN equipamentos_os eq ON eq.os_id=os.os_id
                WHERE {vinculo_os}
                  AND COALESCE(eq.kanban_arquivado,0)=0
                  AND COALESCE(eq.kanban_status,'Recebido') NOT IN ('Entregue','Cancelado')""",
            params_os,
        )
        dados["os"] = (c.fetchone() or {}).get("total") or 0
    except Exception:
        pass
    try:
        if cliente_portal_id:
            c.execute("SELECT COUNT(*) AS total FROM propostas_contratos_cliente WHERE cliente_id=%s OR cliente_nome=%s", (cliente_portal_id, cliente_portal))
        else:
            c.execute("SELECT COUNT(*) AS total FROM propostas_contratos_cliente WHERE cliente_nome=%s", (cliente_portal,))
        dados["propostas"] = (c.fetchone() or {}).get("total") or 0
    except Exception:
        pass
    try:
        c.execute("SELECT data_competencia, emitido_em, criado_em FROM notas_fiscais WHERE cliente=%s", (cliente_portal,))
        hoje = date.today()
        notas_mes = 0
        for nota in c.fetchall():
            data_nota = None
            for valor_data in (nota.get("data_competencia"), nota.get("emitido_em"), nota.get("criado_em")):
                data_nota = parse_data_flex(valor_data) or parse_data_flex(str(valor_data or "")[:10])
                if data_nota:
                    break
            if data_nota and (data_nota.year, data_nota.month) == (hoje.year, hoje.month):
                notas_mes += 1
        dados["notas"] = notas_mes
    except Exception:
        pass
    try:
        if cliente_portal_id:
            c.execute(
                """SELECT COALESCE(SUM(GREATEST(COALESCE(valor_total,0)-COALESCE(valor_baixado,0),0)),0) AS total
                   FROM contas_receber WHERE (cliente_id=%s OR (cliente_id IS NULL AND cliente=%s))
                   AND COALESCE(status,'Aberto') NOT IN ('Recebido','Pago','Cancelado')""",
                (cliente_portal_id, cliente_portal),
            )
        else:
            c.execute(
                """SELECT COALESCE(SUM(GREATEST(COALESCE(valor_total,0)-COALESCE(valor_baixado,0),0)),0) AS total
                   FROM contas_receber WHERE cliente=%s AND COALESCE(status,'Aberto') NOT IN ('Recebido','Pago','Cancelado')""",
                (cliente_portal,),
            )
        dados["financeiro"] = float((c.fetchone() or {}).get("total") or 0)
    except Exception:
        pass
    conn.close()
    return dados

def selecionar_secao_portal(secao, ctx=None):
    if ctx is not None:
        aplicar_contexto_pagina(ctx, globals())
    secao = normalizar_secao_portal(secao)
    st.session_state["portal_cliente_secao"] = secao
    try:
        st.query_params["pagina"] = "portal"
        st.query_params["secao"] = secao
        if st.session_state.get("portal_nav_sid"):
            st.query_params["portal_sid"] = st.session_state["portal_nav_sid"]
    except Exception:
        pass
    st.rerun()


PORTAL_NAV_SESSIONS = {}


def obter_portal_sid_atual(ctx=None):
    if ctx is not None:
        aplicar_contexto_pagina(ctx, globals())
    sid = st.session_state.get("portal_nav_sid")
    if not sid:
        sid = uuid.uuid4().hex
        st.session_state["portal_nav_sid"] = sid
    if len(PORTAL_NAV_SESSIONS) > 200:
        for chave in list(PORTAL_NAV_SESSIONS)[:50]:
            PORTAL_NAV_SESSIONS.pop(chave, None)
    PORTAL_NAV_SESSIONS[sid] = {key: st.session_state[key] for key in st.session_state.keys()}
    return sid


def restaurar_portal_por_sid(ctx=None):
    if ctx is not None:
        aplicar_contexto_pagina(ctx, globals())
    sid = obter_query_param("portal_sid")
    if not sid or st.session_state.get("autenticado"):
        return
    dados = PORTAL_NAV_SESSIONS.get(sid)
    if not dados:
        return
    for key, value in dados.items():
        st.session_state[key] = value
    st.session_state["portal_nav_sid"] = sid
    secao = obter_query_param("secao")
    if secao:
        st.session_state["portal_cliente_secao"] = normalizar_secao_portal(secao)


def portal_href(secao, ctx=None):
    if ctx is not None:
        aplicar_contexto_pagina(ctx, globals())
    return "?" + urlencode({
        "pagina": "portal",
        "secao": normalizar_secao_portal(secao),
        "portal_sid": obter_portal_sid_atual(),
    })


def renderizar_portal_cliente_home(cliente_portal, cliente_portal_id=None, ctx=None):
    if ctx is not None:
        aplicar_contexto_pagina(ctx, globals())
    injetar_css_portal_cliente()
    dados = contar_portal_cliente(cliente_portal, cliente_portal_id)
    logo_src = portal_logo_src()
    logo_html = f'<img src="{logo_src}" alt="Dsystem">' if logo_src else "<strong>Dsystem Tecnologia</strong>"
    whatsapp_href = whatsapp_oficial_url(
        f"Ola, sou {cliente_portal} e preciso de atendimento pelo portal do cliente."
    )
    st.markdown(f"""
<section class="portal-shell">
  <div class="portal-top">
    <div class="portal-brand">{logo_html}</div>
  </div>
  <div class="portal-hero">
    <div class="portal-kicker">Portal exclusivo do cliente</div>
    <h1 class="portal-title"><span>Suporte t&eacute;cnico</span> e gest&atilde;o digital em um s&oacute; lugar</h1>
    <p class="portal-subtitle">Ol&aacute;, {h(cliente_portal)}. Acompanhe atendimentos, documentos, notas, propostas e solicita&ccedil;&otilde;es com mais clareza.</p>
  </div>
</section>
""", unsafe_allow_html=True)

    botoes_portal = (
        ("Abrir chamado", "abrir_chamado"), ("Meus chamados", "meus_chamados"),
        ("Ver notas fiscais", "notas"), ("Financeiro", "financeiro"),
        ("Ordens de serviço", "os"), ("Documentos", "documentos"),
        ("Falar no WhatsApp", "contato"), ("Início", "inicio"),
    )
    for linha in range(0, len(botoes_portal), 4):
        colunas = st.columns(4)
        for coluna, (rotulo, secao) in zip(colunas, botoes_portal[linha:linha + 4]):
            if coluna.button(rotulo, key=f"portal_nav_{secao}", width="stretch"):
                selecionar_secao_portal(secao)

    st.markdown(f"""
<div class="portal-grid">
  {portal_card_html("meus_chamados", "Chamados em aberto", dados["chamados_abertos"], "Solicitações em acompanhamento")}
  {portal_card_html("os", "Ordens de serviço abertas", dados["os"], "Equipamentos ainda em atendimento")}
  {portal_card_html("notas", "Notas fiscais do mês", dados["notas"], "XML e PDF quando emitidas")}
  {portal_card_html("financeiro", "Financeiro em aberto", formatar_moeda_br(dados["financeiro"]), "Saldo total a pagar")}
</div>
""", unsafe_allow_html=True)

    if st.session_state.get("portal_cliente_secao", "inicio") == "inicio":
        st.markdown(portal_mini_grid_html(), unsafe_allow_html=True)

    if st.session_state.get("tipo_login") == "cliente":
        sair_col, _ = st.columns([1, 3])
        if sair_col.button("Sair do portal", width="stretch", key="portal_logout"):
            logout()

def renderizar_portal_ordens_servico(cliente_portal, cursor, conn, ctx=None, cliente_portal_id=None):
    if ctx is not None:
        aplicar_contexto_pagina(ctx, globals())
    if cliente_portal_id:
        cursor.execute(
            """SELECT os_id, data_os, cliente, equipamento, servico FROM ordens_servico
               WHERE cliente_id=%s OR (cliente_id IS NULL AND cliente=%s) ORDER BY os_id DESC""",
            (cliente_portal_id, cliente_portal),
        )
    else:
        cursor.execute(
            "SELECT os_id, data_os, cliente, equipamento, servico FROM ordens_servico WHERE cliente=%s ORDER BY os_id DESC",
            (cliente_portal,),
        )
    ordens_cliente = cursor.fetchall()
    st.markdown("### Ordens de serviço")
    if ordens_cliente:
        for os_cli in ordens_cliente:
            with st.expander(f"OS #{os_cli['os_id']} - {os_cli.get('data_os') or 'Sem data'}", expanded=False):
                st.write(f"**Cliente:** {os_cli.get('cliente') or ''}")
                st.write(f"**Equipamento:** {os_cli.get('equipamento') or ''}")
                st.write(f"**Serviço:** {os_cli.get('servico') or ''}")
                st.write("**Status:** Em acompanhamento")
                cursor.execute(
                    "SELECT numero_item, equipamento, foto_nome, foto FROM equipamentos_os WHERE os_id=%s AND foto IS NOT NULL",
                    (os_cli["os_id"],),
                )
                fotos_cli_os = cursor.fetchall()
                for foto_cli in fotos_cli_os:
                    st.image(
                        foto_cli.get("foto"),
                        caption=f"{foto_cli.get('numero_item') or ''} - {foto_cli.get('equipamento') or ''}",
                        width=240,
                    )
                obs_aut = st.text_area("Observação da autorização:", key=f"aut_obs_{os_cli['os_id']}")
                if tem_permissao("cliente.autorizacao") and st.button("Autorizar serviço", key=f"aut_btn_{os_cli['os_id']}"):
                    cursor.execute(
                        "INSERT INTO autorizacoes_cliente (cliente, os_id, servico, status, observacao, criado_em) VALUES (?,?,?,?,?,?)",
                        (cliente_portal, os_cli["os_id"], os_cli.get("servico") or "", "Autorizado", obs_aut, data_para_banco_br(date.today())),
                    )
                    conn.commit()
                    st.success("Autorização registrada.")
                    st.rerun()
    else:
        st.info("Nenhuma OS encontrada para este cliente.")

def renderizar_portal_notas_cliente(cliente_portal, ctx=None):
    if ctx is not None:
        aplicar_contexto_pagina(ctx, globals())
    st.markdown("### Notas fiscais")
    conn = conectar_banco()
    c = conn.cursor(dictionary=True)
    c.execute("SELECT * FROM notas_fiscais WHERE cliente=%s ORDER BY id DESC", (cliente_portal,))
    notas = c.fetchall()
    conn.close()
    if not notas:
        st.info("Nenhuma nota fiscal encontrada para este cliente.")
        return
    st.dataframe([{
        "ID": n.get("id"),
        "Tipo": n.get("tipo_nota") or "",
        "Status": n.get("status") or "",
        "Número": n.get("numero_nota") or "",
        "Valor": formatar_moeda_br(n.get("valor_servicos")),
        "Competência": n.get("data_competencia") or "",
        "Mensagem": n.get("mensagem_retorno") or "",
    } for n in notas], width="stretch", hide_index=True)
    ids = [int(n.get("id") or 0) for n in notas]
    id_nota = st.selectbox("Baixar documentos da nota:", ids, key="portal_nota_id")
    nota = next((n for n in notas if int(n.get("id") or 0) == int(id_nota)), None)
    if nota:
        c1, c2, c3 = st.columns(3)
        pdf_disponivel = nota.get("pdf_base64")
        if nota.get("tipo_nota") == "Serviço":
            pdf_disponivel = pdf_disponivel if str(nota.get("link_nota") or "").startswith(
                ("https://www.nfse.gov.br/ConsultaPublica/", "https://www.producaorestrita.nfse.gov.br/ConsultaPublica/")
            ) else None
        if pdf_disponivel:
            c1.download_button(
                "Baixar DANFSe" if nota.get("tipo_nota") == "Serviço" else "Baixar PDF",
                data=base64.b64decode(pdf_disponivel),
                file_name=(f"danfse_{nota.get('numero_nota') or id_nota}.pdf" if nota.get("tipo_nota") == "Serviço" else f"nota_{id_nota}.pdf"),
                mime="application/pdf", width="stretch",
            )
        elif nota.get("tipo_nota") == "Serviço" and nota.get("status") == "Autorizada":
            c1.info("DANFSe aguardando geração pela equipe.")
        if nota.get("xml_autorizado") or nota.get("xml_retorno"):
            c2.download_button("Baixar XML", data=nota.get("xml_autorizado") or nota.get("xml_retorno"), file_name=f"nota_{id_nota}.xml", mime="application/xml", width="stretch")
        if nota.get("link_nota") and nota.get("tipo_nota") != "Serviço":
            c3.link_button("Abrir link da nota", nota.get("link_nota"), width="stretch")

def renderizar_portal_documentos_cliente(cliente_portal, cliente_portal_id=None, ctx=None):
    if ctx is not None:
        aplicar_contexto_pagina(ctx, globals())
    st.markdown("### Documentos")
    st.markdown("""
<div class="portal-doc-grid">
  <div class="portal-doc-box"><b>Propostas e contratos</b><br><span class="portal-muted">Arquivos enviados pela equipe para aprovação ou consulta.</span></div>
  <div class="portal-doc-box"><b>Notas fiscais</b><br><span class="portal-muted">XML, PDF e links ficam na área de notas.</span></div>
</div>
""", unsafe_allow_html=True)

    aba_docs, aba_orcamentos, aba_espelhos, aba_contratos, aba_notas = st.tabs(
        ["Propostas", "Orçamentos", "Espelhos de nota", "Contratos", "Notas"]
    )
    with aba_docs:
        renderizar_propostas_contratos(cliente_portal, cliente_portal_id)

    with aba_orcamentos:
        conn = conectar_banco()
        co = conn.cursor(dictionary=True)
        co.execute("SELECT * FROM orcamentos WHERE cliente=%s ORDER BY orc_id DESC", (cliente_portal,))
        orcamentos = co.fetchall()
        if not orcamentos:
            st.info("Nenhum orçamento encontrado para este cliente.")
        for orcamento in orcamentos:
            with st.expander(f"Orçamento #{orcamento.get('numero') or orcamento.get('orc_id')} - {orcamento.get('status') or 'Aberto'}"):
                st.write(f"**Data:** {orcamento.get('data_orc') or '-'}")
                st.write(f"**Valor:** {orcamento.get('valor_total') or '-'}")
                co.execute("SELECT nome_arquivo, mime_type, arquivo FROM orcamento_pdfs WHERE orc_id=%s AND empresa=%s ORDER BY id DESC LIMIT 1", (orcamento.get("orc_id"), "Dsystem Tecnologia"))
                pdf_orc = co.fetchone()
                if pdf_orc and pdf_orc.get("arquivo"):
                    st.download_button("Baixar orçamento", pdf_orc.get("arquivo"), file_name=pdf_orc.get("nome_arquivo") or "orcamento.pdf", mime=pdf_orc.get("mime_type") or "application/pdf", key=f"portal_orc_pdf_{orcamento.get('orc_id')}")
                else:
                    st.info("O PDF Dsystem deste orçamento ainda não está disponível. Solicite à equipe a geração do documento.")
        conn.close()

    with aba_espelhos:
        conn = conectar_banco()
        cf = conn.cursor(dictionary=True)
        cf.execute("SELECT * FROM faturamento WHERE cliente=%s ORDER BY id DESC", (cliente_portal,))
        faturamentos = cf.fetchall()
        conn.close()
        if not faturamentos:
            st.info("Nenhum espelho de nota encontrado para este cliente.")
        for fat in faturamentos:
            st.download_button(
                f"Baixar espelho do faturamento #{fat.get('id')}",
                data=gerar_pdf_espelho_faturamento(fat), file_name=f"espelho_faturamento_{fat.get('id')}.pdf",
                mime="application/pdf", key=f"portal_espelho_{fat.get('id')}", width="stretch",
            )

    with aba_contratos:
        conn = conectar_banco()
        cc = conn.cursor(dictionary=True)
        if cliente_portal_id:
            cc.execute("SELECT * FROM contratos WHERE parte_tipo='Cliente' AND (parte_id=%s OR parte_nome=%s) ORDER BY id DESC", (cliente_portal_id, cliente_portal))
        else:
            cc.execute("SELECT * FROM contratos WHERE parte_tipo='Cliente' AND parte_nome=%s ORDER BY id DESC", (cliente_portal,))
        contratos = cc.fetchall()
        conn.close()
        if not contratos:
            st.info("Nenhum contrato encontrado para este cliente.")
        for contrato in contratos:
            with st.expander(f"Contrato #{contrato.get('id')} - {contrato.get('tipo') or 'Contrato'}"):
                st.write(f"**Status:** {contrato.get('status') or '-'}")
                st.write(f"**Vigência:** {contrato.get('data_inicio') or '-'} a {contrato.get('data_vencimento') or '-'}")
                if contrato.get("arquivo"):
                    st.download_button("Baixar contrato", contrato.get("arquivo"), file_name=contrato.get("nome_arquivo") or "contrato", mime=contrato.get("mime_type") or "application/octet-stream", key=f"portal_contrato_{contrato.get('id')}")

    with aba_notas:
        st.info("As notas fiscais ficam separadas para facilitar o download de XML e PDF.")
        if st.button("Abrir notas fiscais", width="stretch", key="portal_docs_abrir_notas"):
            selecionar_secao_portal("notas")

def renderizar_portal_financeiro_cliente(cliente_portal, cliente_portal_id=None, ctx=None):
    if ctx is not None:
        aplicar_contexto_pagina(ctx, globals())
    st.markdown("### Financeiro")
    conn = conectar_banco()
    c = conn.cursor(dictionary=True)
    if cliente_portal_id:
        c.execute("""SELECT id, data_emissao AS data_lanc, data_vencimento AS vencimento,
                     tipo_receita AS tipo, forma_recebimento AS forma_pag, valor_total, valor_baixado,
                     status, observacoes AS itens, boleto, nota_fiscal
                     FROM contas_receber WHERE cliente_id=%s OR (cliente_id IS NULL AND cliente=%s) ORDER BY id DESC""",
                  (cliente_portal_id, cliente_portal))
    else:
        c.execute("""SELECT id, data_emissao AS data_lanc, data_vencimento AS vencimento,
                     tipo_receita AS tipo, forma_recebimento AS forma_pag, valor_total, valor_baixado,
                     status, observacoes AS itens, boleto, nota_fiscal
                     FROM contas_receber WHERE cliente=%s ORDER BY id DESC""", (cliente_portal,))
    rows = c.fetchall()
    for r in rows:
        r.setdefault("boleto", "")
        r.setdefault("nota_fiscal", "")
    conn.close()
    if not rows:
        st.info("Nenhum lançamento financeiro encontrado para este cliente.")
        return
    hoje = date.today()
    total_aberto = sum(max(float(r.get("valor_total") or 0) - float(r.get("valor_baixado") or 0), 0) for r in rows if (r.get("status") or "Aberto") not in ("Pago", "Recebido", "Cancelado"))
    vencidos = []
    for r in rows:
        venc = parse_data_flex(r.get("vencimento"))
        status = r.get("status") or "Aberto"
        if venc and venc < hoje and status not in ("Pago", "Recebido", "Cancelado", "Faturado"):
            vencidos.append(r)

    f1, f2, f3, f4 = st.columns(4)
    f1.metric("Lançamentos", len(rows))
    f2.metric("Em aberto", formatar_moeda_br(total_aberto))
    f3.metric("Vencidos", len(vencidos))
    f4.metric("Último status", rows[0].get("status") or "-")

    col_f1, col_f2 = st.columns(2)
    status_opcoes = ["Todos"] + sorted({r.get("status") or "Aberto" for r in rows})
    filtro_status = col_f1.selectbox("Filtrar status:", status_opcoes, key="portal_fin_status")
    busca_item = col_f2.text_input("Buscar por item/observação:", key="portal_fin_busca")
    rows_filtrados = rows
    if filtro_status != "Todos":
        rows_filtrados = [r for r in rows_filtrados if (r.get("status") or "Aberto") == filtro_status]
    if busca_item.strip():
        termo = busca_item.strip().lower()
        rows_filtrados = [r for r in rows_filtrados if termo in str(r.get("itens") or "").lower()]

    st.dataframe([{
        "ID": r.get("id"),
        "Data": data_para_br(r.get("data_lanc")),
        "Vencimento": data_para_br(r.get("vencimento")),
        "Tipo": r.get("tipo") or "",
        "Forma": r.get("forma_pag") or "",
        "Itens": r.get("itens") or "",
        "Valor": formatar_moeda_br(r.get("valor_total")),
        "Status": r.get("status") or "",
        "Boleto": "Sim" if r.get("boleto") else "",
        "Nota": r.get("nota_fiscal") or "",
    } for r in rows_filtrados], width="stretch", hide_index=True)

    st.write("---")
    st.markdown("#### Segunda via e atendimento financeiro")
    ids = [int(r.get("id") or 0) for r in rows_filtrados]
    if ids:
        id_segunda_via = st.selectbox("Lançamento:", ids, key="portal_fin_segunda_via")
        lancamento = next((r for r in rows_filtrados if int(r.get("id") or 0) == int(id_segunda_via)), None)
        if lancamento:
            msg = (
                f"Olá, sou {cliente_portal}. Preciso da segunda via do lançamento "
                f"#{id_segunda_via}, vencimento {data_para_br(lancamento.get('vencimento'))}, "
                f"valor {formatar_moeda_br(lancamento.get('valor_total'))}."
            )
            c1, c2 = st.columns(2)
            c1.link_button("Pedir segunda via no WhatsApp", criar_url_whatsapp(WHATSAPP_OFICIAL, msg), width="stretch")
            if lancamento.get("boleto") and str(lancamento.get("boleto")).startswith(("http://", "https://")):
                c2.link_button("Abrir boleto", lancamento.get("boleto"), width="stretch")
            elif lancamento.get("boleto"):
                c2.info("Boleto registrado. Solicite a segunda via pelo WhatsApp.")

def renderizar_portal_contato_cliente(cliente_portal, ctx=None):
    if ctx is not None:
        aplicar_contexto_pagina(ctx, globals())
    st.markdown("### Contato")
    msg = f"Olá, sou {cliente_portal} e preciso de atendimento pelo portal da Dsystem."
    whatsapp_url = criar_url_whatsapp(WHATSAPP_OFICIAL, msg)
    c1, c2 = st.columns(2)
    c1.markdown(
        f"""
<a class="portal-whatsapp" href="{whatsapp_url}" target="_blank">Falar no WhatsApp</a>
""",
        unsafe_allow_html=True,
    )
    c2.link_button("Enviar e-mail", f"mailto:{SMTP_FROM}?subject=Atendimento%20Portal%20Dsystem", width="stretch")
    st.info(f"WhatsApp principal: {WHATSAPP_OFICIAL}")
    st.info(f"E-mail: {SMTP_FROM}")

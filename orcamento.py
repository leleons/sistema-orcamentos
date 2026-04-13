import streamlit as st
import sqlite3
import base64
import os
from datetime import date, timedelta


st.set_page_config(page_title="Sistema Dsystem", page_icon="⚙️", layout="wide")

st.markdown("""
<style>
    /* Ocultar menus desnecessários do Streamlit na tela normal */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Design dos Botões */
    .stButton>button {
        background-color: #004488 !important; color: white !important;
        border-radius: 8px; border: 2px solid #004488;
        padding: 10px 24px; font-weight: bold; transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background-color: #00a2e8 !important; border: 2px solid #004488 !important; transform: scale(1.02);
    }
    
    /* Cartões de Métrica */
    div[data-testid="metric-container"] {
        background-color: #ffffff; border: 1px solid #e0e0e0; padding: 15px;
        border-radius: 10px; border-left: 6px solid #00a2e8; box-shadow: 2px 4px 10px rgba(0,0,0,0.08);
    }
    
    h1, h2, h3 { color: #004488 !important; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { background-color: #f0f2f6; border-radius: 8px 8px 0px 0px; padding: 10px 20px; }
    .stTabs [aria-selected="true"] { background-color: #004488 !important; color: white !important; }

    @media print {
        header, footer, [data-testid="stSidebar"] { display: none !important; }
        .element-container:not(:has(#doc-impressao)) { display: none !important; }
        @page { margin: 1cm; size: A4; }
        body { background-color: white !important; }
        #doc-impressao {
            box-shadow: none !important; border: none !important;
            padding: 0 !important; margin: 0 !important; width: 100% !important;
        }
    }
</style>
""", unsafe_allow_html=True)


if 'pagina_atual' not in st.session_state:
    st.session_state['pagina_atual'] = "🏠 Página Inicial"

def mudar_pagina(nome_pagina):
    st.session_state['pagina_atual'] = nome_pagina

def iniciar_banco():
    conn = sqlite3.connect('banco_dsystem.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS ordens_servico (
            os_id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_os TEXT,
            cliente TEXT,
            cpf_cnpj TEXT,
            endereco TEXT,
            equipamento TEXT,
            marca TEXT,
            avaria TEXT,
            servico TEXT,
            atendente TEXT
        )
    ''')
    conn.commit()
    conn.close()

iniciar_banco()

def deletar_os_do_banco(os_id):
    conn = sqlite3.connect('banco_dsystem.db')
    c = conn.cursor()
    c.execute('DELETE FROM ordens_servico WHERE os_id = ?', (os_id,))
    conn.commit()
    conn.close()

def formata_moeda(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def carrega_logo(caminho_imagem, nome_empresa, cor_texto, largura="150"):
    if os.path.exists(caminho_imagem):
        with open(caminho_imagem, "rb") as img_file:
            codigo = base64.b64encode(img_file.read()).decode()
            return f'<img src="data:image/png;base64,{codigo}" width="{largura}" style="margin-bottom: 10px;">'
    else:
        return f'<h2 style="color: {cor_texto}; margin: 0; letter-spacing: 1px;">{nome_empresa}</h2>'


st.sidebar.image("https://img.icons8.com/color/96/000000/monitor--v1.png", width=60)
st.sidebar.title(" Dsystem OS")
st.sidebar.write("Painel de Controle")

menu = st.sidebar.radio(
    "Navegação:",
    ["🏠 Página Inicial", "📊 Gerador de Orçamentos", "📋 Ordem de Serviço (OS)"],
    key="pagina_atual"
)
st.sidebar.divider()
st.sidebar.caption("Desenvolvido para Dsystem")


if menu == "🏠 Página Inicial":
    st.title("Bem-vindo ao Sistema Dsystem ")
    st.write("Escolha uma das ferramentas abaixo para começar o seu atendimento.")
    st.write("<br>", unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        st.info("### 📊 Gerador de Orçamentos\nCrie propostas comerciais rápidas. O sistema formata a folha A4 pronta para impressão limpa em PDF.")
        st.button("Abrir Gerador de Orçamentos ➔", use_container_width=True, on_click=mudar_pagina, args=("📊 Gerador de Orçamentos",))

    with col2:
        st.success("### 📋 Ordem de Serviço\nRegistre entradas de múltiplos equipamentos. Os dados ficam salvos para sempre no Banco de Dados.")
        st.button("Abrir Ordem de Serviço ➔", use_container_width=True, on_click=mudar_pagina, args=("📋 Ordem de Serviço (OS)",))


elif menu == "📊 Gerador de Orçamentos":
    st.title("📊 Gerador de Orçamentos")
    st.caption("Preencha os dados abaixo para gerar propostas comerciais profissionais.")
    
    with st.container():
        st.subheader(" Dados do Documento")
        col_orc1, col_orc2, col_orc3 = st.columns(3)
        with col_orc1: numero_orcamento = st.text_input("Número do Orçamento:", value="441")
        with col_orc2: forma_pagamento = st.selectbox("Forma de Pagamento:", ["Boleto Bancario", "PIX", "Cartão de Crédito", "A vista", "A Combinar"])
        with col_orc3: observacoes = st.text_input("Observações:", value="")

        st.subheader(" Dados do Cliente")
        col_cli1, col_cli2, col_cli3 = st.columns(3)
        with col_cli1: cliente = st.text_input("Nome da Empresa / Cliente:")
        with col_cli2: telefone = st.text_input("Telefone:")
        with col_cli3: email = st.text_input("E-mail:")

        col_doc1, col_doc2 = st.columns(2)
        with col_doc1: cnpj = st.text_input("CNPJ / CPF:")
        with col_doc2: rg_mei = st.text_input("Nome Fantasia / RG:")

        col_end1, col_end2, col_end3 = st.columns([3, 1, 2])
        with col_end1: endereco = st.text_input("Rua / Endereço:")
        with col_end2: numero = st.text_input("Número:")
        with col_end3: bairro = st.text_input("Bairro:")

        col_cid1, col_cid2 = st.columns([3, 1])
        with col_cid1: cidade = st.text_input("Cidade:", value="Belo Horizonte")
        with col_cid2: estado = st.text_input("Estado (UF):", value="MG")

    st.divider()
    
    with st.container():
        st.subheader(" Serviços e Produtos")
        num_servicos = st.number_input("Quantidade de itens no orçamento:", min_value=1, max_value=20, value=1, step=1)
        servicos = []
        valor_base_total = 0.0

        for i in range(num_servicos):
            col_s1, col_s2 = st.columns([3, 1])
            with col_s1: desc = st.text_input(f"Descrição {i+1}:", key=f"desc_{i}")
            with col_s2: val = st.number_input(f"Valor Base (R$) {i+1}:", min_value=0.0, step=10.0, format="%.2f", key=f"val_{i}")
            if desc:
                servicos.append({"descricao": desc, "valor": val})
                valor_base_total += val

    st.divider()
    st.subheader(" Fechamento e Documento")
    empresa_escolhida = st.radio("Selecione qual layout corporativo usar no documento final:", 
                                 ["Dsystem Tecnologia (Base)", "NC Comercial (+30%)", "GT Solutions (+45%)"], horizontal=True)

    if st.button("Gerar Documento de Orçamento", type="primary", use_container_width=True):
        if valor_base_total > 0 and cliente and len(servicos) > 0:
            
            orcamento_parceiro_1 = valor_base_total * 1.30 
            orcamento_parceiro_2 = valor_base_total * 1.45 

            st.write("<br>", unsafe_allow_html=True)
            col_a, col_b, col_c = st.columns(3)
            col_a.metric("🏢 Dsystem (Base)", formata_moeda(valor_base_total))
            col_b.metric("🤝 NC Comercial (+30%)", formata_moeda(orcamento_parceiro_1))
            col_c.metric("🤝 GT Solutions (+45%)", formata_moeda(orcamento_parceiro_2))
                
            st.divider()
            st.success(" Documento gerado! Aperte **Ctrl + P** no seu teclado para imprimir a folha limpa e formatada.")
            
            data_criacao = date.today().strftime("%d/%m/%Y")
            data_validade = (date.today() + timedelta(days=7)).strftime("%d/%m/%Y")

            if "Dsystem" in empresa_escolhida:
                linhas_tabela_dsystem = "".join([f"<tr><td style='padding:8px; border-bottom:1px solid #ddd;'>{s['descricao']}</td><td align='center' style='padding:8px; border-bottom:1px solid #ddd;'>1,000</td><td align='right' style='padding:8px; border-bottom:1px solid #ddd;'>{formata_moeda(s['valor']).replace('R$ ', '')}</td><td align='right' style='padding:8px; border-bottom:1px solid #ddd;'>0,00</td><td align='right' style='padding:8px; border-bottom:1px solid #ddd;'>{formata_moeda(s['valor']).replace('R$ ', '')}</td></tr>" for s in servicos])
                
                html_orcamento = f"""
<div id="doc-impressao" style="background:white; color:black; padding:40px; font-family:Arial; max-width:800px; margin:0 auto; border:1px solid #ccc; box-shadow: 0 4px 8px rgba(0,0,0,0.1);">

<div style="display:flex; justify-content:space-between; border-bottom:3px solid #004488; padding-bottom:20px;">
    <div>
        {carrega_logo("logo_dsystem.png", "DSYSTEM TECNOLOGIA", "#004488")}
        <p style="margin:5px 0; font-size:14px; font-weight:bold;">D F Pereira Informática</p>
        <p style="margin:0; font-size:12px; color:#555;">Rua Glicério Alves Pinto 129, Alvorada<br>Belo Horizonte MG 34.700-130</p>
    </div>
    <div style="text-align:right; font-size:13px;">
        <h3 style="margin:0; color:#004488;">Orçamento # {numero_orcamento}</h3>
        <p style="margin:5px 0 0 0;"><b>Criação:</b> {data_criacao}</p>
        <p style="margin:0;"><b>Validade:</b> {data_validade}</p>
        <p style="margin:5px 0 0 0; color:#555;">CNPJ: 23.524.449/0001-54<br>adm@dsystemtecnologia.com.br</p>
    </div>
</div>

<div style="margin-top:20px; font-size:14px;">
    <p style="color:#004488; font-weight:bold; margin-bottom:5px;">Cliente</p>
    <p style="margin:0;"><b>{cliente}</b></p>
    <p style="margin:0;">{endereco}, {numero} - {bairro}<br>{cidade} {estado}</p>
    <p style="margin:0;">{rg_mei}</p>
    <p style="margin:0; margin-top:5px;">CNPJ/CPF: {cnpj}</p>
</div>

<p style="color:#004488; font-weight:bold; margin-top:20px; margin-bottom:5px;">Itens</p>
<table style="width:100%; border-collapse:collapse; font-size:14px; margin-bottom:20px;">
    <tr style="background:#f0f0f0; border-top:2px solid #004488; border-bottom:1px solid #ddd;">
        <th style="padding:8px; text-align:left;">Item / Descrição</th>
        <th style="padding:8px; text-align:center;">Qtd</th>
        <th style="padding:8px; text-align:right;">Unitário (R$)</th>
        <th style="padding:8px; text-align:right;">Desconto (R$)</th>
        <th style="padding:8px; text-align:right;">Total (R$)</th>
    </tr>
    {linhas_tabela_dsystem}
</table>

<table style="width:100%; border-collapse:collapse; font-size:14px; text-align:center; margin-bottom:20px;">
    <tr style="background:#f0f0f0; border-top:2px solid #004488; border-bottom:1px solid #ddd;">
        <th style="padding:8px;">Valor Total</th>
        <th style="padding:8px;">Frete</th>
        <th style="padding:8px;">Desconto</th>
        <th style="padding:8px;">Total Liquido</th>
    </tr>
    <tr>
        <td style="padding:8px;">{formata_moeda(valor_base_total).replace('R$ ', '')}</td>
        <td style="padding:8px;">0,00</td>
        <td style="padding:8px;">0,00</td>
        <td style="padding:8px; font-weight:bold;">{formata_moeda(valor_base_total).replace('R$ ', '')}</td>
    </tr>
</table>

<p style="color:#004488; font-weight:bold; margin-top:20px; margin-bottom:5px;">Forma de Pagamento</p>
<table style="width:100%; border-collapse:collapse; font-size:14px; text-align:center; margin-bottom:20px;">
    <tr style="background:#f0f0f0; border-top:2px solid #004488; border-bottom:1px solid #ddd;">
        <th style="padding:8px;">Parcela</th>
        <th style="padding:8px;">Forma de Pagamento</th>
        <th style="padding:8px;">Vencimento</th>
        <th style="padding:8px;">Observação</th>
        <th style="padding:8px;">Total (R$)</th>
    </tr>
    <tr>
        <td style="padding:8px;">1/1</td>
        <td style="padding:8px;">{forma_pagamento}</td>
        <td style="padding:8px;">{data_validade}</td>
        <td style="padding:8px;">{observacoes}</td>
        <td style="padding:8px;">{formata_moeda(valor_base_total).replace('R$ ', '')}</td>
    </tr>
</table>

<p style="color:#004488; font-weight:bold; margin-top:20px; margin-bottom:5px;">Outras informações</p>
<div style="border:1px solid #ddd; padding:15px; font-size:14px; min-height:80px; background-color:#f9f9f9;">
    <b>Observações:</b><br>{observacoes}
</div>

</div>
"""

            elif "NC" in empresa_escolhida:
                linhas_tabela = "".join([f"<tr><td style='border:1px solid #000; padding:8px;'>{i+1}</td><td style='border:1px solid #000; padding:8px;'>{s['descricao']}</td><td style='border:1px solid #000; padding:8px;' align='center'>1</td><td style='border:1px solid #000; padding:8px;' align='right'>{formata_moeda(s['valor']*1.3)}</td><td style='border:1px solid #000; padding:8px;' align='right'>{formata_moeda(s['valor']*1.3)}</td></tr>" for i, s in enumerate(servicos)])
                
                html_orcamento = f"""
<div id="doc-impressao" style="background:white; color:black; padding:40px; font-family:Arial; max-width:800px; margin:0 auto; border:1px solid #ccc;">
<div style="display:flex; justify-content:space-between; border-bottom:2px solid #000; padding-bottom:20px;">
<div>{carrega_logo("logo_nc.png", "NC Comercial", "#000")}
<p style="margin:5px 0 0 0; font-size:11px;">R Dr José Welinton n 93 Planalto CNPJ 23.192.394/0001-22</p>
<p style="margin:0; font-size:11px;">TELEFONE: (31) 99412-2226</p>
</div>
<div style="text-align:right;"><h2 style="margin:0;">ORÇAMENTO Nº {numero_orcamento}</h2><p>DATA DE EMISSÃO: {data_criacao}</p></div>
</div>
<div style="margin-top:20px; font-size:12px; line-height:1.6;">
<table style="width:100%; border:none;">
<tr><td style="width:50%;"><b>NOME:</b> {cliente}</td><td><b>TELEFONE:</b> {telefone}</td></tr>
<tr><td><b>EMAIL:</b> {email}</td><td><b>CPF/CNPJ:</b> {cnpj}</td></tr>
<tr><td colspan="2"><b>ENDEREÇO:</b> {endereco}, {numero} - {bairro} - {cidade}/{estado}</td></tr>
</table>
</div>
<table style="width:100%; border-collapse:collapse; margin-top:20px; font-size:12px;">
<tr style="background:#e6e6e6;"><th style="border:1px solid #000; padding:8px;">ITEM</th><th style="border:1px solid #000; padding:8px;">DESCRIÇÃO</th><th style="border:1px solid #000; padding:8px;">QTD</th><th style="border:1px solid #000; padding:8px;">VALOR UNIDADE</th><th style="border:1px solid #000; padding:8px;">SUBTOTAL</th></tr>
{linhas_tabela}
</table>
<div style="margin-top:20px; display:flex; justify-content:space-between; align-items:center;">
<div style="font-size:12px;"><b>FORMA DE PAGAMENTO:</b><br>{forma_pagamento} - {observacoes}</div>
<div style="text-align:right; font-size:16px;"><b>TOTAL: {formata_moeda(orcamento_parceiro_1)}</b></div>
</div>
</div>
"""
            else:
                linhas_tabela = "".join([f"<tr><td style='border:1px solid #ccc; padding:8px;'>{i+1}</td><td style='border:1px solid #ccc; padding:8px;'>{s['descricao']}</td><td style='border:1px solid #ccc; padding:8px;' align='center'>1</td><td style='border:1px solid #ccc; padding:8px;' align='right'>{formata_moeda(s['valor']*1.45)}</td></tr>" for i, s in enumerate(servicos)])
                
                html_orcamento = f"""
<div id="doc-impressao" style="background:white; color:black; padding:40px; font-family:Arial; max-width:800px; margin:0 auto; border:1px solid #ccc;">
<div style="display:flex; justify-content:space-between; border-bottom:1px solid #ddd; padding-bottom:20px;">
<div>{carrega_logo("logo_gt.png", "GT Solutions", "#00a2e8")}<p style="font-size:11px;">GT Solutions Eireli<br>AV Alterosa 17, sala 6 - Contagem<br>gustavo@gtimpressao.com.br</p></div>
<div style="text-align:right;"><h2>ORÇAMENTO Nº {numero_orcamento}</h2><p>EMITIDO EM: {data_criacao}</p><p>VÁLIDO ATÉ: {data_validade}</p></div>
</div>
<div style="margin-top:20px; font-size:12px; background:#f2f2f2; padding:15px; border-radius:5px;">
<p style="margin:0 0 10px 0;"><b>CLIENTE</b></p>
<table style="width:100%; border:none;">
<tr><td style="width:50%;"><b>NOME:</b> {cliente}</td><td><b>TELEFONE:</b> {telefone}</td></tr>
<tr><td><b>EMAIL:</b> {email}</td><td><b>CPF/CNPJ:</b> {cnpj}</td></tr>
<tr><td colspan="2"><b>ENDEREÇO:</b> {endereco}, {numero} - {bairro} - {cidade}/{estado}</td></tr>
</table>
</div>
<table style="width:100%; border-collapse:collapse; margin-top:20px; font-size:12px;">
<tr style="background:#0088cc; color:white;"><th style="border:1px solid #ccc; padding:8px;">ITEM</th><th style="border:1px solid #ccc; padding:8px;">PRODUTO/SERVIÇO</th><th style="border:1px solid #ccc; padding:8px;">QUANT</th><th style="border:1px solid #ccc; padding:8px;">VALOR</th></tr>
{linhas_tabela}
</table>
<div style="margin-top:20px; display:flex; justify-content:space-between; align-items:center;">
<div style="font-size:11px;"><b>FORMAS DE PAGAMENTO:</b><br>{forma_pagamento} - {observacoes}<br><br>OBS: (12) MESES DE GARANTIA</div>
<div style="text-align:right; font-size:16px; color:#0088cc;"><b>TOTAL: {formata_moeda(orcamento_parceiro_2)}</b></div>
</div>
</div>
"""
            st.markdown(html_orcamento, unsafe_allow_html=True)
        else:
            st.warning("⚠️ Preencha os campos obrigatórios (Nome e Itens do Serviço) para gerar o orçamento.")


elif menu == "📋 Ordem de Serviço (OS)":
    st.title("📋 Controle de Ordem de Serviço")
    
    aba1, aba2 = st.tabs([" Gerar Nova O.S.", " Histórico / Excluir DB"])

    with aba1:
        st.write("Registre a entrada de equipamentos abaixo. Exclusivo Dsystem Tecnologia.")
        
        with st.container():
            data_hoje = date.today().strftime("%d/%m/%Y")
            
            st.write("#### Dados do Cliente")
            col_f1, col_f2 = st.columns(2)
            with col_f1: os_cliente = st.text_input("Nome do Cliente:")
            with col_f2: os_cpf_cnpj = st.text_input("CPF ou CNPJ:")
            os_endereco = st.text_input("Endereço Completo:")
            
            st.write("---")
            st.write("#### Aparelhos Recebidos")
            
            qtd_equipamentos = st.number_input("Quantidade de Equipamentos na OS:", min_value=1, max_value=10, value=1, step=1)
            equipamentos = []
            
            for i in range(qtd_equipamentos):
                col_e1, col_e2, col_e3 = st.columns(3)
                with col_e1: equip = st.text_input(f"Equipamento {i+1}:", key=f"eq_{i}")
                with col_e2: marca = st.text_input(f"Marca/Série {i+1}:", key=f"ma_{i}")
                with col_e3: avaria = st.selectbox(f"Avaria? {i+1}:", ["Não", "Sim"], key=f"av_{i}")
                
                if equip:
                    equipamentos.append({"equipamento": equip, "marca": marca, "avaria": avaria})
            
            st.write("---")
            os_servico = st.text_area("Problema Relatado / Serviço a Executar:", height=100)
            os_atendente = st.text_input("Técnico / Atendente responsável:")

            st.write("<br>", unsafe_allow_html=True)
            submit_os = st.button(" Salvar OS no Sistema e Gerar Ficha", type="primary", use_container_width=True)

        if submit_os:
            if os_cliente and len(equipamentos) > 0 and os_servico:
                
                db_equip_str = " | ".join([e['equipamento'] for e in equipamentos])
                db_marca_str = " | ".join([e['marca'] for e in equipamentos])
                db_avaria_str = " | ".join([e['avaria'] for e in equipamentos])
                
                conn = sqlite3.connect('banco_dsystem.db')
                c = conn.cursor()
                c.execute('''INSERT INTO ordens_servico (data_os, cliente, cpf_cnpj, endereco, equipamento, marca, avaria, servico, atendente)
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                          (data_hoje, os_cliente, os_cpf_cnpj, os_endereco, db_equip_str, db_marca_str, db_avaria_str, os_servico, os_atendente))
                os_id = c.lastrowid 
                conn.commit()
                conn.close()

                st.success(f"✅ Ordem de Serviço N° **{os_id}** gerada e salva! Aperte **Ctrl + P** para imprimir a via do cliente limpa.")
                
                # CORREÇÃO DEFINITIVA DO BUG DA TABELA DE EQUIPAMENTOS (Sem recuos)
                linhas_equipamentos_html = "".join([
                    f"<tr><td style='border: 1px solid #333; padding: 6px;'>{eq['equipamento']}</td>"
                    f"<td style='border: 1px solid #333; padding: 6px;'>{eq['marca']}</td>"
                    f"<td style='border: 1px solid #333; padding: 6px; text-align: center;'>{eq['avaria'].upper()}</td></tr>"
                    for eq in equipamentos
                ])

                tag_logo = carrega_logo("logo_dsystem.png", "DSYSTEM", "#004488", largura="140")
                html_os = f"""
<div id="doc-impressao" style="font-family: Arial, sans-serif; font-size: 11px; color: #000; background: #fff; max-width: 800px; margin: 0 auto; padding: 30px; border: 1px solid #ccc; box-shadow: 0 4px 8px rgba(0,0,0,0.1);">
<table style="width: 100%; border: none; margin-bottom: 20px;">
<tr>
<td style="width: 50%; vertical-align: top;">
{tag_logo}
</td>
<td style="width: 50%; text-align: right; vertical-align: top; line-height: 1.4; color: #444;">
<b style="font-size: 13px; color: #004488;">D F Pereira Informática</b><br>
adm@dsystemtecnologia.com.br<br>
Rua Glicério Alves Pinto 129, Alvorada<br>
Belo Horizonte, MG - CEP: 34.700-130<br>
CNPJ: 23.524.449/0001-54
</td>
</tr>
</table>
<div style="text-align: center; margin-bottom: 25px;">
<div style="display: inline-block; border: 1px solid #666; border-radius: 20px; padding: 6px 25px; font-size: 14px; font-weight: bold; color: #333;">
Ordem de serviço N° {os_id:05d}
</div>
</div>
<table style="width: 100%; border-collapse: collapse; margin-bottom: 15px;">
<tr>
<td style="width: 55%; vertical-align: top; padding-right: 15px; border: none;">
<div style="font-size: 10px; margin-bottom: 3px; font-weight: bold;">Cliente</div>
<div style="border: 1px solid #333; padding: 10px; min-height: 50px;">
<b>{os_cliente}</b><br>
CPF/CNPJ: {os_cpf_cnpj}<br>
Endereço: {os_endereco}
</div>
</td>
<td style="width: 45%; vertical-align: top; border: none;">
<table style="width: 100%; border-collapse: collapse; text-align: center;">
<tr>
<td style="border: 1px solid #333; padding: 6px; background: #f4f4f4; font-size: 10px;"><b>Número<br>da OS</b></td>
<td style="border: 1px solid #333; padding: 6px; font-weight:bold;">{os_id:05d}</td>
<td style="border: 1px solid #333; padding: 6px; background: #f4f4f4; font-size: 10px;"><b>Data de<br>entrada</b></td>
<td style="border: 1px solid #333; padding: 6px;">{data_hoje}</td>
</tr>
<tr>
<td style="border: 1px solid #333; padding: 6px; background: #f4f4f4; font-size: 10px;"><b>Previsão</b></td>
<td style="border: 1px solid #333; padding: 6px;">3 Dias</td>
<td style="border: 1px solid #333; padding: 6px; background: #f4f4f4; font-size: 10px;"><b>Status</b></td>
<td style="border: 1px solid #333; padding: 6px; color: #004488; font-weight: bold;">Aberto</td>
</tr>
</table>
</td>
</tr>
</table>

<div style="font-size: 10px; margin-bottom: 3px; font-weight: bold;">Aparelhos / Equipamentos Recebidos</div>
<table style="width: 100%; border-collapse: collapse; margin-bottom: 15px; text-align: left;">
<tr style="background: #f4f4f4;">
<th style="border: 1px solid #333; padding: 6px; font-size: 10px;">Equipamento</th>
<th style="border: 1px solid #333; padding: 6px; font-size: 10px;">Marca / N° de Série</th>
<th style="border: 1px solid #333; padding: 6px; font-size: 10px; text-align: center;">Tem Avaria?</th>
</tr>
{linhas_equipamentos_html}
</table>

<div style="font-size: 10px; margin-bottom: 3px; font-weight: bold;">Problema / Serviço a Executar</div>
<div style="border: 1px solid #333; padding: 10px; margin-bottom: 15px; min-height: 50px;">
{os_servico}
</div>
<table style="width: 100%; border-collapse: collapse; margin-bottom: 15px; text-align: right;">
<tr>
<td style="border: 1px solid #333; padding: 6px; background: #f4f4f4; font-size: 10px; width: 33%;"><b>Total serviços</b></td>
<td style="border: 1px solid #333; padding: 6px; background: #f4f4f4; font-size: 10px; width: 33%;"><b>Total peças</b></td>
<td style="border: 1px solid #333; padding: 6px; background: #f4f4f4; font-size: 10px; width: 34%;"><b>Total da ordem de serviço</b></td>
</tr>
<tr>
<td style="border: 1px solid #333; padding: 6px;">A definir</td>
<td style="border: 1px solid #333; padding: 6px;">A definir</td>
<td style="border: 1px solid #333; padding: 6px;"><b>A definir</b></td>
</tr>
</table>
<div style="font-size: 10px; margin-bottom: 3px; font-weight: bold;">Observações do recebimento</div>
<div style="border: 1px solid #333; padding: 10px; margin-bottom: 20px; font-size: 9px; text-align: justify; color: #444; line-height: 1.3;">
Informamos que, após a realização do orçamento, o cliente tem um prazo de até 90 dias para retirar o aparelho em nossa loja. Caso a retirada não seja feita dentro deste período, nos reservamos o direito de tomar as medidas cabíveis para a destinação do aparelho, conforme a legislação vigente (artigo 1.275, inciso III, do Código Civil Brasileiro). Reforçamos a importância de buscar o aparelho dentro do prazo estabelecido para evitar qualquer inconveniente. Agradecemos a compreensão e estamos à disposição para quaisquer dúvidas.
</div>
<div style="margin-top: 30px;">
<p style="font-size: 12px;"><b>Técnico(s) / Vendedor:</b> {os_atendente}</p>
<p style="font-size: 11px; margin-bottom: 40px; color: #555;">Concordo com os termos descritos acima.</p>
<table style="width: 100%; border: none;">
<tr>
<td style="width: 40%; vertical-align: bottom; font-size: 12px;">
<b>Data:</b> ____/____/________
</td>
<td style="width: 60%; text-align: center; vertical-align: bottom;">
___________________________________________________<br>
<span style="font-size: 10px; color: #444;">Assinatura do responsável</span>
</td>
</tr>
</table>
</div>
</div>
"""
                st.markdown(html_os, unsafe_allow_html=True)
            else:
                st.error("⚠️ Atenção: Adicione pelo menos 1 Equipamento e preencha o Nome e Problema para gerar a OS.")

    with aba2:
        st.subheader("🗄️ Histórico e Gerenciamento")
        
        col_db1, col_db2 = st.columns([1, 3])
        with col_db1:
            id_para_apagar = st.number_input("Excluir OS Nº:", min_value=1, step=1)
            if st.button("🗑️ Excluir Registro", type="secondary"):
                deletar_os_do_banco(id_para_apagar)
                st.success(f"OS Nº {id_para_apagar} apagada com sucesso!")
                st.rerun()
        
        st.write("---")
        conn = sqlite3.connect('banco_dsystem.db')
        c = conn.cursor()
        c.execute('SELECT os_id, data_os, cliente, equipamento, servico, atendente FROM ordens_servico ORDER BY os_id DESC')
        dados_db = c.fetchall()
        conn.close()

        if len(dados_db) > 0:
            st.dataframe(
                dados_db,
                column_config={"0": "O.S Nº", "1": "Data", "2": "Cliente", "3": "Equipamentos", "4": "Problema", "5": "Técnico"},
                use_container_width=True, hide_index=True
            )
        else:
            st.info("Nenhuma OS registrada no momento.")

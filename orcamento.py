import streamlit as st
import streamlit.components.v1 as components
import sqlite3
import base64
import os
from datetime import date, timedelta


st.set_page_config(page_title="Sistema Dsystem", layout="wide")

st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    .stButton>button {
        background-color: #004488 !important; color: white !important;
        border-radius: 8px; border: 2px solid #004488;
        padding: 10px 24px; font-weight: bold; transition: all 0.3s ease;
    }
    div[data-testid="metric-container"] {
        background-color: #ffffff; border: 1px solid #e0e0e0; padding: 15px;
        border-radius: 10px; border-left: 6px solid #00a2e8; box-shadow: 2px 4px 10px rgba(0,0,0,0.08);
    }
    h1, h2, h3 { color: #004488 !important; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }


    @media print {
        header, footer, [data-testid="stSidebar"], [data-testid="stHeader"] { 
            display: none !important; 
        }
        
        body * { visibility: hidden !important; }
        #doc-impressao, #doc-impressao * { visibility: visible !important; }
        
        html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMainBlockContainer"], .element-container {
            position: static !important;
            width: 100% !important;
            max-width: 100% !important;
            margin: 0 !important;
            padding: 0 !important;
            background-color: white !important;
            transform: none !important;
            overflow: visible !important;
        }

        #doc-impressao {
            position: absolute !important;
            left: 0 !important;
            top: 0 !important;
            width: 100vw !important;
            max-width: none !important;
            min-width: 100vw !important;
            margin: 0 !important;
            padding: 10mm !important;
            border: none !important;
            box-shadow: none !important;
            box-sizing: border-box !important;
        }
        
        table, tr, td, th, p {
            page-break-inside: avoid !important;
            break-inside: avoid !important;
        }

        @page { 
            margin: 0 !important; 
            size: A4 portrait; 
        }
    }
</style>
""", unsafe_allow_html=True)


if 'autenticado' not in st.session_state:
    st.session_state['autenticado'] = False
if 'cargo' not in st.session_state:
    st.session_state['cargo'] = None
if 'pagina_atual' not in st.session_state:
    st.session_state['pagina_atual'] = "Página Inicial"

def login():
    st.title("Acesso ao Sistema Dsystem")
    with st.container():
        user = st.text_input("Usuário")
        password = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            if user == "admin" and password == "123":
                st.session_state['autenticado'] = True
                st.session_state['cargo'] = "admin"
                st.rerun()
            elif user == "user" and password == "456":
                st.session_state['autenticado'] = True
                st.session_state['cargo'] = "usuario"
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")

def logout():
    st.session_state['autenticado'] = False
    st.session_state['cargo'] = None
    st.rerun()


def iniciar_banco():
    conn = sqlite3.connect('banco_dsystem.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS ordens_servico (
            os_id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_os TEXT, cliente TEXT, cpf_cnpj TEXT, endereco TEXT,
            equipamento TEXT, marca TEXT, avaria TEXT, servico TEXT, atendente TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE, telefone TEXT, email TEXT,
            cnpj TEXT, rg_mei TEXT, endereco TEXT, numero TEXT,
            complemento TEXT, bairro TEXT, cidade_estado TEXT, cep TEXT
        )
    ''')
    try:
        c.execute('ALTER TABLE clientes ADD COLUMN cep TEXT')
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

iniciar_banco()

def buscar_clientes():
    conn = sqlite3.connect('banco_dsystem.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM clientes ORDER BY nome')
    dados = c.fetchall()
    conn.close()
    return [dict(row) for row in dados]

def salvar_cliente(nome, tel, email, cnpj, rg, end, num, comp, bairro, cid, cep):
    if not nome.strip(): return
    conn = sqlite3.connect('banco_dsystem.db')
    c = conn.cursor()
    c.execute('SELECT id FROM clientes WHERE nome = ?', (nome,))
    row = c.fetchone()
    if row:
        c.execute('''UPDATE clientes SET telefone=?, email=?, cnpj=?, rg_mei=?, endereco=?, numero=?, complemento=?, bairro=?, cidade_estado=?, cep=? WHERE id=?''', (tel, email, cnpj, rg, end, num, comp, bairro, cid, cep, row[0]))
    else:
        c.execute('''INSERT INTO clientes (nome, telefone, email, cnpj, rg_mei, endereco, numero, complemento, bairro, cidade_estado, cep) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (nome, tel, email, cnpj, rg, end, num, comp, bairro, cid, cep))
    conn.commit()
    conn.close()

def salvar_cliente_simples(nome, cpf, end, tel, cep):
    if not nome.strip(): return
    conn = sqlite3.connect('banco_dsystem.db')
    c = conn.cursor()
    c.execute('SELECT id FROM clientes WHERE nome = ?', (nome,))
    if not c.fetchone():
        c.execute('INSERT INTO clientes (nome, cnpj, endereco, telefone, cep, email, rg_mei, numero, complemento, bairro, cidade_estado) VALUES (?, ?, ?, ?, ?, "", "", "", "", "", "")', (nome, cpf, end, tel, cep))
    conn.commit()
    conn.close()

if not st.session_state['autenticado']:
    login()
    st.stop()

def mudar_pagina(nome_pagina):
    st.session_state['pagina_atual'] = nome_pagina

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
            return f'<img src="data:image/png;base64,{codigo}" width="{largura}" style="margin-bottom: 5px;">'
    else:
        return f'<h2 style="color: {cor_texto}; margin: 0; letter-spacing: 1px; font-family: Arial;">{nome_empresa}</h2>'


st.sidebar.title(f"Olá, {st.session_state['cargo'].capitalize()}")
st.sidebar.write("---")

menu = st.sidebar.radio(
    "Navegação do Sistema:",
    ["Página Inicial", "Gerador de Orçamentos", "Ordem de Serviço (OS)"],
    key="pagina_atual"
)

st.sidebar.write("<br><br>", unsafe_allow_html=True)
if st.sidebar.button("Sair do Sistema"):
    logout()


if menu == "Página Inicial":
    st.title("Visão Geral do Sistema")
    col1, col2 = st.columns(2)
    with col1:
        st.info("### Gerador de Orçamentos")
        st.button("Acessar Módulo de Orçamentos", use_container_width=True, on_click=mudar_pagina, args=("Gerador de Orçamentos",))
    with col2:
        st.success("### Ordem de Serviço")
        st.button("Acessar Módulo de O.S.", use_container_width=True, on_click=mudar_pagina, args=("Ordem de Serviço (OS)",))


elif menu == "Gerador de Orçamentos":
    st.title("Gerador de Orçamentos")
    with st.container():
        col_orc1, col_orc2 = st.columns(2)
        with col_orc1: numero_orcamento = st.text_input("Número do Orçamento:", value="441")
        with col_orc2: forma_pagamento = st.selectbox("Forma de Pagamento:", ["Boleto Bancário", "PIX", "Cartão de Crédito", "A vista", "A Combinar"])
        
        col_obs1, col_obs2 = st.columns(2)
        with col_obs1: obs_pagamento = st.text_input("Observação do Pagamento (Ex: Vencimento dia 10):", value="")
        with col_obs2: obs_gerais = st.text_input("Observações Gerais (Inseridas no fim do documento):", value="")

        st.subheader("Dados do Cliente")
        clientes_db = buscar_clientes()
        lista_nomes = ["-- Preencher Manualmente --"] + [c['nome'] for c in clientes_db]
        
        cliente_selecionado = st.selectbox("Buscar Cliente Cadastrado (Opcional):", lista_nomes)
        
        if cliente_selecionado != "-- Preencher Manualmente --":
            dados_c = next(c for c in clientes_db if c['nome'] == cliente_selecionado)
        else:
            dados_c = {'nome': '', 'telefone': '', 'email': '', 'cnpj': '', 'rg_mei': '', 'endereco': '', 'numero': '', 'complemento': '', 'bairro': '', 'cidade_estado': 'BH / MG', 'cep': ''}

        col_cli1, col_cli2, col_cli3 = st.columns(3)
        with col_cli1: cliente = st.text_input("Nome do Cliente ou Empresa:", value=dados_c.get('nome', ''))
        with col_cli2: telefone = st.text_input("Telefone de Contato:", value=dados_c.get('telefone', ''))
        with col_cli3: email = st.text_input("Endereço de E-mail:", value=dados_c.get('email', ''))
        
        col_d1, col_d2 = st.columns(2)
        with col_d1: cnpj = st.text_input("CNPJ ou CPF:", value=dados_c.get('cnpj', ''))
        with col_d2: rg_mei = st.text_input("Nome Fantasia ou RG:", value=dados_c.get('rg_mei', ''))
        
        col_e1, col_e2, col_e3, col_e4, col_e5, col_e6 = st.columns([3, 1, 2, 2, 2, 2])
        with col_e1: endereco = st.text_input("Rua / Endereço:", value=dados_c.get('endereco', ''))
        with col_e2: numero = st.text_input("Número:", value=dados_c.get('numero', ''))
        with col_e3: complemento = st.text_input("Complemento:", value=dados_c.get('complemento', ''))
        with col_e4: bairro = st.text_input("Bairro:", value=dados_c.get('bairro', ''))
        with col_e5: cidade_estado = st.text_input("Cidade/UF:", value=dados_c.get('cidade_estado', 'BH / MG'))
        with col_e6: cep = st.text_input("CEP:", value=dados_c.get('cep', ''))

    st.divider()
    num_servicos = st.number_input("Quantidade de Itens/Serviços:", min_value=1, max_value=20, value=1)
    servicos = []
    valor_base_total = 0.0
    for i in range(num_servicos):
        c1, c2 = st.columns([3, 1])
        desc = c1.text_input(f"Descrição do Item {i+1}:", key=f"d_{i}")
        val = c2.number_input(f"Valor Base Dsystem (R$) {i+1}:", min_value=0.0, format="%.2f", key=f"v_{i}")
        if desc:
            servicos.append({"descricao": desc, "valor": val})
            valor_base_total += val

    st.write("<br>", unsafe_allow_html=True)
    empresa_escolhida = st.radio("Para pré-visualização, selecione a unidade:", ["Dsystem Tecnologia", "NC Comercial", "GT Solutions"], horizontal=True)

    col_btn1, col_btn2 = st.columns(2)
    btn_preview = col_btn1.button("Visualizar Orçamento na Tela", use_container_width=True)
    
    st.markdown("""
    <style>
    div[data-testid="column"]:nth-of-type(2) button {
        background-color: #28a745 !important;
        border-color: #28a745 !important;
    }
    div[data-testid="column"]:nth-of-type(2) button:hover {
        background-color: #218838 !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    btn_print_all = col_btn2.button("Gerar PDF Múltiplo (Dsystem, NC e GT)", type="primary", use_container_width=True)

    if btn_preview or btn_print_all:
        if valor_base_total > 0 and cliente:
            salvar_cliente(cliente, telefone, email, cnpj, rg_mei, endereco, numero, complemento, bairro, cidade_estado, cep)
            
            comp_fmt = f" - {complemento}" if complemento else ""
            cep_fmt = f" - CEP: {cep}" if cep else ""
            data_c = date.today().strftime("%d/%m/%Y")
            data_v = (date.today() + timedelta(days=7)).strftime("%d/%m/%Y")


            mult_ds = 1.0
            val_ds = valor_base_total * mult_ds
            linhas_ds = "".join([f"<tr><td style='padding:6px; border-bottom:1px solid #ddd;'>{s['descricao']}</td><td align='center' style='padding:6px; border-bottom:1px solid #ddd;'>1,000</td><td align='right' style='padding:6px; border-bottom:1px solid #ddd;'>{formata_moeda(s['valor'] * mult_ds).replace('R$ ', '')}</td><td align='right' style='padding:6px; border-bottom:1px solid #ddd;'>0,00</td><td align='right' style='padding:6px; border-bottom:1px solid #ddd;'>{formata_moeda(s['valor'] * mult_ds).replace('R$ ', '')}</td></tr>" for s in servicos])
            html_dsystem = f"""
<div style="background:white; color:black; padding:20px; font-family:Arial, sans-serif; font-size:12px; width:100%; max-width:21cm; margin:0 auto; box-sizing: border-box;">
<div style="display:flex; justify-content:space-between; margin-bottom:10px; border-bottom:3px solid #004488; padding-bottom:10px;">
    <div style="width:50%;">
        {carrega_logo("logo_dsystem.png", "SYSTEM TECNOLOGIA", "#004488", "140")}<br>
        <span style="color:#004488; font-size:10px; font-weight:bold;">PARCEIRA DA SUA EMPRESA</span><br>
        <span style="font-size:10px; color:#555;">www.dsystemtecnologia.com.br</span><br><br>
        <b style="font-size:12px;">D F Pereira Informática</b><br>
        Rua Glicério Alves Pinto 129 Alvorada<br>Belo Horizonte MG 34.700-130
    </div>
    <div style="width:40%; text-align:right;">
        <table style="width:100%; border-collapse:collapse; margin-bottom:5px; text-align:center;">
            <tr><td style="border:1px solid #ccc; padding:3px; font-weight:bold; background:#f4f4f4;">Criação:</td><td style="border:1px solid #ccc; padding:3px;">{data_c}</td></tr>
            <tr><td style="border:1px solid #ccc; padding:3px; font-weight:bold; background:#f4f4f4;">Validade:</td><td style="border:1px solid #ccc; padding:3px;">{data_v}</td></tr>
        </table>
        <h3 style="margin:5px 0; color:#004488;">Orçamento # {numero_orcamento}</h3>
        <p style="margin:0;">23.524.449/0001-54<br>adm@dsystemtecnologia.com.br<br>(31) 97117-7190</p>
    </div>
</div>
<div style="margin-bottom:10px;">
    <h4 style="color:#004488; border-bottom:1px solid #004488; margin-bottom:5px; padding-bottom:2px;">Cliente</h4>
    <table style="width:100%; border:none; font-size:11px;">
        <tr><td style="width:50%;"><b>Nome:</b> {cliente}</td><td><b>CPF/CNPJ:</b> {cnpj}</td></tr>
        <tr><td><b>Endereço:</b> {endereco}, {numero}{comp_fmt} - {bairro} - {cidade_estado}{cep_fmt}</td><td><b>Telefone:</b> {telefone}</td></tr>
        <tr><td colspan="2"><b>E-mail:</b> {email}</td></tr>
    </table>
    <p style="margin:2px 0 0 0; font-size:11px;">{rg_mei}</p>
</div>
<h4 style="color:#004488; border-bottom:1px solid #004488; margin-bottom:5px; padding-bottom:2px;">Itens</h4>
<table style="width:100%; border-collapse:collapse; margin-bottom:10px; font-size:11px;">
    <tr style="background:#f4f4f4;">
        <th style="padding:5px; border:1px solid #ccc; text-align:left;">Descrição</th><th style="padding:5px; border:1px solid #ccc; text-align:center;">Qtd</th><th style="padding:5px; border:1px solid #ccc; text-align:right;">Unitário (R$)</th><th style="padding:5px; border:1px solid #ccc; text-align:right;">Desconto (R$)</th><th style="padding:5px; border:1px solid #ccc; text-align:right;">Total (R$)</th>
    </tr>
    {linhas_ds}
</table>
<div style="display:flex; justify-content:flex-end; margin-bottom:15px;">
    <table style="width:60%; border-collapse:collapse; text-align:right; font-size:11px;">
        <tr style="background:#f4f4f4;">
            <th style="padding:5px; border:1px solid #ccc; text-align:center;">Valor Total</th><th style="padding:5px; border:1px solid #ccc; text-align:center;">Frete</th><th style="padding:5px; border:1px solid #ccc; text-align:center;">Desconto</th><th style="padding:5px; border:1px solid #ccc; text-align:center;">Total Liquido</th>
        </tr>
        <tr>
            <td style="padding:5px; border:1px solid #ccc; text-align:center;">{formata_moeda(val_ds).replace('R$ ', '')}</td><td style="padding:5px; border:1px solid #ccc; text-align:center;">0,00</td><td style="padding:5px; border:1px solid #ccc; text-align:center;">0,00</td><td style="padding:5px; border:1px solid #ccc; font-weight:bold; text-align:center;">{formata_moeda(val_ds).replace('R$ ', '')}</td>
        </tr>
    </table>
</div>
<h4 style="color:#004488; border-bottom:1px solid #004488; margin-bottom:5px; padding-bottom:2px;">Forma de Pagamento</h4>
<table style="width:100%; border-collapse:collapse; margin-bottom:15px; font-size:11px;">
    <tr style="background:#f4f4f4;">
        <th style="padding:5px; border:1px solid #ccc; text-align:center;">Parcela</th><th style="padding:5px; border:1px solid #ccc; text-align:center;">Forma de Pagamento</th><th style="padding:5px; border:1px solid #ccc; text-align:center;">Vencimento</th><th style="padding:5px; border:1px solid #ccc; text-align:left;">Observação</th><th style="padding:5px; border:1px solid #ccc; text-align:right;">Total (R$)</th>
    </tr>
    <tr>
        <td style="padding:5px; border:1px solid #ccc; text-align:center;">1/1</td><td style="padding:5px; border:1px solid #ccc; text-align:center;">{forma_pagamento}</td><td style="padding:5px; border:1px solid #ccc; text-align:center;">{data_v}</td><td style="padding:5px; border:1px solid #ccc;">{obs_pagamento}</td><td style="padding:5px; border:1px solid #ccc; text-align:right;">{formata_moeda(val_ds).replace('R$ ', '')}</td>
    </tr>
</table>
<h4 style="color:#004488; border-bottom:1px solid #004488; margin-bottom:5px; padding-bottom:2px;">Outras informações</h4>
<p style="margin-top:2px; font-size:11px;"><b>Observações Gerais:</b><br>{obs_gerais}</p>
</div>
"""

            mult_nc = 1.30
            val_nc = valor_base_total * mult_nc
            linhas_nc = "".join([f"<tr><td style='border:1px solid #000; padding:6px; text-align:center;'>{i+1}</td><td style='border:1px solid #000; padding:6px;'>{s['descricao']}</td><td style='border:1px solid #000; padding:6px; text-align:center;'>1</td><td style='border:1px solid #000; padding:6px; text-align:right;'>{formata_moeda(s['valor'] * mult_nc)}</td><td style='border:1px solid #000; padding:6px; text-align:right;'>{formata_moeda(s['valor'] * mult_nc)}</td></tr>" for i, s in enumerate(servicos)])
            html_nc = f"""
<div style="background:white; color:black; padding:20px; font-family:Arial, sans-serif; font-size:11px; width:100%; max-width:21cm; margin:0 auto; box-sizing: border-box;">
<div style="display:flex; justify-content:space-between; margin-bottom:15px;">
    <div style="display:flex; align-items:center;">
        {carrega_logo("logo_nc.png", "NC Comercial", "#000", "100")}
        <div style="margin-left:15px;">
            <h2 style="margin:0; font-size:18px; color:#555;">NC Comercial</h2>
            <p style="margin:2px 0 0 0; font-size:9px;">R Dr José Welinton n 93 Planalto CNPJ 23.192.394/0001-22</p>
            <p style="margin:0; font-size:9px;">EMAIL: financeiro.nccomercial@gmail.com TELEFONE: (31) 99412-2226</p>
        </div>
    </div>
    <div style="text-align:right;">
        <h2 style="margin:0; font-size:16px; color:#333;">ORÇAMENTO</h2>
        <p style="margin:5px 0 0 0; font-weight:bold;">Nº {numero_orcamento}</p>
        <p style="margin:0;">DATA DE EMISSÃO: {data_c}</p>
    </div>
</div>
<div style="border-top:1px solid #000; border-bottom:1px solid #000; padding:8px 0; margin-bottom:15px; font-size:10px; line-height:1.4;">
    <div style="display:flex;"><div style="width:50%;"><b>NOME:</b> {cliente}</div><div style="width:50%;"><b>TELEFONE:</b> {telefone}</div></div>
    <div style="display:flex;"><div style="width:50%;"><b>EMAIL:</b> {email}</div><div style="width:50%;"><b>CPF/CNPJ:</b> {cnpj}</div></div>
    <div style="display:flex;"><div style="width:50%;"><b>RG/MEI:</b> {rg_mei}</div><div style="width:50%;"><b>ENDEREÇO:</b> {endereco}, {numero}{comp_fmt}</div></div>
    <div style="display:flex;"><div style="width:50%;"><b>BAIRRO:</b> {bairro}</div><div style="width:50%;"><b>CIDADE/UF:</b> {cidade_estado}{cep_fmt}</div></div>
</div>
<table style="width:100%; border-collapse:collapse; margin-bottom:15px;">
    <tr style="background:#e6e6e6;">
        <th style="border:1px solid #000; padding:6px;">ITEM</th><th style="border:1px solid #000; padding:6px; width:45%;">PRODUTO/SERVIÇO</th><th style="border:1px solid #000; padding:6px;">QUANT</th><th style="border:1px solid #000; padding:6px;">VALOR UNIDADE</th><th style="border:1px solid #000; padding:6px;">SUBTOTAL</th>
    </tr>
    {linhas_nc}
</table>
<div style="display:flex; justify-content:space-between;">
    <div style="width:50%; font-size:10px;">
        <b>FORMA DE PAGAMENTO:</b><br>{forma_pagamento}<br><br>
        <b>OBSERVAÇÃO DO PAGAMENTO:</b><br>{obs_pagamento}<br><br>
        <b>OBSERVAÇÕES GERAIS:</b><br>{obs_gerais}
    </div>
    <div style="width:40%; border:1px solid #000; padding:10px; text-align:right;">
        <div style="display:flex; justify-content:space-between; margin-bottom:10px;"><span>ACRÉSCIMO: R$ 0,00</span><span>DESCONTO: R$ 0,00</span></div>
        <b style="font-size:14px;">TOTAL: {formata_moeda(val_nc)}</b>
    </div>
</div>
</div>
"""

            mult_gt = 1.45
            val_gt = valor_base_total * mult_gt
            linhas_gt = "".join([f"<tr><td style='border:1px solid #ccc; padding:4px; text-align:center;'>{i+1}</td><td style='border:1px solid #ccc; padding:4px;'>{s['descricao']}</td><td style='border:1px solid #ccc; padding:4px; text-align:center;'>1</td><td style='border:1px solid #ccc; padding:4px; text-align:right;'>{formata_moeda(s['valor'] * mult_gt)}</td></tr>" for i, s in enumerate(servicos)])
            html_gt = f"""
<div style="background:white; color:#333; padding:20px; font-family:Arial, sans-serif; font-size:10px; width:100%; max-width:21cm; margin:0 auto; box-sizing: border-box;">
<div style="display:flex; justify-content:space-between; margin-bottom:15px;">
    <div style="width:30%;">{carrega_logo("logo_gt.png", "GT Solutions", "#4ba3d5", "100")}</div>
    <div style="width:40%; line-height:1.3;">
        <h3 style="margin:0; color:#4ba3d5; font-size:14px;">GT Solutions Eireli</h3>
        ENDEREÇO: AV Alterosa 17, sala 6 parque turista - contagem<br>TELEFONE: (31) 9 8679-7785<br>EMAIL: gustavo@gtimpressao.com.br<br>WEBSITE: www.gtimpressao.com.br<br>CPF/CNPJ: 34.349.098/0001-09
    </div>
    <div style="width:25%; text-align:right;">
        <h2 style="margin:0; color:#666; font-size:18px;">ORÇAMENTO</h2>
        <p style="margin:5px 0 2px 0;"><b>ORÇAMENTO Nº:</b> {numero_orcamento}</p>
        <p style="margin:2px 0;"><b>EMITIDO EM:</b> {data_c}</p>
        <p style="margin:2px 0;"><b>VÁLIDO ATÉ:</b> {data_v}</p>
    </div>
</div>
<div style="background:#f2f2f2; padding:10px; border-radius:5px; margin-bottom:15px; border:1px solid #e0e0e0;">
    <p style="margin:0 0 8px 0; font-weight:bold; font-size:11px; color:#555;">CLIENTE</p>
    <div style="display:flex; flex-wrap:wrap; gap:8px;">
        <div style="width:48%;"><b>NOME:</b> {cliente}</div><div style="width:48%;"><b>TELEFONE:</b> {telefone}</div>
        <div style="width:48%;"><b>CPF/CNPJ:</b> {cnpj}</div><div style="width:48%;"><b>EMAIL:</b> {email}</div>
        <div style="width:48%;"><b>ENDEREÇO:</b> {endereco}, {numero}{comp_fmt}</div><div style="width:48%;"><b>BAIRRO:</b> {bairro}</div>
        <div style="width:100%;"><b>CIDADE/ESTADO:</b> {cidade_estado}{cep_fmt}</div>
    </div>
</div>
<table style="width:100%; border-collapse:collapse; margin-bottom:10px;">
    <tr style="background:#4ba3d5; color:white;">
        <th style="border:1px solid #ccc; padding:6px;">ITEM</th><th style="border:1px solid #ccc; padding:6px; width:50%;">PRODUTO/SERVIÇO</th><th style="border:1px solid #ccc; padding:6px;">QUANT</th><th style="border:1px solid #ccc; padding:6px;">VALOR</th>
    </tr>
    {linhas_gt}
</table>
<div style="display:flex; justify-content:space-between; align-items:center; padding:8px; border:1px solid #ccc; margin-bottom:15px; font-weight:bold; background:#fafafa;">
    <span>SUBTOTAL: {formata_moeda(val_gt)}</span>
    <span>DESCONTO: R$ 0,00</span>
    <span>ACRÉSCIMO: R$ 0,00</span>
    <span style="font-size:14px; color:#4ba3d5;">TOTAL: {formata_moeda(val_gt)}</span>
</div>
<div>
    <p style="margin:0 0 4px 0;"><b>FORMAS DE PAGAMENTO:</b> {forma_pagamento} - {obs_pagamento}</p>
    <p style="margin:0 0 4px 0;"><b>OBSERVAÇÕES:</b> {obs_gerais}</p>
    <p style="margin:10px 0 0 0; font-weight:bold;">OBS: (12) MESES DE GARANTIA</p>
</div>
</div>
"""

            if btn_preview:
                st.info(f"Modo de Visualização: Layout {empresa_escolhida}. Para gerar o PDF completo, utilize a opção de salvamento múltiplo.")
                if "Dsystem" in empresa_escolhida:
                    st.markdown(f'<div id="doc-impressao">{html_dsystem}</div>', unsafe_allow_html=True)
                elif "NC" in empresa_escolhida:
                    st.markdown(f'<div id="doc-impressao">{html_nc}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div id="doc-impressao">{html_gt}</div>', unsafe_allow_html=True)

            elif btn_print_all:
                html_combined = f"""<div id="doc-impressao">
{html_dsystem}
<div style="page-break-before: always;"></div>
{html_nc}
<div style="page-break-before: always;"></div>
{html_gt}
</div>"""
                st.markdown(html_combined, unsafe_allow_html=True)
                components.html("<script>setTimeout(function() { window.parent.print(); }, 500);</script>", height=0)

        else:
            st.warning("Atenção: É necessário preencher o Nome do Cliente e inserir ao menos um serviço para prosseguir.")


elif menu == "Ordem de Serviço (OS)":
    st.title("Controle de Ordens de Serviço")
    tabs = ["Gerar Nova O.S.", "Histórico de Registos"]
    aba1, aba2 = st.tabs(tabs)

    with aba1:
        st.write("Módulo exclusivo para registo de entrada de equipamentos (Dsystem Tecnologia).")
        with st.container():
            
            clientes_db = buscar_clientes()
            lista_nomes_os = ["-- Preencher Manualmente --"] + [c['nome'] for c in clientes_db]
            cli_os_sel = st.selectbox("Buscar Cliente Cadastrado (Opcional):", lista_nomes_os, key="busca_cli_os")
            
            if cli_os_sel != "-- Preencher Manualmente --":
                d_os = next(c for c in clientes_db if c['nome'] == cli_os_sel)
                end_completo = f"{d_os.get('endereco', '')}, {d_os.get('numero', '')}"
                if d_os.get('complemento', ''): end_completo += f" - {d_os['complemento']}"
                end_completo += f" - {d_os.get('bairro', '')} - {d_os.get('cidade_estado', '')}"
                cep_os = d_os.get('cep', '')
            else:
                d_os = {'nome': '', 'cnpj': '', 'telefone': ''}
                end_completo = ''
                cep_os = ''

            data_hoje = date.today().strftime("%d/%m/%Y")
            c_cli1, c_cli2 = st.columns(2)
            with c_cli1: os_cliente = st.text_input("Nome do Cliente:", value=d_os.get('nome', ''))
            with c_cli2: os_cpf = st.text_input("CPF / CNPJ:", value=d_os.get('cnpj', ''))
            
            c_end1, c_end2, c_end3 = st.columns([3, 1, 1])
            with c_end1: os_endereco = st.text_input("Endereço Completo:", value=end_completo)
            with c_end2: os_cep = st.text_input("CEP:", value=cep_os)
            with c_end3: os_telefone = st.text_input("Telefone de Contato:", value=d_os.get('telefone', ''))
            
            st.write("---")
            qtd_eq = st.number_input("Quantidade de Equipamentos:", min_value=1, max_value=10, value=1)
            equipamentos = []
            for i in range(qtd_eq):
                c1, c2, c3 = st.columns(3)
                e = c1.text_input(f"Aparelho/Modelo ({i+1}):", key=f"eq_{i}")
                m = c2.text_input(f"Nº Série/Marca ({i+1}):", key=f"ma_{i}")
                a = c3.selectbox(f"Apresenta Avaria? ({i+1})", ["Não", "Sim"], key=f"av_{i}")
                if e: equipamentos.append({"e": e, "m": m, "a": a})
            
            st.write("---")
            os_servico = st.text_area("Descrição do Problema Relatado:")
            os_tecnico = st.text_input("Responsável Técnico / Atendente:")

            st.write("<br>", unsafe_allow_html=True)
            submit_os = st.button("Salvar Registo e Gerar Ficha (PDF)", type="primary", use_container_width=True)

        if submit_os:
            if os_cliente and equipamentos:
                end_final_os = f"{os_endereco} - CEP: {os_cep}" if os_cep else os_endereco

                conn = sqlite3.connect('banco_dsystem.db')
                c = conn.cursor()
                c.execute('INSERT INTO ordens_servico (data_os, cliente, cpf_cnpj, endereco, equipamento, marca, avaria, servico, atendente) VALUES (?,?,?,?,?,?,?,?,?)',
                          (data_hoje, os_cliente, os_cpf, end_final_os, "|".join([x['e'] for x in equipamentos]), "|".join([x['m'] for x in equipamentos]), "|".join([x['a'] for x in equipamentos]), os_servico, os_tecnico))
                os_id = c.lastrowid
                conn.commit()
                conn.close()
                
                salvar_cliente_simples(os_cliente, os_cpf, os_endereco, os_telefone, os_cep)
                
                st.success(f"Registo da O.S. Nº {os_id} concluído com sucesso. A interface de impressão será iniciada.")
                
                linhas_eq_html = "".join([f"<tr><td style='border:1px solid #333; padding:4px; width:40%;'>{eq['e']}</td><td style='border:1px solid #333; padding:4px; width:45%;'>{eq['m']}</td><td style='border:1px solid #333; padding:4px; text-align:center; width:15%;'>{eq['a'].upper()}</td></tr>" for eq in equipamentos])

                html_os = f"""
<div id="doc-impressao" style="font-family:Arial, sans-serif; font-size:10px; color:#000; background:#fff; width:100%; max-width:21cm; margin:0 auto; padding:20px; box-sizing: border-box;">
<table style="width:100%; border:none; margin-bottom:10px;">
<tr>
<td style="width:50%; vertical-align:top;">{carrega_logo("logo_dsystem.png", "DSYSTEM", "#004488", "130")}</td>
<td style="width:50%; text-align:right; vertical-align:top; line-height:1.3;">
<b style="font-size:12px; color:#004488;">D F Pereira Informática</b><br>adm@dsystemtecnologia.com.br<br>(31) 97117-7190<br>Rua Glicério Alves Pinto 129, Alvorada<br>Belo Horizonte, MG - 34.700-130<br>CNPJ: 23.524.449/0001-54
</td>
</tr>
</table>
<div style="text-align:center; margin-bottom:15px;">
<div style="display:inline-block; border:1px solid #666; border-radius:15px; padding:4px 20px; font-size:12px; font-weight:bold; color:#333; background:#fafafa;">
Ordem de Serviço N° {os_id:05d}
</div>
</div>
<table style="width:100%; border-collapse:collapse; margin-bottom:10px;">
<tr>
<td style="width:55%; vertical-align:top; padding-right:10px; border:none;">
<div style="margin-bottom:2px; font-weight:bold; font-size:10px;">Dados do Cliente</div>
<div style="border:1px solid #333; padding:8px; min-height:40px; font-size:10px;">
<b>{os_cliente}</b><br>Telefone: {os_telefone}<br>CPF/CNPJ: {os_cpf}<br>Endereço: {end_final_os}
</div>
</td>
<td style="width:45%; vertical-align:top; border:none;">
<table style="width:100%; border-collapse:collapse; text-align:center; height:100%;">
<tr>
<td style="border:1px solid #333; padding:4px; font-weight:bold; background:#f4f4f4;">Número<br>da OS</td>
<td style="border:1px solid #333; padding:4px; font-size:11px; font-weight:bold; color:#004488;">{os_id:05d}</td>
<td style="border:1px solid #333; padding:4px; font-weight:bold; background:#f4f4f4;">Data de<br>entrada</td>
<td style="border:1px solid #333; padding:4px;">{data_hoje}</td>
</tr>
<tr>
<td style="border:1px solid #333; padding:4px; font-weight:bold; background:#f4f4f4;">Prazo<br>previsto</td>
<td style="border:1px solid #333; padding:4px;">3 Dias</td>
<td style="border:1px solid #333; padding:4px; font-weight:bold; background:#f4f4f4;">Status</td>
<td style="border:1px solid #333; padding:4px; font-weight:bold; color:red;">Aberto</td>
</tr>
</table>
</td>
</tr>
</table>
<div style="margin-bottom:2px; font-weight:bold; font-size:10px;">Equipamentos Recebidos</div>
<table style="width:100%; border-collapse:collapse; margin-bottom:10px;">
<tr style="background:#f4f4f4;">
<th style="border:1px solid #333; padding:4px; text-align:left; width:40%;">Equipamento</th>
<th style="border:1px solid #333; padding:4px; text-align:left; width:45%;">Número de série / Marca</th>
<th style="border:1px solid #333; padding:4px; text-align:center; width:15%;">Avaria?</th>
</tr>
{linhas_eq_html}
</table>
<div style="margin-bottom:2px; font-weight:bold; font-size:10px;">Descrição do Problema / Serviço a Executar</div>
<div style="border:1px solid #333; padding:8px; margin-bottom:10px; min-height:35px; font-size:10px;">{os_servico}</div>
<table style="width:100%; border-collapse:collapse; margin-bottom:10px; text-align:right;">
<tr><th style="border:1px solid #333; padding:4px; background:#f4f4f4; width:33%; text-align:center;">Total serviços</th><th style="border:1px solid #333; padding:4px; background:#f4f4f4; width:33%; text-align:center;">Total peças</th><th style="border:1px solid #333; padding:4px; background:#f4f4f4; width:34%; text-align:center;">Total da ordem de serviço</th></tr>
<tr><td style="border:1px solid #333; padding:4px; text-align:center;">A definir</td><td style="border:1px solid #333; padding:4px; text-align:center;">A definir</td><td style="border:1px solid #333; padding:4px; text-align:center;"><b>A definir</b></td></tr>
</table>
<div style="margin-bottom:2px; font-weight:bold; font-size:9px;">Termos e Condições do Recebimento</div>
<div style="border:1px solid #333; padding:8px; margin-bottom:15px; font-size:9px; text-align:justify; line-height:1.2; color:#444;">
Informamos que, após a realização do orçamento, o cliente tem um prazo de até 90 dias para retirar o aparelho em nossa loja. Caso a retirada não seja feita dentro deste período, nos reservamos o direito de tomar as medidas cabíveis para a destinação do aparelho, conforme a legislação vigente (artigo 1.275, inciso III, do Código Civil Brasileiro). Reforçamos a importância de buscar o aparelho dentro do prazo estabelecido para evitar qualquer inconveniente. Agradecemos a compreensão e estamos à disposição para quaisquer dúvidas.
</div>
<div style="margin-top:10px;">
<p style="font-size:11px; margin-bottom:15px;"><b>Responsável Técnico:</b> {os_tecnico}</p>
<p style="font-size:9px; color:#555; margin-bottom:20px;">Declaro estar de acordo com os termos descritos acima.</p>
<table style="width:100%; border:none;">
<tr>
<td style="width:40%; vertical-align:bottom; font-size:10px;"><b>Data de Aprovação:</b> ____/____/________</td>
<td style="width:60%; text-align:center; vertical-align:bottom;">___________________________________________________<br><span style="color:#555; font-size:9px;">Assinatura do Responsável / Cliente</span></td>
</tr>
</table>
</div>
</div>"""
                st.markdown(html_os, unsafe_allow_html=True)
                components.html("<script>setTimeout(function() { window.parent.print(); }, 500);</script>", height=0)
            else:
                st.error("Atenção: É obrigatório informar o nome do cliente e adicionar ao menos um equipamento.")

    with aba2:
        st.subheader("Base de Dados de O.S.")
        conn = sqlite3.connect('banco_dsystem.db')
        c = conn.cursor()
        c.execute('SELECT os_id, data_os, cliente, equipamento, servico, atendente FROM ordens_servico ORDER BY os_id DESC')
        dados = c.fetchall()
        conn.close()
        
        if len(dados) > 0:
            st.dataframe(dados, column_config={"0": "Nº O.S.", "1": "Data", "2": "Cliente", "3": "Equipamento(s)", "4": "Problema Detalhado", "5": "Técnico"}, use_container_width=True, hide_index=True)

        if st.session_state['cargo'] == "admin":
            st.warning("Área de Administração: Gestão de Registos")
            col_d1, col_d2 = st.columns([1,3])
            with col_d1:
                id_del = st.number_input("ID da O.S. para remoção", min_value=1, step=1)
                if st.button("Excluir Registo Definitivamente"):
                    deletar_os_do_banco(id_del)
                    st.success("Registo excluído com sucesso do sistema.")
                    st.rerun()

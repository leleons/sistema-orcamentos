import streamlit as st
import sqlite3
import base64
import os
from datetime import date, timedelta


st.set_page_config(page_title="Sistema Dsystem", page_icon="⚙️", layout="wide")

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
        /* 1. Esconde as barras laterais e topo do site */
        header, footer, [data-testid="stSidebar"], [data-testid="stHeader"] { 
            display: none !important; 
        }
        
        /* 2. O GRANDE TRUQUE: Destrói as "colunas invisíveis" do Streamlit */
        html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMainBlockContainer"], .element-container {
            position: static !important;
            width: 100% !important;
            max-width: 100% !important;
            margin: 0 !important;
            padding: 0 !important;
            background-color: white !important;
            transform: none !important;
        }

        /* 3. Deixa todos os botões e formulários do site invisíveis */
        body * {
            visibility: hidden;
        }
        
        /* 4. Torna APENAS o documento visível */
        #doc-impressao, #doc-impressao * {
            visibility: visible;
        }
        
        /* 5. Prega o documento no topo esquerdo do papel e estica */
        #doc-impressao {
            position: absolute !important;
            left: 0 !important;
            top: 0 !important;
            width: 100% !important;
            max-width: 21cm !important; /* Limite perfeito da folha A4 */
            margin: 0 !important;
            padding: 5mm !important; /* Dá um leve respiro na borda do papel */
            border: none !important;
            box-shadow: none !important;
        }
        
        /* Impede que tabelas cortem no meio da folha */
        table, tr, td, th, div, p {
            page-break-inside: avoid !important;
        }

        /* Define o tamanho da folha real da impressora */
        @page { 
            margin: 5mm !important; 
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
    st.session_state['pagina_atual'] = " Página Inicial"

def login():
    st.title(" Acesso ao Sistema Dsystem")
    with st.container():
        user = st.text_input("Usuário")
        password = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            if user == "administrador" and password == "*@Dsystem01":
                st.session_state['autenticado'] = True
                st.session_state['cargo'] = "admin"
                st.rerun()
            elif user == "usuario" and password == "1234":
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
    conn.commit()
    conn.close()

iniciar_banco()

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


st.sidebar.image("https://img.icons8.com/color/96/000000/monitor--v1.png", width=60)
st.sidebar.title(f"Olá, {st.session_state['cargo'].capitalize()}")
st.sidebar.write("---")
menu = st.sidebar.radio("Navegação:", ["🏠 Página Inicial", "📊 Gerador de Orçamentos", "📋 Ordem de Serviço (OS)"], key="pagina_atual")
st.sidebar.write("<br><br>", unsafe_allow_html=True)
if st.sidebar.button("🚪 Sair do Sistema"):
    logout()


if menu == "🏠 Página Inicial":
    st.title("Bem-vindo ao Sistema Dsystem 👋")
    col1, col2 = st.columns(2)
    with col1:
        st.info("### 📊 Gerador de Orçamentos")
        st.button("Abrir Orçamentos ➔", use_container_width=True, on_click=mudar_pagina, args=("📊 Gerador de Orçamentos",))
    with col2:
        st.success("### 📋 Ordem de Serviço")
        st.button("Abrir Nova OS ➔", use_container_width=True, on_click=mudar_pagina, args=("📋 Ordem de Serviço (OS)",))

elif menu == "📊 Gerador de Orçamentos":
    st.title("📊 Gerador de Orçamentos")
    with st.container():
        col_orc1, col_orc2 = st.columns(2)
        with col_orc1: numero_orcamento = st.text_input("Número do Orçamento:", value="441")
        with col_orc2: forma_pagamento = st.selectbox("Forma de Pagamento:", ["Boleto Bancário", "PIX", "Cartão de Crédito", "A vista", "A Combinar"])
        
        col_obs1, col_obs2 = st.columns(2)
        with col_obs1: obs_pagamento = st.text_input("Observação do Pagamento (Ex: Vencimento dia 10):", value="")
        with col_obs2: obs_gerais = st.text_input("Observações Gerais (Fim do Documento):", value="")

        st.subheader("👤 Dados do Cliente")
        col_cli1, col_cli2, col_cli3 = st.columns(3)
        with col_cli1: cliente = st.text_input("Nome do Cliente / Empresa:")
        with col_cli2: telefone = st.text_input("Telefone:")
        with col_cli3: email = st.text_input("E-mail:")
        
        col_d1, col_d2 = st.columns(2)
        with col_d1: cnpj = st.text_input("CNPJ / CPF:")
        with col_d2: rg_mei = st.text_input("Nome Fantasia / RG:")
        
        col_e1, col_e2, col_e3, col_e4 = st.columns([3,1,2,1])
        with col_e1: endereco = st.text_input("Rua / Endereço:")
        with col_e2: numero = st.text_input("Número:")
        with col_e3: bairro = st.text_input("Bairro:")
        with col_e4: cidade_estado = st.text_input("Cidade/UF:", value="BH / MG")

    st.divider()
    num_servicos = st.number_input("Qtd de itens:", min_value=1, max_value=20, value=1)
    servicos = []
    valor_base_total = 0.0
    for i in range(num_servicos):
        c1, c2 = st.columns([3, 1])
        desc = c1.text_input(f"Descrição {i+1}:", key=f"d_{i}")
        val = c2.number_input(f"Valor Dsystem (R$) {i+1}:", min_value=0.0, format="%.2f", key=f"v_{i}")
        if desc:
            servicos.append({"descricao": desc, "valor": val})
            valor_base_total += val

    empresa_escolhida = st.radio("Layout do Orçamento:", ["Dsystem Tecnologia (Base)", "NC Comercial (+30%)", "GT Solutions (+45%)"], horizontal=True)

    if st.button("Gerar Documento", type="primary", use_container_width=True):
        if valor_base_total > 0 and cliente:
            
            mult = 1.0
            if "NC" in empresa_escolhida: mult = 1.30
            elif "GT" in empresa_escolhida: mult = 1.45
            
            valor_final_total = valor_base_total * mult

            st.write("<br>", unsafe_allow_html=True)
            col_a, col_b, col_c = st.columns(3)
            col_a.metric("🏢 Dsystem (Base)", formata_moeda(valor_base_total))
            col_b.metric("🤝 NC (+30%)", formata_moeda(valor_base_total * 1.30))
            col_c.metric("🤝 GT (+45%)", formata_moeda(valor_base_total * 1.45))
                
            st.success("🎉 Documento pronto! Aperte **Ctrl + P** para imprimir a folha cheia.")
            
            data_c = date.today().strftime("%d/%m/%Y")
            data_v = (date.today() + timedelta(days=7)).strftime("%d/%m/%Y")

            if "Dsystem" in empresa_escolhida:
                linhas_html = "".join([f"<tr><td style='padding:6px; border-bottom:1px solid #ddd;'>{s['descricao']}</td><td align='center' style='padding:6px; border-bottom:1px solid #ddd;'>1,000</td><td align='right' style='padding:6px; border-bottom:1px solid #ddd;'>{formata_moeda(s['valor'] * mult).replace('R$ ', '')}</td><td align='right' style='padding:6px; border-bottom:1px solid #ddd;'>0,00</td><td align='right' style='padding:6px; border-bottom:1px solid #ddd;'>{formata_moeda(s['valor'] * mult).replace('R$ ', '')}</td></tr>" for s in servicos])

                html_doc = f"""
<div id="doc-impressao" style="background:white; color:black; padding:20px; font-family:Arial, sans-serif; font-size:12px; width:100%; box-sizing: border-box;">
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
        <tr><td><b>Endereço:</b> {endereco}, {numero} {bairro} - {cidade_estado}</td><td><b>Telefone:</b> {telefone}</td></tr>
        <tr><td colspan="2"><b>E-mail:</b> {email}</td></tr>
    </table>
    <p style="margin:2px 0 0 0; font-size:11px;">{rg_mei}</p>
</div>

<h4 style="color:#004488; border-bottom:1px solid #004488; margin-bottom:5px; padding-bottom:2px;">Itens</h4>
<table style="width:100%; border-collapse:collapse; margin-bottom:10px; font-size:11px;">
    <tr style="background:#f4f4f4;">
        <th style="padding:5px; border:1px solid #ccc; text-align:left;">Descrição</th>
        <th style="padding:5px; border:1px solid #ccc; text-align:center;">Qtd</th>
        <th style="padding:5px; border:1px solid #ccc; text-align:right;">Unitário (R$)</th>
        <th style="padding:5px; border:1px solid #ccc; text-align:right;">Desconto (R$)</th>
        <th style="padding:5px; border:1px solid #ccc; text-align:right;">Total (R$)</th>
    </tr>
    {linhas_html}
</table>

<div style="display:flex; justify-content:flex-end; margin-bottom:15px;">
    <table style="width:60%; border-collapse:collapse; text-align:right; font-size:11px;">
        <tr style="background:#f4f4f4;">
            <th style="padding:5px; border:1px solid #ccc; text-align:center;">Valor Total</th><th style="padding:5px; border:1px solid #ccc; text-align:center;">Frete</th><th style="padding:5px; border:1px solid #ccc; text-align:center;">Desconto</th><th style="padding:5px; border:1px solid #ccc; text-align:center;">Total Liquido</th>
        </tr>
        <tr>
            <td style="padding:5px; border:1px solid #ccc; text-align:center;">{formata_moeda(valor_final_total).replace('R$ ', '')}</td><td style="padding:5px; border:1px solid #ccc; text-align:center;">0,00</td><td style="padding:5px; border:1px solid #ccc; text-align:center;">0,00</td><td style="padding:5px; border:1px solid #ccc; font-weight:bold; text-align:center;">{formata_moeda(valor_final_total).replace('R$ ', '')}</td>
        </tr>
    </table>
</div>

<h4 style="color:#004488; border-bottom:1px solid #004488; margin-bottom:5px; padding-bottom:2px;">Forma de Pagamento</h4>
<table style="width:100%; border-collapse:collapse; margin-bottom:15px; font-size:11px;">
    <tr style="background:#f4f4f4;">
        <th style="padding:5px; border:1px solid #ccc; text-align:center;">Parcela</th><th style="padding:5px; border:1px solid #ccc; text-align:center;">Forma de Pagamento</th><th style="padding:5px; border:1px solid #ccc; text-align:center;">Vencimento</th><th style="padding:5px; border:1px solid #ccc; text-align:left;">Observação</th><th style="padding:5px; border:1px solid #ccc; text-align:right;">Total (R$)</th>
    </tr>
    <tr>
        <td style="padding:5px; border:1px solid #ccc; text-align:center;">1/1</td><td style="padding:5px; border:1px solid #ccc; text-align:center;">{forma_pagamento}</td><td style="padding:5px; border:1px solid #ccc; text-align:center;">{data_v}</td><td style="padding:5px; border:1px solid #ccc;">{obs_pagamento}</td><td style="padding:5px; border:1px solid #ccc; text-align:right;">{formata_moeda(valor_final_total).replace('R$ ', '')}</td>
    </tr>
</table>

<h4 style="color:#004488; border-bottom:1px solid #004488; margin-bottom:5px; padding-bottom:2px;">Outras informações</h4>
<p style="margin-top:2px; font-size:11px;"><b>Observações Gerais:</b><br>{obs_gerais}</p>
</div>"""

            elif "NC" in empresa_escolhida:
                linhas_html = "".join([f"<tr><td style='border:1px solid #000; padding:6px; text-align:center;'>{i+1}</td><td style='border:1px solid #000; padding:6px;'>{s['descricao']}</td><td style='border:1px solid #000; padding:6px; text-align:center;'>1</td><td style='border:1px solid #000; padding:6px; text-align:right;'>{formata_moeda(s['valor'] * mult)}</td><td style='border:1px solid #000; padding:6px; text-align:right;'>{formata_moeda(s['valor'] * mult)}</td></tr>" for i, s in enumerate(servicos)])
                
                html_doc = f"""
<div id="doc-impressao" style="background:white; color:black; padding:20px; font-family:Arial, sans-serif; font-size:11px; width:100%; box-sizing: border-box;">
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
    <div style="display:flex;"><div style="width:50%;"><b>RG/MEI:</b> {rg_mei}</div><div style="width:50%;"><b>ENDEREÇO:</b> {endereco}, {numero}</div></div>
    <div style="display:flex;"><div style="width:50%;"><b>BAIRRO:</b> {bairro}</div><div style="width:50%;"><b>CIDADE/UF:</b> {cidade_estado}</div></div>
</div>
<table style="width:100%; border-collapse:collapse; margin-bottom:15px;">
    <tr style="background:#e6e6e6;">
        <th style="border:1px solid #000; padding:6px;">ITEM</th><th style="border:1px solid #000; padding:6px; width:45%;">PRODUTO/SERVIÇO</th><th style="border:1px solid #000; padding:6px;">QUANT</th><th style="border:1px solid #000; padding:6px;">VALOR UNIDADE</th><th style="border:1px solid #000; padding:6px;">SUBTOTAL</th>
    </tr>
    {linhas_html}
</table>
<div style="display:flex; justify-content:space-between;">
    <div style="width:50%; font-size:10px;">
        <b>FORMA DE PAGAMENTO:</b><br>{forma_pagamento}<br><br>
        <b>OBSERVAÇÃO DO PAGAMENTO:</b><br>{obs_pagamento}<br><br>
        <b>OBSERVAÇÕES GERAIS:</b><br>{obs_gerais}
    </div>
    <div style="width:40%; border:1px solid #000; padding:10px; text-align:right;">
        <div style="display:flex; justify-content:space-between; margin-bottom:10px;"><span>ACRÉSCIMO: R$ 0,00</span><span>DESCONTO: R$ 0,00</span></div>
        <b style="font-size:14px;">TOTAL: {formata_moeda(valor_final_total)}</b>
    </div>
</div>
</div>"""

            else:
                linhas_html = "".join([f"<tr><td style='border:1px solid #ccc; padding:6px; text-align:center;'>{i+1}</td><td style='border:1px solid #ccc; padding:6px;'>{s['descricao']}</td><td style='border:1px solid #ccc; padding:6px; text-align:center;'>1</td><td style='border:1px solid #ccc; padding:6px; text-align:right;'>{formata_moeda(s['valor'] * mult)}</td></tr>" for i, s in enumerate(servicos)])
                
                html_doc = f"""
<div id="doc-impressao" style="background:white; color:#333; padding:20px; font-family:Arial, sans-serif; font-size:10px; width:100%; box-sizing: border-box;">
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
        <div style="width:48%;"><b>ENDEREÇO:</b> {endereco}, {numero}</div><div style="width:48%;"><b>BAIRRO:</b> {bairro}</div>
        <div style="width:48%;"><b>CIDADE/ESTADO:</b> {cidade_estado}</div>
    </div>
</div>
<table style="width:100%; border-collapse:collapse; margin-bottom:10px;">
    <tr style="background:#4ba3d5; color:white;">
        <th style="border:1px solid #ccc; padding:6px;">ITEM</th><th style="border:1px solid #ccc; padding:6px; width:50%;">PRODUTO/SERVIÇO</th><th style="border:1px solid #ccc; padding:6px;">QUANT</th><th style="border:1px solid #ccc; padding:6px;">VALOR</th>
    </tr>
    {linhas_html}
</table>
<div style="display:flex; justify-content:space-between; align-items:center; padding:8px; border:1px solid #ccc; margin-bottom:15px; font-weight:bold; background:#fafafa;">
    <span>SUBTOTAL: {formata_moeda(valor_final_total)}</span>
    <span>DESCONTO: R$ 0,00</span>
    <span>ACRÉSCIMO: R$ 0,00</span>
    <span style="font-size:14px; color:#4ba3d5;">TOTAL: {formata_moeda(valor_final_total)}</span>
</div>
<div>
    <p style="margin:0 0 4px 0;"><b>FORMAS DE PAGAMENTO:</b> {forma_pagamento} - {obs_pagamento}</p>
    <p style="margin:0 0 4px 0;"><b>OBSERVAÇÕES:</b> {obs_gerais}</p>
    <p style="margin:10px 0 0 0; font-weight:bold;">OBS: (12) MESES DE GARANTIA</p>
</div>
</div>"""
            st.markdown(html_doc, unsafe_allow_html=True)
        else:
            st.warning("⚠️ Preencha o Nome e Adicione Serviços.")


elif menu == "📋 Ordem de Serviço (OS)":
    st.title("📋 Controle de OS")
    tabs = ["➕ Gerar Nova", "🗄️ Histórico"]
    aba1, aba2 = st.tabs(tabs)

    with aba1:
        st.write("Registre a entrada de equipamentos. Exclusivo Dsystem Tecnologia.")
        with st.container():
            data_hoje = date.today().strftime("%d/%m/%Y")
            c_cli1, c_cli2 = st.columns(2)
            with c_cli1: os_cliente = st.text_input("Nome do Cliente:")
            with c_cli2: os_cpf = st.text_input("CPF/CNPJ:")
            c_end1, c_end2 = st.columns([3,1])
            with c_end1: os_endereco = st.text_input("Endereço Completo:")
            with c_end2: os_telefone = st.text_input("Telefone do Cliente:")
            
            st.write("---")
            qtd_eq = st.number_input("Qtd Equipamentos:", min_value=1, max_value=10, value=1)
            equipamentos = []
            for i in range(qtd_eq):
                c1, c2, c3 = st.columns(3)
                e = c1.text_input(f"Aparelho/Modelo {i+1}", key=f"eq_{i}")
                m = c2.text_input(f"Nº Série/Marca {i+1}", key=f"ma_{i}")
                a = c3.selectbox(f"Avaria? {i+1}", ["Não", "Sim"], key=f"av_{i}")
                if e: equipamentos.append({"e": e, "m": m, "a": a})
            
            st.write("---")
            os_servico = st.text_area("Problema Relatado:")
            os_tecnico = st.text_input("Técnico / Vendedor:")

            st.write("<br>", unsafe_allow_html=True)
            submit_os = st.button("💾 Salvar OS e Gerar Ficha", type="primary", use_container_width=True)

        if submit_os:
            if os_cliente and equipamentos:
                conn = sqlite3.connect('banco_dsystem.db')
                c = conn.cursor()
                c.execute('INSERT INTO ordens_servico (data_os, cliente, cpf_cnpj, endereco, equipamento, marca, avaria, servico, atendente) VALUES (?,?,?,?,?,?,?,?,?)',
                          (data_hoje, os_cliente, os_cpf, os_endereco, "|".join([x['e'] for x in equipamentos]), "|".join([x['m'] for x in equipamentos]), "|".join([x['a'] for x in equipamentos]), os_servico, os_tecnico))
                os_id = c.lastrowid
                conn.commit()
                conn.close()
                st.success(f"OS Nº {os_id} Salva! Aperte **Ctrl+P** para imprimir a folha cheia.")
                
                linhas_eq_html = "".join([f"<tr><td style='border:1px solid #333; padding:5px; width:40%;'>{eq['e']}</td><td style='border:1px solid #333; padding:5px; width:45%;'>{eq['m']}</td><td style='border:1px solid #333; padding:5px; text-align:center; width:15%;'>{eq['a'].upper()}</td></tr>" for eq in equipamentos])

                html_os = f"""
<div id="doc-impressao" style="font-family:Arial, sans-serif; font-size:10px; color:#000; background:#fff; width:100%; box-sizing: border-box; padding:20px;">
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
Ordem de serviço N° {os_id:05d}
</div>
</div>
<table style="width:100%; border-collapse:collapse; margin-bottom:10px;">
<tr>
<td style="width:55%; vertical-align:top; padding-right:10px; border:none;">
<div style="margin-bottom:2px; font-weight:bold; font-size:10px;">Cliente</div>
<div style="border:1px solid #333; padding:8px; min-height:40px; font-size:10px;">
<b>{os_cliente}</b><br>Telefone: {os_telefone}<br>CPF/CNPJ: {os_cpf}<br>Endereço: {os_endereco}
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
<td style="border:1px solid #333; padding:4px; font-weight:bold; background:#f4f4f4;">Data<br>prevista</td>
<td style="border:1px solid #333; padding:4px;">3 Dias</td>
<td style="border:1px solid #333; padding:4px; font-weight:bold; background:#f4f4f4;">Status</td>
<td style="border:1px solid #333; padding:4px; font-weight:bold; color:red;">Aberto</td>
</tr>
</table>
</td>
</tr>
</table>
<div style="margin-bottom:2px; font-weight:bold; font-size:10px;">Aparelhos / Equipamentos Recebidos</div>
<table style="width:100%; border-collapse:collapse; margin-bottom:10px;">
<tr style="background:#f4f4f4;">
<th style="border:1px solid #333; padding:4px; text-align:left; width:40%;">Equipamento</th>
<th style="border:1px solid #333; padding:4px; text-align:left; width:45%;">Número de série / Marca</th>
<th style="border:1px solid #333; padding:4px; text-align:center; width:15%;">Avaria?</th>
</tr>
{linhas_eq_html}
</table>
<div style="margin-bottom:2px; font-weight:bold; font-size:10px;">Problema / Serviço a Executar</div>
<div style="border:1px solid #333; padding:8px; margin-bottom:10px; min-height:35px; font-size:10px;">{os_servico}</div>
<table style="width:100%; border-collapse:collapse; margin-bottom:10px; text-align:right;">
<tr><th style="border:1px solid #333; padding:4px; background:#f4f4f4; width:33%; text-align:center;">Total serviços</th><th style="border:1px solid #333; padding:4px; background:#f4f4f4; width:33%; text-align:center;">Total peças</th><th style="border:1px solid #333; padding:4px; background:#f4f4f4; width:34%; text-align:center;">Total da ordem de serviço</th></tr>
<tr><td style="border:1px solid #333; padding:4px; text-align:center;">A definir</td><td style="border:1px solid #333; padding:4px; text-align:center;">A definir</td><td style="border:1px solid #333; padding:4px; text-align:center;"><b>A definir</b></td></tr>
</table>
<div style="margin-bottom:2px; font-weight:bold; font-size:9px;">Observações do recebimento</div>
<div style="border:1px solid #333; padding:8px; margin-bottom:15px; font-size:9px; text-align:justify; line-height:1.2; color:#444;">
Informamos que, após a realização do orçamento, o cliente tem um prazo de até 90 dias para retirar o aparelho em nossa loja. Caso a retirada não seja feita dentro deste período, nos reservamos o direito de tomar as medidas cabíveis para a destinação do aparelho, conforme a legislação vigente (artigo 1.275, inciso III, do Código Civil Brasileiro). Reforçamos a importância de buscar o aparelho dentro do prazo estabelecido para evitar qualquer inconveniente. Agradecemos a compreensão e estamos à disposição para quaisquer dúvidas.
</div>
<div style="margin-top:10px;">
<p style="font-size:11px; margin-bottom:15px;"><b>Técnico(s) / Vendedor:</b> {os_tecnico}</p>
<p style="font-size:9px; color:#555; margin-bottom:20px;">Concordo com os termos descritos acima.</p>
<table style="width:100%; border:none;">
<tr>
<td style="width:40%; vertical-align:bottom; font-size:10px;"><b>Data:</b> ____/____/________</td>
<td style="width:60%; text-align:center; vertical-align:bottom;">___________________________________________________<br><span style="color:#555; font-size:9px;">Assinatura do responsável</span></td>
</tr>
</table>
</div>
</div>"""
                st.markdown(html_os, unsafe_allow_html=True)
            else:
                st.error("⚠️ Atenção: Preencha o Nome e Adicione Equipamentos.")

    with aba2:
        st.subheader("Registros de OS")
        conn = sqlite3.connect('banco_dsystem.db')
        c = conn.cursor()
        c.execute('SELECT os_id, data_os, cliente, equipamento, servico, atendente FROM ordens_servico ORDER BY os_id DESC')
        dados = c.fetchall()
        conn.close()
        
        if len(dados) > 0:
            st.dataframe(dados, column_config={"0": "OS Nº", "1": "Data", "2": "Cliente", "3": "Equip.", "4": "Problema", "5": "Técnico"}, use_container_width=True, hide_index=True)

        if st.session_state['cargo'] == "admin":
            st.warning("Área Restrita (Admin): Exclusão de OS")
            col_d1, col_d2 = st.columns([1,3])
            with col_d1:
                id_del = st.number_input("ID da OS", min_value=1, step=1)
                if st.button("🗑️ Excluir Definitivamente"):
                    deletar_os_do_banco(id_del)
                    st.success("Excluída!")
                    st.rerun()

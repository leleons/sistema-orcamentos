import streamlit as st
import sqlite3
import base64
import os
from datetime import date, timedelta


st.set_page_config(page_title="Sistema Dsystem", page_icon="⚙️", layout="wide")

st.markdown("""
<style>
    /* Ocultar menus desnecessários do Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Design dos Botões Principais */
    .stButton>button {
        background-color: #004488 !important;
        color: white !important;
        border-radius: 8px;
        border: 2px solid #004488;
        padding: 10px 24px;
        font-weight: bold;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background-color: #00a2e8 !important;
        color: white !important;
        border: 2px solid #004488 !important;
        transform: scale(1.02);
    }
    
    /* Cartões de Métrica (Valores) */
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        padding: 15px;
        border-radius: 10px;
        border-left: 6px solid #00a2e8;
        box-shadow: 2px 4px 10px rgba(0,0,0,0.08);
    }
    
    /* Títulos padronizados no Azul Dsystem */
    h1, h2, h3 {
        color: #004488 !important;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    
    /* Abas superiores (Tabs) arredondadas e limpas */
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        background-color: #f0f2f6;
        border-radius: 8px 8px 0px 0px;
        padding: 10px 20px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #004488 !important;
        color: white !important;
    }
</style>
""", unsafe_allow_html=True)

if 'pagina_atual' not in st.session_state:
    st.session_state['pagina_atual'] = "🏠 Página Inicial"

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
st.sidebar.title("⚙️ Dsystem OS")
st.sidebar.write("Painel de Controle")

menu = st.sidebar.radio(
    "Navegação:",
    ["🏠 Página Inicial", "📊 Gerador de Orçamentos", "📋 Ordem de Serviço (OS)"],
    key="pagina_atual"
)
st.sidebar.divider()
st.sidebar.caption("Desenvolvido para Dsystem Tecnologia")


if menu == "🏠 Página Inicial":
    st.title("Bem-vindo ao Sistema Dsystem ")
    st.write("Escolha uma das ferramentas abaixo para começar o seu atendimento.")
    st.write("<br>", unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        st.info("### 📊 Gerador de Orçamentos\nCrie propostas comerciais rápidas para a Dsystem, GT Solutions (+45%) ou NC Comercial (+30%). O sistema formata a folha A4 pronta para impressão em PDF.")
        if st.button("Abrir Gerador de Orçamentos ➔", use_container_width=True):
            st.session_state['pagina_atual'] = "📊 Gerador de Orçamentos"
            st.rerun()

    with col2:
        st.success("### 📋 Ordem de Serviço\nRegistre as entradas de equipamentos de forma oficial. Os dados ficam salvos para sempre no Banco de Dados e o sistema gera a via para o cliente assinar.")
        if st.button("Abrir Ordem de Serviço ➔", use_container_width=True):
            st.session_state['pagina_atual'] = "📋 Ordem de Serviço (OS)"
            st.rerun()


elif menu == "📊 Gerador de Orçamentos":
    st.title("📊 Gerador de Orçamentos")
    st.caption("Preencha os dados abaixo para gerar propostas comerciais profissionais.")
    
    with st.container():
        st.subheader("👤 Dados do Cliente")
        col_cli1, col_cli2, col_cli3 = st.columns(3)
        with col_cli1: cliente = st.text_input("Nome do Cliente:")
        with col_cli2: telefone = st.text_input("Telefone:")
        with col_cli3: email = st.text_input("E-mail:")

        col_doc1, col_doc2 = st.columns(2)
        with col_doc1: cnpj = st.text_input("CNPJ / CPF:")
        with col_doc2: rg_mei = st.text_input("RG / MEI / IE:")

        col_end1, col_end2, col_end3 = st.columns([3, 1, 2])
        with col_end1: endereco = st.text_input("Rua / Endereço:")
        with col_end2: numero = st.text_input("Número:")
        with col_end3: bairro = st.text_input("Bairro:")

        col_cid1, col_cid2 = st.columns([3, 1])
        with col_cid1: cidade = st.text_input("Cidade (Ex: Belo Horizonte):", value="Belo Horizonte")
        with col_cid2: estado = st.text_input("Estado (Ex: MG):", value="MG")

    st.divider()
    
    with st.container():
        st.subheader("🛠️ Serviços e Produtos")
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
    st.subheader("🖨️ Fechamento e Documento")
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
            st.success("Documento gerado! Pressione **Ctrl + P** (ou toque em Compartilhar/Imprimir no celular) para salvar como PDF.")
            
            data_criacao = date.today().strftime("%d/%m/%Y")
            data_validade = (date.today() + timedelta(days=7)).strftime("%d/%m/%Y")

            if "Dsystem" in empresa_escolhida:
                linhas_tabela = "".join([f"<tr><td style='padding:8px; border:1px solid #ddd;'>{s['descricao']}</td><td align='center' style='border:1px solid #ddd;'>1</td><td align='right' style='border:1px solid #ddd;'>{formata_moeda(s['valor'])}</td><td align='right' style='border:1px solid #ddd;'>{formata_moeda(s['valor'])}</td></tr>" for s in servicos])
              
                html_orcamento = f"""
<div style="background:white; color:black; padding:40px; font-family:Arial; max-width:800px; margin:0 auto; border:1px solid #ccc; box-shadow: 0 4px 8px rgba(0,0,0,0.1);">
<div style="display:flex; justify-content:space-between; border-bottom:3px solid #004488; padding-bottom:20px;">
<div>{carrega_logo("logo_dsystem.png", "DSYSTEM TECNOLOGIA", "#004488")}<p style="margin:5px 0; font-size:14px; font-weight:bold;">D F Pereira Informática</p></div>
<div style="text-align:right; font-size:13px;"><p><b>Criação:</b> {data_criacao}</p><p><b>Validade:</b> {data_validade}</p><p>CNPJ: 23.524.449/0001-54</p></div>
</div>
<div style="margin-top:20px; font-size:14px;"><p style="color:#004488; font-weight:bold;">Cliente</p><p><b>{cliente}</b></p><p>{endereco}, {numero} - {bairro}</p></div>
<table style="width:100%; border-collapse:collapse; margin-top:20px; font-size:14px;">
<tr style="background:#f0f0f0; border:1px solid #ddd;"><th style="padding:8px; text-align:left;">Item / Descrição</th><th>Qtd</th><th style="text-align:right;">Unitário</th><th style="text-align:right;">Total</th></tr>
{linhas_tabela}
</table>
<div style="text-align:right; margin-top:20px; font-size:18px;"><b>Total Líquido: <span style="color:#004488;">{formata_moeda(valor_base_total)}</span></b></div>
</div>
"""

            elif "NC" in empresa_escolhida:
                linhas_tabela = "".join([f"<tr><td style='border:1px solid #000; padding:8px;'>{i+1}</td><td style='border:1px solid #000; padding:8px;'>{s['descricao']}</td><td style='border:1px solid #000; padding:8px;' align='center'>1</td><td style='border:1px solid #000; padding:8px;' align='right'>{formata_moeda(s['valor']*1.3)}</td><td style='border:1px solid #000; padding:8px;' align='right'>{formata_moeda(s['valor']*1.3)}</td></tr>" for i, s in enumerate(servicos)])
                html_orcamento = f"""
<div style="background:white; color:black; padding:40px; font-family:Arial; max-width:800px; margin:0 auto; border:1px solid #ccc;">
<div style="display:flex; justify-content:space-between; border-bottom:2px solid #000; padding-bottom:20px;">
<div>{carrega_logo("logo_nc.png", "NC Comercial", "#000")}</div>
<div style="text-align:right;"><h2 style="margin:0;">ORÇAMENTO n° 056</h2><p>DATA DE EMISSÃO: {data_criacao}</p></div>
</div>
<div style="margin-top:20px; font-size:12px;"><b>NOME:</b> {cliente} | <b>CPF/CNPJ:</b> {cnpj} | <b>EMAIL:</b> {email}<br><b>ENDEREÇO:</b> {endereco}, {numero}</div>
<table style="width:100%; border-collapse:collapse; margin-top:20px; font-size:12px;"><tr style="background:#e6e6e6;"><th style="border:1px solid #000; padding:8px;">ITEM</th><th style="border:1px solid #000; padding:8px;">DESCRIÇÃO</th><th style="border:1px solid #000; padding:8px;">QTD</th><th style="border:1px solid #000; padding:8px;">VALOR UNIDADE</th><th style="border:1px solid #000; padding:8px;">SUBTOTAL</th></tr>{linhas_tabela}</table>
<div style="text-align:right; margin-top:20px; font-size:16px;"><b>TOTAL: {formata_moeda(orcamento_parceiro_1)}</b></div>
</div>
"""
                
            else:
                linhas_tabela = "".join([f"<tr><td style='border:1px solid #ccc; padding:8px;'>{i+1}</td><td style='border:1px solid #ccc; padding:8px;'>{s['descricao']}</td><td style='border:1px solid #ccc; padding:8px;' align='center'>1</td><td style='border:1px solid #ccc; padding:8px;' align='right'>{formata_moeda(s['valor']*1.45)}</td></tr>" for i, s in enumerate(servicos)])
                html_orcamento = f"""
<div style="background:white; color:black; padding:40px; font-family:Arial; max-width:800px; margin:0 auto; border:1px solid #ccc;">
<div style="display:flex; justify-content:space-between; border-bottom:1px solid #ddd; padding-bottom:20px;">
<div>{carrega_logo("logo_gt.png", "GT Solutions", "#00a2e8")}<p style="font-size:11px;">GT Solutions Eireli<br>gustavo@gtimpressao.com.br</p></div>
<div style="text-align:right;"><h2>ORÇAMENTO</h2><p>EMITIDO EM: {data_criacao}</p></div>
</div>
<div style="margin-top:20px; font-size:12px; background:#f2f2f2; padding:10px;"><b>CLIENTE:</b> {cliente} | <b>CPF/CNPJ:</b> {cnpj} | <b>EMAIL:</b> {email}<br><b>ENDEREÇO:</b> {endereco}, {numero}</div>
<table style="width:100%; border-collapse:collapse; margin-top:20px; font-size:12px;"><tr style="background:#0088cc; color:white;"><th style="border:1px solid #ccc; padding:8px;">ITEM</th><th style="border:1px solid #ccc; padding:8px;">DESCRIÇÃO</th><th style="border:1px solid #ccc; padding:8px;">QTD</th><th style="border:1px solid #ccc; padding:8px;">VALOR</th></tr>{linhas_tabela}</table>
<div style="text-align:right; margin-top:20px; font-size:16px; color:#0088cc;"><b>TOTAL: {formata_moeda(orcamento_parceiro_2)}</b></div>
</div>
"""

            st.markdown(html_orcamento, unsafe_allow_html=True)
        else:
            st.warning("⚠️ Preencha os campos obrigatórios (Nome e Itens do Serviço) para gerar o orçamento.")

elif menu == "📋 Ordem de Serviço (OS)":
    st.title("📋 Controle de Ordem de Serviço")
    
    aba1, aba2 = st.tabs(["➕ Gerar Nova O.S.", "🗄️ Histórico (Banco de Dados)"])

    with aba1:
        st.write("Registre a entrada de equipamentos abaixo. Exclusivo Dsystem Tecnologia.")
        
        with st.form("form_os", clear_on_submit=False):
            data_hoje = date.today().strftime("%d/%m/%Y")
            
            col_f1, col_f2 = st.columns(2)
            with col_f1: os_cliente = st.text_input("Nome do Cliente:")
            with col_f2: os_cpf_cnpj = st.text_input("CPF ou CNPJ:")
            
            os_endereco = st.text_input("Endereço Completo:")
            
            col_f3, col_f4, col_f5 = st.columns(3)
            with col_f3: os_equipamento = st.text_input("Equipamento:")
            with col_f4: os_marca = st.text_input("Marca / N° de Série:")
            with col_f5: os_avaria = st.selectbox("Apresenta Avaria?", ["Não", "Sim, possui marcas/quebras"])
            
            os_servico = st.text_area("Problema Relatado / Serviço a Executar:", height=100)
            os_atendente = st.text_input("Técnico / Atendente responsável:")

           

        if submit_os:
            if os_cliente and os_equipamento and os_servico:
     
                conn = sqlite3.connect('banco_dsystem.db')
                c = conn.cursor()
                c.execute('''INSERT INTO ordens_servico (data_os, cliente, cpf_cnpj, endereco, equipamento, marca, avaria, servico, atendente)
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                          (data_hoje, os_cliente, os_cpf_cnpj, os_endereco, os_equipamento, os_marca, os_avaria, os_servico, os_atendente))
                os_id = c.lastrowid 
                conn.commit()
                conn.close()

                st.success(f"✅ Ordem de Serviço N° **{os_id}** gerada com sucesso!")
                
     
                tag_logo = carrega_logo("logo_dsystem.png", "DSYSTEM", "#004488", largura="140")
                html_os = f"""
<div style="font-family: Arial, sans-serif; font-size: 11px; color: #000; background: #fff; max-width: 800px; margin: 0 auto; padding: 30px; border: 1px solid #ccc; box-shadow: 0 4px 8px rgba(0,0,0,0.1);">
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
<td style="border: 1px solid #333; padding: 6px;">{os_id}</td>
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
<table style="width: 100%; border-collapse: collapse; margin-bottom: 15px;">
<tr>
<td style="width: 55%; vertical-align: top; padding-right: 15px; border: none;">
<div style="font-size: 10px; margin-bottom: 3px; font-weight: bold;">Equipamento / Marca / Nº de Série</div>
<div style="border: 1px solid #333; padding: 10px;">
{os_equipamento} / {os_marca}
</div>
</td>
<td style="width: 45%; vertical-align: top; border: none;">
<div style="font-size: 10px; margin-bottom: 3px; font-weight: bold;">Avarias visíveis?</div>
<div style="border: 1px solid #333; padding: 10px;">
{os_avaria}
</div>
</td>
</tr>
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
                st.error("⚠️ Atenção: Preencha o Nome, Equipamento e Serviço para gerar a Ordem.")

    with aba2:
        st.subheader("🗄️ Histórico de Atendimentos")
        
        conn = sqlite3.connect('banco_dsystem.db')
        c = conn.cursor()
        c.execute('SELECT os_id, data_os, cliente, equipamento, servico, atendente FROM ordens_servico ORDER BY os_id DESC')
        dados_db = c.fetchall()
        conn.close()

        if len(dados_db) > 0:
            st.dataframe(
                dados_db,
                column_config={"0": "O.S Nº", "1": "Data", "2": "Cliente", "3": "Equipamento", "4": "Problema", "5": "Técnico"},
                use_container_width=True, hide_index=True
            )
        else:
            st.info("Nenhuma OS registrada no momento.")

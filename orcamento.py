import streamlit as st
import base64
import os
from datetime import date, timedelta


st.set_page_config(page_title="Gerador de Orçamentos", page_icon="📊", layout="centered")

def formata_moeda(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def carrega_logo(caminho_imagem, nome_empresa, cor_texto):
    if os.path.exists(caminho_imagem):
        with open(caminho_imagem, "rb") as img_file:
            codigo = base64.b64encode(img_file.read()).decode()
            return f'<img src="data:image/png;base64,{codigo}" width="150" style="margin-bottom: 10px;">'
    else:
        return f'<h2 style="color: {cor_texto}; margin: 0; letter-spacing: 1px;">{nome_empresa}</h2>'

st.title("📊 Sistema de Orçamentos")
st.write("Preencha os dados e escolha qual documento deseja gerar.")


col_cli1, col_cli2, col_cli3 = st.columns(3)
with col_cli1:
    cliente = st.text_input("Nome do Cliente:")
with col_cli2:
    telefone = st.text_input("Telefone:")
with col_cli3:
    cnpj = st.text_input("CNPJ / CPF:")

col_end1, col_end2, col_end3 = st.columns([3, 1, 2])
with col_end1:
    endereco = st.text_input("Rua / Endereço:")
with col_end2:
    numero = st.text_input("Número:")
with col_end3:
    bairro = st.text_input("Bairro:")

col_cid1, col_cid2 = st.columns([3, 1])
with col_cid1:
    cidade = st.text_input("Cidade (Ex: Belo Horizonte):", value="Belo Horizonte")
with col_cid2:
    estado = st.text_input("Estado (Ex: MG):", value="MG")

servico = st.text_input("Descrição do Serviço (Ex: Instalação Impressora Epson):")
valor_base = st.number_input("Valor do nosso orçamento - Dsystem (R$):", min_value=0.0, value=0.0, step=50.0, format="%.2f")

st.write("---")
st.write("### Escolha a Empresa para o Documento Final:")
empresa_escolhida = st.radio(
    "Selecione uma opção:", 
    ["Dsystem Tecnologia (Base)", "NC Comercial (+30%)", "GT Solutions (+45%)"],
    horizontal=True,
    label_visibility="collapsed"
)

if st.button("Gerar Documento Oficial", type="primary"):
    
    if valor_base > 0 and cliente and servico and endereco:
        
        orcamento_parceiro_1 = valor_base * 1.30 # 
        orcamento_parceiro_2 = valor_base * 1.45 # 
        st.success(f"Cálculos realizados com sucesso para **{cliente}**!")
        
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.metric(label="Dsystem", value=formata_moeda(valor_base))
        with col_b:
            st.metric(label="NC (+30%)", value=formata_moeda(orcamento_parceiro_1))
        with col_c:
            st.metric(label="GT (+45%)", value=formata_moeda(orcamento_parceiro_2))
            
        st.divider()
        st.write(f"### 🖨️ Documento do Cliente")
        st.info("Para salvar como PDF, aperte **Ctrl + P**, escolha 'Salvar como PDF' e desmarque 'Cabeçalhos e rodapés'.")

        data_criacao = date.today().strftime("%d/%m/%Y")
        data_validade = (date.today() + timedelta(days=7)).strftime("%d/%m/%Y")


        if "Dsystem" in empresa_escolhida:
            valor_final = valor_base
            tag_logo = carrega_logo("logo_dsystem.png", "DSYSTEM TECNOLOGIA", "#004488")
            
            html_orcamento = f"""
<div style="background-color: white; color: black; padding: 40px; border: 1px solid #ccc; font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto;">
<div style="display: flex; justify-content: space-between; border-bottom: 3px solid #004488; padding-bottom: 20px;">
<div>
{tag_logo}
<p style="margin: 5px 0; font-size: 14px; font-weight: bold;">D F Pereira Informática</p>
<p style="margin: 0; font-size: 12px; color: #555;">Rua Glicério Alves Pinto 129, Alvorada</p>
<p style="margin: 0; font-size: 12px; color: #555;">Belo Horizonte MG 34.700-130</p>
</div>
<div style="text-align: right; font-size: 13px;">
<p style="margin: 0;"><b>Criação:</b> {data_criacao}</p>
<p style="margin: 0; margin-bottom: 10px;"><b>Validade:</b> {data_validade}</p>
<p style="margin: 0; color: #555;">CNPJ: 23.524.449/0001-54</p>
<p style="margin: 0; color: #555;">adm@dsystemtecnologia.com.br</p>
</div>
</div>
<div style="margin-top: 20px; font-size: 14px; padding-bottom: 10px; border-bottom: 1px solid #eee;">
<p style="margin: 0; color: #004488; font-weight: bold; margin-bottom: 5px;">Cliente</p>
<p style="margin: 0;"><b>{cliente}</b></p>
<p style="margin: 0;">{endereco}, {numero} - {bairro}</p>
</div>
<div style="margin-top: 20px;">
<p style="margin: 0; color: #004488; font-weight: bold; margin-bottom: 5px;">Itens</p>
<table style="width: 100%; border-collapse: collapse; font-size: 14px;">
<tr style="background-color: #f0f0f0; border: 1px solid #ddd;">
<th style="padding: 8px; text-align: left; border: 1px solid #ddd;">Item / Descrição</th>
<th style="padding: 8px; text-align: center; border: 1px solid #ddd;">Qtd</th>
<th style="padding: 8px; text-align: right; border: 1px solid #ddd;">Unitário (R$)</th>
<th style="padding: 8px; text-align: right; border: 1px solid #ddd;">Desconto (R$)</th>
<th style="padding: 8px; text-align: right; border: 1px solid #ddd;">Total (R$)</th>
</tr>
<tr>
<td style="padding: 8px; border: 1px solid #ddd;">{servico}</td>
<td style="padding: 8px; text-align: center; border: 1px solid #ddd;">1,00</td>
<td style="padding: 8px; text-align: right; border: 1px solid #ddd;">{formata_moeda(valor_final).replace('R$ ', '')}</td>
<td style="padding: 8px; text-align: right; border: 1px solid #ddd;">0,00</td>
<td style="padding: 8px; text-align: right; border: 1px solid #ddd;">{formata_moeda(valor_final).replace('R$ ', '')}</td>
</tr>
</table>
</div>
<div style="margin-top: 20px; display: flex; justify-content: flex-end;">
<table style="width: 60%; border-collapse: collapse; font-size: 14px;">
<tr style="background-color: #f0f0f0; border: 1px solid #ddd;">
<th style="padding: 8px; text-align: right; border: 1px solid #ddd;">Valor Total</th>
<th style="padding: 8px; text-align: right; border: 1px solid #ddd;">Frete</th>
<th style="padding: 8px; text-align: right; border: 1px solid #ddd;">Desconto</th>
<th style="padding: 8px; text-align: right; border: 1px solid #ddd; background-color: #004488; color: white;">Total Líquido</th>
</tr>
<tr>
<td style="padding: 8px; text-align: right; border: 1px solid #ddd;">{formata_moeda(valor_final).replace('R$ ', '')}</td>
<td style="padding: 8px; text-align: right; border: 1px solid #ddd;">0,00</td>
<td style="padding: 8px; text-align: right; border: 1px solid #ddd;">0,00</td>
<td style="padding: 8px; text-align: right; border: 1px solid #ddd; font-weight: bold;">{formata_moeda(valor_final).replace('R$ ', '')}</td>
</tr>
</table>
</div>
</div>
"""

        elif "NC" in empresa_escolhida:
            valor_final = orcamento_parceiro_1
            tag_logo = carrega_logo("logo_nc.png", "NC", "#000")
            
            html_orcamento = f"""
<div style="font-family: Arial, sans-serif; padding: 40px; color: #000; background: #fff; max-width: 800px; margin: 0 auto; border: 1px solid #ccc;">
<div style="display: flex; justify-content: space-between; border-bottom: 2px solid #000; padding-bottom: 10px; margin-bottom: 20px;">
<div style="width: 50%;">
<div style="display: flex; align-items: center; gap: 10px;">
{tag_logo}
<h1 style="margin: 0; font-size: 24px;">NC Comercial</h1>
</div>
<p style="margin: 5px 0 0 0; font-size: 11px;">R Dr José Welinton n 93 Planalto CNPJ 23.192.394/0001-22</p>
<p style="margin: 0; font-size: 11px;">EMAIL: financeiro.nccomercial@gmail.com TELEFONE: (31) 99412-2226</p>
</div>
<div style="width: 40%; text-align: right;">
<h2 style="margin: 0; font-size: 18px;">ORÇAMENTO n° 056</h2>
<p style="margin: 5px 0 0 0; font-size: 12px;">DATA DE EMISSÃO:</p>
<p style="margin: 0; font-size: 14px; font-weight: bold;">{data_criacao}</p>
</div>
</div>
<div style="font-size: 12px; line-height: 1.6; margin-bottom: 20px;">
<div style="display: flex;">
<div style="width: 50%;"><b>NOME:</b> {cliente}</div>
<div style="width: 50%;"><b>TELEFONE:</b> {telefone}</div>
</div>
<div style="display: flex;">
<div style="width: 50%;"><b>EMAIL:</b> </div>
<div style="width: 50%;"><b>CPF/CNPJ:</b> {cnpj}</div>
</div>
<div style="display: flex;">
<div style="width: 50%;"><b>RG/MEI:</b> </div>
<div style="width: 50%;"><b>ENDEREÇO:</b> {endereco}, {numero}</div>
</div>
<div style="display: flex;">
<div style="width: 40%;"><b>BAIRRO:</b> {bairro}</div>
<div style="width: 40%;"><b>CIDADE:</b> {cidade}</div>
<div style="width: 20%;"><b>UF:</b> {estado}</div>
</div>
</div>
<table style="width: 100%; border-collapse: collapse; font-size: 12px; text-align: center; margin-bottom: 20px;">
<tr style="background-color: #e6e6e6;">
<th style="padding: 8px; border: 1px solid #000;">ITEM</th>
<th style="padding: 8px; border: 1px solid #000; width: 40%;">PRODUTO/SERVIÇO</th>
<th style="padding: 8px; border: 1px solid #000;">QUANT</th>
<th style="padding: 8px; border: 1px solid #000;">VALOR UNIDADE</th>
<th style="padding: 8px; border: 1px solid #000;">SUBTOTAL</th>
</tr>
<tr>
<td style="padding: 8px; border: 1px solid #000;">1</td>
<td style="padding: 8px; border: 1px solid #000; text-align: left;">{servico}</td>
<td style="padding: 8px; border: 1px solid #000;">1</td>
<td style="padding: 8px; border: 1px solid #000;">{formata_moeda(valor_final)}</td>
<td style="padding: 8px; border: 1px solid #000;">{formata_moeda(valor_final)}</td>
</tr>
</table>
<div style="display: flex; justify-content: flex-end; font-size: 12px; font-weight: bold;">
<div style="width: 50%; border: 1px solid #000; padding: 10px;">
<div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
<span>ACRÉSCIMO: R$ 0,00</span>
<span>DESCONTO: R$ 0,00</span>
</div>
<div style="text-align: right; font-size: 14px; margin-top: 10px;">
TOTAL: {formata_moeda(valor_final)}
</div>
</div>
</div>
</div>
"""

        else:
            valor_final = orcamento_parceiro_2
            tag_logo = carrega_logo("logo_gt.png", "GT Soluções", "#00a2e8")
            
            html_orcamento = f"""
<div style="font-family: Arial, sans-serif; padding: 40px; color: #333; background: #fff; max-width: 800px; margin: 0 auto; border: 1px solid #ccc;">
<div style="display: flex; justify-content: space-between; margin-bottom: 20px;">
<div style="width: 30%;">
{tag_logo}
</div>
<div style="width: 40%; font-size: 11px; line-height: 1.4;">
<h3 style="margin:0; color: #0088cc;">GT Solutions Eireli</h3>
<p style="margin:0;">ENDEREÇO: AV Alterosa 17, sala 6</p>
<p style="margin:0;">parque turista - contagem</p>
<p style="margin:0;">TELEFONE: (31) 9 8679-7785</p>
<p style="margin:0;">EMAIL: gustavo@gtimpressao.com.br</p>
<p style="margin:0;">WEBSITE: www.gtimpressao.com.br</p>
<p style="margin:0;">CPF/CNPJ: 34.349.098/0001-09</p>
</div>
<div style="width: 25%; font-size: 12px; text-align: right;">
<h2 style="margin:0; color: #555;">ORÇAMENTO</h2>
<p style="margin:5px 0 0 0;"><b>ORÇAMENTO N°:</b> 001</p>
<p style="margin:2px 0;"><b>EMITIDO EM:</b> {data_criacao}</p>
<p style="margin:2px 0;"><b>VÁLIDO ATÉ:</b> {data_validade}</p>
</div>
</div>
<div style="background-color: #f2f2f2; padding: 10px; margin-bottom: 20px; font-size: 12px; border-radius: 5px;">
<h4 style="margin: 0 0 10px 0; color: #333;">CLIENTE</h4>
<div style="display: flex; flex-wrap: wrap; gap: 10px;">
<div style="width: 48%;"><b>NOME:</b> {cliente}</div>
<div style="width: 48%;"><b>TELEFONE:</b> {telefone}</div>
<div style="width: 48%;"><b>CPF/CNPJ:</b> {cnpj}</div>
<div style="width: 48%;"><b>EMAIL:</b> </div>
<div style="width: 48%;"><b>ENDEREÇO:</b> {endereco}, {numero}</div>
<div style="width: 48%;"><b>BAIRRO:</b> {bairro}</div>
<div style="width: 48%;"><b>CIDADE:</b> {cidade}</div>
<div style="width: 48%;"><b>ESTADO:</b> {estado}</div>
</div>
</div>
<table style="width: 100%; border-collapse: collapse; font-size: 12px; text-align: center; margin-bottom: 10px;">
<tr style="background-color: #0088cc; color: white;">
<th style="padding: 8px; border: 1px solid #ccc;">ITEM</th>
<th style="padding: 8px; border: 1px solid #ccc; width: 50%;">PRODUTO/SERVIÇO</th>
<th style="padding: 8px; border: 1px solid #ccc;">QUANT</th>
<th style="padding: 8px; border: 1px solid #ccc;">VALOR</th>
</tr>
<tr>
<td style="padding: 8px; border: 1px solid #ccc;">1</td>
<td style="padding: 8px; border: 1px solid #ccc; text-align: left;">{servico}</td>
<td style="padding: 8px; border: 1px solid #ccc;">1</td>
<td style="padding: 8px; border: 1px solid #ccc;">{formata_moeda(valor_final)}</td>
</tr>
</table>
<div style="display: flex; justify-content: space-between; font-size: 12px; font-weight: bold; padding: 10px; border: 1px solid #ccc; margin-bottom: 20px;">
<span>SUBTOTAL: {formata_moeda(valor_final)}</span>
<span>DESCONTO: R$ 0,00</span>
<span>ACRÉSCIMO: R$ 0,00</span>
<span style="font-size: 14px; color: #0088cc;">TOTAL: {formata_moeda(valor_final)}</span>
</div>
<div style="font-size: 11px;">
<p style="margin: 2px 0;"><b>OBSERVAÇÕES</b></p>
<p style="margin: 2px 0;"><b>FORMAS DE PAGAMENTO:</b></p>
<p style="margin: 2px 0;">- A vista</p>
<p style="margin: 2px 0;">- Parcelamento no Cartão</p>
<p style="margin: 10px 0 0 0;">OBS: (12) MESES DE GARANTIA</p>
</div>
</div>
"""
        st.markdown(html_orcamento, unsafe_allow_html=True)
            
    else:
        st.warning("Por favor, preencha pelo menos Nome, Serviço, Valor e Endereço para gerar o documento.")
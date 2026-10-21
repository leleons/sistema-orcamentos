"""Descritivo comercial de produtos e serviços, inspirado no modelo do cliente."""
import io
from pathlib import Path
from html import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, Image
from dsystem_erp.services.faturamento import itens_faturamento_lista
from dsystem_erp.utils.datas import data_para_br
from dsystem_erp.utils.formatadores import formatar_moeda_br


def gerar_pdf_espelho_faturamento(faturamento: dict, cliente: dict | None = None) -> bytes:
    cliente = cliente or {}
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=18*mm, rightMargin=18*mm,
        topMargin=18*mm, bottomMargin=18*mm, title="Descritivo de serviços e produtos / Espelho de nota")
    normal = ParagraphStyle("normal", fontName="Helvetica", fontSize=8, leading=11)
    bold = ParagraphStyle("bold", parent=normal, fontName="Helvetica-Bold")
    def p(valor, forte=False):
        return Paragraph(escape(str(valor or "")).replace("\n", "<br/>"), bold if forte else normal)
    azul = colors.HexColor("#5B9BD5")
    claro = colors.HexColor("#DEEBF7")
    def tabela(linhas, larguras, header=False):
        t = Table(linhas, colWidths=[x*mm for x in larguras], repeatRows=1 if header else 0)
        regras = [("VALIGN", (0,0),(-1,-1),"TOP"), ("GRID", (0,0),(-1,-1), .35, azul),
                  ("LEFTPADDING",(0,0),(-1,-1),4), ("RIGHTPADDING",(0,0),(-1,-1),4),
                  ("TOPPADDING",(0,0),(-1,-1),5), ("BOTTOMPADDING",(0,0),(-1,-1),5)]
        if header:
            regras.append(("BACKGROUND",(0,0),(-1,0),claro))
        t.setStyle(TableStyle(regras))
        return t
    logo = Path(__file__).resolve().parents[2] / "logo_dsystem.png"
    marca = p("DSYSTEM TECNOLOGIA", True)
    if logo.exists():
        largura, altura = ImageReader(str(logo)).getSize()
        escala = min(38*mm/largura, 12*mm/altura)
        marca = Image(str(logo), width=largura*escala, height=altura*escala)
        marca.hAlign = "LEFT"
    elementos = [tabela([[marca, p(data_para_br(faturamento.get("data_lanc")), True)]],[134,40])]
    competencia = data_para_br(faturamento.get("medicao_inicio") or faturamento.get("data_lanc"))
    competencia = competencia[3:] if competencia else ""
    endereco = " ".join(str(cliente.get(k) or "") for k in ("endereco", "numero", "complemento", "bairro", "cidade_estado")).strip()
    elementos.append(tabela([
        [p("Faturar para",True), p(f"Competência {competencia}",True)],
        [p("Cliente"),p(faturamento.get("cliente"),True)],
        [p("ID do cliente / CPF-CNPJ"),p(f"{cliente.get('codigo_cliente') or cliente.get('id') or ''} / {faturamento.get('cnpj') or cliente.get('cnpj') or ''}")],
        [p("Endereço"),p(endereco)], [p("Telefone"),p(cliente.get("telefone"))],
        [p("Vencimento do pagamento"),p(data_para_br(faturamento.get("vencimento")))],
        [p("Condições de pagamento"),p(faturamento.get("forma_pag"))],
        [p("Referência"),p(f"Lançamento #{faturamento.get('id') or ''} - {faturamento.get('orc_ref') or ''}")],
    ],[44,130],True))
    linhas = [[p(x,True) for x in ("Qtd.","Nº item","Descrição","Preço unitário","Desconto","Total")]]
    for i, item in enumerate(itens_faturamento_lista(faturamento.get("itens")),1):
        linhas.append([p(item.get("qtd")), p(item.get("estoque_id") or i),
            p(f"{item.get('tipo_item') or ''}: {item.get('desc') or ''}"),
            p(formatar_moeda_br(item.get("vunit"))),p("-"),p(formatar_moeda_br(item.get("vtotal")))])
    elementos += [Spacer(1,3*mm),tabela(linhas,[12,16,71,27,20,28],True)]
    total = tabela([[p("Total Geral",True), p(formatar_moeda_br(faturamento.get("valor_total")),True)]],[146,28])
    total.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),claro)]))
    elementos.append(total)
    for titulo, texto in [("Histórico / informações da nota",faturamento.get("obs_nota")),
                          ("Histórico da medição",faturamento.get("medicao_historico")),
                          ("Observação interna",faturamento.get("obs_interna"))]:
        if texto:
            elementos += [Spacer(1,3*mm),p(titulo,True),p(texto)]
    if faturamento.get("modalidade_faturamento") == "Por medição":
        elementos += [Spacer(1,3*mm),p(f"Medição {faturamento.get('medicao_numero') or ''} - "
            f"{data_para_br(faturamento.get('medicao_inicio'))} a {data_para_br(faturamento.get('medicao_fim'))}"),
            p(faturamento.get("medicao_referencia"))]
    elementos += [Spacer(1,5*mm),p("Obrigado por fazer negócios conosco!",True),
                  p("Espelho de faturamento / descritivo comercial. Não substitui a nota fiscal.")]
    def rodape(canvas, doc):
        canvas.setFont("Helvetica",7)
        canvas.drawRightString(192*mm,10*mm,f"Página {doc.page}")
    doc.build(elementos,onFirstPage=rodape,onLaterPages=rodape)
    return buffer.getvalue()

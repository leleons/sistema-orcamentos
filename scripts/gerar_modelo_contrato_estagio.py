from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "modelos_contratos" / "CONTRATOS" / "Contrato_Estagio_DSystem_Auditoria_Premium.pdf"
LOGO = ROOT / "logo_dsystem.png"

W, H = A4
NAVY = colors.HexColor("#17324D")
BLUE = colors.HexColor("#1976A8")
GREEN = colors.HexColor("#77B82A")
INK = colors.HexColor("#263238")
MUTED = colors.HexColor("#667784")
LINE = colors.HexColor("#D8E1E6")
PALE = colors.HexColor("#F5F8FA")
WHITE = colors.white
LEFT = 20 * mm
RIGHT = W - 20 * mm


def text(c, value, x, y, size=9, bold=False, color=INK):
    c.setFillColor(color)
    c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
    c.drawString(x, y, value)


def header(c, page, title):
    c.setFillColor(NAVY)
    c.rect(0, H - 17 * mm, W, 17 * mm, fill=1, stroke=0)
    if LOGO.exists():
        c.drawImage(str(LOGO), LEFT, H - 14 * mm, width=34 * mm, height=12 * mm, preserveAspectRatio=True, mask="auto")
    text(c, title.upper(), RIGHT - 1, H - 10 * mm, 7.5, True, WHITE)
    c.setFillColor(GREEN)
    c.rect(LEFT, 13 * mm, 24 * mm, 1.2 * mm, fill=1, stroke=0)
    text(c, "D-System Tecnologia  |  Contrato de Estágio", LEFT, 8 * mm, 7, color=MUTED)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 7)
    c.drawRightString(RIGHT, 8 * mm, f"Página {page} de 6")


def title(c, value, subtitle, y=H - 38 * mm):
    text(c, value, LEFT, y, 17, True, NAVY)
    text(c, subtitle, LEFT, y - 7 * mm, 8.5, color=MUTED)


def field(c, name, label, x, y, width, height=8 * mm, value="", multiline=False):
    text(c, label.upper(), x, y + height + 2.5 * mm, 6.8, True, MUTED)
    flags = 4096 if multiline else 0
    c.acroForm.textfield(
        name=name,
        value=value,
        x=x,
        y=y,
        width=width,
        height=height,
        borderWidth=0.7,
        borderColor=LINE,
        fillColor=WHITE,
        textColor=INK,
        forceBorder=True,
        fontName="Helvetica",
        fontSize=9,
        fieldFlags=flags,
    )


def checkbox(c, name, label, x, y):
    c.acroForm.checkbox(
        name=name, x=x, y=y - 1.5 * mm, size=4.5 * mm,
        borderWidth=0.7, borderColor=LINE, fillColor=WHITE,
        buttonStyle="check", checked=False, forceBorder=True,
    )
    text(c, label, x + 7 * mm, y, 8.5)


def note(c, heading, body, y, height=24 * mm):
    c.setFillColor(PALE)
    c.setStrokeColor(LINE)
    c.roundRect(LEFT, y - height, RIGHT - LEFT, height, 2 * mm, fill=1, stroke=1)
    text(c, heading.upper(), LEFT + 5 * mm, y - 7 * mm, 7.5, True, BLUE)
    lines = body.split("\n")
    for index, line in enumerate(lines):
        text(c, line, LEFT + 5 * mm, y - 13 * mm - (index * 4.5 * mm), 8)


def table(c, headers, widths, rows, y, row_h=11 * mm):
    x = LEFT
    c.setFillColor(NAVY)
    c.rect(LEFT, y - row_h, sum(widths), row_h, fill=1, stroke=0)
    for header, width in zip(headers, widths):
        text(c, header, x + 2 * mm, y - 7 * mm, 7, True, WHITE)
        x += width
    y -= row_h
    for row in rows:
        x = LEFT
        c.setFillColor(WHITE if row % 2 else PALE)
        c.setStrokeColor(LINE)
        c.rect(LEFT, y - row_h, sum(widths), row_h, fill=1, stroke=1)
        for width in widths[:-1]:
            x += width
            c.line(x, y, x, y - row_h)
        y -= row_h
    return y


def cover(c):
    c.setFillColor(WHITE)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColor(NAVY)
    c.rect(0, H - 92 * mm, W, 92 * mm, fill=1, stroke=0)
    c.setFillColor(GREEN)
    c.rect(0, H - 92 * mm, 8 * mm, 92 * mm, fill=1, stroke=0)
    if LOGO.exists():
        c.drawImage(str(LOGO), LEFT, H - 42 * mm, width=72 * mm, height=30 * mm, preserveAspectRatio=True, mask="auto")
    text(c, "CONTRATO DE ESTÁGIO", LEFT, H - 62 * mm, 25, True, WHITE)
    text(c, "PROFISSIONALIZANTE", LEFT, H - 74 * mm, 25, True, WHITE)
    text(c, "Simples, preenchível e preparado para assinatura digital.", LEFT, H - 84 * mm, 9, color=colors.HexColor("#D5E2E9"))
    note(c, "Como usar", "1. Preencha os campos destacados.\n2. Marque as opções aplicáveis.\n3. Salve e encaminhe para assinatura.", H - 118 * mm, 34 * mm)
    field(c, "numero_contrato", "Número do contrato", LEFT, H - 174 * mm, 75 * mm)
    field(c, "data_emissao", "Data de emissão", LEFT + 85 * mm, H - 174 * mm, 75 * mm)
    text(c, "D-System Tecnologia  |  Documento controlado", LEFT, 16 * mm, 7, color=MUTED)
    c.showPage()


def identification(c):
    header(c, 2, "Identificação")
    title(c, "Identificação das partes", "Dados essenciais da concedente e do estagiário.")
    field(c, "razao_social", "Razão social da concedente", LEFT, H - 62 * mm, 105 * mm)
    field(c, "cnpj_concedente", "CNPJ", LEFT + 112 * mm, H - 62 * mm, 58 * mm)
    field(c, "endereco_concedente", "Endereço da concedente", LEFT, H - 82 * mm, 170 * mm)
    field(c, "supervisor", "Supervisor de estágio", LEFT, H - 102 * mm, 105 * mm)
    field(c, "cpf_supervisor", "CPF do supervisor", LEFT + 112 * mm, H - 102 * mm, 58 * mm)
    text(c, "DADOS DO ESTAGIÁRIO", LEFT, H - 126 * mm, 9, True, BLUE)
    field(c, "nome_estagiario", "Nome completo", LEFT, H - 143 * mm, 105 * mm)
    field(c, "cpf_estagiario", "CPF", LEFT + 112 * mm, H - 143 * mm, 58 * mm)
    field(c, "endereco_estagiario", "Endereço", LEFT, H - 163 * mm, 170 * mm)
    field(c, "telefone_estagiario", "Telefone", LEFT, H - 183 * mm, 50 * mm)
    field(c, "email_estagiario", "E-mail", LEFT + 57 * mm, H - 183 * mm, 113 * mm)
    field(c, "instituicao_ensino", "Instituição de ensino", LEFT, H - 203 * mm, 105 * mm)
    field(c, "curso", "Curso", LEFT + 112 * mm, H - 203 * mm, 58 * mm)
    text(c, "JORNADA", LEFT, H - 226 * mm, 7, True, MUTED)
    checkbox(c, "jornada_20", "20 horas semanais (4h/dia)", LEFT, H - 237 * mm)
    checkbox(c, "jornada_30", "30 horas semanais (6h/dia)", LEFT + 82 * mm, H - 237 * mm)
    c.showPage()


def activities(c):
    header(c, 3, "Plano de atividades")
    title(c, "Plano de atividades", "Objetivos claros e acompanhamento simples.")
    cards = [
        ("1º trimestre", "Integração, suporte básico, ativos e documentação."),
        ("2º trimestre", "Redes, cabeamento, switches, Wi-Fi e infraestrutura."),
        ("3º trimestre", "CFTV, alarmes, monitoramento e testes operacionais."),
        ("4º trimestre", "Projetos supervisionados e atendimento avançado."),
    ]
    y = H - 65 * mm
    for index, (period, body) in enumerate(cards):
        c.setFillColor(PALE)
        c.setStrokeColor(LINE)
        c.roundRect(LEFT, y - 27 * mm, 170 * mm, 23 * mm, 2 * mm, fill=1, stroke=1)
        c.setFillColor(BLUE if index % 2 == 0 else GREEN)
        c.rect(LEFT, y - 27 * mm, 4 * mm, 23 * mm, fill=1, stroke=0)
        text(c, period, LEFT + 8 * mm, y - 12 * mm, 9, True, NAVY)
        text(c, body, LEFT + 42 * mm, y - 12 * mm, 8)
        y -= 31 * mm
    field(c, "atividades_complementares", "Atividades complementares / projetos", LEFT, H - 222 * mm, 170 * mm, 28 * mm, multiline=True)
    c.showPage()


def policies(c):
    header(c, 4, "Confidencialidade e segurança")
    title(c, "Confidencialidade e segurança", "Regras essenciais para proteção dos dados e recursos.")
    note(c, "Compromisso", "O estagiário manterá sigilo sobre dados, credenciais, documentos, contratos,\nprojetos e informações obtidas durante e após o estágio.", H - 62 * mm, 26 * mm)
    items = [
        ("ciencia_lgpd", "Tratarei dados pessoais somente para finalidades profissionais."),
        ("ciencia_senhas", "Não compartilharei senhas ou credenciais."),
        ("ciencia_softwares", "Não instalarei softwares sem autorização."),
        ("ciencia_bloqueio", "Bloquearei a sessão ao me ausentar."),
        ("ciencia_incidentes", "Comunicarei imediatamente incidentes ou suspeitas."),
        ("ciencia_equipamentos", "Utilizarei equipamentos e recursos com responsabilidade."),
    ]
    y = H - 105 * mm
    for name, label in items:
        checkbox(c, name, label, LEFT, y)
        y -= 15 * mm
    field(c, "observacoes_politicas", "Observações", LEFT, H - 225 * mm, 170 * mm, 28 * mm, multiline=True)
    c.showPage()


def controls(c):
    header(c, 5, "Controles")
    title(c, "Controles de acompanhamento", "Registros rápidos para o dia a dia.")
    text(c, "ENTREGA DE EQUIPAMENTOS E FERRAMENTAS", LEFT, H - 60 * mm, 8, True, BLUE)
    y = table(c, ["Data", "Item", "Patrimônio", "Assinatura"], [26 * mm, 70 * mm, 35 * mm, 39 * mm], range(4), H - 66 * mm)
    text(c, "FREQUÊNCIA", LEFT, y - 12 * mm, 8, True, BLUE)
    y = table(c, ["Data", "Entrada", "Saída", "Horas", "Rubrica"], [34 * mm] * 5, range(5), y - 18 * mm)
    field(c, "observacoes_controles", "Observações", LEFT, y - 28 * mm, 170 * mm, 22 * mm, multiline=True)
    c.showPage()


def signatures(c):
    header(c, 6, "Avaliação e assinaturas")
    title(c, "Avaliação e assinaturas", "Registro final para validação das partes.")
    text(c, "AVALIAÇÃO RESUMIDA", LEFT, H - 60 * mm, 8, True, BLUE)
    table(c, ["Critério", "Nota 1–5", "Observações"], [55 * mm, 28 * mm, 87 * mm], range(5), H - 66 * mm)
    field(c, "avaliacao_observacoes", "Síntese da avaliação", LEFT, H - 152 * mm, 170 * mm, 22 * mm, multiline=True)
    text(c, "ASSINATURAS", LEFT, H - 188 * mm, 8, True, BLUE)
    field(c, "assinatura_empresa", "Empresa / representante legal", LEFT, H - 207 * mm, 80 * mm)
    field(c, "assinatura_estagiario", "Estagiário(a)", LEFT + 90 * mm, H - 207 * mm, 80 * mm)
    field(c, "assinatura_instituicao", "Instituição de ensino", LEFT, H - 230 * mm, 80 * mm)
    field(c, "assinatura_supervisor", "Supervisor de estágio", LEFT + 90 * mm, H - 230 * mm, 80 * mm)
    field(c, "data_assinatura", "Data", LEFT, H - 253 * mm, 50 * mm)
    c.showPage()


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(OUTPUT), pagesize=A4)
    c.setTitle("Contrato de Estágio Profissionalizante - D-System Tecnologia")
    c.setAuthor("D-System Tecnologia")
    cover(c)
    identification(c)
    activities(c)
    policies(c)
    controls(c)
    signatures(c)
    c.save()
    print(OUTPUT)


if __name__ == "__main__":
    main()

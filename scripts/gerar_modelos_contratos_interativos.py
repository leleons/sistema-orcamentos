from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "modelos_contratos" / "CONTRATOS"
LOGO = ROOT / "logo_dsystem.png"
W, H = A4
LEFT, RIGHT = 20 * mm, W - 20 * mm
NAVY, BLUE, GREEN = colors.HexColor("#17324D"), colors.HexColor("#1976A8"), colors.HexColor("#77B82A")
INK, MUTED, LINE, PALE, WHITE = colors.HexColor("#263238"), colors.HexColor("#667784"), colors.HexColor("#D8E1E6"), colors.HexColor("#F5F8FA"), colors.white


def txt(c, value, x, y, size=9, bold=False, color=INK):
    c.setFillColor(color)
    c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
    c.drawString(x, y, value)


def header(c, page, pages, title):
    c.setFillColor(NAVY); c.rect(0, H - 17 * mm, W, 17 * mm, fill=1, stroke=0)
    if LOGO.exists():
        c.drawImage(str(LOGO), LEFT, H - 14 * mm, width=34 * mm, height=12 * mm, preserveAspectRatio=True, mask="auto")
    c.setFillColor(WHITE); c.setFont("Helvetica-Bold", 7.5); c.drawRightString(RIGHT, H - 10 * mm, title.upper())
    c.setFillColor(GREEN); c.rect(LEFT, 13 * mm, 24 * mm, 1.2 * mm, fill=1, stroke=0)
    txt(c, "D-System Tecnologia  |  Documento preenchível", LEFT, 8 * mm, 7, color=MUTED)
    c.setFillColor(MUTED); c.setFont("Helvetica", 7); c.drawRightString(RIGHT, 8 * mm, f"Página {page} de {pages}")


def title(c, value, subtitle):
    txt(c, value, LEFT, H - 38 * mm, 17, True, NAVY)
    txt(c, subtitle, LEFT, H - 45 * mm, 8.5, color=MUTED)


def field(c, name, label, x, y, width, height=8 * mm, value="", multiline=False):
    txt(c, label.upper(), x, y + height + 2.5 * mm, 6.8, True, MUTED)
    c.acroForm.textfield(
        name=name, value=value, x=x, y=y, width=width, height=height,
        borderWidth=0.7, borderColor=LINE, fillColor=WHITE, textColor=INK,
        forceBorder=True, fontName="Helvetica", fontSize=9, fieldFlags=4096 if multiline else 0,
    )


def check(c, name, label, x, y):
    c.acroForm.checkbox(name=name, x=x, y=y - 1.5 * mm, size=4.5 * mm, borderWidth=0.7, borderColor=LINE, fillColor=WHITE, buttonStyle="check", forceBorder=True)
    txt(c, label, x + 7 * mm, y, 8.5)


def note(c, heading, lines, y, height=27 * mm):
    c.setFillColor(PALE); c.setStrokeColor(LINE); c.roundRect(LEFT, y - height, RIGHT - LEFT, height, 2 * mm, fill=1, stroke=1)
    txt(c, heading.upper(), LEFT + 5 * mm, y - 7 * mm, 7.5, True, BLUE)
    for i, line in enumerate(lines):
        txt(c, line, LEFT + 5 * mm, y - 13 * mm - (i * 4.5 * mm), 8)


def grid(c, headers, widths, rows, y, row_h=11 * mm):
    c.setFillColor(NAVY); c.rect(LEFT, y - row_h, sum(widths), row_h, fill=1, stroke=0)
    x = LEFT
    for label, width in zip(headers, widths):
        txt(c, label, x + 2 * mm, y - 7 * mm, 7, True, WHITE); x += width
    y -= row_h
    for row in range(rows):
        c.setFillColor(WHITE if row % 2 else PALE); c.setStrokeColor(LINE); c.rect(LEFT, y - row_h, sum(widths), row_h, fill=1, stroke=1)
        x = LEFT
        for width in widths[:-1]:
            x += width; c.line(x, y, x, y - row_h)
        y -= row_h
    return y


def cover(c, title1, title2, subtitle, pages):
    c.setFillColor(WHITE); c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColor(NAVY); c.rect(0, H - 92 * mm, W, 92 * mm, fill=1, stroke=0)
    c.setFillColor(GREEN); c.rect(0, H - 92 * mm, 8 * mm, 92 * mm, fill=1, stroke=0)
    if LOGO.exists():
        c.drawImage(str(LOGO), LEFT, H - 42 * mm, width=72 * mm, height=30 * mm, preserveAspectRatio=True, mask="auto")
    txt(c, title1, LEFT, H - 62 * mm, 24, True, WHITE); txt(c, title2, LEFT, H - 74 * mm, 24, True, WHITE)
    txt(c, subtitle, LEFT, H - 84 * mm, 9, color=colors.HexColor("#D5E2E9"))
    note(c, "Como usar", ["1. Confira os dados preenchidos automaticamente.", "2. Complete os campos e marque as opções aplicáveis.", "3. Salve e encaminhe para assinatura."], H - 118 * mm, 34 * mm)
    field(c, "numero_contrato", "Número do contrato", LEFT, H - 174 * mm, 75 * mm)
    field(c, "data_emissao", "Data de emissão", LEFT + 85 * mm, H - 174 * mm, 75 * mm)
    txt(c, f"D-System Tecnologia  |  Documento controlado  |  {pages} páginas", LEFT, 16 * mm, 7, color=MUTED)
    c.showPage()


def gerar_clt():
    out = DIR / "Contrato_Corporativo_CLT_DSystem.pdf"
    c = canvas.Canvas(str(out), pagesize=A4); c.setTitle("Contrato Corporativo de Trabalho CLT")
    cover(c, "CONTRATO CORPORATIVO", "DE TRABALHO (CLT)", "Modelo simples, preenchível e preparado para assinatura digital.", 6)

    header(c, 2, 6, "Identificação"); title(c, "Identificação das partes", "Dados essenciais da empresa e do colaborador.")
    field(c, "razao_social", "Razão social", LEFT, H - 62 * mm, 105 * mm); field(c, "cnpj_empresa", "CNPJ", LEFT + 112 * mm, H - 62 * mm, 58 * mm)
    field(c, "endereco_empresa", "Endereço da empresa", LEFT, H - 82 * mm, 170 * mm)
    field(c, "representante_legal", "Representante legal", LEFT, H - 102 * mm, 105 * mm); field(c, "cpf_representante", "CPF do representante", LEFT + 112 * mm, H - 102 * mm, 58 * mm)
    txt(c, "DADOS DO COLABORADOR", LEFT, H - 126 * mm, 9, True, BLUE)
    field(c, "nome_colaborador", "Nome completo", LEFT, H - 143 * mm, 105 * mm); field(c, "cpf_colaborador", "CPF", LEFT + 112 * mm, H - 143 * mm, 58 * mm)
    field(c, "rg_colaborador", "RG", LEFT, H - 163 * mm, 50 * mm); field(c, "cargo_colaborador", "Cargo / função", LEFT + 57 * mm, H - 163 * mm, 113 * mm)
    field(c, "endereco_colaborador", "Endereço", LEFT, H - 183 * mm, 170 * mm)
    field(c, "telefone_colaborador", "Telefone", LEFT, H - 203 * mm, 50 * mm); field(c, "email_colaborador", "E-mail", LEFT + 57 * mm, H - 203 * mm, 113 * mm)
    field(c, "salario_colaborador", "Salário", LEFT, H - 223 * mm, 50 * mm); field(c, "jornada_colaborador", "Jornada", LEFT + 57 * mm, H - 223 * mm, 113 * mm)
    c.showPage()

    header(c, 3, 6, "Condições do trabalho"); title(c, "Condições do trabalho", "Escopo, jornada e responsabilidades principais.")
    note(c, "Atividades", ["Suporte de TI, redes, servidores, cabeamento, CFTV, alarmes, controle de acesso,", "manutenção preventiva e corretiva, atendimento remoto e presencial e documentação técnica."], H - 62 * mm, 27 * mm)
    field(c, "atividades_especificas", "Atividades específicas / observações", LEFT, H - 118 * mm, 170 * mm, 35 * mm, multiline=True)
    txt(c, "CONDIÇÕES APLICÁVEIS", LEFT, H - 140 * mm, 8, True, BLUE)
    check(c, "periodo_experiencia", "Período de experiência aplicável", LEFT, H - 154 * mm)
    check(c, "vale_transporte", "Vale-transporte autorizado", LEFT, H - 170 * mm)
    check(c, "uso_veiculo", "Uso de veículo corporativo autorizado", LEFT, H - 186 * mm)
    check(c, "trabalho_externo", "Atividades externas / em clientes", LEFT, H - 202 * mm)
    field(c, "beneficios", "Benefícios e condições complementares", LEFT, H - 238 * mm, 170 * mm, 25 * mm, multiline=True)
    c.showPage()

    header(c, 4, 6, "Confidencialidade e segurança"); title(c, "Confidencialidade e segurança", "Regras essenciais para proteção das informações e recursos.")
    note(c, "Compromisso", ["O colaborador manterá sigilo sobre informações técnicas, comerciais, financeiras,", "credenciais, projetos, clientes e documentos durante e após o vínculo."], H - 62 * mm, 27 * mm)
    for i, (name, label) in enumerate([
        ("ciencia_lgpd", "Tratarei dados pessoais conforme a LGPD e orientações internas."),
        ("ciencia_senhas", "Não compartilharei senhas ou credenciais."),
        ("ciencia_softwares", "Não instalarei softwares sem autorização."),
        ("ciencia_incidentes", "Comunicarei imediatamente incidentes ou suspeitas."),
        ("ciencia_equipamentos", "Utilizarei equipamentos e recursos com responsabilidade."),
    ]): check(c, name, label, LEFT, H - (110 + i * 17) * mm)
    field(c, "observacoes_seguranca", "Observações", LEFT, H - 225 * mm, 170 * mm, 28 * mm, multiline=True)
    c.showPage()

    header(c, 5, 6, "Controles"); title(c, "Controles de entrega e treinamento", "Registros rápidos para admissão e acompanhamento.")
    txt(c, "EQUIPAMENTOS, EPIs E FERRAMENTAS", LEFT, H - 60 * mm, 8, True, BLUE)
    y = grid(c, ["Data", "Item", "Patrimônio", "Assinatura"], [26 * mm, 70 * mm, 35 * mm, 39 * mm], 5, H - 66 * mm)
    txt(c, "TREINAMENTOS", LEFT, y - 12 * mm, 8, True, BLUE)
    grid(c, ["Data", "Treinamento", "Responsável", "Assinatura"], [26 * mm, 70 * mm, 38 * mm, 36 * mm], 5, y - 18 * mm)
    c.showPage()

    header(c, 6, 6, "Assinaturas"); title(c, "Assinaturas e validação", "Formalização e ciência das partes.")
    note(c, "Declaração", ["As partes declaram ciência e concordância com as condições, responsabilidades", "e políticas apresentadas neste instrumento."], H - 62 * mm, 27 * mm)
    field(c, "assinatura_empresa", "Empresa / representante legal", LEFT, H - 118 * mm, 80 * mm)
    field(c, "assinatura_colaborador", "Colaborador", LEFT + 90 * mm, H - 118 * mm, 80 * mm)
    field(c, "assinatura_testemunha_1", "Testemunha 1", LEFT, H - 145 * mm, 80 * mm)
    field(c, "assinatura_testemunha_2", "Testemunha 2", LEFT + 90 * mm, H - 145 * mm, 80 * mm)
    field(c, "data_assinatura", "Data", LEFT, H - 172 * mm, 50 * mm)
    c.save(); return out


def gerar_suporte():
    out = DIR / "Contrato_Suporte_Tecnologico_DSystem.pdf"
    c = canvas.Canvas(str(out), pagesize=A4); c.setTitle("Contrato de Suporte Tecnológico")
    cover(c, "CONTRATO DE SUPORTE", "TECNOLÓGICO", "Modelo simples, preenchível e preparado para assinatura digital.", 5)

    header(c, 2, 5, "Identificação"); title(c, "Identificação das partes", "Dados da contratante e da D-System Tecnologia.")
    field(c, "nome_contratante", "Contratante / empresa", LEFT, H - 62 * mm, 105 * mm); field(c, "cnpj_contratante", "CPF / CNPJ", LEFT + 112 * mm, H - 62 * mm, 58 * mm)
    field(c, "endereco_contratante", "Endereço da contratante", LEFT, H - 82 * mm, 170 * mm)
    field(c, "responsavel_contratante", "Responsável legal", LEFT, H - 102 * mm, 105 * mm); field(c, "cpf_responsavel", "CPF do responsável", LEFT + 112 * mm, H - 102 * mm, 58 * mm)
    field(c, "telefone_contratante", "Telefone", LEFT, H - 122 * mm, 50 * mm); field(c, "email_contratante", "E-mail", LEFT + 57 * mm, H - 122 * mm, 113 * mm)
    note(c, "Contratada", ["D F Pereira Informática - ME (D-System Tecnologia)", "CNPJ 23.524.449/0001-54  |  Belo Horizonte / MG"], H - 152 * mm, 25 * mm)
    field(c, "data_inicio", "Data de início", LEFT, H - 205 * mm, 50 * mm); field(c, "vigencia", "Vigência", LEFT + 57 * mm, H - 205 * mm, 50 * mm); field(c, "dia_vencimento", "Dia do vencimento", LEFT + 114 * mm, H - 205 * mm, 56 * mm)
    c.showPage()

    header(c, 3, 5, "Objeto e atendimento"); title(c, "Objeto e atendimento", "Escopo do suporte contratado.")
    note(c, "Objeto", ["Manutenção, suporte e reparo de estações, servidores, notebooks, redes,", "periféricos e softwares necessários ao funcionamento dos equipamentos."], H - 62 * mm, 27 * mm)
    txt(c, "MODALIDADES INCLUÍDAS", LEFT, H - 105 * mm, 8, True, BLUE)
    check(c, "atendimento_remoto", "Atendimento remoto", LEFT, H - 119 * mm); check(c, "atendimento_presencial", "Atendimento presencial", LEFT + 75 * mm, H - 119 * mm)
    check(c, "manutencao_preventiva", "Manutenção preventiva", LEFT, H - 136 * mm); check(c, "manutencao_corretiva", "Manutenção corretiva", LEFT + 75 * mm, H - 136 * mm)
    check(c, "backup", "Backup e recuperação", LEFT, H - 153 * mm); check(c, "antivirus", "Antivírus", LEFT + 75 * mm, H - 153 * mm)
    field(c, "escopo_especifico", "Escopo específico e equipamentos atendidos", LEFT, H - 210 * mm, 170 * mm, 35 * mm, multiline=True)
    c.showPage()

    header(c, 4, 5, "Pagamento e condições"); title(c, "Pagamento e condições", "Valores, vencimento e responsabilidades.")
    field(c, "valor_mensal", "Valor mensal", LEFT, H - 62 * mm, 50 * mm); field(c, "forma_pagamento", "Forma de pagamento", LEFT + 57 * mm, H - 62 * mm, 55 * mm); field(c, "reajuste", "Índice de reajuste", LEFT + 119 * mm, H - 62 * mm, 51 * mm)
    note(c, "Peças e serviços externos", ["Peças, licenças e serviços de terceiros não estão incluídos, salvo quando expressamente", "indicados. Qualquer custo adicional deverá ser previamente aprovado pela contratante."], H - 95 * mm, 29 * mm)
    note(c, "Responsabilidades", ["A contratada não se responsabiliza por mau uso, intervenções de terceiros ou peças", "adquiridas diretamente pela contratante sem validação técnica."], H - 139 * mm, 29 * mm)
    field(c, "condicoes_adicionais", "Condições adicionais", LEFT, H - 218 * mm, 170 * mm, 38 * mm, multiline=True)
    c.showPage()

    header(c, 5, 5, "Rescisão e assinaturas"); title(c, "Rescisão e assinaturas", "Formalização do contrato de suporte.")
    note(c, "Rescisão", ["A rescisão deverá observar as obrigações pendentes e as condições acordadas entre as partes.", "O foro eleito será o da comarca de Belo Horizonte / MG."], H - 62 * mm, 29 * mm)
    field(c, "assinatura_contratante", "Contratante / responsável legal", LEFT, H - 125 * mm, 80 * mm)
    field(c, "assinatura_contratada", "D-System Tecnologia", LEFT + 90 * mm, H - 125 * mm, 80 * mm)
    field(c, "assinatura_testemunha_1", "Testemunha 1", LEFT, H - 152 * mm, 80 * mm)
    field(c, "assinatura_testemunha_2", "Testemunha 2", LEFT + 90 * mm, H - 152 * mm, 80 * mm)
    field(c, "data_assinatura", "Data", LEFT, H - 179 * mm, 50 * mm)
    c.save(); return out


if __name__ == "__main__":
    DIR.mkdir(parents=True, exist_ok=True)
    print(gerar_clt())
    print(gerar_suporte())

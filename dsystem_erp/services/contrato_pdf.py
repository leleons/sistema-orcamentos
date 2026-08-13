from __future__ import annotations

import io
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

MODELOS_CONTRATO = {
    "Suporte Tecnológico": "Contrato_Suporte_Tecnologico_DSystem.pdf",
    "Corporativo CLT": "Contrato_Corporativo_CLT_DSystem.pdf",
    "Estágio": "Contrato_Estagio_DSystem_Auditoria_Premium.pdf",
}

def caminho_modelo_contrato(tipo_contrato):
    nome_arquivo = MODELOS_CONTRATO.get(tipo_contrato)
    if not nome_arquivo:
        raise ValueError("Tipo de contrato inválido.")
    return PROJECT_ROOT / "modelos_contratos" / "CONTRATOS" / nome_arquivo

def _texto_pdf(canvas_pdf, texto, x, y, largura, tamanho=9, entrelinha=None, negrito=False, max_linhas=5):
    entrelinha = entrelinha or (tamanho + 2)
    try:
        from reportlab.pdfbase import pdfmetrics
        fonte_personalizada = "ContratoSans-Bold" if negrito else "ContratoSans"
        fonte = fonte_personalizada if fonte_personalizada in pdfmetrics.getRegisteredFontNames() else ("Helvetica-Bold" if negrito else "Helvetica")
    except Exception:
        fonte = "Helvetica-Bold" if negrito else "Helvetica"
    palavras = str(texto or "").split()
    linhas, atual = [], ""
    for palavra in palavras:
        tentativa = f"{atual} {palavra}".strip()
        if canvas_pdf.stringWidth(tentativa, fonte, tamanho) <= largura:
            atual = tentativa
        else:
            if atual:
                linhas.append(atual)
            atual = palavra
    if atual:
        linhas.append(atual)
    canvas_pdf.setFont(fonte, tamanho)
    for indice, linha in enumerate(linhas[:max_linhas]):
        canvas_pdf.drawString(x, y - (indice * entrelinha), linha)

def _caixa_pdf(canvas_pdf, x, y, largura, altura):
    canvas_pdf.setFillColorRGB(1, 1, 1)
    canvas_pdf.setStrokeColorRGB(1, 1, 1)
    canvas_pdf.rect(x, y, largura, altura, fill=1, stroke=0)
    canvas_pdf.setFillColorRGB(0, 0, 0)

def anexar_clausulas_pdf(pdf_original, clausulas, tipo_contrato=""):
    clausulas_validas = [
        {"titulo": str(item.get("titulo") or "").strip(), "texto": str(item.get("texto") or "").strip()}
        for item in (clausulas or [])
        if str(item.get("titulo") or "").strip() and str(item.get("texto") or "").strip()
    ]
    if not clausulas_validas:
        return pdf_original
    try:
        import reportlab
        from pypdf import PdfReader, PdfWriter
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfgen import canvas
    except ImportError as ex:
        raise RuntimeError("Instale as dependências pypdf e reportlab para adicionar cláusulas.") from ex

    fonte_normal, fonte_negrito = "Helvetica", "Helvetica-Bold"
    try:
        pasta_fontes = Path(reportlab.__file__).resolve().parent / "fonts"
        if "ClausulaSans" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("ClausulaSans", str(pasta_fontes / "Vera.ttf")))
        if "ClausulaSans-Bold" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("ClausulaSans-Bold", str(pasta_fontes / "VeraBd.ttf")))
        fonte_normal, fonte_negrito = "ClausulaSans", "ClausulaSans-Bold"
    except Exception:
        pass

    def quebrar_linhas(pdf, texto, largura, fonte=fonte_normal, tamanho=9):
        linhas = []
        for paragrafo in str(texto).splitlines() or [""]:
            palavras = paragrafo.split()
            atual = ""
            for palavra in palavras:
                tentativa = f"{atual} {palavra}".strip()
                if pdf.stringWidth(tentativa, fonte, tamanho) <= largura:
                    atual = tentativa
                else:
                    if atual:
                        linhas.append(atual)
                    atual = palavra
            linhas.append(atual)
        return linhas or [""]

    camada = io.BytesIO()
    pdf = canvas.Canvas(camada, pagesize=A4)
    largura, altura = A4
    margem = 52
    y = altura - 72
    numero_pagina = 1

    def cabecalho():
        nonlocal y
        pdf.setFillColorRGB(0.09, 0.20, 0.30)
        pdf.rect(0, altura - 48, largura, 48, fill=1, stroke=0)
        pdf.setFillColorRGB(1, 1, 1)
        pdf.setFont(fonte_negrito, 11)
        pdf.drawString(margem, altura - 30, "CLÁUSULAS ADICIONAIS")
        pdf.setFont(fonte_normal, 8)
        pdf.drawRightString(largura - margem, altura - 30, tipo_contrato)
        pdf.setFillColorRGB(0.35, 0.42, 0.46)
        pdf.drawRightString(largura - margem, 28, f"Página adicional {numero_pagina}")
        pdf.setFillColorRGB(0, 0, 0)
        y = altura - 76

    cabecalho()
    for indice, item in enumerate(clausulas_validas, start=1):
        linhas = quebrar_linhas(pdf, item["texto"], largura - (2 * margem), tamanho=9)
        altura_bloco = 30 + (len(linhas) * 13)
        if y - altura_bloco < 55:
            pdf.showPage()
            numero_pagina += 1
            cabecalho()
        pdf.setFont(fonte_negrito, 10)
        pdf.setFillColorRGB(0.10, 0.46, 0.66)
        pdf.drawString(margem, y, f"Cláusula adicional {indice}ª - {item['titulo']}")
        y -= 18
        pdf.setFont(fonte_normal, 9)
        pdf.setFillColorRGB(0.12, 0.15, 0.17)
        for linha in linhas:
            pdf.drawString(margem, y, linha)
            y -= 13
        y -= 14
    pdf.save()
    camada.seek(0)

    leitor_original = PdfReader(io.BytesIO(pdf_original))
    leitor_clausulas = PdfReader(camada)
    escritor = PdfWriter()
    escritor.clone_document_from_reader(leitor_original)
    for pagina in leitor_clausulas.pages:
        escritor.add_page(pagina)
    saida = io.BytesIO()
    escritor.write(saida)
    return saida.getvalue()

def gerar_contrato_pdf(tipo_contrato, dados):
    try:
        import reportlab
        from pypdf import PdfReader, PdfWriter
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfgen import canvas
    except ImportError as ex:
        raise RuntimeError("Instale as dependências pypdf e reportlab para gerar contratos.") from ex

    pasta_fontes = Path(reportlab.__file__).resolve().parent / "fonts"
    try:
        if "ContratoSans" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("ContratoSans", str(pasta_fontes / "Vera.ttf")))
        if "ContratoSans-Bold" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("ContratoSans-Bold", str(pasta_fontes / "VeraBd.ttf")))
    except Exception:
        pass

    caminho_modelo = caminho_modelo_contrato(tipo_contrato)
    if not caminho_modelo.exists():
        raise FileNotFoundError(f"Modelo não encontrado: {caminho_modelo.name}")

    leitor = PdfReader(str(caminho_modelo))
    escritor = PdfWriter()
    if tipo_contrato in {"Estágio", "Corporativo CLT", "Suporte Tecnológico"} and leitor.get_fields():
        escritor.clone_document_from_reader(leitor)
        endereco_formulario = ", ".join(
            parte for parte in [dados.get("endereco"), dados.get("numero"), dados.get("complemento"),
                                dados.get("bairro"), dados.get("cidade_estado"), dados.get("cep")]
            if str(parte or "").strip()
        )
        if tipo_contrato == "Estágio":
            campos_formulario = {
                "nome_estagiario": dados.get("nome") or "", "cpf_estagiario": dados.get("cnpj") or "",
                "endereco_estagiario": endereco_formulario, "telefone_estagiario": dados.get("telefone") or "",
                "email_estagiario": dados.get("email") or "", "instituicao_ensino": dados.get("instituicao_ensino") or "",
                "curso": dados.get("curso") or "", "jornada_20": "/Yes" if str(dados.get("jornada") or "").startswith("20") else "/Off",
                "jornada_30": "/Yes" if str(dados.get("jornada") or "").startswith("30") else "/Off",
                "data_emissao": dados.get("data_contrato") or "",
            }
        elif tipo_contrato == "Corporativo CLT":
            campos_formulario = {
                "nome_colaborador": dados.get("nome") or "", "cpf_colaborador": dados.get("cnpj") or "",
                "rg_colaborador": dados.get("rg_mei") or "", "cargo_colaborador": dados.get("cargo") or "",
                "endereco_colaborador": endereco_formulario, "telefone_colaborador": dados.get("telefone") or "",
                "email_colaborador": dados.get("email") or "", "salario_colaborador": dados.get("valor_contrato") or "",
                "data_emissao": dados.get("data_contrato") or "",
            }
        else:
            campos_formulario = {
                "nome_contratante": dados.get("nome") or "", "cnpj_contratante": dados.get("cnpj") or "",
                "endereco_contratante": endereco_formulario, "responsavel_contratante": dados.get("responsavel_legal") or "",
                "cpf_responsavel": dados.get("cpf_responsavel") or "", "telefone_contratante": dados.get("telefone") or "",
                "email_contratante": dados.get("email") or "", "data_inicio": dados.get("data_contrato") or "",
                "dia_vencimento": dados.get("dia_vencimento") or "", "valor_mensal": dados.get("valor_contrato") or "",
                "forma_pagamento": dados.get("forma_pagamento") or "", "data_emissao": dados.get("data_contrato") or "",
            }
        for pagina in escritor.pages:
            escritor.update_page_form_field_values(pagina, campos_formulario, auto_regenerate=False)
        saida = io.BytesIO()
        escritor.write(saida)
        return anexar_clausulas_pdf(saida.getvalue(), dados.get("clausulas"), tipo_contrato)

    endereco_completo = ", ".join(
        parte for parte in [
            dados.get("endereco"), dados.get("numero"), dados.get("complemento"),
            dados.get("bairro"), dados.get("cidade_estado"), f"CEP {dados.get('cep')}" if dados.get("cep") else "",
        ] if str(parte or "").strip()
    )

    for indice_pagina, pagina in enumerate(leitor.pages):
        largura = float(pagina.mediabox.width)
        altura = float(pagina.mediabox.height)
        camada = io.BytesIO()
        pdf = canvas.Canvas(camada, pagesize=(largura, altura))

        if tipo_contrato == "Suporte Tecnológico":
            if indice_pagina == 0:
                _caixa_pdf(pdf, 35, altura - 165, largura - 70, 120)
                _texto_pdf(pdf, f"Contrato de Manutenção das estações de trabalho entre {dados.get('nome')} e D-System Tecnologia - ME", 42, altura - 75, largura - 84, 12, 15, True, 3)
                _caixa_pdf(pdf, 35, 350, largura - 70, 340)
                _texto_pdf(pdf, "CONTRATANTE:", 42, altura - 188, largura - 84, 10, negrito=True)
                qualificacao = f"{dados.get('nome')}, com sede em {endereco_completo}, inscrita no CPF/CNPJ sob o nº {dados.get('cnpj')}."
                _texto_pdf(pdf, qualificacao, 42, altura - 210, largura - 84, 10, 13, False, 5)
                _texto_pdf(pdf, "CONTRATADA:", 42, altura - 285, largura - 84, 10, negrito=True)
                _texto_pdf(pdf, "D F PEREIRA INFORMÁTICA - ME (D-System Tecnologia), com sede em Sabará, na Rua Glória, nº 25, CEP 34.700-150, no Estado MG, inscrita no CNPJ sob o nº 23.524.449/0001-54.", 42, altura - 307, largura - 84, 10, 13, False, 6)
                _texto_pdf(pdf, "As partes acima identificadas têm, entre si, justo e acertado o presente Contrato de manutenção de computadores, redes periféricas adjuntas e softwares próprios necessários ao funcionamento dos computadores, que se regerá pelas cláusulas seguintes e pelas condições descritas no presente contrato e proposta comercial anexa.", 42, 445, largura - 84, 10, 13, False, 6)
                _texto_pdf(pdf, "DO OBJETO DO CONTRATO", 42, 370, largura - 84, 11, negrito=True)
            elif indice_pagina == 2:
                _caixa_pdf(pdf, 35, 440, largura - 70, 260)
                _texto_pdf(pdf, "DO PAGAMENTO", 42, altura - 165, largura - 84, 11, negrito=True)
                pagamento = (
                    f"Cláusula 8ª. Pelo serviço prestado, a CONTRATANTE pagará à CONTRATADA "
                    f"a quantia mensal de {dados.get('valor_contrato')}, com vencimento todo dia "
                    f"{dados.get('dia_vencimento')} de cada mês, por meio de {dados.get('forma_pagamento')}."
                )
                _texto_pdf(pdf, pagamento, 42, altura - 195, largura - 84, 10, 14, False, 6)
            elif indice_pagina == 3:
                _caixa_pdf(pdf, 90, 685, 260, 30)
                _caixa_pdf(pdf, 35, 525, largura - 70, 175)
                _texto_pdf(pdf, f"Belo Horizonte, {dados.get('data_contrato')}.", 42, altura - 165, largura - 84, 10)
                _texto_pdf(pdf, dados.get("nome"), 42, altura - 225, largura - 84, 10, negrito=True)
                _texto_pdf(pdf, "(Assinatura certificado gov.br)", 42, altura - 244, largura - 84, 9)
                _texto_pdf(pdf, f"{dados.get('responsavel_legal')} - CPF {dados.get('cpf_responsavel')}", 42, altura - 263, largura - 84, 9)
        elif tipo_contrato == "Corporativo CLT" and indice_pagina == 0:
            _caixa_pdf(pdf, 35, 380, largura - 70, 310)
            _texto_pdf(pdf, "CONTRATO CORPORATIVO DE TRABALHO (CLT)", 42, altura - 175, largura - 84, 13, negrito=True)
            _texto_pdf(pdf, "DADOS DO COLABORADOR", 42, altura - 215, largura - 84, 11, negrito=True)
            linhas = [
                ("Nome Completo", dados.get("nome")), ("CPF", dados.get("cnpj")),
                ("RG", dados.get("rg_mei")), ("Endereço", endereco_completo),
                ("Telefone", dados.get("telefone")), ("E-mail", dados.get("email")),
                ("Cargo", dados.get("cargo")), ("Salário", dados.get("valor_contrato")),
            ]
            y = altura - 242
            for rotulo, valor in linhas:
                _texto_pdf(pdf, f"{rotulo}: {valor or ''}", 42, y, largura - 84, 9, max_linhas=2)
                y -= 25
        elif tipo_contrato == "Estágio" and indice_pagina == 1:
            _caixa_pdf(pdf, 35, 320, largura - 70, 280)
            _texto_pdf(pdf, "DADOS DO ESTAGIÁRIO", 42, altura - 275, largura - 84, 11, negrito=True)
            linhas = [
                ("Nome", dados.get("nome")), ("CPF", dados.get("cnpj")),
                ("Instituição de Ensino", dados.get("instituicao_ensino")),
                ("Curso", dados.get("curso")), ("Jornada", dados.get("jornada")),
                ("Endereço", endereco_completo), ("Telefone", dados.get("telefone")),
                ("E-mail", dados.get("email")),
            ]
            y = altura - 305
            for rotulo, valor in linhas:
                _texto_pdf(pdf, f"{rotulo}: {valor or ''}", 42, y, largura - 84, 9, max_linhas=2)
                y -= 23

        pdf.save()
        camada.seek(0)
        sobreposicao = PdfReader(camada)
        if sobreposicao.pages:
            pagina.merge_page(sobreposicao.pages[0])
        escritor.add_page(pagina)

    saida = io.BytesIO()
    escritor.write(saida)
    return anexar_clausulas_pdf(saida.getvalue(), dados.get("clausulas"), tipo_contrato)

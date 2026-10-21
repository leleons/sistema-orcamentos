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


def _corrigir_layout_preenchivel(escritor, tipo):
    """Corrige somente posições defeituosas dos originais na cópia de saída."""
    from pypdf import PdfReader
    from pypdf.generic import ContentStream, FloatObject, ArrayObject, NameObject, TextStringObject
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    for pagina in escritor.pages:
        conteudo = ContentStream(pagina.get_contents(),escritor)
        matriz, tamanho = None, 7.5
        for operandos, operador in conteudo.operations:
            if operador == b'Tf':
                tamanho = float(operandos[1])
            elif operador == b'Tm':
                matriz = operandos
            elif operador == b'Tj' and matriz is not None:
                texto = str(operandos[0])
                if float(matriz[5]) > 790 and float(matriz[4]) > float(pagina.mediabox.width)/2:
                    largura = pdfmetrics.stringWidth(texto,'Helvetica-Bold',tamanho)
                    matriz[4] = FloatObject(float(pagina.mediabox.width)-56.7-largura)
                if tipo == 'Corporativo CLT' and texto == 'ATIVIDADES ESPECÍFICAS / OBSERVAÇÕES':
                    operandos[0] = TextStringObject('')
        pagina.replace_contents(conteudo)
        if tipo == 'Corporativo CLT':
            for ref in pagina.get('/Annots',[]):
                widget = ref.get_object()
                if widget.get('/T') == 'atividades_especificas':
                    rect = list(widget['/Rect'])
                    rect[3] = FloatObject(float(rect[3])-14)
                    widget[NameObject('/Rect')] = ArrayObject(rect)
                    camada = io.BytesIO()
                    rotulo = canvas.Canvas(camada,pagesize=(float(pagina.mediabox.width),float(pagina.mediabox.height)))
                    rotulo.setFont('Helvetica-Bold',7)
                    rotulo.setFillColorRGB(.4,.466667,.517647)
                    rotulo.drawString(float(rect[0]),float(rect[3])+5,'ATIVIDADES ESPECÍFICAS / OBSERVAÇÕES')
                    rotulo.save()
                    pagina.merge_page(PdfReader(io.BytesIO(camada.getvalue())).pages[0])

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
        {"titulo": str(item.get("titulo") or "").strip(), "texto": str(item.get("texto") or "").strip(), "categoria": item.get('categoria','clausula')}
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
                while pdf.stringWidth(palavra, fonte, tamanho) > largura:
                    if atual:
                        linhas.append(atual)
                        atual = ''
                    corte = 1
                    while corte < len(palavra) and pdf.stringWidth(palavra[:corte+1],fonte,tamanho) <= largura:
                        corte += 1
                    linhas.append(palavra[:corte])
                    palavra = palavra[corte:]
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
        pdf.drawString(margem, altura - 30, "CLÁUSULAS E DADOS COMPLEMENTARES")
        pdf.setFont(fonte_normal, 8)
        pdf.drawRightString(largura - margem, altura - 30, tipo_contrato)
        pdf.setFillColorRGB(0.35, 0.42, 0.46)
        pdf.drawRightString(largura - margem, 28, f"Página adicional {numero_pagina}")
        pdf.setFillColorRGB(0, 0, 0)
        y = altura - 76

    cabecalho()
    for indice, item in enumerate(clausulas_validas, start=1):
        linhas = quebrar_linhas(pdf, item["texto"], largura - (2 * margem), tamanho=9)
        titulo = (f"Dado complementar {indice} - " if item['categoria'] == 'dados' else f"Cláusula adicional {indice}ª - ") + item['titulo']
        linhas_titulo = quebrar_linhas(pdf,titulo,largura-2*margem,fonte_negrito,10)
        if y - (len(linhas_titulo)*14+26) < 55:
            pdf.showPage()
            numero_pagina += 1
            cabecalho()
        pdf.setFont(fonte_negrito, 10)
        pdf.setFillColorRGB(0.10, 0.46, 0.66)
        for linha in linhas_titulo:
            pdf.drawString(margem,y,linha)
            y -= 14
        y -= 4
        pdf.setFont(fonte_normal, 9)
        pdf.setFillColorRGB(0.12, 0.15, 0.17)
        for linha in linhas:
            if y < 55:
                pdf.showPage()
                numero_pagina += 1
                cabecalho()
                pdf.setFont(fonte_normal,9)
                pdf.setFillColorRGB(0.12,0.15,0.17)
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
        _corrigir_layout_preenchivel(escritor, tipo_contrato)
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
        # Exponha e preencha também os campos nativos antes ignorados, incluindo
        # empresa, condições, jornada e observações. Assinaturas não são simuladas.
        campos_nativos = leitor.get_fields()
        for nome, campo in campos_nativos.items():
            if nome.startswith('assinatura_') or nome == 'data_assinatura':
                continue
            if nome in dados:
                valor = dados[nome]
                campos_formulario[nome] = ('/Yes' if valor else '/Off') if campo.get('/FT') == '/Btn' else str(valor or '')
        from dsystem_erp.services.contratos_vigencia import data_contrato, fim_vigencia
        inicio = data_contrato(dados.get('data_contrato') or __import__('datetime').date.today())
        fim = fim_vigencia(inicio)
        assinatura = data_contrato(dados['data_assinatura']) if dados.get('data_assinatura') else inicio
        campos_formulario.update(data_emissao=assinatura.strftime('%d/%m/%Y'), data_inicio=inicio.strftime('%d/%m/%Y'), vigencia='1 ano')
        if dados.get('data_assinatura'):
            campos_formulario['data_assinatura'] = assinatura.strftime('%d/%m/%Y')
        campos_formulario = {nome: valor for nome, valor in campos_formulario.items() if nome in campos_nativos}
        complementos = []
        from reportlab.lib.utils import simpleSplit
        for pagina in escritor.pages:
            for referencia in pagina.get('/Annots', []):
                widget = referencia.get_object()
                pai = widget.get('/Parent')
                nome = widget.get('/T') or (pai.get_object().get('/T') if pai else None)
                if nome not in campos_formulario or campos_nativos[nome].get('/FT') != '/Tx':
                    continue
                valor = str(campos_formulario[nome])
                if isinstance(campos_formulario[nome], tuple):
                    continue
                x1,y1,x2,y2 = map(float,widget['/Rect'])
                largura, altura = x2-x1-4, y2-y1-4
                multiline = int(campos_nativos[nome].get('/Ff',0)) & 4096
                tamanho = 9.0
                def cabe():
                    if multiline:
                        linhas = [linha for p in valor.splitlines() or [''] for linha in simpleSplit(p,'Helvetica',tamanho,largura)]
                        return len(linhas)*tamanho*1.25 <= altura and all(pdfmetrics.stringWidth(l,'Helvetica',tamanho) <= largura for l in linhas)
                    return '\n' not in valor and pdfmetrics.stringWidth(valor,'Helvetica',tamanho) <= largura and tamanho <= altura
                while tamanho > 6 and not cabe():
                    tamanho = round(tamanho-.25,2)
                if not cabe():
                    complementos.append({'titulo':nome.replace('_',' ').capitalize(),'texto':valor,'categoria':'dados'})
                    valor = 'Ver complemento.'
                    tamanho = min(9, largura / max(pdfmetrics.stringWidth(valor,'Helvetica',1),1))
                campos_formulario[nome] = (valor,'/Helv',tamanho)
        for pagina in escritor.pages:
            escritor.update_page_form_field_values(pagina, campos_formulario, auto_regenerate=False)
        # Os modelos CLT/estágio não têm um campo nativo de vigência. Registrar
        # as datas na área livre da capa sem encobrir cláusulas ou assinaturas.
        camada_vigencia = io.BytesIO()
        capa = escritor.pages[0]
        carimbo = canvas.Canvas(camada_vigencia, pagesize=(float(capa.mediabox.width), float(capa.mediabox.height)))
        carimbo.setFont('ContratoSans', 11)
        carimbo.drawString(56.7, 250, 'Vigência: 1 ano')
        carimbo.drawString(56.7, 230, f'Início: {inicio:%d/%m/%Y} — Término: {fim:%d/%m/%Y}')
        carimbo.save()
        capa.merge_page(PdfReader(io.BytesIO(camada_vigencia.getvalue())).pages[0])
        saida = io.BytesIO()
        escritor.write(saida)
        return anexar_clausulas_pdf(saida.getvalue(), list(dados.get("clausulas") or []) + complementos, tipo_contrato)

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
                _texto_pdf(pdf, f"Belo Horizonte, {dados.get('data_assinatura') or dados.get('data_contrato')}.", 42, altura - 165, largura - 84, 10)
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

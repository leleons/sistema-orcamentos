"""Fluxo de recepção e etiquetas dos equipamentos de O.S."""

from __future__ import annotations

import io
import json
from urllib.parse import urlencode, urlsplit


def configuracao_etiqueta_os(config_get):
    """O perfil da i8 ignora medidas legadas de etiquetas maiores que a bobina."""
    perfil = config_get("ETIQUETA_OS_PERFIL", "elgin_i8")
    if perfil == "elgin_i8":
        # Papel nominal de 80 mm; área de conteúdo de 72 mm, centralizada.
        # Altura de 60 mm é escolha de layout do ERP, não tamanho fixo da bobina.
        return {"perfil": perfil, "largura_mm": 80.0, "altura_mm": 60.0, "margem_mm": 4.0}
    if perfil != "personalizado":
        raise ValueError("Selecione um perfil de impressão válido em Configurações do Sistema > Empresa.")
    largura = float(config_get("ETIQUETA_OS_LARGURA_MM", "100"))
    altura = float(config_get("ETIQUETA_OS_ALTURA_MM", "50"))
    if not (70 <= largura <= 150 and 40 <= altura <= 150):
        raise ValueError("Confira o tamanho da etiqueta em Configurações do Sistema > Empresa.")
    return {"perfil": perfil, "largura_mm": largura, "altura_mm": altura, "margem_mm": 3.0}


def alvo_qr_equipamento(parametros):
    """Aceita somente identificadores; dados pessoais na URL nunca são usados."""
    if parametros.get("pagina") != "Recepção e Kanban":
        return None
    equipamento = str(parametros.get("equipamento_id") or "")
    if len(equipamento) <= 19 and equipamento.isascii() and equipamento.isdigit() and 0 < int(equipamento) < 2**63:
        return ("id", int(equipamento))
    # Compatibilidade com etiquetas antigas que já continham um link.
    os_id = str(parametros.get("os") or "")
    item = str(parametros.get("item") or "")
    if len(os_id) <= 19 and os_id.isascii() and os_id.isdigit() and 0 < int(os_id) < 2**63 and 0 < len(item) <= 80:
        return ("item", int(os_id), item)
    return None


def encaminhar_qr_equipamento(estado, parametros, paginas_permitidas):
    alvo = alvo_qr_equipamento(parametros)
    if alvo and "Recepção e Kanban" in paginas_permitidas and estado.get("qr_os_aberto") != alvo:
        estado["qr_os_aberto"] = alvo
        estado["pagina_atual"] = "Recepção e Kanban"
        estado["pagina_atual_radio"] = "Recepção e Kanban"


def buscar_equipamento_qr(cursor, alvo):
    if not alvo:
        return None
    condicao, valores = ("eo.id=?", (alvo[1],)) if alvo[0] == "id" else (
        "eo.os_id=? AND eo.numero_item=?", (alvo[1], alvo[2]))
    cursor.execute("""SELECT eo.*, os.cliente, os.atendente, os.tecnico_extra, os.chamado_id
                      FROM equipamentos_os eo JOIN ordens_servico os ON os.os_id=eo.os_id
                      WHERE """ + condicao, valores)
    item = cursor.fetchone()
    return dict(item) if item else None


def servicos_equipamento(registro):
    texto = str(registro.get("servico") or registro.get("defeito") or "").strip()
    config = registro.get("configuracao") or {}
    if isinstance(config, str):
        try:
            config = json.loads(config)
        except (ValueError, TypeError):
            config = {}
    if not isinstance(config, dict):
        config = {}
    tarefas = [texto] if texto else []
    for chave, rotulo in (("formatar", "Formatar"), ("backup", "Fazer backup"),
                          ("apps_padrao", "Instalar aplicativos padrão")):
        if str(config.get(chave)).casefold() == "sim":
            tarefas.append(rotulo)
    if str(config.get("app_especifico")).casefold() == "sim":
        tarefas.append("Aplicativo específico: " + str(config.get("app_especifico_nome") or "a definir"))
    return "\n".join(tarefas) or "Serviço a fazer ainda não informado."


def atualizar_equipamentos_os(cursor, os_id, itens, numero_item, letra):
    """Edita sem excluir/reinserir: ID e etiqueta de cada aparelho são permanentes.

    A quantidade só pode aumentar neste editor. Não reutiliza a etiqueta de outro
    aparelho nem tenta deduzir identidade por nome ou posição.
    """
    cursor.execute("SELECT id, numero_item FROM equipamentos_os WHERE os_id=? ORDER BY id", (os_id,))
    existentes = {int(item["id"]): dict(item) for item in cursor.fetchall()}
    recebidos = [int(item["id"]) for item in itens if item.get("id")]
    if len(set(recebidos)) != len(recebidos) or set(recebidos) != set(existentes):
        raise ValueError("Os equipamentos desta O.S. mudaram. Reabra a edição antes de salvar.")
    numeros = {item["numero_item"] for item in existentes.values()}
    indice_novo = 0
    for item in itens:
        valores = (item.get("e", ""), item.get("m", ""), item.get("a", ""),
                   item.get("servico", ""), item.get("serie", ""),
                   json.dumps(item.get("configuracao") or {}, ensure_ascii=False))
        if item.get("id"):
            cursor.execute("""UPDATE equipamentos_os SET equipamento=?, marca=?, avaria=?,
                              servico=?, numero_serie=?, configuracao=? WHERE id=? AND os_id=?""",
                           (*valores, item["id"], os_id))
        else:
            while numero_item(os_id, indice_novo) in numeros:
                indice_novo += 1
            numero = numero_item(os_id, indice_novo)
            cursor.execute("""INSERT INTO equipamentos_os
                (equipamento, marca, avaria, servico, numero_serie, configuracao,
                 os_id, numero_item, letra_equipamento, etiqueta_codigo, kanban_status)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (*valores, os_id, numero, letra(indice_novo), numero, "Recebido"))
            numeros.add(numero)
            indice_novo += 1


def validar_url_etiqueta(base_url):
    url = urlsplit(str(base_url or "").strip())
    if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError("Configure a URL HTTP/HTTPS do sistema em Configurações do Sistema > Empresa.")
    if url.hostname.lower() in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        raise ValueError("Use o endereço do servidor acessível pelo celular, não localhost, na URL do sistema.")
    return str(base_url).strip().rstrip("/")


STATUS_KANBAN_OS = (
    "Recebido", "Triagem / Diagnóstico", "Aguardando aprovação",
    "Em execução", "Aguardando peça", "Pronto", "Entregue",
)

CORES_KANBAN_OS = {
    "Recebido": "#3b82f6",
    "Triagem / Diagnóstico": "#8b5cf6",
    "Aguardando aprovação": "#f59e0b",
    "Em execução": "#06b6d4",
    "Aguardando peça": "#f97316",
    "Pronto": "#22c55e",
    "Entregue": "#64748b",
}


def texto_cartao_equipamento(item: dict) -> str:
    """Monta um cartão legível e com identificador único para o quadro."""
    equipamento_id = int(item.get("id") or 0)
    os_id = int(item.get("os_id") or 0)
    numero_item = str(item.get("numero_item") or f"ITEM-{equipamento_id}")
    cliente = str(item.get("cliente") or "Cliente não informado").strip()
    equipamento = " · ".join(
        parte for parte in (
            str(item.get("tipo_equipamento") or "").strip(),
            str(item.get("equipamento") or "").strip(),
        )
        if parte
    ) or "Equipamento não informado"
    serie = str(item.get("numero_serie") or "").strip()
    complemento = f" · Série {serie}" if serie else ""
    return f"OS #{os_id:05d} · {numero_item}\n{cliente}\n{equipamento}{complemento}\nEQ-{equipamento_id}"


def texto_cartao_registro(item: dict) -> str:
    """Monta o texto de um cartão originado de O.S., atendimento ou chamado."""
    origem = str(item.get("_origem") or "O.S.")
    registro_id = int(item.get("_registro_id") or item.get("id") or 0)
    cliente = str(item.get("_cliente") or "Cliente não informado").strip()
    titulo = str(item.get("_titulo") or "Registro sem título").strip()
    complemento = str(item.get("_complemento") or "").strip()
    linhas = [f"{origem} #{registro_id:05d}", cliente, titulo]
    if complemento:
        linhas.append(complemento)
    linhas.append(str(item.get("_chave") or f"registro:{registro_id}"))
    return "\n".join(linhas)


def montar_quadro_registros(registros: list[dict]) -> tuple[list[dict], dict[str, str]]:
    """Converte registros das três origens para um único quadro."""
    por_status = {status: [] for status in STATUS_KANBAN_OS}
    cartao_para_chave = {}
    ordenados = sorted(
        (dict(item) for item in registros),
        key=lambda item: (int(item.get("kanban_ordem") or 0), -int(item.get("_registro_id") or 0)),
    )
    for item in ordenados:
        status = item.get("kanban_status") or STATUS_KANBAN_OS[0]
        if status not in por_status:
            status = STATUS_KANBAN_OS[0]
        texto = texto_cartao_registro(item)
        por_status[status].append(texto)
        cartao_para_chave[texto] = str(item.get("_chave"))
    return (
        [{"header": status, "items": por_status[status]} for status in STATUS_KANBAN_OS],
        cartao_para_chave,
    )


def alteracoes_do_quadro_registros(
    quadro_resultado: list[dict] | None,
    registros: list[dict],
    cartao_para_chave: dict[str, str],
) -> list[dict]:
    """Calcula mudanças de etapa e ordem de um quadro com origens diferentes."""
    if not isinstance(quadro_resultado, list) or len(quadro_resultado) != len(STATUS_KANBAN_OS):
        return []
    headers = []
    cartoes = []
    for coluna in quadro_resultado:
        if not isinstance(coluna, dict) or not isinstance(coluna.get("items"), list):
            return []
        header = coluna.get("header")
        if not isinstance(header, str) or header not in STATUS_KANBAN_OS:
            return []
        headers.append(header)
        if not all(isinstance(cartao, str) for cartao in coluna["items"]):
            return []
        cartoes.extend(coluna["items"])
    if len(set(headers)) != len(STATUS_KANBAN_OS):
        return []
    if len(cartoes) != len(set(cartoes)) or set(cartoes) != set(cartao_para_chave):
        return []

    atuais = {str(item.get("_chave")): dict(item) for item in registros}
    alteracoes = []
    chaves_processadas = set()
    for coluna in quadro_resultado:
        status = coluna["header"]
        for ordem, cartao in enumerate(coluna["items"]):
            chave = cartao_para_chave.get(cartao)
            if not chave or chave in chaves_processadas or chave not in atuais:
                continue
            chaves_processadas.add(chave)
            item = atuais[chave]
            status_anterior = item.get("kanban_status") or STATUS_KANBAN_OS[0]
            ordem_anterior = int(item.get("kanban_ordem") or 0)
            if status != status_anterior or ordem != ordem_anterior:
                alteracoes.append({
                    "chave": chave,
                    "origem": item.get("_origem_codigo"),
                    "id": int(item.get("_registro_id") or 0),
                    "status": status,
                    "ordem": ordem,
                    "status_anterior": status_anterior,
                })
    return alteracoes


def montar_quadro_equipamentos(equipamentos: list[dict]) -> tuple[list[dict], dict[str, int]]:
    """Converte os equipamentos do banco para as colunas do componente."""
    por_status = {status: [] for status in STATUS_KANBAN_OS}
    cartao_para_id = {}
    ordenados = sorted(
        (dict(item) for item in equipamentos),
        key=lambda item: (int(item.get("kanban_ordem") or 0), -int(item.get("id") or 0)),
    )
    for item in ordenados:
        status = item.get("kanban_status") or STATUS_KANBAN_OS[0]
        if status not in por_status:
            status = STATUS_KANBAN_OS[0]
        texto = texto_cartao_equipamento(item)
        por_status[status].append(texto)
        cartao_para_id[texto] = int(item.get("id") or 0)
    return (
        [{"header": status, "items": por_status[status]} for status in STATUS_KANBAN_OS],
        cartao_para_id,
    )


def alteracoes_do_quadro(
    quadro_resultado: list[dict] | None,
    equipamentos: list[dict],
    cartao_para_id: dict[str, int],
) -> list[dict]:
    """Calcula somente mudanças válidas de coluna ou ordem feitas no quadro."""
    if not isinstance(quadro_resultado, list) or len(quadro_resultado) != len(STATUS_KANBAN_OS):
        return []
    headers = []
    cartoes = []
    for coluna in quadro_resultado:
        if not isinstance(coluna, dict) or not isinstance(coluna.get("items"), list):
            return []
        header = coluna.get("header")
        if not isinstance(header, str) or header not in STATUS_KANBAN_OS:
            return []
        headers.append(header)
        if not all(isinstance(cartao, str) for cartao in coluna["items"]):
            return []
        cartoes.extend(coluna["items"])
    # Um evento parcial/duplicado não pode movimentar só parte dos equipamentos.
    if len(set(headers)) != len(STATUS_KANBAN_OS):
        return []
    if len(cartoes) != len(set(cartoes)) or set(cartoes) != set(cartao_para_id):
        return []
    atuais = {int(item.get("id") or 0): dict(item) for item in equipamentos}
    alteracoes = []
    ids_processados = set()
    for coluna in quadro_resultado or []:
        status = coluna.get("header")
        if status not in STATUS_KANBAN_OS:
            continue
        for ordem, cartao in enumerate(coluna.get("items") or []):
            equipamento_id = cartao_para_id.get(cartao)
            if not equipamento_id or equipamento_id in ids_processados or equipamento_id not in atuais:
                continue
            ids_processados.add(equipamento_id)
            item = atuais[equipamento_id]
            status_anterior = item.get("kanban_status") or STATUS_KANBAN_OS[0]
            ordem_anterior = int(item.get("kanban_ordem") or 0)
            if status != status_anterior or ordem != ordem_anterior:
                alteracoes.append({
                    "id": equipamento_id,
                    "status": status,
                    "ordem": ordem,
                    "status_anterior": status_anterior,
                })
    return alteracoes


def proximo_status(status: str, direcao: int = 1) -> str:
    atual = status if status in STATUS_KANBAN_OS else STATUS_KANBAN_OS[0]
    indice = max(0, min(len(STATUS_KANBAN_OS) - 1, STATUS_KANBAN_OS.index(atual) + direcao))
    return STATUS_KANBAN_OS[indice]


def dados_qr_equipamento(registro: dict, base_url: str = "") -> str:
    dados = {
        "os": registro.get("os_id") or "",
        "item": registro.get("numero_item") or "",
        "cliente": registro.get("cliente") or "",
        "equipamento": registro.get("equipamento") or "",
        "serie": registro.get("numero_serie") or "",
        "chamado": registro.get("chamado_id") or "",
    }
    if base_url:
        base_url = validar_url_etiqueta(base_url)
        vinculo = {"equipamento_id": registro["id"]} if registro.get("id") else {"os": dados["os"], "item": dados["item"]}
        return f"{base_url}/?{urlencode({'pagina': 'Recepção e Kanban', **vinculo})}"
    dados["servico"] = servicos_equipamento(registro)
    return " | ".join(f"{chave.upper()}: {valor}" for chave, valor in dados.items() if valor not in (None, ""))


def gerar_etiqueta_equipamento(registro: dict, base_url: str = "", largura_mm=100, altura_mm=50, margem_mm=3) -> bytes:
    from reportlab.graphics.barcode import code128
    from reportlab.graphics.barcode.qr import QrCodeWidget
    from reportlab.graphics.shapes import Drawing
    from reportlab.graphics import renderPDF
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import simpleSplit
    from reportlab.pdfbase.pdfmetrics import stringWidth

    saida = io.BytesIO()
    if not (70 <= float(largura_mm) <= 150 and 40 <= float(altura_mm) <= 150):
        raise ValueError("Etiqueta suportada: largura de 70 a 150 mm e altura de 40 a 150 mm.")
    if not (3 <= float(margem_mm) <= 5):
        raise ValueError("Margem suportada de 3 a 5 mm.")
    largura, altura = float(largura_mm) * mm, float(altura_mm) * mm
    margem = float(margem_mm) * mm
    pdf = canvas.Canvas(saida, pagesize=(largura, altura))
    pdf.setTitle(f"Etiqueta {registro.get('numero_item') or registro.get('os_id')}")
    def linha(texto, y, largura_texto, negrito=False, fonte=7):
        nome_fonte = "Helvetica-Bold" if negrito else "Helvetica"
        texto = " ".join(str(texto).split())
        if stringWidth(texto, nome_fonte, fonte) > largura_texto:
            while texto and stringWidth(texto + "...", nome_fonte, fonte) > largura_texto:
                texto = texto[:-1]
            texto += "..."
        pdf.setFont(nome_fonte, fonte)
        pdf.drawString(margem, y, texto)

    linha(f"OS #{int(registro.get('os_id') or 0):05d} | ITEM {registro.get('numero_item') or ''}", altura-5*mm, largura-2*margem, True, 9)
    texto_largura = largura-2*margem-31*mm
    linha(registro.get("cliente") or "Cliente não informado", altura-10*mm, texto_largura, True)
    linha(f"Equip.: {registro.get('equipamento') or registro.get('tipo_equipamento') or ''}", altura-14*mm, texto_largura)
    linha(f"Marca: {registro.get('marca') or ''}", altura-18*mm, texto_largura)
    linha(f"Série: {registro.get('numero_serie') or ''}", altura-22*mm, texto_largura)
    linhas_servico = simpleSplit("Fazer: " + " / ".join(servicos_equipamento(registro).splitlines()), "Helvetica", 6.5, texto_largura)
    max_linhas = max(1, int((float(altura_mm)-35)/3))
    for indice, texto in enumerate(linhas_servico[:max_linhas]):
        if indice == max_linhas-1 and len(linhas_servico) > max_linhas:
            texto += "..."
        linha(texto, altura-(26+3*indice)*mm, texto_largura, fonte=6.5)

    codigo = str(registro.get("numero_item") or f"OS{registro.get('os_id') or 0}")
    barras = code128.Code128(codigo, barHeight=5 * mm, barWidth=0.25 * mm, quiet=False)
    pdf.saveState()
    pdf.translate(margem, 3*mm)
    pdf.scale(min(1, texto_largura/barras.width), 1)
    barras.drawOn(pdf, 0, 0)
    pdf.restoreState()
    qr = QrCodeWidget(dados_qr_equipamento(registro, base_url))
    limites = qr.getBounds(); tamanho = 30 * mm
    desenho = Drawing(tamanho, tamanho, transform=[tamanho / (limites[2] - limites[0]), 0, 0, tamanho / (limites[3] - limites[1]), 0, 0])
    desenho.add(qr)
    renderPDF.draw(desenho, pdf, largura-margem-30*mm, altura-36*mm)
    pdf.setFont("Helvetica", 5.5)
    pdf.drawCentredString(largura-margem-15*mm, altura-38*mm, "Leia para ver serviço atualizado" if base_url else "QR estático - não atualiza")
    pdf.showPage(); pdf.save()
    return saida.getvalue()

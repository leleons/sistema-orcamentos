"""Identificação portátil do produto, sem informações privadas do cadastro."""
from io import BytesIO
import qrcode


def conteudo_qr_produto(produto):
    """Somente identificação; não expõe dados financeiros nem saldo desatualizável."""
    codigo = produto.get("codigo_entrada") or produto.get("codigo_item") or produto["id"]
    campos = [
        ("Produto ID", produto['id']), ("Código", codigo),
        ("Descrição", produto.get("nome_generico") or produto.get("produto")),
        ("Modelo", produto.get("modelo")),
        ("Estado / Fileira 1", produto.get("codigo")),
        ("Categoria / Fileira 2", produto.get("categoria")),
        ("Caixa / Gaveta", produto.get("caixa")),
        ("Tem fonte", produto.get("tem_fonte")),
    ]
    linhas = ["DSYSTEM - Identificação do produto"]
    for rotulo, valor in campos:
        texto = " ".join(str(valor).split()) if valor is not None else ""
        if texto:
            # Mantém a etiqueta legível e evita exceder a capacidade do QR.
            texto = texto if len(texto) <= 140 else texto[:137] + "..."
            linhas.append(f"{rotulo}: {texto}")
    return "\n".join(linhas)


def gerar_qr_produto(produto):
    conteudo = conteudo_qr_produto(produto)
    buffer = BytesIO()
    qrcode.make(conteudo).save(buffer, format="PNG")
    return buffer.getvalue()

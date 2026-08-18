"""Monta um único PDF com os documentos enviados ao cliente."""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from typing import Iterable

from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


@dataclass(frozen=True)
class DocumentoFaturamento:
    codigo: str
    titulo: str
    categoria: str
    arquivo: bytes
    nome_arquivo: str


def decodificar_pdf_base64(valor: str | bytes | None) -> bytes:
    """Decodifica o PDF salvo pela emissao fiscal."""
    if not valor:
        return b""
    if isinstance(valor, bytes):
        valor = valor.decode("ascii")
    try:
        return base64.b64decode(valor, validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError("O PDF da nota fiscal salvo no banco está corrompido.") from exc


def pdf_de_referencia(titulo: str, descricao: str, referencia: str) -> bytes:
    """Cria uma página PDF para um documento disponível por número ou link."""
    saida = io.BytesIO()
    pdf = canvas.Canvas(saida, pagesize=A4)
    largura, altura = A4
    pdf.setTitle(titulo)
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(50, altura - 70, titulo)
    pdf.setFont("Helvetica", 11)
    pdf.drawString(50, altura - 100, descricao)
    referencia = str(referencia or "").strip()
    if referencia:
        texto = referencia if len(referencia) <= 92 else referencia[:89] + "..."
        pdf.setFillColorRGB(0.05, 0.25, 0.55)
        pdf.drawString(50, altura - 130, texto)
        if referencia.startswith(("http://", "https://")):
            pdf.linkURL(referencia, (48, altura - 135, largura - 48, altura - 116), relative=0)
    pdf.setFillColorRGB(0, 0, 0)
    pdf.setFont("Helvetica-Oblique", 9)
    pdf.drawString(50, 45, "Documento de referência gerado pelo Dsystem ERP.")
    pdf.save()
    return saida.getvalue()


def _capa_pacote(faturamento_id: int, cliente: str, documentos: list[DocumentoFaturamento]) -> bytes:
    saida = io.BytesIO()
    pdf = canvas.Canvas(saida, pagesize=A4)
    _, altura = A4
    pdf.setTitle(f"Documentos do faturamento {faturamento_id}")
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(50, altura - 65, "Documentos do faturamento")
    pdf.setFont("Helvetica", 11)
    pdf.drawString(50, altura - 95, f"Faturamento: #{faturamento_id}")
    pdf.drawString(50, altura - 115, f"Cliente: {cliente or 'Não informado'}")
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(50, altura - 155, "Conteudo do arquivo:")
    pdf.setFont("Helvetica", 10)
    y = altura - 178
    for indice, documento in enumerate(documentos, start=1):
        pdf.drawString(62, y, f"{indice}. {documento.categoria} - {documento.titulo}"[:105])
        y -= 18
        if y < 60:
            pdf.showPage()
            pdf.setFont("Helvetica", 10)
            y = altura - 60
    pdf.save()
    return saida.getvalue()


def juntar_documentos_pdf(
    documentos: Iterable[DocumentoFaturamento],
    faturamento_id: int,
    cliente: str,
) -> bytes:
    """Valida e combina os documentos, precedidos por uma capa descritiva."""
    selecionados = list(documentos)
    if not selecionados:
        raise ValueError("Selecione pelo menos um documento para montar o conjunto.")

    writer = PdfWriter()
    fontes = [
        DocumentoFaturamento(
            codigo="capa",
            titulo="Capa",
            categoria="Capa",
            arquivo=_capa_pacote(faturamento_id, cliente, selecionados),
            nome_arquivo="capa.pdf",
        ),
        *selecionados,
    ]
    for documento in fontes:
        dados = bytes(documento.arquivo or b"")
        if not dados.startswith(b"%PDF"):
            raise ValueError(f"O arquivo '{documento.nome_arquivo}' não é um PDF válido.")
        try:
            leitor = PdfReader(io.BytesIO(dados))
            for pagina in leitor.pages:
                writer.add_page(pagina)
        except Exception as exc:
            raise ValueError(f"Não foi possível ler o PDF '{documento.nome_arquivo}'.") from exc

    writer.add_metadata({
        "/Title": f"Documentos do faturamento {faturamento_id}",
        "/Subject": "Nota fiscal, boleto e orçamentos selecionados",
    })
    saida = io.BytesIO()
    writer.write(saida)
    return saida.getvalue()


def nome_pacote_faturamento(faturamento_id: int) -> str:
    return f"faturamento_{int(faturamento_id)}_documentos.pdf"

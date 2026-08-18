import base64
import io
import unittest

from pypdf import PdfReader

from dsystem_erp.services.pacote_faturamento import (
    DocumentoFaturamento,
    decodificar_pdf_base64,
    juntar_documentos_pdf,
    nome_pacote_faturamento,
    pdf_de_referencia,
)


class PacoteFaturamentoTests(unittest.TestCase):
    def setUp(self):
        self.pdf_nota = pdf_de_referencia("Nota fiscal", "Nota autorizada", "NF-123")
        self.pdf_boleto = pdf_de_referencia(
            "Boleto", "Segunda via", "https://example.com/boleto/123"
        )

    def test_decodifica_pdf_salvo_em_base64(self):
        codificado = base64.b64encode(self.pdf_nota).decode("ascii")
        self.assertEqual(decodificar_pdf_base64(codificado), self.pdf_nota)

    def test_rejeita_base64_corrompido(self):
        with self.assertRaisesRegex(ValueError, "corrompido"):
            decodificar_pdf_base64("nao-e-base64!!!")

    def test_junta_capa_e_documentos_na_ordem(self):
        documentos = [
            DocumentoFaturamento("nota:1", "Nota 123", "Nota fiscal", self.pdf_nota, "nota.pdf"),
            DocumentoFaturamento("boleto:1", "Boleto", "Boleto", self.pdf_boleto, "boleto.pdf"),
        ]
        pacote = juntar_documentos_pdf(documentos, 42, "Cliente Teste")
        leitor = PdfReader(io.BytesIO(pacote))
        self.assertEqual(len(leitor.pages), 3)
        self.assertEqual(leitor.metadata.title, "Documentos do faturamento 42")

    def test_exige_ao_menos_um_documento(self):
        with self.assertRaisesRegex(ValueError, "pelo menos um"):
            juntar_documentos_pdf([], 1, "Cliente")

    def test_rejeita_anexo_que_nao_e_pdf(self):
        documento = DocumentoFaturamento("x", "Arquivo", "Anexo", b"texto", "arquivo.txt")
        with self.assertRaisesRegex(ValueError, "não é um PDF"):
            juntar_documentos_pdf([documento], 1, "Cliente")

    def test_nome_do_conjunto_identifica_faturamento(self):
        self.assertEqual(nome_pacote_faturamento(87), "faturamento_87_documentos.pdf")


if __name__ == "__main__":
    unittest.main()

import json
import unittest
import io
from pypdf import PdfReader

from dsystem_erp.services.faturamento_espelho import gerar_pdf_espelho_faturamento


class FaturamentoEspelhoTests(unittest.TestCase):
    def test_pdf_espelho_inclui_faturamento_por_medicao(self):
        pdf = gerar_pdf_espelho_faturamento({
            "id": 42, "status": "Aberto", "cliente": "Cliente Teste",
            "cnpj": "12.345.678/0001-90", "data_lanc": "2026-09-10",
            "vencimento": "2026-09-20", "modalidade_faturamento": "Por medição",
            "tipo_nota": "Produto e Serviço", "forma_pag": "Boleto", "parcelas": "Não",
            "medicao_numero": "MED-01", "medicao_inicio": "2026-09-01",
            "medicao_fim": "2026-09-10", "medicao_percentual": 25,
            "medicao_referencia": "Contrato #7", "medicao_historico": "Primeira etapa.",
            "itens": json.dumps([
                {"tipo_item": "Produto", "desc": "Peça", "qtd": 2, "vunit": 50, "vtotal": 100},
                {"tipo_item": "Serviço", "desc": "Instalação", "qtd": 1, "vunit": 150, "vtotal": 150},
            ]),
            "valor_total": 250, "obs_nota": "Histórico completo.",
        })
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertGreater(len(pdf), 1000)
        documento = PdfReader(io.BytesIO(pdf))
        self.assertEqual(len(documento.pages), 1)
        texto = documento.pages[0].extract_text()
        self.assertIn("Total Geral", texto)
        self.assertIn("Primeira etapa.", texto)


if __name__ == "__main__":
    unittest.main()

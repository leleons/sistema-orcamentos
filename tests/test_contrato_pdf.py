import io
import unittest

from pypdf import PdfReader

from dsystem_erp.services.contrato_pdf import (
    MODELOS_CONTRATO,
    anexar_clausulas_pdf,
    caminho_modelo_contrato,
    gerar_contrato_pdf,
)


class ContratoPdfTests(unittest.TestCase):
    def setUp(self):
        self.dados = {
            "nome": "Cliente Teste",
            "cnpj": "00.000.000/0001-00",
            "endereco": "Rua Teste",
            "numero": "10",
            "bairro": "Centro",
            "cidade_estado": "Sabará/MG",
            "cep": "34700-000",
            "telefone": "(31) 99999-0000",
            "email": "teste@example.com",
            "data_contrato": "13/08/2026",
            "valor_contrato": "R$ 1.000,00",
            "dia_vencimento": "10",
            "forma_pagamento": "PIX",
        }

    def test_todos_os_modelos_configurados_existem(self):
        for tipo in MODELOS_CONTRATO:
            with self.subTest(tipo=tipo):
                self.assertTrue(caminho_modelo_contrato(tipo).is_file())

    def test_rejeita_tipo_de_contrato_desconhecido(self):
        with self.assertRaises(ValueError):
            caminho_modelo_contrato("Contrato inexistente")

    def test_gera_os_tres_tipos_de_contrato(self):
        for tipo in MODELOS_CONTRATO:
            with self.subTest(tipo=tipo):
                pdf = gerar_contrato_pdf(tipo, self.dados)
                self.assertTrue(pdf.startswith(b"%PDF"))
                self.assertGreater(len(PdfReader(io.BytesIO(pdf)).pages), 0)

    def test_clausula_adicional_cria_nova_pagina(self):
        original = gerar_contrato_pdf("Suporte Tecnológico", self.dados)
        alterado = anexar_clausulas_pdf(
            original,
            [{"titulo": "Confidencialidade", "texto": "As partes preservarão os dados."}],
            "Suporte Tecnológico",
        )

        paginas_originais = len(PdfReader(io.BytesIO(original)).pages)
        paginas_alteradas = len(PdfReader(io.BytesIO(alterado)).pages)
        self.assertEqual(paginas_alteradas, paginas_originais + 1)


if __name__ == "__main__":
    unittest.main()

import unittest
import xml.etree.ElementTree as ET

from dsystem_erp.services.nfse_xml import formatar_decimal_xml, gerar_xml_nfse_bh_rps


class NfseXmlServiceTests(unittest.TestCase):
    def test_formata_decimal_xml(self):
        self.assertEqual(formatar_decimal_xml("12,30"), "0.00")
        self.assertEqual(formatar_decimal_xml(12.3), "12.30")

    def test_gera_xml_nfse_com_dados_basicos(self):
        xml_bytes = gerar_xml_nfse_bh_rps(
            {"id": 7, "cliente": "Cliente Teste", "cnpj": "12.345.678/0001-90"},
            "Servico",
            {
                "competencia": "14/07/2026",
                "valor": 100,
                "aliquota_iss": 5,
                "descricao": "Servico tecnico",
                "codigo_servico": "0107",
                "item_lista_servico": "1.07",
            },
        )

        root = ET.fromstring(xml_bytes)
        texto = xml_bytes.decode("utf-8")
        self.assertTrue(root.tag.endswith("GerarNfseEnvio"))
        self.assertIn("Cliente Teste", texto)
        self.assertIn("Servico tecnico", texto)
        self.assertIn("100.00", texto)
        self.assertIn("<Cnpj>12345678000190</Cnpj>", texto)

    def test_gera_xml_nfse_exige_documento_tomador(self):
        with self.assertRaisesRegex(ValueError, "tomador"):
            gerar_xml_nfse_bh_rps(
                {"id": 7, "cliente": "Cliente Teste", "cnpj": ""},
                "Servico",
                {
                    "competencia": "14/07/2026",
                    "valor": 100,
                    "aliquota_iss": 5,
                    "descricao": "Servico tecnico",
                    "codigo_servico": "0107",
                    "item_lista_servico": "1.07",
                },
            )


if __name__ == "__main__":
    unittest.main()

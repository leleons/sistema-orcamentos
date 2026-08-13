import unittest

from dsystem_erp.services.settings import endpoint_nfse_nacional_rest, normalizar_whatsapp_config, validar_nfse_config


class SettingsTests(unittest.TestCase):
    def test_reconhece_endpoint_sefin_nacional(self):
        self.assertTrue(endpoint_nfse_nacional_rest("https://sefin.nfse.gov.br/SefinNacional"))

    def test_normalizar_whatsapp_config_adiciona_codigo_brasil(self):
        self.assertEqual(normalizar_whatsapp_config("(31) 93502-3241"), "5531935023241")

    def test_validar_nfse_config_rejeita_cnpj_curto(self):
        resultado = validar_nfse_config({
            "NFSE_CNPJ": "123",
            "NFSE_INSCRICAO_MUNICIPAL": "07395930011",
            "NFSE_ENDPOINT_SOAP": "https://exemplo.com/soap",
        })
        self.assertFalse(resultado.ok)
        self.assertIn("CNPJ deve ter 14 digitos.", resultado.mensagens)

    def test_validar_nfse_config_rejeita_endpoint_sem_http(self):
        resultado = validar_nfse_config({
            "NFSE_CNPJ": "23524449000154",
            "NFSE_INSCRICAO_MUNICIPAL": "07395930011",
            "NFSE_ENDPOINT_SOAP": "portal.prefeitura.local",
        })
        self.assertFalse(resultado.ok)
        self.assertIn("Endpoint/API deve comecar com http:// ou https://.", resultado.mensagens)


if __name__ == "__main__":
    unittest.main()

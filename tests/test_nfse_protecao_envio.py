import unittest
from unittest.mock import patch
from tests import test_nfse_nacional as exemplos
from dsystem_erp.services.nfse_nacional import (
    gerar_xml_dps_nacional, enviar_dps_nacional, validar_destino_dps,
    ENDPOINT_HOMOLOGACAO, ENDPOINT_PRODUCAO,
)


class ProtecaoEnvioTests(unittest.TestCase):
    def setUp(self):
        exemplo = exemplos.NfseNacionalTest()
        exemplo.setUp()
        self.faturamento, self.dados = exemplo.faturamento, exemplo.dados

    def test_bloqueio_antes_de_certificado_ou_rede(self):
        xml = gerar_xml_dps_nacional(self.faturamento, self.dados)
        with patch('dsystem_erp.services.nfse_nacional.urlopen') as rede:
            for endpoint in [ENDPOINT_PRODUCAO, 'https://exemplo.com', 'http://sefin.producaorestrita.nfse.gov.br']:
                with self.assertRaises(ValueError):
                    enviar_dps_nacional(endpoint, xml, '', '')
            rede.assert_not_called()
        validar_destino_dps(ENDPOINT_HOMOLOGACAO, xml)

    def test_nao_corta_textos(self):
        for campo, valor in [('descricao', 'a' * 1001), ('observacoes', 'a' * 2001)]:
            with self.assertRaises(ValueError):
                gerar_xml_dps_nacional(self.faturamento, {**self.dados, campo: valor})

    def test_valor_invalido(self):
        for valor in ['NaN', 'Infinity', '-1', '0.001', 'abc']:
            with self.assertRaises(ValueError):
                gerar_xml_dps_nacional(self.faturamento, {**self.dados, 'valor': valor})

    def test_tres_regimes_no_xml(self):
        for opcao in ['1', '2', '3']:
            xml = gerar_xml_dps_nacional(self.faturamento, {**self.dados,
                'opcao_simples_nacional': opcao, 'regime_apuracao_simples': '1',
                'percentual_tributos_simples': '6.00'})
            self.assertIn(f'<opSimpNac>{opcao}</opSimpNac>'.encode(), xml)
            self.assertEqual(b'<regApTribSN>' in xml, opcao == '3')

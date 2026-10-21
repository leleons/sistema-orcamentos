import unittest
from unittest.mock import patch
from lxml import etree
from tests import test_nfse_nacional as exemplos
from dsystem_erp.services.nfse_nacional import (
    executar_fluxo_nfse_nacional, ENDPOINT_HOMOLOGACAO, NS_NFSE, RejeicaoNacionalHTTP,
)


class InscricaoAutomaticaTests(unittest.TestCase):
    def executar(self, respostas):
        exemplo = exemplos.NfseNacionalTest()
        exemplo.setUp()
        with patch('dsystem_erp.services.nfse_nacional.assinar_xml_dps_nacional', side_effect=lambda xml, *args: xml), \
             patch('dsystem_erp.services.nfse_nacional.enviar_dps_nacional', side_effect=respostas) as envio:
            resultado = executar_fluxo_nfse_nacional(exemplo.faturamento, exemplo.dados,
                endpoint=ENDPOINT_HOMOLOGACAO, cert_path='', cert_password='')
        self.assertEqual(exemplo.dados['inscricao_municipal'], '07395930011')
        return resultado, envio

    def test_e0120_repete_mesma_dps_sem_im(self):
        for rejeicao in [ {'erros': [{'Codigo': 'E0120'}]},
                         RejeicaoNacionalHTTP('E0120', {'erros': [{'codigo': 'E0120'}]}, 400) ]:
            resultado, envio = self.executar([rejeicao, {}])
            self.assertEqual(envio.call_count, 2)
            original = etree.fromstring(envio.call_args_list[0].args[1])
            final = etree.fromstring(resultado.xml_dps)
            ns = {'n': NS_NFSE}
            prest = original.find('n:infDPS/n:prest', ns)
            prest.remove(prest.find('n:IM', ns))
            self.assertEqual(etree.tostring(original), etree.tostring(final))
            self.assertIn('omitida automaticamente', resultado.mensagem)

    def test_nao_repete_sucesso_ou_outro_erro(self):
        for resposta in [{}, {'erros': [{'Codigo': 'E9999'}]},
                         {'erros': [{'Codigo': 'E0120'}, {'Codigo': 'E9999'}]}]:
            _, envio = self.executar([resposta])
            self.assertEqual(envio.call_count, 1)

    def test_sem_loop(self):
        erro = {'erros': [{'Codigo': 'E0120'}]}
        resultado, envio = self.executar([erro, erro])
        self.assertEqual(envio.call_count, 2)
        self.assertEqual(resultado.status, 'Rejeitada')

    def test_nao_repete_timeout(self):
        with self.assertRaises(TimeoutError):
            self.executar([TimeoutError('incerto')])

import io
import unittest
from unittest.mock import patch
from pypdf import PdfReader
from tests.preview_danfse_local import xml_exemplo, CHAVE
from dsystem_erp.services.danfse_local import gerar_danfse_local


class DanfseLocalTests(unittest.TestCase):
    def test_xml_autorizado_gera_uma_pagina_sem_rede(self):
        with patch('urllib.request.urlopen', side_effect=AssertionError('Não deve acessar rede')):
            pdf = gerar_danfse_local({'xml_autorizado':xml_exemplo(), 'chave_acesso':CHAVE,
                                    'cliente':'Não deve usar este cliente', 'valor_servicos':999})
        reader = PdfReader(io.BytesIO(pdf))
        self.assertEqual(len(reader.pages), 1)
        text = reader.pages[0].extract_text()
        for value in ['DANFSe v2.0', CHAVE, 'NFS-e SEM VALIDADE JURÍDICA',
                      'MIRANTE DA SERRA', '01.07.01 / 001', 'R$ 1,00']:
            self.assertIn(value,text)
        self.assertNotIn('Não deve usar este cliente',text)
        self.assertNotIn('999',text)

    def test_producao_nao_imprime_aviso_homologacao(self):
        pdf = gerar_danfse_local({'xml_autorizado':xml_exemplo().replace('<tpAmb>2</tpAmb>', '<tpAmb>1</tpAmb>')})
        self.assertNotIn('SEM VALIDADE',PdfReader(io.BytesIO(pdf)).pages[0].extract_text())

    def test_nao_gera_para_dps_ou_chave_divergente(self):
        for nota in [{'xml_autorizado':'<DPS/>'}, {'xml_autorizado':xml_exemplo(), 'chave_acesso':'1'*50}]:
            with self.assertRaises(ValueError):
                gerar_danfse_local(nota)

    def test_nao_corta_descricao_longa(self):
        xml = xml_exemplo().replace('suporte - Qtd: 1 - Total: R$ 1,00', 'Serviço extenso. '*3000)
        with self.assertRaisesRegex(ValueError,'excedem uma página'):
            gerar_danfse_local({'xml_autorizado':xml})

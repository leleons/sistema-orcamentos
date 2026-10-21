from copy import deepcopy
from datetime import datetime, timezone
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET

from dsystem_erp.services.nfe_produto import (
    gerar_xml_nfe_produto_400, validar_xml_nfe_produto_minimo,
    validar_aliquotas_ibscbs_xml, aliquotas_ibscbs_integral, enviar_xml_nfe_produto,
)
from tests import test_nfe_produto as fixtures


class AliquotasTests(unittest.TestCase):
    def exemplo(self, ano=2026):
        fat, itens, dados = fixtures.NFeProdutoTests().exemplo()
        dados['data_emissao'] = datetime(ano, 10, 6, 12, tzinfo=timezone.utc)
        return fat, itens, dados

    def test_integral_2026_e_calculo_de_totais(self):
        fat, itens, dados = self.exemplo()
        itens[0]['ibscbs'].update(aliquotas_ibscbs_integral(2026))
        xml = gerar_xml_nfe_produto_400(fat, itens, dados)
        self.assertEqual(validar_aliquotas_ibscbs_xml(xml), [])
        self.assertEqual(validar_xml_nfe_produto_minimo(xml, dados, itens), [])
        root = ET.fromstring(xml)
        self.assertEqual(root.findtext('.//{*}pIBSUF'), '0.1000')
        self.assertEqual(root.findtext('.//{*}vIBSUF'), '0.10')
        self.assertEqual(root.findtext('.//{*}pIBSMun'), '0.0000')
        self.assertEqual(root.findtext('.//{*}vCBS'), '0.90')

    def test_reproduz_aliquotas_2_da_nota_rejeitada_sem_sobrescrever(self):
        fat, itens, dados = self.exemplo()
        itens[0]['ibscbs'].update(uf=2, municipal=2, cbs=2)
        antes = deepcopy(itens)
        xml = gerar_xml_nfe_produto_400(fat, itens, dados)
        erros = validar_xml_nfe_produto_minimo(xml, dados, itens)
        self.assertTrue(all(any(codigo in e for e in erros) for codigo in ('1026','1032','1037')))
        self.assertEqual(itens, antes)
        assinado, _ = fixtures.NFeProdutoTests().xml_assinado_teste(xml)
        with patch('urllib.request.urlopen') as rede:
            with self.assertRaisesRegex(ValueError, 'Envio bloqueado.*1026'):
                enviar_xml_nfe_produto('https://exemplo.invalid', assinado, '', '')
            rede.assert_not_called()

    def test_nao_aplica_tabela_2026_em_outro_ano(self):
        self.assertEqual(aliquotas_ibscbs_integral(2027), {})
        fat, itens, dados = self.exemplo(2027)
        xml = gerar_xml_nfe_produto_400(fat, itens, dados)
        self.assertEqual(validar_aliquotas_ibscbs_xml(xml), [])


if __name__ == '__main__':
    unittest.main()

import unittest
from xml.etree import ElementTree as ET
from tests import test_nfe_produto as exemplos
from dsystem_erp.services.nfe_cliente import destinatario_do_cadastro
from dsystem_erp.services.nfe_produto import gerar_xml_nfe_produto_400, NFE_NS


class CadastroNfeTests(unittest.TestCase):
    def test_normaliza_sem_inventar_ie_ou_ibge(self):
        dados = destinatario_do_cadastro({'cidade_estado': 'BH / MG', 'cep': '31920-440',
            'telefone': '(31) 99999-0000', 'estado_insc_estadual': '123'})
        self.assertEqual(dados['municipio'], 'Belo Horizonte')
        self.assertEqual(dados['uf'], 'MG')
        self.assertEqual(dados['cep'], '31920440')
        self.assertEqual(dados['telefone'], '31999990000')
        self.assertEqual(dados['indicador_ie'], '')
        self.assertEqual(dados['codigo_municipio'], '')

    def test_campos_cadastrados_no_xml(self):
        fat, itens, dados = exemplos.NFeProdutoTests().exemplo()
        dados['destinatario'].update(complemento='Sala 2', telefone='31999990000', email='cliente@example.com')
        root = ET.fromstring(gerar_xml_nfe_produto_400(fat, itens, dados))
        ns = {'n': NFE_NS}
        self.assertEqual(root.findtext('.//n:dest/n:enderDest/n:xCpl', namespaces=ns), 'Sala 2')
        self.assertEqual(root.findtext('.//n:dest/n:enderDest/n:fone', namespaces=ns), '31999990000')
        self.assertEqual(root.findtext('.//n:dest/n:email', namespaces=ns), 'cliente@example.com')

    def test_sem_cadastro(self):
        self.assertEqual(destinatario_do_cadastro(None)['municipio'], '')

    def test_indicador_explicito_preservado(self):
        self.assertEqual(destinatario_do_cadastro({'indicador_ie': '2'})['indicador_ie'], '2')

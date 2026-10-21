import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from dsystem_erp.services.nfe_cadastro_automatico import completar_destinatario, interpretar_cadastro, NS

CLIENTE = dict(cnpj='19737899000158', endereco='Rua', numero='1',
               cidade_estado='Contagem / MG', cep='32113340')


def resposta(cstat='111', ie='123', situacao='1', documento=CLIENTE['cnpj'], extra=''):
    return (f'<retConsCad xmlns="{NS}"><infCons><cStat>{cstat}</cStat><UF>MG</UF>'
            f'<CNPJ>{documento}</CNPJ><infCad><CNPJ>{documento}</CNPJ><UF>MG</UF>'
            f'<cSit>{situacao}</cSit><IE>{ie}</IE></infCad>{extra}</infCons></retConsCad>')


class CadastroAutomaticoTests(unittest.TestCase):
    def test_inscricao_ativa_exata(self):
        self.assertEqual(interpretar_cadastro(resposta(), CLIENTE['cnpj'], 'MG'),
                         {'ie': '123', 'indicador_ie': '1'})

    def test_nao_infere_nao_contribuinte_ou_escolhe_inscricao_ambigua(self):
        extra = f'<infCad><CNPJ>{CLIENTE["cnpj"]}</CNPJ><UF>MG</UF><cSit>1</cSit><IE>456</IE></infCad>'
        for xml in (resposta(cstat='259'), resposta(situacao='0'), resposta(ie=''),
                    resposta(documento='23524449000154'), resposta(extra=extra), '<outro/>'):
            with self.subTest(xml=xml), self.assertRaises(ValueError):
                interpretar_cadastro(xml, CLIENTE['cnpj'], 'MG')

    @patch('dsystem_erp.services.nfe_cadastro_automatico.consultar_ie', return_value={'ie':'123','indicador_ie':'1'})
    @patch('dsystem_erp.services.nfe_cadastro_automatico.consultar_cep', return_value={
        'codigo_ibge':'3118601','cidade_estado':'CONTAGEM / MG','uf':'MG'})
    def test_preenche_sem_alterar_cadastro(self, cep, ie):
        original = dict(CLIENTE)
        result = completar_destinatario(CLIENTE, 'homologacao')
        self.assertEqual(result['dados']['codigo_municipio'], '3118601')
        self.assertEqual(result['dados']['ie'], '123')
        self.assertEqual(CLIENTE, original)
        self.assertFalse(result['avisos'])

    @patch('dsystem_erp.services.nfe_cadastro_automatico.consultar_ie', side_effect=TimeoutError)
    @patch('dsystem_erp.services.nfe_cadastro_automatico.consultar_cep', side_effect=TimeoutError)
    def test_indisponibilidade_preserva_dados(self, cep, ie):
        result = completar_destinatario(CLIENTE, 'homologacao')
        self.assertEqual(result['dados']['logradouro'], 'Rua')
        self.assertEqual(result['dados']['indicador_ie'], '')
        self.assertEqual(len(result['avisos']), 2)

    @patch('dsystem_erp.services.nfe_cadastro_automatico.consultar_ie', return_value={'ie':'123','indicador_ie':'1'})
    @patch('dsystem_erp.services.nfe_cadastro_automatico.consultar_cep', return_value={
        'codigo_ibge':'3106200','cidade_estado':'Belo Horizonte / MG','uf':'MG'})
    def test_nao_substitui_ie_ou_municipio_divergente(self, cep, ie):
        result = completar_destinatario(dict(CLIENTE, estado_insc_estadual='456'), 'homologacao')
        self.assertEqual(result['dados']['codigo_municipio'], '')
        self.assertEqual(result['dados']['ie'], '456')
        self.assertEqual(result['dados']['indicador_ie'], '')
        self.assertEqual(len(result['avisos']), 2)

    def test_ui_cache_preserva_edicoes_e_separa_ambientes(self):
        source = '''
import streamlit as st
from dsystem_erp.pages.nfe_destinatario import preparar_destinatario
ambiente = st.selectbox('Ambiente', ['homologacao', 'producao'])
dados, prefixo = preparar_destinatario(st, {'id':1}, 99, ambiente, '', '')
st.text_input('IE', key=prefixo+'_ie')
st.selectbox('Indicador', ['', '1', '2', '9'], key=prefixo+'_indicador_ie')
'''
        with patch('dsystem_erp.pages.nfe_destinatario.completar_destinatario', return_value={
                'dados':{'ie':'123', 'indicador_ie':'1'}, 'avisos':[], 'fontes':['teste']}) as consulta:
            app = AppTest.from_string(source).run()
            self.assertFalse(app.exception)
            self.assertEqual(app.text_input[0].value, '123')
            app.text_input[0].set_value('456').run()
            self.assertEqual(consulta.call_count, 1)
            app.button[0].click().run()
            self.assertEqual(app.text_input[0].value, '456')
            self.assertEqual(consulta.call_count, 2)
            app.selectbox[0].select('producao').run()
            self.assertEqual(app.text_input[0].value, '123')
            self.assertEqual(consulta.call_count, 3)
            self.assertFalse(app.exception)

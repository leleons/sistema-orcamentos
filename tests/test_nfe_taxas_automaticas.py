import copy
import json
import unittest
from unittest.mock import Mock
from streamlit.testing.v1 import AppTest

from tests import test_fiscal_modelos as fixtures
from dsystem_erp.services.nfe_tributacao_item import buscar_tributacao_item, chave_widgets_tributacao
from dsystem_erp.services.fiscal_automatico import atualizar_taxas_tabeladas
from dsystem_erp.pages.nfe_tributacao_item import salvar_regra_produtos


class TaxasAutomaticasTests(unittest.TestCase):
    def setUp(self):
        self.factory = fixtures.ModelosTests()
        self.factory.setUp()
        self.addCleanup(self.factory.doCleanups)
        self.modelo = self.factory.modelo_item('Mouse USB', vinculo=1)
        self.dados = copy.deepcopy(self.modelo['plano']['dados'])
        self.fat = dict(self.factory.fixture.fat, itens=[dict(
            desc='Mouse USB', estoque_id=1, tipo_item='Produto', qtd=4, vunit=50, vtotal=200)])
        self.item = self.fat['itens'][0]

    def buscar(self, **kwargs):
        return buscar_tributacao_item(kwargs.get('fat', self.fat), kwargs.get('item', self.item),
                                     kwargs.get('dados', self.dados), kwargs.get('modelos', [self.modelo]), ano=2026)

    def test_copia_regra_e_recalcula_bases_sem_alterar_referencia(self):
        antes = copy.deepcopy(self.modelo)
        resultado = self.buscar()
        self.assertTrue(resultado['aplicada'], resultado['mensagem'])
        item = resultado['item']
        self.assertEqual(item['tributos']['base_icms'], 200)
        self.assertEqual(item['tributos']['base_pis'], 200)
        self.assertEqual(item['tributos']['icms'], 18)
        self.assertEqual(item['ibscbs']['base'], 200)
        self.assertEqual(item['ncm'], '84716053')
        self.assertEqual(self.modelo, antes)

    def test_contexto_diferente_ou_ano_antigo_nao_copia_taxas(self):
        for campo, valor in [('ambiente','producao'), ('regime_tributario','1'),
                             ('uf','SP'), ('natureza_operacao','Devolução')]:
            with self.subTest(campo=campo):
                dados = dict(self.dados, **{campo:valor})
                self.assertFalse(self.buscar(dados=dados)['aplicada'])
        for campo, valor in [('uf','RJ'), ('indicador_ie','1'), ('indicador_ie','')]:
            dados = copy.deepcopy(self.dados)
            dados['destinatario'][campo] = valor
            self.assertFalse(self.buscar(dados=dados)['aplicada'])
        self.assertFalse(self.buscar(fat=dict(self.fat, cnpj='99999999000199'))['aplicada'])
        antigo = dict(self.modelo, ano_referencia=2025)
        self.assertFalse(self.buscar(modelos=[antigo])['aplicada'])

    def test_nome_ambiguo_taxas_divergentes_e_bases_reduzidas(self):
        outro = copy.deepcopy(self.modelo)
        outro['itens_referencia'][0]['tributos']['icms'] = 12
        self.assertFalse(self.buscar(modelos=[self.modelo, outro])['aplicada'])
        reduzida = copy.deepcopy(self.modelo)
        reduzida['itens_referencia'][0]['tributos']['base_icms'] = 50
        self.assertFalse(self.buscar(modelos=[reduzida])['aplicada'])
        outro = self.factory.modelo_item('Mouse USB', vinculo=2)
        item = dict(self.item)
        item.pop('estoque_id')
        self.assertFalse(self.buscar(item=item, modelos=[self.modelo, outro])['aplicada'])
        self.assertFalse(self.buscar(item=dict(item, desc='Mouse'))['aplicada'])

    def test_zero_preservado_e_codigo_cadastrado_divergente_bloqueia(self):
        self.modelo['itens_referencia'][0]['tributos']['pis'] = 0
        resultado = self.buscar()
        self.assertTrue(resultado['aplicada'])
        self.assertEqual(resultado['item']['tributos']['pis'], 0)
        self.assertFalse(self.buscar(item=dict(self.item, ncm='84716052'))['aplicada'])

    def test_widgets_nao_carregam_taxas_de_outro_contexto(self):
        base = chave_widgets_tributacao(self.fat, 0, self.item, self.dados)
        self.assertNotEqual(base, chave_widgets_tributacao(self.fat, 0, dict(self.item,vtotal=300), self.dados))
        self.assertNotEqual(base, chave_widgets_tributacao(dict(self.fat,cnpj='99999999000199'),0,self.item,self.dados))
        self.assertNotEqual(base, chave_widgets_tributacao(self.fat,0,self.item,dict(self.dados,regime_tributario='1')))

    def test_salvar_regra_valida_gera_modelo_reutilizavel(self):
        resultado = self.buscar()
        salvar = Mock()
        modelo = salvar_regra_produtos(self.fat, self.dados, [resultado['item']],
                                      self.modelo['plano']['endpoint'], 'gerente', salvar)
        salvar.assert_called_once()
        self.assertTrue(modelo['reutilizar_por_item'])
        self.assertEqual(json.loads(salvar.call_args.args[1])['autorizado_por'], 'gerente')
        self.assertTrue(self.buscar(modelos=[modelo])['aplicada'])
        resultado['item']['tributos']['base_icms'] = 50
        with self.assertRaisesRegex(ValueError, 'Bases reduzidas'):
            salvar_regra_produtos(self.fat, self.dados, [resultado['item']],
                                 self.modelo['plano']['endpoint'], 'gerente', Mock())

    def test_conferir_taxa_atualiza_combinacoes_salvas_do_mesmo_produto(self):
        anterior = copy.deepcopy(self.modelo)
        anterior['chave'] += '_combinacao'
        anterior['itens_referencia'][0]['tributos']['icms'] = 12
        anterior['plano']['itens'][0]['tributos']['icms'] = 12
        fora = copy.deepcopy(anterior)
        fora['chave'] += '_outro_cliente'
        fora['plano']['faturamento']['cnpj'] = '99999999000199'
        antes = copy.deepcopy(anterior)
        salvar = Mock()
        novo = salvar_regra_produtos(self.fat, self.dados, [self.buscar()['item']],
                                    self.modelo['plano']['endpoint'], 'gerente', salvar, [anterior, fora])
        self.assertEqual(salvar.call_count, 2)
        atualizado = json.loads(salvar.call_args_list[1].args[1])
        self.assertEqual(atualizado['chave'], anterior['chave'])
        self.assertEqual(atualizado['plano']['itens'][0]['tributos']['icms'], 18)
        self.assertEqual(atualizado['plano']['itens'][0]['tributos']['base_icms'], 100)
        self.assertTrue(self.buscar(modelos=[novo, atualizado])['aplicada'])
        self.assertEqual(anterior, antes)

    def test_retirar_ibscbs_nao_reativa_padrao_antigo_do_documento(self):
        self.modelo['plano']['dados']['regime_tributario'] = '1'
        self.dados['regime_tributario'] = '1'
        anterior = copy.deepcopy(self.modelo)
        anterior['chave'] += '_combinacao'
        anterior['plano']['dados']['ibscbs'] = copy.deepcopy(anterior['plano']['itens'][0]['ibscbs'])
        preparado = self.buscar()['item']
        preparado.pop('ibscbs')
        salvar = Mock()
        salvar_regra_produtos(self.fat, self.dados, [preparado], self.modelo['plano']['endpoint'],
                             'gerente', salvar, [anterior])
        atualizado = json.loads(salvar.call_args_list[1].args[1])
        self.assertNotIn('ibscbs', atualizado['plano']['dados'])
        self.assertNotIn('ibscbs', atualizado['plano']['itens'][0])

    def test_preparacao_antiga_preenche_taxas_fixas_sem_alterar_enquadramento(self):
        plano = copy.deepcopy(self.modelo['plano'])
        plano['itens'][0]['ibscbs'].update(uf=2, municipal=2, cbs=2)
        corrigido = atualizar_taxas_tabeladas(plano, 'Produto')
        self.assertEqual(corrigido['itens'][0]['ibscbs']['uf'], 0.1)
        self.assertEqual(corrigido['itens'][0]['ibscbs']['municipal'], 0)
        self.assertEqual(corrigido['itens'][0]['ibscbs']['cbs'], 0.9)
        self.assertEqual(plano['itens'][0]['ibscbs']['uf'], 2)
        plano['itens'][0].pop('ibscbs')
        self.assertNotIn('ibscbs', atualizar_taxas_tabeladas(plano,'Produto')['itens'][0])

    def test_tela_preserva_edicao_manual_e_desmarcar_remove_ibscbs(self):
        item = self.buscar()['item']
        source = '''
import streamlit as st
from dsystem_erp.pages.nfe_tributacao_item import renderizar_taxas
item = ''' + repr(item) + '''
st.session_state['resultado'] = renderizar_taxas(st,item,'item_teste','3',ano=2026)
'''
        app = AppTest.from_string(source, default_timeout=15).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.number_input(key='item_teste_base_icms').value, 200)
        self.assertEqual(app.number_input(key='item_teste_rtc_uf_2026').value, 0.1)
        self.assertTrue(app.number_input(key='item_teste_rtc_uf_2026').disabled)
        app.number_input(key='item_teste_icms').set_value(12).run()
        self.assertEqual(app.session_state['resultado']['tributos']['icms'], 12)
        app.checkbox(key='item_teste_rtc').uncheck().run()
        self.assertNotIn('ibscbs', app.session_state['resultado'])
        self.assertFalse(app.exception)

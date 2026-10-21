import io
import re
import unittest
from zipfile import ZipFile
from lxml import etree
try:
    from streamlit.testing.v1 import AppTest
except ImportError:
    AppTest = None

from dsystem_erp.services.contratos_modelos import (
    WORD, W, modelos_disponiveis, abrir_modelo, slots_modelo,
    preencher_cadastro, gerar_word, substituir_texto,
)


class ContratosModelosTests(unittest.TestCase):
    def test_seis_modelos(self):
        self.assertEqual(len(modelos_disponiveis()), 6)

    def test_preenche_ambas_partes_sem_inverter(self):
        a = dict(nome='Cliente A', cnpj='111', endereco='Rua A', numero='10', cidade_estado='Contagem / MG')
        b = dict(nome='Empresa B', cnpj='222', endereco='Rua B', numero='20', cidade_estado='Belo Horizonte / MG')
        for tipo in WORD:
            slots = slots_modelo(tipo)
            values = preencher_cadastro(tipo, slots, a, b)
            p_a = 1 if tipo in ('Tecnologia e Infraestrutura','Prestação de Serviços PJ') else 3
            p_b = 2
            if tipo != 'Prestação de Serviços PJ':
                self.assertIn('Cliente A', [values[s['chave']] for s in slots if s['paragrafo'] == p_a])
            else:
                self.assertIn('111', [values[s['chave']] for s in slots if s['paragrafo'] == p_a])
            self.assertIn('Empresa B', [values[s['chave']] for s in slots if s['paragrafo'] == p_b])

    def test_gera_modelos_preservando_partes_nao_editadas_e_sem_campos_pendentes(self):
        for tipo in WORD:
            for prazo in ('Determinado', 'Indeterminado'):
                for regime in ('Franquia', 'Fixo sem franquia', 'Contador'):
                    slots = slots_modelo(tipo, prazo, regime)
                    dados = {s['chave']: 'Dado confirmado ' + s['chave'] for s in slots}
                    result = gerar_word(tipo, dados, prazo, regime)
                    with ZipFile(io.BytesIO(abrir_modelo(tipo))) as original, ZipFile(io.BytesIO(result)) as saida:
                        self.assertEqual(original.namelist(), saida.namelist())
                        for nome in original.namelist():
                            if nome != 'word/document.xml':
                                self.assertEqual(original.read(nome), saida.read(nome), nome)
                        root = etree.fromstring(saida.read('word/document.xml'))
                        text = ''.join(t.text or '' for t in root.iter(W+'t'))
                        self.assertNotIn('____', text)
                        self.assertNotIn('``', text)
                        self.assertFalse(set(re.findall(r'\[[^\]]+\]', text)) - {'[1]', '[1, 2]', '[6.1]', '[6.2]'})
                        if tipo == 'Serviços e Locação de Equipamentos':
                            self.assertNotIn('Escolha e preencha apenas UMA', text)
                            self.assertEqual('prazo indeterminado' in text, prazo == 'Indeterminado')

    def test_recusa_campos_vazios(self):
        for tipo in WORD:
            with self.assertRaises(ValueError):
                gerar_word(tipo, {})

    def test_placeholder_dividido_entre_runs_preserva_formatacao(self):
        p = etree.fromstring(f'<w:p xmlns:w="{W[1:-1]}"><w:r><w:rPr><w:b/></w:rPr><w:t>Antes [No</w:t></w:r><w:r><w:t>me] depois</w:t></w:r></w:p>')
        substituir_texto(p, '[Nome]', 'José & Maria')
        self.assertEqual(''.join(p.itertext()), 'Antes José & Maria depois')
        self.assertIsNotNone(p.find('.//'+W+'b'))

    @unittest.skipIf(AppTest is None, 'Testes da interface usam o ambiente do aplicativo.')
    def test_tela_troca_cliente_sem_misturar_dados(self):
        fonte = '''
import streamlit as st
from unittest.mock import MagicMock
from dsystem_erp.pages.contratos_gerar import renderizar_gerador
conn = MagicMock()
conn.cursor.return_value.lastrowid = 123
clientes = [dict(id=1, nome='Cliente A', cnpj='111', endereco='Rua A', cidade_estado='Contagem/MG', telefone='31', email='a@example.com'), dict(id=2, nome='Empresa B', cnpj='222', endereco='Rua B', cidade_estado='Belo Horizonte/MG', telefone='32', email='b@example.com')]
renderizar_gerador(dict(st=st,tem_permissao=lambda p:True,buscar_clientes=lambda:clientes,conectar_banco=lambda:conn,agora_br=lambda:'02/10/2026'))
'''
        app = AppTest.from_string(fonte).run()
        app.selectbox(key='central_parte_Suporte Tecnológico').select('1').run()
        self.assertEqual(app.text_input(key='central_contrato_Suporte Tecnológico_1_nome').value, 'Cliente A')
        app.selectbox(key='central_parte_Suporte Tecnológico').select('2').run()
        self.assertEqual(app.text_input(key='central_contrato_Suporte Tecnológico_2_nome').value, 'Empresa B')
        app.selectbox(key='central_contrato_modelo').select('Serviços e Locação de Equipamentos').run()
        app.selectbox(key='central_parte_Serviços e Locação de Equipamentos').select('1').run()
        prefixo = 'central_contrato_Serviços e Locação de Equipamentos_1'
        self.assertEqual(app.selectbox(key=prefixo+'_contratante').value, '1')
        app.selectbox(key=prefixo+'_contratada').select('2').run()
        for campo in app.text_input:
            if not campo.value:
                campo.set_value('Preenchido para teste')
        app.run()
        gerar = next(b for b in app.button if b.label == 'Gerar e salvar na aba Contratos')
        self.assertFalse(gerar.disabled)
        gerar.click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['central_contrato_resultado']['id'], 123)

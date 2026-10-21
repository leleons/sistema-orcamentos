import io
import unittest
from datetime import date
from pypdf import PdfReader
from dsystem_erp.services.contratos_vigencia import fim_vigencia, preencher_datas_word
from dsystem_erp.services.contratos_modelos import WORD, slots_modelo
from dsystem_erp.services.contratos_word_pdf import gerar_pdf_word
from dsystem_erp.services.contrato_pdf import MODELOS_CONTRATO, caminho_modelo_contrato, gerar_contrato_pdf


class ContratosVigenciaPdfTests(unittest.TestCase):
    def test_um_ano_calendario_e_locacao_variavel(self):
        self.assertEqual(fim_vigencia('07/10/2026'), date(2027,10,7))
        self.assertEqual(fim_vigencia('29/02/2024'), date(2025,2,28))
        self.assertEqual(fim_vigencia('31/01/2026',1), date(2026,2,28))
        self.assertEqual(fim_vigencia('07/10/2026',24), date(2028,10,7))
        with self.assertRaises(ValueError):
            fim_vigencia('07/10/2026',0)

    def test_word_datas_nao_alteram_dia_pagamento_ou_franquia(self):
        inicio, fim = date(2026,10,7), date(2027,10,7)
        for tipo in WORD:
            slots = slots_modelo(tipo)
            automaticos = preencher_datas_word(tipo, slots, inicio, fim)
            for s in slots:
                if s['paragrafo'] in (11,18,20):
                    self.assertNotIn(s['chave'], automaticos)
            self.assertIn('2027', ' '.join(automaticos.values()))
        slots = slots_modelo('Serviços e Locação de Equipamentos','Indeterminado')
        valores = preencher_datas_word('Serviços e Locação de Equipamentos',slots,inicio,None)
        self.assertNotIn('2027',' '.join(valores.values()))

    def test_word_pdf_todos_regimes_com_texto_e_datas(self):
        for tipo in WORD:
            for prazo in ('Determinado','Indeterminado'):
                for regime in ('Franquia','Fixo sem franquia','Contador'):
                    slots = slots_modelo(tipo,prazo,regime)
                    valores = {s['chave']: f'Dado {s["chave"]} José & Maria' for s in slots}
                    valores.update(preencher_datas_word(tipo,slots,date(2026,10,7),None if prazo == 'Indeterminado' and 'Locação' in tipo else date(2027,10,7)))
                    pdf = gerar_pdf_word(tipo,valores,prazo,regime)
                    self.assertTrue(pdf.startswith(b'%PDF'))
                    texto = '\n'.join(p.extract_text() for p in PdfReader(io.BytesIO(pdf)).pages)
                    self.assertIn('José & Maria',texto)
                    self.assertIn('2026',texto)
                    self.assertIn('Testemunhas',texto)
                    self.assertNotIn('____',texto)
                    if tipo == 'Tecnologia e Infraestrutura':
                        self.assertIn('1 ano, de 07/10/2026 a 07/10/2027',' '.join(texto.split()))

    def test_pdf_campos_adicionais_checkbox_vigencia_e_assinaturas(self):
        for tipo in MODELOS_CONTRATO:
            campos = PdfReader(str(caminho_modelo_contrato(tipo))).get_fields()
            dados = dict(nome='Cliente José',cnpj='00000000000',endereco='Rua Teste',data_contrato='07/10/2026')
            for nome,campo in campos.items():
                if not nome.startswith('assinatura_') and nome not in {'data_assinatura','data_emissao','data_inicio','vigencia'}:
                    dados[nome] = True if campo.get('/FT') == '/Btn' else 'Preenchido ' + nome
            leitor = PdfReader(io.BytesIO(gerar_contrato_pdf(tipo,dados)))
            resultado = leitor.get_fields()
            for nome,campo in campos.items():
                if nome.startswith('assinatura_') or nome == 'data_assinatura':
                    self.assertFalse(resultado[nome].get('/V'))
                elif nome in dados:
                    self.assertEqual(str(resultado[nome]['/V']), '/Yes' if campo.get('/FT') == '/Btn' else str(dados[nome]),nome)
            capa = leitor.pages[0].extract_text()
            self.assertIn('Vigência: 1 ano',capa)
            self.assertIn('07/10/2027',capa)
            if tipo == 'Suporte Tecnológico':
                self.assertEqual(resultado['vigencia']['/V'],'1 ano')

    def test_tela_salva_pdf_e_datas_sem_gravar_banco_real(self):
        from streamlit.testing.v1 import AppTest
        fonte = '''
import streamlit as st
from unittest.mock import MagicMock
from dsystem_erp.pages.contratos_gerar import renderizar_gerador
st.session_state['is_admin'] = True
conn = MagicMock()
conn.cursor.return_value.lastrowid = 77
conn.cursor.return_value.fetchall.return_value = [dict(id=5,funcionario_nome='José Funcionário',funcionario_cpf='123',funcionario_rj='456',funcionario_endereco='Rua Funcionario',funcionario_telefone='31',funcionario_email='f@example.com',funcionario_tipo_contrato='PJ',funcionario_pj_razao_social='Empresa PJ',funcionario_pj_cnpj='11.222.333/0001-44',funcionario_pj_endereco='Rua Empresa')]
st.session_state['conn_teste'] = conn
renderizar_gerador(dict(st=st,tem_permissao=lambda p: True,buscar_clientes=lambda: [dict(id=1,nome='Cliente Maria',cnpj='123',endereco='Rua A',cidade_estado='Contagem / MG',telefone='31',email='c@example.com')],conectar_banco=lambda:conn,agora_br=lambda:'07/10/2026'))
'''
        for tipo in list(MODELOS_CONTRATO) + list(WORD):
            app = AppTest.from_string(fonte,default_timeout=15).run()
            app.selectbox(key='central_contrato_modelo').select(tipo).run()
            app.selectbox(key='central_parte_'+tipo).select('5' if tipo in ('Corporativo CLT','Estágio','Prestação de Serviços PJ') else '1').run()
            key = f'central_contrato_{tipo}_' + ('5' if tipo in ('Corporativo CLT','Estágio','Prestação de Serviços PJ') else '1')
            app.date_input(key=key+'_inicio').set_value(date(2026,10,7)).run()
            for campo in app.text_input:
                if not campo.value:
                    campo.set_value('Confirmado no site')
            app.run()
            botao = next(b for b in app.button if b.label == 'Gerar e salvar na aba Contratos')
            self.assertFalse(botao.disabled,tipo)
            botao.click().run()
            self.assertFalse(app.exception,tipo)
            result = app.session_state['central_contrato_resultado']
            self.assertEqual(result['mime'],'application/pdf')
            self.assertTrue(result['arquivo'].startswith(b'%PDF'))
            conn = app.session_state['conn_teste']
            args = conn.cursor.return_value.execute.call_args.args[1]
            self.assertEqual(args[9:11],('07/10/2026','07/10/2027'))
            app.run()
            self.assertTrue(next(b for b in app.button if b.label == 'Gerar e salvar na aba Contratos').disabled)

    def test_texto_longo_no_pdf_tem_complemento_legivel_sem_perder_o_final(self):
        dados = dict(nome='Cliente',data_contrato='07/10/2026',reajuste='Índice ' + 'x'*150,
                     escopo_especifico='Atividade detalhada. '*1700 + 'FIM DO CONTEÚDO')
        leitor = PdfReader(io.BytesIO(gerar_contrato_pdf('Suporte Tecnológico',dados)))
        self.assertEqual(leitor.get_fields()['reajuste']['/V'],'Ver complemento.')
        self.assertEqual(leitor.get_fields()['escopo_especifico']['/V'],'Ver complemento.')
        texto = '\n'.join(p.extract_text() for p in leitor.pages)
        self.assertIn('FIM DO CONTEÚDO',texto)
        self.assertGreater(len(leitor.pages),6)

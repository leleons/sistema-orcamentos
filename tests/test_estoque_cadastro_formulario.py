"""Interações reais do formulário com banco isolado, sem importar o aplicativo."""
import unittest
from streamlit.testing.v1 import AppTest


FONTE = '''
import ast
from pathlib import Path
from unittest.mock import MagicMock
import streamlit as st
from dsystem_erp.services.estoque_importacao import ESTADOS_POR_CODIGO
from dsystem_erp.services.estoque_fiscal import SITUACOES_DOCUMENTO_COMPRA
from dsystem_erp.services.precificacao_estoque import calcular_preco_revenda

if 'banco_teste' not in st.session_state:
    conn = MagicMock()
    conn.cursor.return_value.lastrowid = 10
    conn.cursor.return_value.fetchone.return_value = {'ultimo':4}
    st.session_state['banco_teste'] = conn
conn = st.session_state['banco_teste']
def conectar_banco():
    if st.session_state.get('falhar_insert'):
        def executar(sql,*args):
            if 'INSERT INTO estoque ' in sql:
                raise RuntimeError('Falha simulada no banco')
        conn.cursor.return_value.execute.side_effect = executar
    return conn
proximo_codigo_item = 5
TIPOS_IMAGEM_UPLOAD = ['png','jpg']
montar_codigo_entrada = lambda *args:'01.01.'+str(args[2])
formatar_moeda_br = lambda valor:f'R$ {valor:.2f}'
dados_upload = lambda upload:(None,None,None)
upload_dentro_limite = lambda upload:True
registrar_movimentacao = MagicMock()
agora_br = lambda:'07/10/2026'
gerar_qr_produto = lambda produto:b'PNG teste'
arvore = ast.parse(Path('dsystem_erp/pages/estoque.py').read_text(encoding='utf-8-sig'))
funcao = next(n for n in arvore.body if isinstance(n,ast.FunctionDef) and n.name == 'renderizar_estoque')
bloco = next(n for n in ast.walk(funcao) if isinstance(n,ast.With) and any(isinstance(i.context_expr,ast.Name) and i.context_expr.id == 'aba_est2' for i in n.items))
exec(compile(ast.fix_missing_locations(ast.Module(body=bloco.body,type_ignores=[])),'cadastro_estoque','exec'))
'''


class EstoqueCadastroFormularioTests(unittest.TestCase):
    def nova_tela(self):
        app = AppTest.from_string(FONTE,default_timeout=15).run()
        self.assertFalse(app.exception)
        return app

    def preencher(self,app):
        app.selectbox(key='estoque_novo_cod').select(app.selectbox(key='estoque_novo_cod').options[1])
        app.selectbox(key='estoque_novo_cat').select('2-01 Informática')
        app.text_input(key='estoque_novo_modelo').set_value('Notebook de teste')
        app.text_area(key='estoque_novo_obs').set_value('Não apagar observações')
        app.number_input(key='estoque_novo_custo').set_value(100.0)
        app.number_input(key='estoque_novo_deslocamento').set_value(20.0)
        app.number_input(key='estoque_novo_imposto').set_value(10.0)
        app.number_input(key='estoque_novo_lucro').set_value(25.0)

    def test_enter_desativado_e_atualizar_campos_nao_grava(self):
        app = self.nova_tela()
        form = app.get('form')[0].proto.form
        self.assertFalse(form.enter_to_submit)
        self.assertFalse(form.clear_on_submit)
        self.preencher(app)
        # Campos de form ficam no navegador até um submit. Um rerun sem submit
        # não os transmite em versões recentes do AppTest.
        self.assertEqual(app.text_input(key='estoque_novo_modelo').value,'Notebook de teste')
        app.run()
        self.assertFalse(app.exception)
        app.session_state['banco_teste'].cursor.return_value.execute.assert_not_called()
        app.session_state['banco_teste'].commit.assert_not_called()

    def test_previa_calcula_sem_cadastrar_ou_limpar(self):
        app = self.nova_tela()
        self.preencher(app)
        app.button(key='estoque_novo_previa').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value,'R$ 165.00')
        self.assertEqual(app.text_area(key='estoque_novo_obs').value,'Não apagar observações')
        app.session_state['banco_teste'].cursor.return_value.execute.assert_not_called()
        app.session_state['banco_teste'].commit.assert_not_called()

    def test_previa_habilita_preco_manual_e_preserva_rascunho(self):
        app = self.nova_tela()
        self.preencher(app)
        app.checkbox(key='estoque_novo_auto').uncheck()
        app.button(key='estoque_novo_previa').click().run()
        self.assertFalse(app.number_input(key='estoque_novo_venda').disabled)
        app.number_input(key='estoque_novo_venda').set_value(199.9)
        app.button(key='estoque_novo_previa').click().run()
        self.assertEqual(app.metric[0].value,'R$ 199.90')
        self.assertEqual(app.text_input(key='estoque_novo_modelo').value,'Notebook de teste')
        app.session_state['banco_teste'].commit.assert_not_called()

    def test_dados_incompletos_nao_gravam_nem_apagam(self):
        app = self.nova_tela()
        app.text_input(key='estoque_novo_modelo').set_value('Modelo incompleto')
        app.number_input(key='estoque_novo_custo').set_value(100.0)
        app.button(key='estoque_novo_salvar').click().run()
        self.assertTrue(app.error)
        self.assertEqual(app.text_input(key='estoque_novo_modelo').value,'Modelo incompleto')
        self.assertEqual(app.number_input(key='estoque_novo_custo').value,100.0)
        app.session_state['banco_teste'].commit.assert_not_called()

    def test_falha_no_banco_preserva_dados_e_faz_rollback(self):
        app = self.nova_tela()
        self.preencher(app)
        app.session_state['falhar_insert'] = True
        app.button(key='estoque_novo_salvar').click().run()
        self.assertFalse(app.exception)
        self.assertIn('Falha simulada',app.error[0].value)
        self.assertEqual(app.text_input(key='estoque_novo_modelo').value,'Notebook de teste')
        self.assertEqual(app.number_input(key='estoque_novo_custo').value,100.0)
        app.session_state['banco_teste'].rollback.assert_called_once()
        app.session_state['banco_teste'].commit.assert_not_called()

    def test_so_salvar_cadastra_e_limpa_apos_sucesso(self):
        app = self.nova_tela()
        self.preencher(app)
        app.session_state['outro_cadastro'] = 'preservar'
        app.button(key='estoque_novo_salvar').click().run()
        self.assertFalse(app.exception)
        conn = app.session_state['banco_teste']
        conn.commit.assert_called_once()
        inserts = [c for c in conn.cursor.return_value.execute.call_args_list if 'INSERT INTO estoque ' in c.args[0]]
        self.assertEqual(len(inserts),1)
        self.assertEqual(inserts[0].args[1][3],'Notebook de teste')
        self.assertEqual(inserts[0].args[1][13],165.0)
        self.assertEqual(app.text_input(key='estoque_novo_modelo').value,'')
        self.assertEqual(app.number_input(key='estoque_novo_custo').value,0.0)
        self.assertEqual(app.session_state['outro_cadastro'],'preservar')

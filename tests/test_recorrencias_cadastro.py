import ast
import inspect
import unittest

from streamlit.testing.v1 import AppTest
from dsystem_erp.pages.financeiro import renderizar_conta_financeira


class RecorrenciasCadastroTests(unittest.TestCase):
    def test_salvar_e_gerar_recorrencia_copia_quatro_classificacoes(self):
        tree = ast.parse(inspect.getsource(renderizar_conta_financeira))
        block = next(n for n in ast.walk(tree) if isinstance(n, ast.With)
                     and ast.unparse(n.items[0].context_expr) == 'aba_rec')
        source = ast.unparse(ast.Module(body=block.body, type_ignores=[]))
        base = '''
import streamlit as st
import sqlite3
from types import SimpleNamespace
from datetime import date, datetime
from dsystem_erp.pages.classificacao_financeira import renderizar as classificacao_financeira
from dsystem_erp.repositories.financeiro import listar_recorrencias as repo_listar_recorrencias
from dsystem_erp.services.permissions import usuario_eh_gerencial
st.session_state['is_admin']=1
if 'db_teste' not in st.session_state:
    db=sqlite3.connect(':memory:',check_same_thread=False)
    db.row_factory=sqlite3.Row
    db.execute('CREATE TABLE financeiro_cadastros_aux (tipo TEXT,nome TEXT,ativo TEXT)')
    db.executemany('INSERT INTO financeiro_cadastros_aux VALUES (?,?,?)',[
        ('Categoria financeira','Serviços','Sim'),('Centro de custo','TI','Sim'),
        ('Plano de contas','Receitas','Sim'),('Conta bancária','Banco A','Sim')])
    db.execute('CREATE TABLE financeiro_recorrencias_v2 (id INTEGER PRIMARY KEY,tipo TEXT,parte TEXT,cpf_cnpj TEXT,descricao TEXT,valor REAL,frequencia TEXT,dia_vencimento INTEGER,data_inicial TEXT,data_final TEXT,centro TEXT,categoria TEXT,gerar_automaticamente TEXT,ativo TEXT,criado_por TEXT,criado_em TEXT,plano_contas TEXT,conta_bancaria TEXT,ultima_geracao TEXT)')
    campos='cpf_cnpj numero_documento categoria data_emissao data_competencia data_vencimento valor_original valor_total status observacoes criado_por criado_em plano_contas conta_bancaria'.split()
    db.execute('CREATE TABLE contas_pagar (id INTEGER PRIMARY KEY,fornecedor TEXT,tipo_documento TEXT,centro_custo TEXT,solicitante TEXT,status_aprovacao TEXT,' + ','.join(c+' TEXT' for c in campos)+')')
    db.execute('CREATE TABLE contas_receber (id INTEGER PRIMARY KEY,cliente TEXT,tipo_receita TEXT,centro_receita TEXT,' + ','.join(c+' TEXT' for c in campos)+')')
    st.session_state['db_teste']=db
db=st.session_state['db_teste']
def conectar_banco():
    return SimpleNamespace(cursor=db.cursor,commit=db.commit,close=lambda:None)
data_para_banco_br=lambda d:d.isoformat() if d else ''
clientes=[{'id':1,'nome':'Cliente','cnpj':'111'}]
parte_label='Cliente/fornecedor'
'''
        for tipo in ('pagar','receber'):
            with self.subTest(tipo=tipo):
                app = AppTest.from_string(base + f'\ntipo={tipo!r}\ntabela="contas_{tipo}"\neh_pagar={tipo == "pagar"!r}\n' + source,
                                          default_timeout=15).run()
                self.assertFalse(app.exception)
                app.selectbox(key=f'contas_{tipo}_recorrencia_cadastro').select('1').run()
                next(i for i in app.text_input if i.label == 'Descrição:').input('Mensalidade')
                next(i for i in app.number_input if i.label == 'Valor R$:').set_value(50)
                for campo, valor in {'categoria':'Serviços','centro':'TI','plano_contas':'Receitas','conta_bancaria':'Conta bancária — Banco A'}.items():
                    app.selectbox(key=f'contas_{tipo}_rec_classificacao_{campo}').select(valor)
                next(b for b in app.button if b.label == 'Salvar recorrência').click().run()
                self.assertFalse(app.exception)
                next(b for b in app.button if b.label == 'Gerar lançamento desta recorrência').click().run()
                self.assertFalse(app.exception)
                db = app.session_state['db_teste']
                centro = 'centro_custo' if tipo == 'pagar' else 'centro_receita'
                row = db.execute(f'SELECT categoria,{centro},plano_contas,conta_bancaria FROM contas_{tipo}').fetchone()
                self.assertEqual(tuple(row),('Serviços','TI','Receitas','Conta bancária — Banco A'))
                db.close()

    def test_selecao_por_id_preenche_e_atualiza_documento_nos_dois_modulos(self):
        tree = ast.parse(inspect.getsource(renderizar_conta_financeira))
        block = next(n for n in ast.walk(tree) if isinstance(n, ast.With)
                     and ast.unparse(n.items[0].context_expr) == 'aba_rec')
        nodes = []
        for node in block.body:
            if isinstance(node, ast.Assign) and ast.unparse(node.targets[0]) == 'recorrencias':
                break
            nodes.append(node)
        source = ast.unparse(ast.Module(body=nodes, type_ignores=[]))
        for tipo in ('pagar', 'receber'):
            with self.subTest(tipo=tipo):
                app = AppTest.from_string(
                    'import streamlit as st\nfrom datetime import date\n'
                    'from dsystem_erp.pages.classificacao_financeira import renderizar as classificacao_financeira\n'
                    'from unittest.mock import Mock\n'
                    'conectar_banco=Mock()\nconectar_banco.return_value.cursor.return_value.fetchall.return_value=[]\n'
                    f'tabela="contas_{tipo}"\ntipo="{tipo}"\nparte_label="Cadastro"\n'
                    'clientes=[{"id":1,"nome":"Mesmo nome","cnpj":"111"},'
                    '{"id":2,"nome":"Mesmo nome","cnpj":"222"}]\n' + source
                ).run()
                self.assertFalse(app.exception)
                key = f'contas_{tipo}_recorrencia_cadastro'
                app.selectbox(key=key).select('1').run()
                self.assertEqual(app.text_input(key=f'contas_{tipo}_recorrencia_documento_1').value, '111')
                app.selectbox(key=key).select('2').run()
                self.assertEqual(app.text_input(key=f'contas_{tipo}_recorrencia_documento_2').value, '222')
                self.assertFalse(app.exception)

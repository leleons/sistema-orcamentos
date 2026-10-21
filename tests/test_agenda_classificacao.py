import ast
import inspect
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import Mock

from streamlit.testing.v1 import AppTest
from dsystem_erp.pages.agenda_visual import cartao_visita
from dsystem_erp.pages.classificacao_financeira import carregar_opcoes, salvar_faturamento
from dsystem_erp.pages.atendimentos import renderizar_atendimentos_checklists


class AgendaClassificacaoTests(unittest.TestCase):
    def test_cartao_escapa_html_e_quebras_de_linha(self):
        html = cartao_visita(dict(id=11, cliente_nome='<script>cliente</script>',
                                descricao='Texto\n\n    </div>'))
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;/div&gt;', html)
        self.assertNotIn('\n', html)

    def test_calendario_seleciona_compromisso(self):
        tree = ast.parse(inspect.getsource(renderizar_atendimentos_checklists))
        bloco = next(n for n in ast.walk(tree) if isinstance(n, ast.With)
                     and ast.unparse(n.items[0].context_expr) == 'sub_ag2')
        nodes = []
        for n in bloco.body:
            if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == '(ag_f1, ag_f2, ag_f3)':
                break
            nodes.append(n)
        source = ast.unparse(ast.Module(body=nodes, type_ignores=[]))
        app = AppTest.from_string('''
import streamlit as st
from datetime import date
from unittest.mock import Mock
from dsystem_erp.pages import atendimentos
atendimentos.st=st
_limpar_estado_editor_agenda=atendimentos._limpar_estado_editor_agenda
parse_data_flex=date.fromisoformat
conectar_banco=Mock()
conectar_banco.return_value.cursor.return_value.fetchall.return_value=[{
    'id':11,'data_visita':date.today().replace(day=7).isoformat(),
    'cliente_nome':'Cliente teste', 'hora_inicio':'14:00'}]
''' + source, default_timeout=15).run()
        self.assertFalse(app.exception)
        app.button(key='cal_visita_11').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['ag_id_edicao'], 11)
        self.assertEqual(app.session_state['ag_fil_status_v2'], 'Todos')
        self.assertEqual(app.session_state['ag_fil_data'].day, 7)

    def test_editor_vazio_nao_interrompe_outras_abas(self):
        tree = ast.parse(inspect.getsource(renderizar_atendimentos_checklists))
        bloco = next(n for n in ast.walk(tree) if isinstance(n, ast.With)
                     and ast.unparse(n.items[0].context_expr) == 'sub_ag2')
        self.assertFalse(any(isinstance(n, ast.Return) for n in ast.walk(bloco)))

    def test_home_filtra_usuario_e_abre_compromisso(self):
        tree = ast.parse((Path(__file__).resolve().parents[1] / 'orcamento.py').read_text(encoding='utf-8-sig'))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'renderizar_agenda_usuario_home')
        source = ast.unparse(node)
        app = AppTest.from_string('''
import streamlit as st
import sqlite3
from datetime import date, datetime
from unittest.mock import Mock
if 'username' not in st.session_state:
    st.session_state['username']='usuario1'
def conectar_banco():
    db=sqlite3.connect(':memory:')
    db.row_factory=sqlite3.Row
    db.execute('CREATE TABLE agenda_visitas (id INTEGER,tecnico TEXT,data_visita TEXT,status TEXT,cliente_nome TEXT,hora_inicio TEXT,hora_fim TEXT,tipo_visita TEXT,descricao TEXT,criado_em TEXT)')
    db.executemany('INSERT INTO agenda_visitas VALUES (?,?,?,?,?,?,?,?,?,?)',[
        (1,'usuario1',date.today().isoformat(),'Agendado','Cliente A','10:00','','Suporte','',''),
        (2,'usuario2',date.today().isoformat(),'Agendado','Cliente B','11:00','','Suporte','',''),
        (3,'usuario1',date.today().isoformat(),'Cancelado','Cancelado','12:00','','Suporte','','')])
    return db
tem_permissao=lambda acao:True
def mudar_pagina(pagina):
    st.session_state['destino']=pagina
''' + source + '\nrenderizar_agenda_usuario_home()', default_timeout=15).run()
        self.assertFalse(app.exception)
        self.assertEqual([b.key for b in app.button], ['home_visita_1'])
        self.assertEqual(len(app.warning), 1)
        app.button(key='home_visita_1').click().run()
        self.assertEqual(app.session_state['agenda_abrir_home']['id'], 1)
        self.assertEqual(app.session_state['destino'], 'Atendimentos e Checklists')
        app.session_state['username']='usuario2'
        app.run()
        self.assertEqual([b.key for b in app.button], ['home_visita_2'])

    def test_cadastros_ativos_e_persistencia(self):
        db = sqlite3.connect(':memory:')
        self.addCleanup(db.close)
        db.row_factory = sqlite3.Row
        db.execute('CREATE TABLE financeiro_cadastros_aux (tipo TEXT,nome TEXT,ativo TEXT)')
        db.executemany('INSERT INTO financeiro_cadastros_aux VALUES (?,?,?)', [
            ('Categoria financeira','Serviços','Sim'), ('Centro de custo','TI','Sim'),
            ('Plano de contas','Receitas','Sim'), ('Conta bancária','Banco A','Sim'),
            ('Categoria financeira','Inativa','Não')])
        conn = Mock()
        conn.cursor.return_value = db.cursor()
        opcoes = carregar_opcoes(lambda: conn)
        self.assertEqual(opcoes['categoria'], ['Serviços'])
        self.assertEqual(opcoes['conta_bancaria'], ['Conta bancária — Banco A'])
        conn.close.assert_called_once()
        db.execute('CREATE TABLE faturamento (id INTEGER,categoria TEXT,centro TEXT,plano_contas TEXT,conta_bancaria TEXT)')
        db.execute('INSERT INTO faturamento (id) VALUES (1)')
        salvar_faturamento(db.cursor(), 1, {k:v[0] for k,v in opcoes.items()})
        self.assertEqual(dict(db.execute('SELECT * FROM faturamento').fetchone()),
                         dict(id=1,categoria='Serviços',centro='TI',plano_contas='Receitas',conta_bancaria='Conta bancária — Banco A'))

    def test_seletores_preservam_legado_e_restringem_conta(self):
        source = '''
import streamlit as st
from unittest.mock import Mock
from dsystem_erp.pages.classificacao_financeira import renderizar
conn=Mock()
conn.return_value.cursor.return_value.fetchall.return_value=[
 {'tipo':'Categoria financeira','nome':'Serviços'}, {'tipo':'Conta bancária','nome':'Banco A'}]
renderizar(st,conn,'teste',{'categoria':'Legada','conta_bancaria':'Banco antigo'})
'''
        app = AppTest.from_string(source).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox(key='teste_categoria').value, 'Legada')
        self.assertNotIn('teste_conta_bancaria', [s.key for s in app.selectbox])
        app.session_state['is_admin'] = 1
        app.run()
        self.assertEqual(app.selectbox(key='teste_conta_bancaria').value, 'Banco antigo')
        app.selectbox(key='teste_categoria').select('Serviços').run()
        self.assertEqual(app.selectbox(key='teste_categoria').value, 'Serviços')

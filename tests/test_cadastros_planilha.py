import io
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from xml.sax.saxutils import escape
from zipfile import ZipFile

from streamlit.testing.v1 import AppTest
from dsystem_erp.services import cadastros_planilha as cp
from dsystem_erp.pages.classificacao_financeira import carregar_opcoes


def xlsx(abas):
    """Fixture OOXML mínima em memória; não altera a planilha do usuário."""
    arquivo = io.BytesIO()
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    rel = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    with ZipFile(arquivo, 'w') as z:
        z.writestr('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/></Types>')
        z.writestr('xl/workbook.xml', f'<workbook xmlns="{ns}" xmlns:r="{rel}"><sheets>'+''.join(f'<sheet name="{escape(nome)}" sheetId="{i}" r:id="rId{i}"/>' for i,nome in enumerate(abas,1))+'</sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'+''.join(f'<Relationship Id="rId{i}" Type="{rel}/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1,len(abas)+1))+'</Relationships>')
        for i, linhas in enumerate(abas.values(),1):
            rows = []
            for j, linha in enumerate(linhas,1):
                cells = []
                for k,v in enumerate(linha,1):
                    ref = chr(64+k)+str(j)
                    if v is None:
                        cells.append(f'<c r="{ref}"/>')
                    elif isinstance(v,int):
                        cells.append(f'<c r="{ref}" t="n"><v>{v}</v></c>')
                    elif str(v).startswith('='):
                        cells.append(f'<c r="{ref}"><f>{escape(v[1:])}</f></c>')
                    else:
                        cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{escape(v)}</t></is></c>')
                rows.append(f'<row r="{j}">'+''.join(cells)+'</row>')
            z.writestr(f'xl/worksheets/sheet{i}.xml',f'<worksheet xmlns="{ns}"><sheetData>'+''.join(rows)+'</sheetData></worksheet>')
    return arquivo.getvalue()


def dados():
    return {
        'Plano de contas': [cp.ABAS['Plano de contas'][1].split(),
            ['4','Receitas',None,1,'SINTETICA','CREDORA','Receitas','RECEITA_BRUTA','NAO','SIM',None],
            ['4.001','Suporte','4',2,'ANALITICA','CREDORA','Receitas','RECEITA_BRUTA','SIM','SIM','Conferir']],
        'Centros de custo': [cp.ABAS['Centros de custo'][1].split(),
            ['30','TI',None,1,'SINTETICA','NAO','SIM',None,None,None],
            ['30.001','Suporte','30',2,'ANALITICA','SIM','SIM','Responsável','DIRETO','Centro']],
        'Naturezas financeiras': [cp.ABAS['Naturezas financeiras'][1].split(),
            ['R','Receitas',None,1,'SINTETICA','ENTRADA',None,None,'NAO','FORA_DRE','NAO','SIM','Grupo'],
            ['R.001','Mensalidade','R',2,'ANALITICA','ENTRADA','4.001','30.001','SIM','RECEITA_BRUTA','SIM','SIM','Sem duplicar']],
        'Exemplos': [['nome'],['Não importar']],
        'Como importar': [['Instruções não são dados']],
    }


class CadastrosPlanilhaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/'teste.db'
        with closing(self.conectar()) as c:
            c.execute('CREATE TABLE financeiro_cadastros_aux (id INTEGER PRIMARY KEY, '+', '.join(k+' '+('INTEGER' if k=='nivel' else 'TEXT') for k in cp.CAMPOS)+', criado_por TEXT, criado_em TEXT, alterado_por TEXT, alterado_em TEXT)')
        self.usuario = dict(autenticado=True,username='teste',submodulos=['financeiro.cadastros','financeiro.cadastros.edit'])

    def conectar(self):
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        return c

    def importar(self, conteudo=None, atualizar=False):
        conteudo = conteudo or xlsx(dados())
        plano = cp.preparar_importacao(cp.ler_planilha(conteudo),cp.carregar_cadastros(self.conectar))
        return cp.importar(self.conectar,conteudo,plano['assinatura'],self.usuario,atualizar)

    def test_mapeamento_preserva_campos_codigos_e_ignora_exemplos(self):
        linhas = cp.ler_planilha(xlsx(dados()))
        self.assertEqual(len(linhas),6)
        r = next(r for r in linhas if r['codigo']=='R.001')
        self.assertEqual(r['tipo'],'Natureza financeira')
        self.assertEqual((r['conta_contabil_sugerida'],r['centro_custo_sugerido']),('4.001','30.001'))
        self.assertEqual(r['regra_uso'],'Sem duplicar')
        self.assertEqual(r['aceita_lancamento'],'Sim')

    def test_importacao_idempotente_e_seletores_analiticos(self):
        self.assertEqual(self.importar(),{'Novo':6,'Atualizar':0,'Sem alteração':0})
        self.assertEqual(self.importar(),{'Novo':0,'Atualizar':0,'Sem alteração':6})
        op = carregar_opcoes(self.conectar)
        self.assertEqual(op['categoria'],['R.001 — Mensalidade'])
        self.assertEqual(op['centro'],['30.001 — Suporte'])
        self.assertEqual(op['plano_contas'],['4.001 — Suporte'])
        self.assertEqual(op['conta_bancaria'],[])

    def test_atualizacao_preserva_ids_exige_confirmacao_e_nao_exclui(self):
        self.importar()
        antes = cp.carregar_cadastros(self.conectar)
        d = dados(); d['Plano de contas'][2][1] = 'Suporte técnico'
        conteudo = xlsx(d)
        with self.assertRaisesRegex(ValueError,'Confirme'):
            self.importar(conteudo)
        self.assertEqual(cp.carregar_cadastros(self.conectar),antes)
        self.assertEqual(self.importar(conteudo,True)['Atualizar'],1)
        depois = cp.carregar_cadastros(self.conectar)
        self.assertEqual([r['id'] for r in antes],[r['id'] for r in depois])
        self.assertEqual(len(depois),6)

    def test_importacao_parcial_reutiliza_pais_e_vinculos_existentes(self):
        self.importar()
        d = dados()
        d = {'Naturezas financeiras': d['Naturezas financeiras']}
        self.assertEqual(self.importar(xlsx(d))['Sem alteração'],2)
        self.assertEqual(len(cp.carregar_cadastros(self.conectar)),6)

    def test_formula_codigo_numerico_e_tipo_invalido_bloqueados(self):
        for coluna,valor in ((0,4),(1,'=1+1'),(4,'INVALIDO'),(9,'TALVEZ')):
            with self.subTest(coluna=coluna):
                d = dados(); d['Plano de contas'][1][coluna]=valor
                with self.assertRaises(ValueError): cp.ler_planilha(xlsx(d))

    def test_duplicidade_orfao_ciclo_e_vinculos_invalidos(self):
        for caso in ('duplicado','orfao','ciclo','sugestao'):
            d=dados()
            if caso=='duplicado': d['Plano de contas'].append(d['Plano de contas'][2])
            if caso=='orfao': d['Plano de contas'][2][2]='9'
            if caso=='ciclo': d['Plano de contas'][1][2]='4.001'
            if caso=='sugestao': d['Naturezas financeiras'][2][6]='4'
            with self.subTest(caso=caso), self.assertRaises(ValueError):
                cp.preparar_importacao(cp.ler_planilha(xlsx(d)),[])

    def test_sintetico_nao_pode_aceitar_lancamento(self):
        d=dados(); d['Plano de contas'][1][8]='SIM'
        with self.assertRaisesRegex(ValueError,'sintética'): cp.ler_planilha(xlsx(d))

    def test_previa_vencida_e_permissoes(self):
        conteudo=xlsx(dados())
        plano=cp.preparar_importacao(cp.ler_planilha(conteudo),[])
        with self.assertRaises(PermissionError):
            cp.importar(self.conectar,conteudo,plano['assinatura'],dict(self.usuario,submodulos=[]))
        with self.assertRaises(PermissionError):
            cp.importar(self.conectar,conteudo,plano['assinatura'],dict(self.usuario,tipo_login='cliente',is_admin=1))
        self.importar()
        with self.assertRaisesRegex(ValueError,'mudaram'):
            cp.importar(self.conectar,conteudo,plano['assinatura'],self.usuario)

    def test_rollback_integral_em_falha(self):
        with closing(self.conectar()) as c:
            c.execute("CREATE TRIGGER falhar BEFORE INSERT ON financeiro_cadastros_aux WHEN NEW.tipo='Natureza financeira' BEGIN SELECT RAISE(ABORT, 'teste'); END")
        with self.assertRaises(sqlite3.IntegrityError): self.importar()
        self.assertEqual(cp.carregar_cadastros(self.conectar),[])

    def test_desativacao_retira_seletor_e_preserva_historico(self):
        self.importar()
        d=dados(); d['Naturezas financeiras'][2][11]='NAO'
        self.importar(xlsx(d),True)
        self.assertEqual(carregar_opcoes(self.conectar)['categoria'],[])
        self.assertEqual(len(cp.carregar_cadastros(self.conectar)),6)

    def test_pagina_exibe_tres_destinos_sem_gravar(self):
        codigo='''
import streamlit as st
from dsystem_erp.pages.cadastros_planilha import renderizar
st.session_state.update(autenticado=True,username='teste',submodulos=['financeiro.cadastros','financeiro.cadastros.edit'])
renderizar(st, lambda: None)
'''
        with patch('dsystem_erp.pages.cadastros_planilha.carregar_cadastros',return_value=[]), patch('dsystem_erp.pages.cadastros_planilha.importar') as gravar:
            app=AppTest.from_string(codigo).run()
            self.assertFalse(app.exception)
            self.assertEqual([tab.label for tab in app.tabs],list(cp.ABAS))
            gravar.assert_not_called()

    def test_pagina_importa_somente_apos_confirmacao(self):
        codigo='''
import streamlit as st
from dsystem_erp.pages.cadastros_planilha import renderizar
st.session_state.update(autenticado=True,username='teste',submodulos=['financeiro.cadastros','financeiro.cadastros.edit'])
renderizar(st, lambda: None)
'''
        with patch('dsystem_erp.pages.cadastros_planilha.carregar_cadastros',return_value=[]), patch('streamlit.file_uploader',return_value=io.BytesIO(xlsx(dados()))), patch('dsystem_erp.pages.cadastros_planilha.importar',return_value={'Novo':6,'Atualizar':0,'Sem alteração':0}) as gravar:
            app=AppTest.from_string(codigo).run()
            self.assertFalse(app.exception)
            self.assertTrue(app.button[0].disabled)
            gravar.assert_not_called()
            app.checkbox[0].check().run()
            self.assertFalse(app.button[0].disabled)
            app.button[0].click().run()
            self.assertFalse(app.exception)
            gravar.assert_called_once()
            self.assertIn('6 novos', app.success[0].value)

    def test_sem_autenticacao_nao_consulta_cadastros(self):
        with patch('dsystem_erp.pages.cadastros_planilha.carregar_cadastros') as carregar:
            app=AppTest.from_string('''
import streamlit as st
from dsystem_erp.pages.cadastros_planilha import renderizar
renderizar(st, lambda: None)
''').run()
            self.assertFalse(app.exception)
            carregar.assert_not_called()


if __name__=='__main__':
    unittest.main()

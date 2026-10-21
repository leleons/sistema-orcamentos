import unittest
import sqlite3
from dsystem_erp.services.portal_cliente import filtro_chamados_portal, exigir_acesso_chamado, exigir_conta_portal_ativa


class CursorPortal:
    def __init__(self, conn):
        self.cursor = conn.cursor()
    def execute(self, sql, params=()):
        return self.cursor.execute(sql.replace('%s', '?'), params)
    def fetchone(self):
        return self.cursor.fetchone()


class PortalIsolamentoTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.addCleanup(self.conn.close)
        self.conn.executescript('''
            CREATE TABLE chamados_cliente(id INTEGER, cliente_id INTEGER, cliente_nome TEXT, criado_por TEXT);
            CREATE TABLE clientes_portal_usuarios(id INTEGER, cliente_id INTEGER, username TEXT, ativo INTEGER);
            INSERT INTO clientes_portal_usuarios VALUES(1,10,'ana@teste',1),(2,10,'bia@teste',1),(3,20,'caio@teste',1);
            INSERT INTO chamados_cliente VALUES(1,10,'Empresa','ana@teste'),(2,10,'Empresa','bia@teste'),
                (3,20,'Empresa','caio@teste'),(4,10,'Empresa',NULL),(5,NULL,'Empresa','ana@teste');
        ''')
        self.estado = dict(tipo_login='cliente', portal_tipo_usuario='Funcionário', cliente_id=10, username='ana@teste')
        self.cursor = CursorPortal(self.conn)

    def ids(self, estado):
        filtro, params = filtro_chamados_portal(estado, 10, 'Empresa')
        return [r[0] for r in self.conn.execute('SELECT id FROM chamados_cliente WHERE ' + filtro.replace('%s', '?'), params)]

    def test_funcionarios_mesma_empresa_e_empresas_homonimas_isolados(self):
        self.assertEqual(self.ids(self.estado), [1])
        self.assertEqual(self.ids(dict(self.estado, username='bia@teste')), [2])
        self.assertEqual(self.ids(dict(self.estado, username='caio@teste')), [])
        self.assertEqual(self.ids(dict(self.estado, username='')), [])
        self.assertEqual(self.ids(dict(self.estado, cliente_id=None)), [])

    def test_acesso_direto_conversa_anexo_e_mutacao_negado_ao_colega(self):
        exigir_acesso_chamado(self.cursor, self.estado, 1)
        for chamado in (2,3,4,5,999):
            with self.assertRaises(PermissionError):
                exigir_acesso_chamado(self.cursor, self.estado, chamado)

    def test_desativado_nao_lista_le_responde_nem_abre(self):
        self.conn.execute('UPDATE clientes_portal_usuarios SET ativo=0 WHERE id=1')
        self.assertEqual(self.ids(self.estado), [])
        with self.assertRaises(PermissionError):
            exigir_acesso_chamado(self.cursor, self.estado, 1)
        with self.assertRaises(PermissionError):
            exigir_conta_portal_ativa(self.cursor, self.estado)

    def test_equipe_mantem_visao_empresa_inclusive_legado(self):
        self.assertEqual(self.ids(dict(tipo_login='usuario')), [1,2,4,5])
        exigir_acesso_chamado(self.cursor, dict(tipo_login='usuario'), 2)

    def test_dono_ve_todos_autores_da_empresa_mas_nao_outros_clientes(self):
        dono = dict(self.estado, portal_tipo_usuario='Empresa', username='login-principal')
        self.assertEqual(self.ids(dono), [1,2,4])
        for chamado in (1,2,4):
            exigir_acesso_chamado(self.cursor, dono, chamado)
        for chamado in (3,5):
            with self.assertRaises(PermissionError):
                exigir_acesso_chamado(self.cursor, dono, chamado)

    def test_todas_acoes_cliente_revalidam_autoria(self):
        import ast
        from pathlib import Path
        raiz = Path(__file__).resolve().parents[1]
        arvore = ast.parse((raiz/'dsystem_erp/pages/chamados.py').read_text(encoding='utf-8-sig'))
        func = next(n for n in arvore.body if isinstance(n, ast.FunctionDef) and n.name == 'renderizar_chamados_cliente')
        guardas = [n for n in ast.walk(func) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'exigir_acesso_chamado']
        self.assertEqual(len(guardas), 4)  # editar, cancelar, aprovar, recusar
        app = ast.parse((raiz/'orcamento.py').read_text(encoding='utf-8-sig'))
        for nome in ('mensagens_chamado', 'salvar_mensagem_chamado'):
            func = next(n for n in app.body if isinstance(n, ast.FunctionDef) and n.name == nome)
            self.assertTrue(any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'exigir_acesso_chamado' for n in ast.walk(func)))

    def test_contador_nao_consulta_financeiro_ou_outros_dados_empresa(self):
        from unittest.mock import MagicMock
        from dsystem_erp.pages.portal_sections import contar_portal_cliente
        tela, conexao = MagicMock(), MagicMock()
        tela.session_state = self.estado
        cursor = conexao.cursor.return_value
        cursor.fetchone.return_value = {'total': 1}
        resultado = contar_portal_cliente('Empresa', 10, ctx={'st': tela, 'conectar_banco': lambda: conexao})
        self.assertEqual(resultado['chamados_abertos'], 1)
        self.assertEqual(resultado['financeiro'], 0)
        cursor.execute.assert_called_once()
        self.assertIn('criado_por=%s', cursor.execute.call_args.args[0])
        self.assertEqual(cursor.execute.call_args.args[1], (10, 'ana@teste', 10, 'ana@teste'))
        conexao.close.assert_called_once()

    def test_url_direta_nao_abre_areas_corporativas_para_funcionario(self):
        from unittest.mock import MagicMock
        from dsystem_erp.pages.portal_cliente import renderizar_portal_cliente_page
        for secao in ('financeiro', 'documentos', 'notas', 'os'):
            tela, conexao = MagicMock(), MagicMock()
            tela.session_state = dict(self.estado, cliente_nome='Empresa')
            chamados, privado = MagicMock(), MagicMock()
            renderizar_portal_cliente_page({
                'st': tela, 'conectar_banco': lambda: conexao,
                'obter_query_param': lambda *args: secao,
                'normalizar_secao_portal': normalizar_secao_portal,
                'renderizar_portal_cliente_home': MagicMock(),
                'renderizar_chamados_cliente': chamados,
                'renderizar_portal_financeiro_cliente': privado,
                'renderizar_portal_documentos_cliente': privado,
                'renderizar_portal_notas_cliente': privado,
                'renderizar_portal_ordens_servico': privado,
            })
            chamados.assert_called_once_with('Empresa', 10)
            privado.assert_not_called()

    def test_login_principal_pode_abrir_financeiro_da_empresa(self):
        from unittest.mock import MagicMock
        from dsystem_erp.pages.portal_cliente import renderizar_portal_cliente_page
        tela, conexao, financeiro = MagicMock(), MagicMock(), MagicMock()
        tela.session_state = dict(self.estado, portal_tipo_usuario='Empresa', cliente_nome='Empresa')
        renderizar_portal_cliente_page({
            'st': tela, 'conectar_banco': lambda: conexao,
            'obter_query_param': lambda *args: 'financeiro',
            'normalizar_secao_portal': normalizar_secao_portal,
            'renderizar_portal_cliente_home': MagicMock(),
            'renderizar_portal_financeiro_cliente': financeiro,
        })
        financeiro.assert_called_once_with('Empresa', 10)

from dsystem_erp.services.portal_cliente import link_portal, normalizar_secao_portal, portal_card_html


class PortalClienteTests(unittest.TestCase):
    def test_normalizar_secao_alias_chamados(self):
        self.assertEqual(normalizar_secao_portal("chamados"), "meus_chamados")
        self.assertEqual(normalizar_secao_portal(""), "inicio")

    def test_link_portal(self):
        self.assertEqual(link_portal("notas"), "?pagina=portal&secao=notas")

    def test_card_escapa_texto(self):
        html = portal_card_html("notas", "<Notas>", "1", "XML & PDF")
        self.assertIn("&lt;Notas&gt;", html)
        self.assertIn("XML &amp; PDF", html)
        self.assertIn("?pagina=portal&secao=notas", html)


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest


class InterPaginaTests(unittest.TestCase):
    def setUp(self):
        # Nunca abrir a base de usuários ou o cofre real durante AppTest.
        from tests.test_inter_painel import usuario_teste
        p = patch('dsystem_erp.pages.banco_inter_painel.carregar_usuario', return_value=usuario_teste())
        p.start()
        self.addCleanup(p.stop)
        p = patch('dsystem_erp.services.inter_runtime.chave_mestra', return_value=b'x'*32)
        p.start()
        self.addCleanup(p.stop)

    def app(self, permissoes=True, ambiente='Simulação sem rede'):
        codigo = '''
import streamlit as st
from dsystem_erp.pages.banco_inter import renderizar_banco_inter
st.session_state['autenticado'] = True
st.session_state['username'] = 'teste'
st.session_state['tipo_login'] = 'interno'
st.session_state['submodulos'] = PERMISSOES
renderizar_banco_inter()
'''.replace('PERMISSOES',repr(['inter.view','inter.preparar','inter.aprovar','inter.executar'] if permissoes else []))
        app = AppTest.from_string(codigo, default_timeout=20)
        if ambiente is not None:
            app.session_state['inter_ambiente'] = ambiente
        return app

    def test_renderizacao_simulada_sem_rede_ou_mysql(self):
        with patch('requests.Session.request',side_effect=AssertionError('rede proibida')), patch('dsystem_erp.db.conectar_mysql',side_effect=AssertionError('mysql proibido')):
            app = self.app().run(timeout=20)
            self.assertEqual(len(app.exception),0)
            self.assertEqual(app.radio(key='inter_ambiente').value,'Simulação sem rede')
            next(b for b in app.button if b.label=='Consultar saldo e extrato').click().run()
            self.assertEqual(len(app.exception),0)
            self.assertTrue(any('10000' in j.value for j in app.json))

    def test_sem_permissao_nao_inicializa_demo(self):
        with patch('dsystem_erp.pages.banco_inter.criar_repositorio_demo') as criar:
            app = self.app(False).run()
        criar.assert_not_called()
        self.assertEqual(len(app.exception),0)
        self.assertIn('inter.view',app.error[0].value)

    def test_preparar_pix_na_tela_nao_envia(self):
        app = self.app().run(timeout=20)
        next(t for t in app.text_input if t.label=='Referência única do lançamento').set_value('teste-tela')
        next(t for t in app.text_input if t.label=='Chave Pix do favorecido').set_value('ficticia')
        next(b for b in app.button if b.label=='Preparar para aprovação').click().run()
        self.assertEqual(len(app.exception),0)
        self.assertTrue(any('Preparada' in s.value for s in app.success))
        servico = app.session_state['_inter_demo']['servico']
        self.assertEqual(servico.cliente.chamadas,[])
        self.assertEqual(servico.repo.listar(1,'simulacao','teste')[0]['estado'],'PENDENTE_APROVACAO')

    def test_configuracao_separada_nao_abre_sandbox(self):
        import tempfile
        from pathlib import Path
        from dsystem_erp.repositories.inter import criar_repositorio_demo
        codigo = '''
import streamlit as st
from dsystem_erp.pages.banco_inter import renderizar_banco_inter
st.session_state.update(autenticado=True,username='teste',tipo_login='interno',submodulos=['inter.view','inter.configurar'])
st.session_state['inter_ambiente'] = 'Configurar chaves (sem conexão bancária)'
st.session_state['inter_config_ambiente'] = 'sandbox'
renderizar_banco_inter()
'''
        with tempfile.TemporaryDirectory() as pasta:
            repo = criar_repositorio_demo(Path(pasta)/'demo.sqlite','teste')
            with patch('dsystem_erp.services.inter_runtime.repositorio_teste',return_value=repo), patch('dsystem_erp.services.inter_runtime.abrir_sandbox') as abrir:
                app = AppTest.from_string(codigo,default_timeout=20).run()
                self.assertEqual(len(app.exception),0)
                self.assertIn('Client Secret do Banco Inter',[x.label for x in app.text_input])
                self.assertEqual(len(app.get('file_uploader')),1)
                next(r for r in app.radio if r.label=='Formato dos certificados').set_value('Arquivos separados').run()
                self.assertEqual(len(app.get('file_uploader')),2)
                self.assertTrue(any('sem ativar' in b.label for b in app.button))
                abrir.assert_not_called()

    def test_producao_somente_consulta_sem_chamada_ao_renderizar(self):
        import tempfile
        from pathlib import Path
        from dsystem_erp.repositories.inter import criar_repositorio_demo
        with tempfile.TemporaryDirectory() as pasta:
            repo = criar_repositorio_demo(Path(pasta)/'demo.sqlite','teste')
            with patch('dsystem_erp.services.inter_runtime.repositorio_configuracao',return_value=repo), patch('requests.Session.request',side_effect=AssertionError('rede proibida')):
                app = self.app(ambiente=None).run()
                self.assertEqual(len(app.exception),0)
                self.assertEqual(app.radio(key='inter_ambiente').value, 'Produção — somente consultas')
                self.assertEqual([b.label for b in app.button],['Acessar conta real — saldo e extrato', 'Boletos e pagamentos', 'Atualizar agora'])
                self.assertFalse(any('Preparar' in b.label or 'Executar' in b.label for b in app.button))

    def test_atalho_sai_da_simulacao_e_consulta_somente_apos_clique(self):
        import tempfile
        from pathlib import Path
        from dsystem_erp.repositories.inter import criar_repositorio_demo
        with tempfile.TemporaryDirectory() as pasta:
            repo = criar_repositorio_demo(Path(pasta)/'demo.sqlite','teste')
            from tests.test_inter_painel import credencial_ficticia
            credencial_ficticia(repo)
            with patch('dsystem_erp.services.inter_runtime.repositorio_configuracao',return_value=repo), \
                    patch('dsystem_erp.services.inter_runtime.ConsultasInterProducao') as classe, \
                    patch('requests.Session.request',side_effect=AssertionError('rede proibida')):
                servico = classe.return_value
                servico.consultar.side_effect = [{'disponivel': 23}, {'transacoes': [], 'totalPaginas': 0, 'totalElementos': 0}]
                app = self.app().run()
                app.button(key='inter_abrir_producao').click().run()
                self.assertEqual(len(app.exception), 0)
                self.assertEqual(app.radio(key='inter_ambiente').value, 'Produção — somente consultas')
                servico.consultar.assert_not_called()
                next(b for b in app.button if b.label=='Atualizar agora').click().run()
                self.assertEqual(len(app.exception), 0)
                self.assertEqual([c.args[2] for c in servico.consultar.call_args_list], ['saldo', 'extrato'])
                self.assertEqual(len(app.json), 0)
                self.assertTrue(any('R$ 23,00' in m.value for m in app.markdown))
                app.run()
                self.assertEqual(servico.consultar.call_count, 2)
                self.assertTrue(any('R$ 23,00' in m.value for m in app.markdown))

    def test_configurar_conta_real_nao_abre_sandbox_nem_rede(self):
        import tempfile
        from pathlib import Path
        from dsystem_erp.repositories.inter import criar_repositorio_demo
        codigo = '''
import streamlit as st
from dsystem_erp.pages.banco_inter import renderizar_banco_inter
st.session_state.update(autenticado=True,username='teste',tipo_login='interno',submodulos=['inter.view','inter.configurar'])
renderizar_banco_inter()
'''
        with tempfile.TemporaryDirectory() as pasta:
            repo = criar_repositorio_demo(Path(pasta)/'demo.sqlite','teste')
            with patch('dsystem_erp.services.inter_runtime.repositorio_configuracao',return_value=repo), \
                    patch('dsystem_erp.services.inter_runtime.abrir_sandbox') as abrir, \
                    patch('dsystem_erp.services.inter_pendente.existe_pendente',return_value=False), \
                    patch('requests.Session.request',side_effect=AssertionError('rede proibida')):
                app = AppTest.from_string(codigo,default_timeout=20).run()
                app.button(key='inter_configurar_producao').click().run()
                self.assertEqual(len(app.exception),0)
                self.assertEqual(app.selectbox(key='inter_config_ambiente').value,'producao')
                self.assertTrue(any('Salvar chaves para consultas reais' in b.label for b in app.button))
                abrir.assert_not_called()

    def test_falha_mysql_nao_expoe_detalhes_nem_finge_falta_de_empresa(self):
        from unittest.mock import Mock
        from mysql.connector import Error
        repo = Mock()
        repo.empresas.side_effect = Error('senha-confidencial', errno=2003)
        with patch('dsystem_erp.services.inter_runtime.repositorio_configuracao', return_value=repo):
            app = self.app(ambiente=None).run()
        self.assertEqual(len(app.exception), 0)
        self.assertIn('MySQL', app.error[0].value)
        self.assertNotIn('senha-confidencial', app.error[0].value)
        self.assertFalse(any('vinculada' in i.value for i in app.info))


if __name__ == '__main__':
    unittest.main()

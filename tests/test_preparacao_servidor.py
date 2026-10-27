import unittest
from unittest.mock import Mock, patch

from scripts.fiscal_ativar_producao import configurar, ENDPOINT_PRODUCAO, ENDPOINT_HOMOLOGACAO
from scripts.inter_agendar_servidor import unidades


class PreparacaoServidorTests(unittest.TestCase):
    def conexao(self, valores=None, admin=1):
        conn = Mock()
        conn.cursor.return_value.fetchone.return_value = {'is_admin': admin}
        conn.cursor.return_value.fetchall.return_value = [
            {'chave': k, 'valor': v} for k, v in (valores or {}).items()]
        return conn

    def test_producao_atomica_sem_rede_sem_alterar_documentos(self):
        conn = self.conexao({'NFSE_NACIONAL_ENDPOINT': ENDPOINT_HOMOLOGACAO})
        with patch('requests.Session.request', side_effect=AssertionError('Rede proibida')):
            result = configurar(conn, 'admin', aplicar=True, config=lambda k,d:d)
        self.assertEqual(result, {'NFE_AMBIENTE': 'producao', 'NFSE_AMBIENTE': 'producao',
                                  'NFSE_NACIONAL_ENDPOINT': ENDPOINT_PRODUCAO})
        conn.commit.assert_called_once()
        escritas = [c for c in conn.cursor.return_value.execute.call_args_list if c.args[0].startswith('INSERT')]
        self.assertEqual(len(escritas), 3)
        self.assertTrue(all('configuracoes_sistema' in c.args[0] for c in escritas))

    def test_previa_nao_grava(self):
        conn = self.conexao()
        configurar(conn, 'admin', config=lambda k,d:d)
        conn.commit.assert_not_called()
        self.assertEqual(conn.cursor.return_value.execute.call_count, 2)

    def test_bloqueia_endpoint_desconhecido_e_municipal_sem_mudancas(self):
        for valores in ({'NFSE_NACIONAL_ENDPOINT':'https://outro.invalid'}, {'NFSE_MODO_EMISSAO':'municipal_soap'}):
            conn = self.conexao(valores)
            with self.assertRaises(ValueError):
                configurar(conn, 'admin', aplicar=True, config=lambda k,d:d)
            conn.commit.assert_not_called()
            conn.rollback.assert_called_once()

    def test_admin_obrigatorio(self):
        conn = self.conexao(admin=0)
        with self.assertRaises(PermissionError):
            configurar(conn, 'comum', aplicar=True)
        conn.commit.assert_not_called()

    def test_erro_na_escrita_desfaz_todas(self):
        conn = self.conexao()
        conn.cursor.return_value.execute.side_effect = [None, None, None, RuntimeError('teste')]
        with self.assertRaises(RuntimeError):
            configurar(conn, 'admin', aplicar=True, config=lambda k,d:d)
        conn.commit.assert_not_called()
        conn.rollback.assert_called_once()

    def test_timer_somente_leitura_brasilia_recuperacao_sem_senha(self):
        nome, servico, timer = unidades('/opt/orcamento', 1, 'Daniel.fabio', 'dsystem', 'dsystem')
        self.assertEqual(nome, 'dsystem-inter-painel-1')
        self.assertIn('User=dsystem', servico)
        self.assertIn('--agendado', servico)
        self.assertNotIn('pagamento', servico)
        self.assertIn('08,12:00:00 America/Sao_Paulo', timer)
        self.assertIn('OnUnitActiveSec=5min', timer)
        self.assertIn('Persistent=true', timer)
        self.assertIn('OnBootSec=2min', timer)

    def test_timer_rejeita_injecao(self):
        for login in ('nome --executar', 'x\nExecStart=errado', '%u', '$USER'):
            with self.assertRaises(ValueError):
                unidades('/opt/orcamento', 1, login, 'dsystem')


if __name__ == '__main__':
    unittest.main()

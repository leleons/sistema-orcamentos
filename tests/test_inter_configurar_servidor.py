import base64
import unittest
from unittest.mock import Mock, patch

from scripts.inter_configurar_servidor import escolher_base, escolher_chave, conferir_empresa, arquivo_protegido, diagnostico_seguro, ETAPAS


class InterConfigurarServidorTests(unittest.TestCase):
    def test_diagnostico_usa_ambiente_do_servico_e_nao_aplica_mudancas(self):
        import io
        import os
        from contextlib import redirect_stdout
        from scripts import inter_configurar_servidor as script
        cofre = Mock()
        cofre.is_symlink.return_value = False
        cofre.exists.return_value = False
        conn = Mock()
        cur = conn.cursor.return_value
        cur.fetchone.return_value = {'conta_mysql': 'erp@localhost'}
        propriedades = {'WorkingDirectory': str(script.ROOT), 'User': 'erp',
                        'EnvironmentFiles': '', 'Environment': 'MYSQL_USER=erp MYSQL_PASSWORD=SEGREDO'}
        sistema = Mock()
        sistema.environ = os.environ
        sistema.name = 'posix'
        sistema.geteuid.return_value = 0
        def config_mysql(base):
            self.assertEqual(os.environ['MYSQL_USER'], 'erp')
            self.assertEqual(os.environ['MYSQL_PASSWORD'], 'SEGREDO')
            return {'database': base}
        saida = io.StringIO()
        with patch.object(script, 'os', sistema), patch.object(script, 'ENV', cofre), \
                patch.dict('sys.modules', {'pwd': Mock(), 'dotenv': Mock()}), patch.dict(os.environ, {}, clear=False), \
                patch.object(script.subprocess, 'check_output', side_effect=lambda cmd, **kw: propriedades[cmd[-2]]), \
                patch.object(script.subprocess, 'run') as run, \
                patch.object(script, 'config_val', return_value='erp'), \
                patch.object(script, 'mysql_connection_config', side_effect=config_mysql), \
                patch('mysql.connector.connect', return_value=conn), \
                patch.object(script, 'RepositorioInter') as repo, redirect_stdout(saida):
            self.assertEqual(script.main(['--diagnostico-mysql']), 0)
        cur.execute.assert_called_once_with('SELECT CURRENT_USER() AS conta_mysql')
        conn.commit.assert_not_called()
        cofre.open.assert_not_called()
        sistema.chown.assert_not_called()
        sistema.umask.assert_not_called()
        repo.assert_not_called()
        run.assert_not_called()
        conn.close.assert_called_once()
        self.assertIn('erp@localhost', saida.getvalue())
        self.assertNotIn('SEGREDO', saida.getvalue())

    def test_diagnostico_nao_aceita_confirmacao_de_escrita(self):
        import io
        from contextlib import redirect_stderr
        from scripts.inter_configurar_servidor import main
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as erro:
            main(['--diagnostico-mysql', '--confirmar', 'CONFIGURAR'])
        self.assertEqual(erro.exception.code, 2)

    def test_diagnostico_identifica_etapa_e_codigo_sem_expor_segredos(self):
        import mysql.connector
        erro = mysql.connector.Error(msg='senha=SEGREDO SQL privado', errno=1044)
        texto = diagnostico_seguro(erro, 'base')
        self.assertIn('criar a base isolada', texto)
        self.assertIn('1044', texto)
        self.assertIn('permissões do usuário MySQL', texto)
        self.assertNotIn('SEGREDO', texto)
        self.assertNotIn('SQL privado', texto)

    def test_diagnostico_cobre_etapas_e_nao_imprime_excecao(self):
        for etapa, descricao in ETAPAS.items():
            texto = diagnostico_seguro(RuntimeError('SEGREDO'), etapa)
            self.assertIn(descricao, texto)
            self.assertNotIn('SEGREDO', texto)
        erro = RuntimeError('SEGREDO')
        erro.errno = 'SEGREDO'
        texto = diagnostico_seguro(erro, 'SEGREDO')
        self.assertNotIn('SEGREDO', texto)

    def test_diagnostico_servico_nao_expoe_comando_ou_output(self):
        import subprocess
        erro = subprocess.CalledProcessError(1, ['SEGREDO'], output='SEGREDO', stderr='SEGREDO')
        texto = diagnostico_seguro(erro, 'restart')
        self.assertIn('reiniciar o ERP', texto)
        self.assertIn('Saída do serviço: 1', texto)
        self.assertNotIn('SEGREDO', texto)

    def test_diagnostico_arquivo_nao_expoe_caminho(self):
        texto = diagnostico_seguro(PermissionError(13, 'SEGREDO', '/SEGREDO'), 'cofre')
        self.assertIn('Código: 13', texto)
        self.assertIn('cofre', texto)
        self.assertNotIn('SEGREDO', texto)

    def test_base_reutiliza_existente_sem_escolher_outra_empresa(self):
        self.assertEqual(escolher_base('', ['atual_inter_config'], 'erp'), 'atual_inter_config')
        self.assertEqual(escolher_base('', [], 'erp'), 'dsystem_inter_config')
        self.assertEqual(escolher_base('outra_inter_config', ['atual_inter_config'], 'erp'), 'outra_inter_config')
        with self.assertRaises(ValueError):
            escolher_base('', ['a_inter_config','b_inter_config'], 'erp')

    def test_base_financeira_e_injecao_sao_rejeitadas(self):
        for nome in ('erp', 'x_inter_config; DROP DATABASE erp', 'inter-config', 'x_inter_config`'):
            with self.assertRaises(ValueError):
                escolher_base(nome, [], 'erp')
        with self.assertRaises(ValueError):
            escolher_base('erp_inter_config', [], 'erp_inter_config')

    def test_nao_rotaciona_chave_existente(self):
        chave = base64.b64encode(b't'*32).decode()
        with patch('scripts.inter_configurar_servidor.os.urandom', side_effect=AssertionError('Não gerar chave')):
            self.assertEqual(escolher_chave(chave, True), chave)
            self.assertEqual(escolher_chave(chave, False), chave)

    def test_dados_cifrados_sem_chave_bloqueiam_novo_cofre(self):
        with patch('scripts.inter_configurar_servidor.os.urandom', side_effect=AssertionError('Não gerar chave')):
            with self.assertRaises(ValueError):
                escolher_chave('', True)
            for invalida in ('invalida', base64.b64encode(b'curta').decode()):
                with self.assertRaises(ValueError):
                    escolher_chave(invalida, False)

    def test_primeiro_cofre_gera_chave_32_bytes(self):
        a, b = escolher_chave('', False), escolher_chave('', False)
        self.assertEqual(len(base64.b64decode(a)), 32)
        self.assertNotEqual(a, b)

    def test_empresa_exige_dados_reais_preserva_identidade(self):
        self.assertEqual(conferir_empresa(None, 'Empresa', '12.345.678/0001-95'), '12345678000195')
        existente = {'nome':'Empresa', 'cnpj':'12345678000195'}
        self.assertEqual(conferir_empresa(existente, 'Empresa', '12345678000195'), existente['cnpj'])
        for nome, cnpj in (('', ''), ('Empresa', '00000000000000'), ('Outra','12345678000195'), ('Empresa','12345678000196')):
            with self.assertRaises(ValueError):
                conferir_empresa(existente, nome, cnpj)

    def test_cofre_recusa_link_diretorio_permissoes_abertas_ou_outro_dono(self):
        for link, regular, modo, uid in ((True,True,0o600,0),(False,False,0o600,0),
                                        (False,True,0o644,0),(False,True,0o600,1000)):
            caminho = Mock()
            caminho.is_symlink.return_value = link
            caminho.exists.return_value = True
            caminho.is_file.return_value = regular
            caminho.stat.return_value = Mock(st_mode=modo, st_uid=uid)
            with self.assertRaises(ValueError):
                arquivo_protegido(caminho)
            caminho.write_text.assert_not_called()

    def test_provisionamento_nao_importa_cliente_nem_chama_api_bancaria(self):
        import ast
        from pathlib import Path
        source = Path(__file__).resolve().parents[1] / 'scripts/inter_configurar_servidor.py'
        arvore = ast.parse(source.read_text(encoding='utf-8'))
        imports = [n.module or '' for n in ast.walk(arvore) if isinstance(n, ast.ImportFrom)]
        imports += [a.name for n in ast.walk(arvore) if isinstance(n, ast.Import) for a in n.names]
        self.assertFalse(any(x in imports for x in ('requests','urllib.request','dsystem_erp.services.inter_api')))


if __name__ == '__main__':
    unittest.main()

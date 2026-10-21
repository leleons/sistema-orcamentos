"""Falhas externas simuladas; nenhum acesso à rede ou gravação em banco."""
import ast
import inspect
import unittest
from unittest.mock import MagicMock, Mock, patch
from urllib.error import HTTPError, URLError

from dsystem_erp.services.dados_publicos import (
    ConsultaDadosPublicosErro, ConsultaDadosPublicosIndisponivel, consultar_cnpj,
)
from tests.test_dados_publicos import _Resposta


class CnpjIndisponibilidadeTests(unittest.TestCase):
    def setUp(self):
        self.pausa = patch('dsystem_erp.services.dados_publicos.sleep').start()
        self.addCleanup(patch.stopall)

    @staticmethod
    def http(codigo, headers=None):
        return HTTPError('https://brasilapi.com.br/api/cnpj/v1/12345678000195', codigo, 'falha simulada', headers or {}, None)

    def test_falhas_transitorias_recuperam_na_segunda_tentativa(self):
        for falha in [self.http(c) for c in (408,500,502,503,504)] + [TimeoutError(), URLError('sem conexão')]:
            with self.subTest(falha=falha):
                self.pausa.reset_mock()
                abrir = Mock(side_effect=[falha, _Resposta({'razao_social':'Empresa Teste'})])
                dados = consultar_cnpj('12.345.678/0001-95', timeout=8, opener=abrir)
                self.assertEqual(dados['nome'], 'Empresa Teste')
                self.assertEqual(abrir.call_count, 2)
                self.pausa.assert_called_once_with(0.5)
                for chamada in abrir.call_args_list:
                    self.assertEqual(chamada.args[0].get_method(), 'GET')
                    self.assertEqual(chamada.kwargs['timeout'], 8)

    def test_falha_persistente_para_apos_alternativa_e_orienta_sem_http500(self):
        abrir = Mock(side_effect=self.http(500))
        with self.assertRaises(ConsultaDadosPublicosIndisponivel) as erro:
            consultar_cnpj('12345678000195', opener=abrir)
        self.assertEqual(abrir.call_count, 3)
        self.assertIn('manualmente', str(erro.exception))
        self.assertIn('preservados', str(erro.exception))
        self.assertNotIn('HTTP 500', str(erro.exception))
        self.assertFalse(erro.exception.repetir)

    def test_nao_repete_400_404_403_429_ou_retry_after(self):
        for codigo, headers in ((400,{}),(404,{}),(403,{}),(429,{}),(503,{'Retry-After':'60'})):
            with self.subTest(codigo=codigo):
                self.pausa.reset_mock()
                abrir = Mock(side_effect=self.http(codigo, headers))
                with self.assertRaises(ConsultaDadosPublicosErro):
                    consultar_cnpj('12345678000195', opener=abrir)
                self.assertEqual(abrir.call_count, 2 if codigo in (429, 503) else 1)
                if codigo in (429, 503):
                    self.assertIn('publica.cnpj.ws', abrir.call_args.args[0].full_url)
                self.pausa.assert_not_called()

    def test_alternativa_mapeia_dados_e_confere_documento(self):
        resposta = {'razao_social': 'Empresa Alternativa', 'simples': {'simples': 'Sim', 'mei': 'Não'},
                    'estabelecimento': {'cnpj': '12345678000195', 'nome_fantasia': 'Teste',
                        'cidade': {'nome': 'Sabará'}, 'estado': {'sigla': 'MG'},
                        'tipo_logradouro': 'RUA', 'logradouro': 'Um', 'numero': '10',
                        'cep': '34505-000', 'ddd1': '31', 'telefone1': '33334444',
                        'email': 'teste@example.com', 'atividade_principal': {'descricao': 'Suporte'},
                        'situacao_cadastral': 'Ativa'}}
        abrir = Mock(side_effect=[self.http(500), self.http(500), _Resposta(resposta)])
        dados = consultar_cnpj('12345678000195', opener=abrir)
        self.assertEqual(dados['nome'], 'Empresa Alternativa')
        self.assertEqual(dados['cidade_estado'], 'Sabará / MG')
        self.assertEqual(dados['endereco'], 'RUA Um')
        self.assertEqual(dados['telefone'], '3133334444')
        self.assertEqual(dados['situacao_simples_nacional'], '3')
        self.assertEqual(dados['ramo_atividade'], 'Suporte')
        self.assertEqual(dados['cep'], '34505000')
        self.assertEqual(abrir.call_args.args[0].full_url, 'https://publica.cnpj.ws/cnpj/12345678000195')
        resposta['simples'] = None
        abrir = Mock(side_effect=[self.http(429), _Resposta(resposta)])
        self.assertEqual(consultar_cnpj('12345678000195', opener=abrir)['optante_simples_nacional'], '')
        resposta['estabelecimento']['cnpj'] = '00000000000191'
        abrir = Mock(side_effect=[self.http(429), _Resposta(resposta)])
        with self.assertRaises(ConsultaDadosPublicosIndisponivel):
            consultar_cnpj('12345678000195', opener=abrir)

    def test_alternativa_nao_aceita_payload_vazio_ou_repete_limite(self):
        for retorno in (_Resposta({}), _Resposta({'estabelecimento': []}), self.http(429)):
            abrir = Mock(side_effect=[self.http(429), retorno])
            with self.assertRaises(ConsultaDadosPublicosIndisponivel):
                consultar_cnpj('12345678000195', opener=abrir)
            self.assertEqual(abrir.call_count, 2)

    def test_cnpj_invalido_nao_acessa_servico(self):
        abrir = Mock()
        with self.assertRaises(ConsultaDadosPublicosErro):
            consultar_cnpj('123', opener=abrir)
        abrir.assert_not_called()
        self.pausa.assert_not_called()

    def test_sucesso_nao_faz_nova_consulta(self):
        abrir = Mock(return_value=_Resposta({'razao_social':'Empresa Teste'}))
        self.assertEqual(consultar_cnpj('12345678000195', opener=abrir)['nome'], 'Empresa Teste')
        abrir.assert_called_once()
        self.pausa.assert_not_called()

    def test_novo_e_edicao_preservam_campos_quando_servico_falha(self):
        from dsystem_erp.pages import clientes
        arvore = ast.parse(inspect.getsource(clientes.renderizar_cadastro_cliente_fornecedor))
        for acao in ('consultar_cnpj_agora', 'buscar_cnpj_edicao'):
            with self.subTest(acao=acao):
                bloco = next(n for n in ast.walk(arvore) if isinstance(n, ast.If)
                             and isinstance(n.test, ast.Name) and n.test.id == acao)
                tela = MagicMock()
                estado = {'cad_cli_nome':'Texto já digitado', 'edit_cli_nome_9':'Cliente salvo', 'cad_cli_cpf_cnpj':'12345678000195'}
                tela.session_state = estado.copy()
                ambiente = dict(vars(clientes), st=tela, consultar_cnpj=Mock(side_effect=ConsultaDadosPublicosIndisponivel('Tente mais tarde')),
                                cnpj_consulta='12345678000195', cnpj_edicao_consulta='12345678000195', id_edit_cli=9)
                ambiente[acao] = True
                exec(compile(ast.Module(body=[bloco], type_ignores=[]), '<consulta-isolada>', 'exec'), ambiente)
                self.assertEqual(tela.session_state, estado)
                tela.warning.assert_called_once()
                tela.error.assert_not_called()
                tela.rerun.assert_not_called()


if __name__ == '__main__':
    unittest.main()

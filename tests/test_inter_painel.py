import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock

from dsystem_erp.repositories.inter import criar_repositorio_demo
from dsystem_erp.services.inter_api import InterErro, decifrar_credencial
from dsystem_erp.services.inter_painel import PainelInter, CONTEXTO, slot_atual, proxima_atualizacao, normalizar_transacao, reais


def usuario_teste():
    return {'username': 'teste', 'autenticado': True, 'tipo_login': 'interno', 'is_admin': 1,
            'submodulos': ['inter.view', 'inter.configurar']}


def credencial_ficticia(repo):
    with repo.transacao() as c:
        repo.executar(c, 'INSERT INTO inter_contas (empresa_id,ambiente,conta,credencial_secret) VALUES (%s,%s,%s,%s)',
                      (1, 'producao', '', 'credencial-ficticia-nao-utilizavel'))


def transacao(identificador='1', direcao='C', valor='123.45'):
    return {'idTransacao': identificador, 'dataTransacao': '2026-10-20', 'tipoOperacao': direcao,
            'tipoTransacao': 'PIX', 'valor': valor, 'descricao': 'Descrição de teste'}


class InterPainelTests(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        self.repo = criar_repositorio_demo(Path(self.pasta.name)/'painel.sqlite', 'teste')
        credencial_ficticia(self.repo)
        self.usuario = usuario_teste()
        self.agora = datetime(2026, 10, 21, 14, tzinfo=timezone.utc)  # 11h BRT
        self.api = Mock()
        self.obter = Mock(side_effect=lambda nome: dict(self.usuario))
        self.painel = PainelInter(self.repo, self.api, obter_usuario=self.obter, chave=lambda: b'x'*32, clock=lambda: self.agora)
        self.respostas()

    def respostas(self, itens=None):
        itens = [transacao(), transacao('2', 'D', '20.15')] if itens is None else itens
        self.api.consultar.side_effect = [{'disponivel': '890.10'}, {'transacoes': itens, 'totalPaginas': 1, 'totalElementos': len(itens)}]

    def test_snapshot_cifrado_sem_rede_ao_ler(self):
        self.assertIsNone(self.painel.ler(1, self.usuario)['dados'])
        self.api.consultar.assert_not_called()
        self.assertEqual(self.painel.atualizar(1, self.usuario), 'atualizado')
        dados = self.painel.ler(1, self.usuario)['dados']
        self.assertEqual(dados['saldo'], '890.10')
        self.assertEqual((dados['inicio'], dados['fim']), ('2026-09-22', '2026-10-21'))
        self.assertEqual(len(dados['transacoes']), 2)
        self.assertEqual([c.args[2] for c in self.api.consultar.call_args_list], ['saldo', 'extrato'])
        with self.repo.transacao() as c:
            self.repo.executar(c, 'SELECT snapshot_secret FROM inter_painel WHERE empresa_id=1')
            cifrado = c.fetchone()['snapshot_secret']
        self.assertNotIn('890.10', cifrado)
        with self.assertRaises(InterErro):
            decifrar_credencial(cifrado, 2, b'x'*32, CONTEXTO)

    def test_paginas_completas_e_valor_debito_positivo_ou_negativo(self):
        self.api.consultar.side_effect = [{'disponivel': 0},
            {'transacoes': [transacao()], 'totalPaginas': 2, 'totalElementos': 2},
            {'transacoes': [transacao('2', 'D', '-20.15')], 'totalPaginas': 2, 'totalElementos': 2}]
        self.painel.atualizar(1, self.usuario)
        self.assertEqual([c.kwargs['params']['pagina'] for c in self.api.consultar.call_args_list[1:]], [0, 1])
        self.assertEqual(self.painel.ler(1, self.usuario)['dados']['transacoes'][1]['valor'], '20.15')

    def test_falha_preserva_snapshot_e_libera_trava_sem_detalhes(self):
        self.painel.atualizar(1, self.usuario)
        anterior = self.painel.ler(1, self.usuario)['dados']
        self.api.consultar.side_effect = RuntimeError('segredo-que-nao-pode-vazar')
        with self.assertRaises(InterErro) as erro:
            self.painel.atualizar(1, self.usuario)
        self.assertNotIn('segredo', str(erro.exception))
        atual = self.painel.ler(1, self.usuario)
        self.assertEqual(atual['dados'], anterior)
        self.assertEqual(atual['erro'], 'FALHA_NA_ATUALIZACAO')
        self.respostas([])
        self.assertEqual(self.painel.atualizar(1, self.usuario), 'atualizado')
        self.assertIsNone(self.painel.ler(1, self.usuario)['erro'])

    def test_agenda_dois_horarios_deduplicados_no_fuso_brasilia(self):
        self.painel.configurar_agenda(1, self.usuario, ativo=True)
        self.assertTrue(self.painel.ler(1, self.usuario)['agenda_ativa'])
        self.agora = self.agora.replace(hour=10, minute=59)  # 07:59
        self.assertEqual(self.painel.atualizar(1, self.usuario, agendado=True), 'ja_verificado')
        self.agora += timedelta(minutes=1)
        self.assertEqual(self.painel.atualizar(1, self.usuario, agendado=True), 'atualizado')
        self.assertEqual(self.painel.atualizar(1, self.usuario, agendado=True), 'ja_verificado')
        self.respostas()
        self.agora = self.agora.replace(hour=15)  # meio-dia
        self.assertEqual(self.painel.atualizar(1, self.usuario, agendado=True), 'atualizado')
        self.agora = self.agora.replace(hour=22)
        self.assertEqual(self.painel.atualizar(1, self.usuario, agendado=True), 'ja_verificado')
        self.assertEqual(self.api.consultar.call_count, 4)

    def test_falha_agendada_nao_dispara_loop_e_manual_pode_tentar(self):
        self.painel.configurar_agenda(1, self.usuario, ativo=True)
        self.api.consultar.side_effect = RuntimeError('indisponível')
        with self.assertRaises(InterErro):
            self.painel.atualizar(1, self.usuario, agendado=True)
        self.assertEqual(self.painel.atualizar(1, self.usuario, agendado=True), 'aguardando_nova_tentativa')
        self.respostas()
        self.assertEqual(self.painel.atualizar(1, self.usuario), 'atualizado')
        self.assertEqual(self.painel.atualizar(1, self.usuario, agendado=True), 'ja_verificado')

    def test_falha_recupera_apos_cinco_minutos_sem_consumir_slot(self):
        self.painel.configurar_agenda(1, self.usuario, ativo=True)
        self.api.consultar.side_effect = RuntimeError('indisponivel')
        with self.assertRaises(InterErro):
            self.painel.atualizar(1, self.usuario, agendado=True)
        self.agora += timedelta(minutes=4)
        self.assertEqual(self.painel.atualizar(1, self.usuario, agendado=True), 'aguardando_nova_tentativa')
        self.agora += timedelta(minutes=1)
        self.respostas()
        self.assertEqual(self.painel.atualizar(1, self.usuario, agendado=True), 'atualizado')
        self.assertEqual(self.painel.atualizar(1, self.usuario, agendado=True), 'ja_verificado')
        self.assertEqual(self.api.consultar.call_count, 3)

    def test_credencial_alterada_recupera_mesmo_slot(self):
        self.painel.configurar_agenda(1, self.usuario, ativo=True)
        self.painel.atualizar(1, self.usuario, agendado=True)
        with self.repo.transacao() as c:
            c.execute("UPDATE inter_contas SET credencial_secret='nova-configuracao'")
        self.assertIsNone(self.painel.ler(1, self.usuario)['dados'])
        self.respostas()
        self.assertEqual(self.painel.atualizar(1, self.usuario, agendado=True), 'atualizado')
        self.assertIsNotNone(self.painel.ler(1, self.usuario)['dados'])

    def test_trava_de_processo_encerrado_expira_e_recupera(self):
        self.painel.configurar_agenda(1, self.usuario, ativo=True)
        with self.repo.transacao() as c:
            self.repo.executar(c, '''INSERT INTO inter_painel
                (empresa_id,lock_token,lock_ate,tentativa_em,ultimo_slot)
                VALUES (%s,%s,%s,%s,%s)''', (1, 'interrompido',
                (self.agora + timedelta(minutes=20)).isoformat(), self.agora.isoformat(), slot_atual(self.agora)))
        self.assertEqual(self.painel.atualizar(1, self.usuario, agendado=True), 'em_andamento')
        self.agora += timedelta(minutes=21)
        self.assertEqual(self.painel.atualizar(1, self.usuario, agendado=True), 'atualizado')

    def test_revogacao_no_erp_bloqueia_leitura_cache_e_atualizacao(self):
        self.painel.atualizar(1, self.usuario)
        sessao_antiga = dict(self.usuario)
        self.usuario['submodulos'] = []
        for funcao in (self.painel.ler, self.painel.atualizar):
            with self.assertRaises(PermissionError):
                funcao(1, sessao_antiga)

    def test_empresa_nao_autorizada_e_portal_cliente_nao_leem_cache(self):
        self.painel.atualizar(1, self.usuario)
        with self.assertRaises(PermissionError):
            self.painel.ler(2, self.usuario)
        with self.assertRaises(PermissionError):
            self.painel.ler(1, {**self.usuario, 'tipo_login': 'cliente'})
        with self.repo.transacao() as c:
            c.execute('DELETE FROM inter_acessos')
        with self.assertRaises(PermissionError):
            self.painel.ler(1, self.usuario)

    def test_agenda_exige_admin_e_vinculo_explicito(self):
        with self.assertRaises(PermissionError):
            self.painel.atualizar(1, self.usuario, agendado=True)
        self.usuario['is_admin'] = 0
        with self.assertRaises(PermissionError):
            self.painel.configurar_agenda(1, self.usuario, ativo=True)
        self.api.consultar.assert_not_called()

    def test_cache_nao_reaproveita_credencial_de_outra_conta(self):
        self.painel.atualizar(1, self.usuario)
        with self.repo.transacao() as c:
            c.execute("UPDATE inter_contas SET credencial_secret='outra-conta'")
        self.assertIsNone(self.painel.ler(1, self.usuario)['dados'])

    def test_concorrencia_manual_e_agendado_nao_duplica_requisicoes(self):
        respostas = iter([{'disponivel': '10'}, {'transacoes': [], 'totalPaginas': 0, 'totalElementos': 0}])
        def consultar(*args, **kwargs):
            self.assertEqual(self.painel.atualizar(1, self.usuario), 'em_andamento')
            return next(respostas)
        self.api.consultar.side_effect = consultar
        self.assertEqual(self.painel.atualizar(1, self.usuario), 'atualizado')
        self.assertEqual(self.api.consultar.call_count, 2)

    def test_extrato_incompleto_duplicado_ou_mudando_falha_sem_publicar(self):
        for respostas in (
            [{'transacoes': [], 'totalPaginas': 99}],
            [{'transacoes': [], 'totalPaginas': 1, 'totalElementos': 1}],
            [{'transacoes': [transacao(), transacao()], 'totalPaginas': 1}],
            [{'transacoes': [transacao()], 'totalPaginas': 2}, {'transacoes': [], 'totalPaginas': 3}],
        ):
            with self.subTest(respostas=respostas):
                self.api.consultar.side_effect = [{'disponivel': 10}, *respostas]
                with self.assertRaises(InterErro):
                    self.painel.atualizar(1, self.usuario)
                self.assertIsNone(self.painel.ler(1, self.usuario)['dados'])

    def test_retorno_invalido_nao_inventa_saldo_zero(self):
        for saldo in ({}, {'disponivel': 'NaN'}, {'disponivel': True}, {'disponivel': '0.001'}):
            self.api.consultar.side_effect = [saldo]
            with self.assertRaises(InterErro):
                self.painel.atualizar(1, self.usuario)
        self.assertIsNone(self.painel.ler(1, self.usuario)['dados'])

    def test_formatacao_e_direcao_desconhecida(self):
        self.assertEqual(reais('12345.67'), 'R$ 12.345,67')
        with self.assertRaises(InterErro):
            normalizar_transacao(transacao(direcao='?'))

    def test_proximo_horario_e_virada_do_dia(self):
        antes = datetime(2026, 10, 21, 10, 59, tzinfo=timezone.utc)
        self.assertIsNone(slot_atual(antes))
        self.assertEqual(proxima_atualizacao(antes).hour, 8)
        self.assertEqual(proxima_atualizacao(antes + timedelta(hours=1)).hour, 12)
        depois = antes + timedelta(hours=6)
        self.assertEqual(proxima_atualizacao(depois).day, 22)
        self.assertEqual(slot_atual(depois), '2026-10-21T12:00')


if __name__ == '__main__':
    unittest.main()

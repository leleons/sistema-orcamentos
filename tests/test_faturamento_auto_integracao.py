"""Exercita a integração sem importar o entrypoint que abre o banco real."""
import ast
import json
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


class FaturamentoAutomaticoIntegracaoTests(unittest.TestCase):
    def setUp(self):
        arvore = ast.parse((Path(__file__).resolve().parents[1] / 'orcamento.py').read_text(encoding='utf-8-sig'))
        funcao = next(n for n in arvore.body if isinstance(n, ast.FunctionDef) and n.name == 'faturar_lancamento_com_integracoes')
        self.conn = MagicMock()
        self.c = self.conn.cursor.return_value
        self.c.fetchone.side_effect = [dict(status='Aberto'), dict(id=8), None]
        parcela = dict(documento='FAT-1', quantidade=1, rotulo='1/1', valor=100, vencimento='2026-10-01')
        self.ctx = dict(date=date, json=json, st=SimpleNamespace(session_state={'username': 'teste'}),
            conectar_banco=lambda: self.conn, itens_faturamento_lista=json.loads,
            agora_br=lambda: '2026-09-25', data_para_banco_br=str,
            gerar_parcelas_faturamento=lambda fat: [parcela], registrar_evento_sistema=MagicMock(),
            config_sistema_val=MagicMock(), salvar_retorno_nota_fiscal=MagicMock())
        exec(compile(ast.Module(body=[funcao], type_ignores=[]), '<integracao-isolada>', 'exec'), self.ctx)
        self.faturar = self.ctx['faturar_lancamento_com_integracoes']
        self.fat = dict(id=1, status='Aberto', cliente='TESTE', emite_nf='Sim', valor_total=100,
                        itens=json.dumps([dict(tipo_item='Serviço', desc='Teste', qtd=1, vunit=100, vtotal=100)]))
        from dsystem_erp.services.fiscal_automatico import hash_origem
        preflight = patch('dsystem_erp.services.fiscal_automatico.preparar_antes_de_faturar', return_value=hash_origem(self.fat))
        self.preflight = preflight.start()
        self.addCleanup(preflight.stop)
        prontidao = patch('dsystem_erp.services.fiscal_documentos.resultado_emissao', return_value=dict(
            fiscal_pronto=True, mensagem='Notas autorizadas e PDFs prontos para baixar juntos.'))
        self.prontidao = prontidao.start()
        self.addCleanup(prontidao.stop)

    def test_fiscal_so_inicia_depois_do_commit_financeiro(self):
        def processar(*args):
            self.conn.commit.assert_called_once()
            return [dict(tipo='Serviço', estado='Autorizada')]
        with patch('dsystem_erp.services.fiscal_automatico.processar_emissoes', side_effect=processar) as envio:
            resultado = self.faturar(self.fat)
            self.assertTrue(resultado['ok'])
            self.assertIn('PDFs prontos', resultado['mensagem'])
            self.assertTrue(resultado['fiscal_pronto'])
            envio.assert_called_once()

    def test_erro_fiscal_nao_desfaz_faturamento_ja_gravado(self):
        with patch('dsystem_erp.services.fiscal_automatico.processar_emissoes', side_effect=RuntimeError('Certificado ausente')):
            resultado = self.faturar(self.fat)
        self.assertTrue(resultado['ok'])
        self.assertIn('pendente de conferência', resultado['mensagem'])
        self.assertFalse(resultado['fiscal_pronto'])
        self.conn.commit.assert_called_once()
        self.conn.rollback.assert_not_called()

    def test_clique_repetido_nao_duplica_financeiro_nem_dispara_fiscal(self):
        self.c.fetchone.side_effect = [dict(status='Faturado')]
        with patch('dsystem_erp.services.fiscal_automatico.processar_emissoes') as envio:
            self.assertFalse(self.faturar(self.fat)['ok'])
            envio.assert_not_called()
        self.conn.commit.assert_not_called()
        self.assertFalse(any('INSERT INTO' in chamada.args[0] for chamada in self.c.execute.call_args_list))

    def test_opcao_da_listagem_e_gravada_na_mesma_transacao(self):
        self.c.fetchone.side_effect = [self.fat, dict(id=8), None]
        with patch('dsystem_erp.services.fiscal_automatico.processar_emissoes', return_value=[]):
            self.assertTrue(self.faturar(self.fat, emitir_automaticamente=True)['ok'])
        self.c.execute.assert_any_call('UPDATE faturamento SET emitir_automaticamente=? WHERE id=?', (1,1))
        self.conn.commit.assert_called_once()

    def test_somente_espelho_nao_ativa_emissao_mesmo_em_lote(self):
        self.c.fetchone.side_effect = [dict(self.fat, documentos_entrega='Somente espelho'), dict(id=8), None]
        with patch('dsystem_erp.services.fiscal_automatico.processar_emissoes', return_value=[]):
            self.assertTrue(self.faturar(self.fat, emitir_automaticamente=True)['ok'])
        self.c.execute.assert_any_call('UPDATE faturamento SET emitir_automaticamente=? WHERE id=?', (0,1))

    def test_preparacao_incompleta_nao_fatura_nem_emite(self):
        self.preflight.side_effect = ValueError('Produto: falta NCM conferido.')
        with patch('dsystem_erp.services.fiscal_automatico.processar_emissoes') as envio:
            resultado = self.faturar(self.fat, emitir_automaticamente=True)
        self.assertFalse(resultado['ok'])
        self.assertIn('falta NCM', resultado['mensagem'])
        self.conn.commit.assert_not_called()
        self.c.execute.assert_not_called()
        envio.assert_not_called()

    def test_autorizada_sem_pdf_nao_informa_pronta(self):
        self.prontidao.return_value = dict(fiscal_pronto=False, mensagem='Produto: PDF pendente')
        with patch('dsystem_erp.services.fiscal_automatico.processar_emissoes', return_value=[dict(tipo='Produto', estado='Autorizada')]):
            resultado = self.faturar(self.fat)
        self.assertTrue(resultado['ok'])  # Financeiro já gravado não deve ser repetido.
        self.assertFalse(resultado['fiscal_pronto'])
        self.assertIn('PDF pendente', resultado['mensagem'])

    def test_alteracao_durante_preparacao_impede_baixa(self):
        self.c.fetchone.side_effect = [dict(self.fat, valor_total=900)]
        with patch('dsystem_erp.services.fiscal_automatico.processar_emissoes') as envio:
            resultado = self.faturar(self.fat, emitir_automaticamente=True)
        self.assertFalse(resultado['ok'])
        self.conn.commit.assert_not_called()
        self.assertFalse(any('INSERT INTO' in call.args[0] for call in self.c.execute.call_args_list))
        envio.assert_not_called()

import unittest
from datetime import date, timedelta
from decimal import Decimal

from dsystem_erp.services.dashboard import resumo_financeiro, total_saldo, resumo_atendimentos, resumo_orcamentos


class DashboardTests(unittest.TestCase):
    def test_prazos_acumulados_e_saldo_parcial(self):
        hoje = date(2026, 9, 3)
        dados = [dict(id=i, data_vencimento=hoje + timedelta(days=d),
                      valor_total='100.00', valor_baixado='25.00', status='Aberto')
                 for i, d in enumerate([-1, 0, 5, 6, 10, 11, 15, 16])]
        resumo = resumo_financeiro(dados, hoje)
        self.assertEqual([len(resumo['janelas'][d]) for d in (5, 10, 15)], [2, 4, 6])
        self.assertEqual(total_saldo(resumo['vencidos']), Decimal('75'))
        self.assertEqual(total_saldo(resumo['janelas'][15]), Decimal('450'))
        self.assertNotIn('saldo', dados[0])

    def test_encerrados_e_datas_invalidas(self):
        dados = [dict(valor_total=100, status=s) for s in ('Pago', 'Recebido', 'Cancelado', 'Baixado por perda')]
        dados += [dict(valor_total='R$ 1.234,56', status='Aberto', data_vencimento='invalida'),
                  dict(valor_total=100, valor_baixado=100), dict(valor_total='NaN')]
        resumo = resumo_financeiro(dados, date(2026, 9, 3))
        self.assertEqual(len(resumo['abertos']), 1)
        self.assertEqual(total_saldo(resumo['sem_data']), Decimal('1234.56'))

    def test_atendimentos_prazos_sem_inventar_deadline_checklist(self):
        hoje = date(2026, 9, 3)
        resumo = resumo_atendimentos(
            [dict(id=1, status='Em Andamento'), dict(id=2, status='Concluído')],
            [dict(id=3, status='Agendado', data_visita='02/09/2026'),
             dict(id=4, status='Realizado', data_visita='01/09/2026')],
            [dict(id=5, status='Aberto', data_solicitada='01/09/2026', ajuste_data='05/09/2026')], hoje)
        self.assertEqual(len(resumo['Em aberto']), 3)
        self.assertEqual(len(resumo['Pendentes']), 2)
        self.assertEqual([r['ID'] for r in resumo['Vencidos']], [3])
        self.assertEqual([r['ID'] for r in resumo['A vencer (15 dias)']], [5])

    def test_orcamentos_faturados_e_cancelados(self):
        dados = [dict(orc_id=1, status='Aberto', data_validade='01/09/2026'),
                 dict(orc_id=2, status='Aberto', faturamento_id=9),
                 dict(orc_id=3, status='Aprovado e lançado'),
                 dict(orc_id=4, status='Cancelado'),
                 dict(orc_id=5, status='Aberto', data_validade='20/09/2026')]
        resumo = resumo_orcamentos(dados, date(2026, 9, 3))
        self.assertEqual([r['orc_id'] for r in resumo['Não faturados']], [1, 5])
        self.assertEqual([r['orc_id'] for r in resumo['Vencidos']], [1])
        self.assertEqual([r['orc_id'] for r in resumo['Faturados']], [2, 3])

import unittest
from dsystem_erp.services.nfse_item_cadastro import buscar_servico_dos_itens


class ServicoCadastroTests(unittest.TestCase):
    def setUp(self):
        self.catalogo = [dict(id=1, nome='Suporte técnico em informática', codigo_servico='01.07.01', ativo='Sim'),
                         dict(id=2, nome='Manutenção de notebooks', codigo_servico='14.01.01', ativo='Sim')]

    def test_nome_exato_normalizado_e_vinculo_tem_prioridade(self):
        for item in [dict(desc='  SUPORTE TECNICO EM INFORMATICA '), dict(desc='Descrição livre', servico_id=1)]:
            resultado = buscar_servico_dos_itens([item], self.catalogo)
            self.assertEqual(resultado['servico']['codigo_servico'], '01.07.01')

    def test_nome_parcial_id_inexistente_e_codigo_diferente_bloqueiam(self):
        for item in [dict(desc='Suporte'), dict(desc='Suporte técnico em informática', servico_id=999),
                     dict(desc='Suporte técnico em informática', codigo_servico='140101')]:
            self.assertIsNone(buscar_servico_dos_itens([item], self.catalogo)['servico'])

    def test_duplicado_inativo_e_codigo_incompleto_bloqueiam(self):
        item = dict(desc='Suporte técnico em informática')
        for catalogo in [self.catalogo + [dict(self.catalogo[0], id=3)],
                         [dict(self.catalogo[0], ativo='Não')],
                         [dict(self.catalogo[0], codigo_servico='01.07')]]:
            self.assertIsNone(buscar_servico_dos_itens([item], catalogo)['servico'])

    def test_multiplos_servicos_nao_recebem_codigo_do_primeiro(self):
        itens = [dict(desc=s['nome']) for s in self.catalogo]
        self.assertIsNone(buscar_servico_dos_itens(itens, self.catalogo)['servico'])
        self.assertEqual(buscar_servico_dos_itens([itens[0], itens[0]], self.catalogo)['servico']['id'], 1)

    def test_produtos_nao_classificam_servico(self):
        self.assertIsNone(buscar_servico_dos_itens([dict(desc='Suporte técnico em informática', tipo_item='Produto')], self.catalogo)['servico'])

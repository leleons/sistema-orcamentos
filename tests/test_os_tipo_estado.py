import unittest

from dsystem_erp.pages.ordens_servico import limpar_equipamento_ao_trocar_tipo


class TrocaTipoTests(unittest.TestCase):
    def test_limpa_apenas_rascunho_do_equipamento_atual(self):
        estado = {'os_novo_0_tipo_0': 'Notebook', 'os_novo_0_cpu_0': 'Outro aparelho',
                  'os_novo_0_equip_0': 'Impressora', 'os_novo_0_cpu_1': 'Preservar',
                  'os_novo_nome_0_1': 'Cliente', 'os_itens_temp': [{'tipo': 'Desktop'}]}
        limpar_equipamento_ao_trocar_tipo(estado, 0, 0)
        self.assertNotIn('os_novo_0_cpu_0', estado)
        self.assertNotIn('os_novo_0_equip_0', estado)
        self.assertEqual(estado['os_novo_0_tipo_0'], 'Notebook')
        self.assertEqual(estado['os_novo_0_cpu_1'], 'Preservar')
        self.assertEqual(estado['os_novo_nome_0_1'], 'Cliente')
        self.assertEqual(len(estado['os_itens_temp']), 1)

import unittest
from dsystem_erp.pages.infraestrutura import (
    CAMPOS_HARDWARE_PC, compor_item_composto_infra, decompor_item_composto_infra,
)


class HardwarePcTests(unittest.TestCase):
    def test_salvar_e_reabrir_todos_campos(self):
        valores = {campo['chave']: f"valor {i}" for i, campo in enumerate(CAMPOS_HARDWARE_PC)}
        valores.update(tipo='Notebook', nome='Financeiro', anydesk='123 / senha',
                       remote_email='teste@example.com', remote_nome='PC01',
                       informacoes='PC da tesouraria', usuario='financeiro', senha='segredo')
        gravado = compor_item_composto_infra('pcs_acessos', valores)
        self.assertEqual(decompor_item_composto_infra('pcs_acessos', gravado), valores)
        self.assertEqual(len(CAMPOS_HARDWARE_PC), 12)
        self.assertIn('Informações: PC da tesouraria', gravado)
        self.assertIn('Usuário: financeiro', gravado)
        self.assertIn('Senha: segredo', gravado)

    def test_cadastro_antigo_preservado(self):
        antigo = 'Desktop | Recepção | AnyDesk: 123 | Remote: teste@example.com / PC01'
        campos = decompor_item_composto_infra('pcs_acessos', antigo)
        self.assertEqual(campos['remote_nome'], 'PC01')
        self.assertEqual(campos['nome'], 'Recepção')
        self.assertEqual(campos['informacoes'], '')
        self.assertEqual(campos['usuario'], '')
        self.assertEqual(campos['senha'], '')
        self.assertTrue(all(campos[c['chave']] == '' for c in CAMPOS_HARDWARE_PC))

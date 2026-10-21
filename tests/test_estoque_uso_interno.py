import unittest
from dsystem_erp.services.estoque_notas import validar_saida_com_cliente


class UsoInternoTests(unittest.TestCase):
    def test_exige_usuario(self):
        self.assertIn('usuário', validar_saida_com_cliente('', '', 1, 7, uso_interno=True))

    def test_usuario_sem_cliente(self):
        self.assertIsNone(validar_saida_com_cliente('daniel', 'Daniel (daniel)', 1, 7, uso_interno=True))

    def test_nao_permite_saldo_negativo(self):
        self.assertIsNotNone(validar_saida_com_cliente('daniel', 'Daniel', 8, 7, uso_interno=True))
        self.assertIsNotNone(validar_saida_com_cliente('daniel', 'Daniel', 0, 7, uso_interno=True))

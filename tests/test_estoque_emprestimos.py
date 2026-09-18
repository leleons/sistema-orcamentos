import unittest
from datetime import date

from dsystem_erp.services.estoque_emprestimos import (
    data_limite_emprestimo,
    emprestimo_atrasado,
)


class EstoqueEmprestimosTests(unittest.TestCase):
    def test_prazo_padrao_e_de_dois_dias(self):
        self.assertEqual(data_limite_emprestimo(date(2026, 9, 1)), date(2026, 9, 3))

    def test_alerta_inicia_no_dia_limite_enquanto_estiver_aberto(self):
        emprestimo = {"status": "Em aberto", "data_limite": "2026-09-03"}
        self.assertFalse(emprestimo_atrasado(emprestimo, date(2026, 9, 2)))
        self.assertTrue(emprestimo_atrasado(emprestimo, date(2026, 9, 3)))

    def test_emprestimo_concluido_nao_gera_alerta(self):
        emprestimo = {"status": "Concluído", "data_limite": "01/09/2026"}
        self.assertFalse(emprestimo_atrasado(emprestimo, date(2026, 9, 10)))


if __name__ == "__main__":
    unittest.main()

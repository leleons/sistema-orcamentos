import sqlite3
import unittest

from dsystem_erp.pages.atendimentos import filtro_status_agenda


class AgendaFiltroStatusTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.addCleanup(self.conn.close)
        self.conn.execute("CREATE TABLE agenda_visitas (status TEXT)")
        self.status = ["Agendado", "Realizado", "Concluído", " CONCLUIDO ", "Atrasado", None]
        self.conn.executemany("INSERT INTO agenda_visitas VALUES (?)", [(s,) for s in self.status])

    def consultar(self, filtro="Não realizados"):
        sql, params = filtro_status_agenda(filtro)
        return [r[0] for r in self.conn.execute("SELECT status FROM agenda_visitas WHERE 1=1" + sql, params)]

    def test_padrao_oculta_realizados_e_concluidos(self):
        self.assertEqual(self.consultar(), ["Agendado", "Atrasado", None])

    def test_todos_preserva_historico_completo(self):
        self.assertEqual(self.consultar("Todos"), self.status)

    def test_status_especifico(self):
        self.assertEqual(self.consultar("Atrasado"), ["Atrasado"])


if __name__ == "__main__":
    unittest.main()

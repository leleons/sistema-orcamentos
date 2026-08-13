import unittest

from dsystem_erp.repositories.faturamento import (
    listar_faturados_para_nf,
    listar_faturamentos,
    listar_faturamentos_para_nf,
)


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.last_sql = ""

    def execute(self, sql, params=()):
        self.last_sql = sql

    def fetchall(self):
        if "status='Faturado'" in self.last_sql:
            return [row for row in self.rows if row.get("emite_nf") == "Sim" and row.get("status") == "Faturado"]
        if "emite_nf='Sim'" in self.last_sql:
            return [row for row in self.rows if row.get("emite_nf") == "Sim"]
        return self.rows


class FakeConnection:
    def __init__(self, rows):
        self.rows = rows
        self.closed = False

    def cursor(self):
        return FakeCursor(self.rows)

    def close(self):
        self.closed = True


class FaturamentoRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.conn = FakeConnection([
            {"id": 1, "cliente": "A", "emite_nf": "Sim", "status": "Aberto"},
            {"id": 2, "cliente": "B", "emite_nf": "Sim", "status": "Faturado"},
            {"id": 3, "cliente": "C", "emite_nf": "Nao", "status": "Faturado"},
        ])

    def factory(self):
        return self.conn

    def test_listar_faturamentos(self):
        self.assertEqual(len(listar_faturamentos(self.factory)), 3)
        self.assertTrue(self.conn.closed)

    def test_listar_faturamentos_para_nf(self):
        self.assertEqual([r["id"] for r in listar_faturamentos_para_nf(self.factory)], [1, 2])

    def test_listar_faturados_para_nf(self):
        self.assertEqual([r["id"] for r in listar_faturados_para_nf(self.factory)], [2])


if __name__ == "__main__":
    unittest.main()

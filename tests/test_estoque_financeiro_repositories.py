import unittest

from dsystem_erp.repositories.estoque import listar_alertas_estoque_minimo, listar_estoque
from dsystem_erp.repositories.financeiro import listar_recorrencias


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.sql = None
        self.params = None

    def execute(self, sql, params=()):
        self.sql = sql
        self.params = params

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, rows):
        self.cursor_obj = FakeCursor(rows)
        self.closed = False

    def cursor(self):
        return self.cursor_obj

    def close(self):
        self.closed = True


class RepositoryTests(unittest.TestCase):
    def make_factory(self, rows):
        conn = FakeConnection(rows)
        return lambda: conn, conn

    def test_listar_estoque_orders_by_product(self):
        factory, conn = self.make_factory([{"id": 1, "produto": "Mouse"}])

        rows = listar_estoque(factory)

        self.assertEqual(rows, [{"id": 1, "produto": "Mouse"}])
        self.assertIn("ORDER BY produto ASC", conn.cursor_obj.sql)
        self.assertTrue(conn.closed)

    def test_listar_alertas_estoque_minimo_filters_minimum(self):
        factory, conn = self.make_factory([{"id": 2, "produto": "Cabo"}])

        rows = listar_alertas_estoque_minimo(factory)

        self.assertEqual(rows[0]["produto"], "Cabo")
        self.assertIn("quantidade <= estoque_minimo", conn.cursor_obj.sql)
        self.assertTrue(conn.closed)

    def test_listar_recorrencias_filters_tipo(self):
        factory, conn = self.make_factory([{"id": 3, "tipo": "pagar"}])

        rows = listar_recorrencias(factory, "pagar")

        self.assertEqual(rows[0]["tipo"], "pagar")
        self.assertEqual(conn.cursor_obj.params, ("pagar",))
        self.assertTrue(conn.closed)


if __name__ == "__main__":
    unittest.main()

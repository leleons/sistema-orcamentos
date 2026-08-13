import unittest

from dsystem_erp.repositories.clientes import (
    buscar_cliente_por_nome,
    buscar_cliente_portal_por_usuario,
    buscar_cliente_resumo,
    listar_clientes,
)


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.last_sql = ""
        self.params = ()

    def execute(self, sql, params=()):
        self.last_sql = sql
        self.params = params

    def fetchall(self):
        return self.rows

    def fetchone(self):
        if "WHERE portal_username" in self.last_sql:
            usuario = self.params[0]
            return next((row for row in self.rows if row.get("portal_username") == usuario), None)
        if "WHERE id" in self.last_sql:
            cliente_id = self.params[0]
            return next((row for row in self.rows if row.get("id") == cliente_id), None)
        if "WHERE nome" in self.last_sql:
            nome = self.params[0]
            return next((row for row in self.rows if row.get("nome") == nome), None)
        return self.rows[0] if self.rows else None


class FakeConnection:
    def __init__(self, rows):
        self.rows = rows
        self.closed = False

    def cursor(self, dictionary=False):
        return FakeCursor(self.rows)

    def close(self):
        self.closed = True


class ClientesRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.conn = FakeConnection([
            {"id": 2, "nome": "Beta", "portal_username": "beta"},
            {"id": 1, "nome": "Alpha", "portal_username": "alpha"},
        ])

    def factory(self):
        return self.conn

    def test_listar_clientes_fecha_conexao(self):
        rows = listar_clientes(self.factory)
        self.assertEqual(len(rows), 2)
        self.assertTrue(self.conn.closed)

    def test_buscar_cliente_por_nome_case_insensitive(self):
        row = buscar_cliente_por_nome(self.factory, "alpha")
        self.assertEqual(row["id"], 1)

    def test_buscar_cliente_portal_por_usuario(self):
        row = buscar_cliente_portal_por_usuario(self.factory, "beta")
        self.assertEqual(row["nome"], "Beta")

    def test_buscar_cliente_resumo_por_id(self):
        row = buscar_cliente_resumo(self.factory, cliente_id=2)
        self.assertEqual(row["nome"], "Beta")


if __name__ == "__main__":
    unittest.main()

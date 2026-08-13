import json
import unittest
from datetime import datetime

from dsystem_erp.services.audit_log import inserir_log_cursor, resumir_detalhes_log


class CursorFake:
    def __init__(self):
        self.comando = None

    def execute(self, sql, params):
        self.comando = (sql, params)


class AuditLogTests(unittest.TestCase):
    def test_insere_log_com_contexto_e_acao_em_portugues(self):
        cursor = CursorFake()

        inserir_log_cursor(
            cursor,
            "update",
            "clientes",
            10,
            "Empresa",
            {"alterado": {"nome": "Novo"}},
            usuario="admin",
            pagina="Clientes",
            ip="127.0.0.1",
            criado_em=datetime(2026, 8, 13, 10, 30),
        )

        _, params = cursor.comando
        self.assertEqual(params[0], "2026-08-13 10:30:00")
        self.assertEqual(params[1:4], ("admin", "Editar", "clientes"))
        self.assertEqual(json.loads(params[7])["alterado"]["nome"], "Novo")

    def test_resume_detalhes_e_respeita_limite(self):
        resumo = resumir_detalhes_log('{"novo": {"nome": "Empresa", "telefone": "123"}}')
        curto = resumir_detalhes_log("x" * 30, limite=10)

        self.assertIn("nome: Empresa", resumo)
        self.assertEqual(curto, "xxxxxxxxxx...")


if __name__ == "__main__":
    unittest.main()

import unittest

from dsystem_erp.services.session import limpar_sessao, preencher_sessao


class SessionTests(unittest.TestCase):
    def test_preenche_sem_expor_senha(self):
        sessao = {"existente": True}

        preencher_sessao(sessao, {"id": 10, "username": "usuario", "password": "segredo"})

        self.assertEqual(sessao["id"], 10)
        self.assertEqual(sessao["username"], "usuario")
        self.assertNotIn("password", sessao)

    def test_limpa_todas_as_chaves(self):
        sessao = {"autenticado": True, "id": 10}

        limpar_sessao(sessao)

        self.assertEqual(sessao, {})


if __name__ == "__main__":
    unittest.main()

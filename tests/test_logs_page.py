import unittest

from dsystem_erp.pages.logs import renderizar_log_sistema


class FakeStreamlit:
    def __init__(self):
        self.erros = []

    def error(self, mensagem):
        self.erros.append(mensagem)


class LogsPageTests(unittest.TestCase):
    def test_bloqueia_consulta_para_usuario_sem_permissao_master(self):
        st = FakeStreamlit()

        renderizar_log_sistema({"st": st, "eh_admin_master": lambda: False})

        self.assertEqual(st.erros, ["Este log é exclusivo para Daniel.fabio."])


if __name__ == "__main__":
    unittest.main()

import unittest

from dsystem_erp.pages.chamados import renderizar_chamados_funcionario


class FakeStreamlit:
    def __init__(self, session_state=None):
        self.session_state = session_state or {}


class ChamadosPageTests(unittest.TestCase):
    def test_funcionario_sem_usuario_nao_consulta_banco(self):
        st = FakeStreamlit()

        resultado = renderizar_chamados_funcionario(ctx={"st": st})

        self.assertIsNone(resultado)


if __name__ == "__main__":
    unittest.main()

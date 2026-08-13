import ast
import unittest
from pathlib import Path


class StartupPerformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        caminho_app = Path(__file__).resolve().parents[1] / "orcamento.py"
        cls.arvore = ast.parse(caminho_app.read_text(encoding="utf-8-sig"))

    def _decoradores(self, nome_funcao):
        funcao = next(
            node
            for node in self.arvore.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == nome_funcao
        )
        return {ast.unparse(decorator.func) if isinstance(decorator, ast.Call) else ast.unparse(decorator) for decorator in funcao.decorator_list}

    def test_schema_do_banco_e_inicializado_uma_vez_por_processo(self):
        self.assertIn("st.cache_resource", self._decoradores("iniciar_banco"))

    def test_migracao_de_logins_e_executada_uma_vez_por_processo(self):
        self.assertIn(
            "st.cache_resource",
            self._decoradores("garantir_logins_clientes_existentes"),
        )


if __name__ == "__main__":
    unittest.main()

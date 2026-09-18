import unittest

from dsystem_erp.navigation import ARVORE_PERMISSOES, LEGACY_PERMISSOES, MODULOS_NAVEGACAO, TODAS_PERMISSOES


class NavigationTests(unittest.TestCase):
    def test_permissoes_derivadas_tem_acoes_principais(self):
        self.assertIn("clientes.view", TODAS_PERMISSOES)
        self.assertIn("faturamento.view", TODAS_PERMISSOES)
        self.assertIn("infra.senhas.view", TODAS_PERMISSOES)
        self.assertIn("softwares.pesquisa", TODAS_PERMISSOES)
        self.assertEqual(LEGACY_PERMISSOES["clientes.view"], "perm_clientes")
        self.assertEqual(LEGACY_PERMISSOES["orcamentos.edit"], "perm_orcamentos")

    def test_navegacao_tem_paginas_base(self):
        paginas = {
            item.get("pagina")
            for modulo in MODULOS_NAVEGACAO
            for item in modulo.get("submodulos", [])
            if item.get("pagina")
        }
        self.assertIn("Cadastro de Cliente/Fornecedor", paginas)
        self.assertIn("Faturamento", paginas)
        self.assertIn("Compras e Cotações", paginas)
        self.assertIn("Contratos", paginas)
        self.assertIn("Recepção e Kanban", paginas)
        self.assertIn("Base de Pesquisa", paginas)

    def test_compras_tem_permissoes(self):
        self.assertIn("compras.view", TODAS_PERMISSOES)
        self.assertIn("compras.edit", TODAS_PERMISSOES)

    def test_arvore_tem_modulos(self):
        modulos = {modulo.get("modulo") for modulo in ARVORE_PERMISSOES}
        self.assertIn("cadastros", modulos)
        self.assertIn("infraestrutura", modulos)

    def test_dashboard_fica_no_menu_financeiro(self):
        por_modulo = {
            modulo["titulo"]: [item.get("pagina") for item in modulo.get("submodulos", [])]
            for modulo in MODULOS_NAVEGACAO
        }
        self.assertIn("Dashboard", por_modulo["Financeiro"])
        self.assertNotIn("Dashboard", por_modulo["Acesso Softwares"])
        self.assertIn("Base de Pesquisa", por_modulo["Acesso Softwares"])


if __name__ == "__main__":
    unittest.main()

import unittest

from dsystem_erp.pages.acesso_softwares import renderizar_acesso_softwares
from dsystem_erp.pages.atendimentos import renderizar_atendimentos_checklists
from dsystem_erp.pages.cobrancas import renderizar_cobrancas
from dsystem_erp.pages.emails import renderizar_gestao_emails
from dsystem_erp.pages.estoque import renderizar_estoque
from dsystem_erp.pages.compras import renderizar_compras
from dsystem_erp.pages.contratos import renderizar_contratos
from dsystem_erp.pages.recepcao_kanban import renderizar_recepcao_kanban
from dsystem_erp.pages.ordens_servico import renderizar_ordem_servico
from dsystem_erp.pages.portal_cliente import renderizar_portal_cliente_page
from dsystem_erp.pages.usuarios import renderizar_gerenciador_usuarios
from dsystem_erp.pages.login import renderizar_login


class ExtraPagesImportTests(unittest.TestCase):
    def test_extra_pages_are_importable(self):
        self.assertTrue(callable(renderizar_gestao_emails))
        self.assertTrue(callable(renderizar_estoque))
        self.assertTrue(callable(renderizar_compras))
        self.assertTrue(callable(renderizar_contratos))
        self.assertTrue(callable(renderizar_recepcao_kanban))
        self.assertTrue(callable(renderizar_acesso_softwares))
        self.assertTrue(callable(renderizar_portal_cliente_page))
        self.assertTrue(callable(renderizar_gerenciador_usuarios))
        self.assertTrue(callable(renderizar_ordem_servico))
        self.assertTrue(callable(renderizar_cobrancas))
        self.assertTrue(callable(renderizar_atendimentos_checklists))
        self.assertTrue(callable(renderizar_login))


if __name__ == "__main__":
    unittest.main()

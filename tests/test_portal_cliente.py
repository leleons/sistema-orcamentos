import unittest

from dsystem_erp.services.portal_cliente import link_portal, normalizar_secao_portal, portal_card_html


class PortalClienteTests(unittest.TestCase):
    def test_normalizar_secao_alias_chamados(self):
        self.assertEqual(normalizar_secao_portal("chamados"), "meus_chamados")
        self.assertEqual(normalizar_secao_portal(""), "inicio")

    def test_link_portal(self):
        self.assertEqual(link_portal("notas"), "?pagina=portal&secao=notas")

    def test_card_escapa_texto(self):
        html = portal_card_html("notas", "<Notas>", "1", "XML & PDF")
        self.assertIn("&lt;Notas&gt;", html)
        self.assertIn("XML &amp; PDF", html)
        self.assertIn("?pagina=portal&secao=notas", html)


if __name__ == "__main__":
    unittest.main()

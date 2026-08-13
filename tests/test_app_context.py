import unittest

from dsystem_erp.app_context import AppContext, aplicar_contexto_pagina, criar_app_context


class AppContextTests(unittest.TestCase):
    def test_cria_contexto_a_partir_de_mapping(self):
        ctx = criar_app_context({"usuario": "Daniel.fabio", "valor": 10})

        self.assertIsInstance(ctx, AppContext)
        self.assertEqual(ctx.get("usuario"), "Daniel.fabio")
        self.assertEqual(ctx.get("faltando", "padrao"), "padrao")

    def test_aplica_contexto_em_destino(self):
        destino = {"existente": True}
        aplicar_contexto_pagina(AppContext({"novo": "ok"}), destino)

        self.assertTrue(destino["existente"])
        self.assertEqual(destino["novo"], "ok")

    def test_aplica_mapping_antigo(self):
        destino = {}
        aplicar_contexto_pagina({"st": "fake"}, destino)

        self.assertEqual(destino["st"], "fake")


if __name__ == "__main__":
    unittest.main()

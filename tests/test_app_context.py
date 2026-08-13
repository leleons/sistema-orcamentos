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

    def test_preserva_funcao_local_em_colisao_com_wrapper(self):
        def funcao_da_pagina(ctx=None):
            return ctx

        def wrapper_principal():
            return "wrapper"

        destino = {
            "__name__": funcao_da_pagina.__module__,
            "restaurar_portal_por_sid": funcao_da_pagina,
        }
        aplicar_contexto_pagina(
            {"restaurar_portal_por_sid": wrapper_principal},
            destino,
        )

        self.assertIs(destino["restaurar_portal_por_sid"], funcao_da_pagina)
        self.assertEqual(destino["restaurar_portal_por_sid"](ctx="ok"), "ok")


if __name__ == "__main__":
    unittest.main()

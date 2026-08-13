import unittest

from dsystem_erp.pages.portal_sections import injetar_css_portal_cliente


class FakeStreamlit:
    def __init__(self):
        self.markdowns = []

    def markdown(self, conteudo, **kwargs):
        self.markdowns.append((conteudo, kwargs))


class PortalSectionsTests(unittest.TestCase):
    def test_injeta_estilo_do_portal(self):
        st = FakeStreamlit()

        injetar_css_portal_cliente(ctx={"st": st})

        self.assertTrue(st.markdowns)
        self.assertIn("portal", st.markdowns[0][0].lower())
        self.assertTrue(st.markdowns[0][1].get("unsafe_allow_html"))


if __name__ == "__main__":
    unittest.main()

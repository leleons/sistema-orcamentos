import unittest

from dsystem_erp.ui import BASE_CSS, configurar_campos_data_br, injetar_css_base


class FakeStreamlit:
    def __init__(self):
        self.calls = []

    def markdown(self, text, unsafe_allow_html=False):
        self.calls.append((text, unsafe_allow_html))


class UiTests(unittest.TestCase):
    def test_css_base_tem_tokens_do_sistema(self):
        self.assertIn("--ds-primary", BASE_CSS)
        self.assertIn(".ds-soft-card", BASE_CSS)

    def test_injeta_css_base_com_html_liberado(self):
        fake = FakeStreamlit()

        injetar_css_base(fake)

        self.assertEqual(len(fake.calls), 1)
        self.assertTrue(fake.calls[0][1])

    def test_configura_formato_brasileiro_nos_campos_de_data(self):
        class StreamlitFalso:
            def __init__(self):
                self.recebido = None

            def date_input(self, *args, **kwargs):
                self.recebido = kwargs
                return kwargs

        falso = StreamlitFalso()
        configurar_campos_data_br(falso)
        falso.date_input("Data")
        self.assertEqual(falso.recebido["format"], "DD/MM/YYYY")


if __name__ == "__main__":
    unittest.main()

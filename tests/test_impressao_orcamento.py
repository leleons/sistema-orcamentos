import unittest
from pathlib import Path


class ImpressaoOrcamentoTests(unittest.TestCase):
    def test_impressao_usa_pagina_principal_sem_iframe_temporario(self):
        raiz = Path(__file__).resolve().parents[1]
        fonte = (raiz / "orcamento.py").read_text(encoding="utf-8")
        inicio = fonte.index("def imprimir_html(")
        fim = fonte.index("\nst.markdown(", inicio)
        funcao = fonte[inicio:fim]

        self.assertIn("def imprimir_html(conteudo_html,", funcao)
        self.assertNotIn("def imprimir_html(html,", funcao)
        self.assertIn("const pagina = window.parent", funcao)
        self.assertIn("afterprint", funcao)
        self.assertIn("pagina.print()", funcao)
        self.assertNotIn("document.createElement('iframe')", funcao)

    def test_gerador_mantem_documento_oculto_para_impressao(self):
        raiz = Path(__file__).resolve().parents[1]
        fonte = (raiz / "dsystem_erp" / "pages" / "gerador_orcamentos.py").read_text(encoding="utf-8")
        estilo = (raiz / "orcamento.py").read_text(encoding="utf-8")
        self.assertIn('id="doc-impressao"', fonte)
        self.assertIn("#doc-impressao {\n        display: none;", estilo)
        self.assertIn("display: block !important;", estilo)

    def test_botoes_de_impressao_mantem_aba_de_edicao(self):
        raiz = Path(__file__).resolve().parents[1]
        fonte = (raiz / "dsystem_erp" / "pages" / "gerador_orcamentos.py").read_text(encoding="utf-8")
        inicio = fonte.index('bimp = cb3.button(')
        fim = fonte.index('if salvar_limpar or bpa or bimp', inicio)
        botoes = fonte[inicio:fim]
        self.assertGreaterEqual(botoes.count("on_click=manter_edicao_orcamento_ativa"), 4)

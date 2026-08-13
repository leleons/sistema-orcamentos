from datetime import date
import unittest

from xml.etree import ElementTree as ET

from dsystem_erp.services.nfe_produto import (
    NFE_NS,
    gerar_xml_nfe_produto_400,
    gerar_xml_nfe_produto_rascunho,
    validar_prontidao_envio_nfe_produto,
    validar_xml_nfe_produto_minimo,
)


class NFeProdutoTests(unittest.TestCase):
    def test_gerar_xml_nfe_produto_rascunho_com_itens(self):
        faturamento = {
            "id": 3,
            "orcamento_ref": "9080898098",
            "cliente": "Cliente Teste",
            "cnpj": "12.345.678/0001-90",
        }
        itens = [
            {"desc": "Notebook", "tipo_item": "Produto", "qtd": 2, "vunit": 1500, "vtotal": 3000},
        ]
        dados = {
            "competencia": date(2026, 7, 15),
            "ncm": "8471.30.12",
            "cfop": "5102",
            "unidade": "UN",
            "ambiente": "homologacao",
        }

        xml = gerar_xml_nfe_produto_rascunho(faturamento, itens, dados).decode("utf-8")

        self.assertIn("<NFeProdutoRascunho", xml)
        self.assertIn("<Nome>Cliente Teste</Nome>", xml)
        self.assertIn("<NCM>8471.30.12</NCM>", xml)
        self.assertIn("<CFOP>5102</CFOP>", xml)
        self.assertIn("<ValorNota>3000.00</ValorNota>", xml)

    def test_validar_prontidao_envio_nfe_produto_aponta_pendencias(self):
        prontidao = validar_prontidao_envio_nfe_produto(
            endpoint="",
            cert_path="",
            cert_password="",
            ncm="",
            cfop="",
            inscricao_estadual="",
            regime_tributario="",
            itens=[],
        )

        self.assertFalse(prontidao.pronto)
        self.assertTrue(any("endpoint" in pendencia.lower() for pendencia in prontidao.pendencias))
        self.assertTrue(any("NCM" in pendencia for pendencia in prontidao.pendencias))

    def test_gerar_xml_nfe_produto_400_com_chave_e_totais(self):
        faturamento = {
            "id": 12,
            "cliente": "Cliente Produto",
            "cnpj": "12.345.678/0001-90",
        }
        itens = [
            {"desc": "Mouse", "tipo_item": "Produto", "qtd": 2, "vunit": 25, "vtotal": 50},
        ]
        dados = {
            "ambiente": "homologacao",
            "natureza_operacao": "Venda de mercadoria",
            "ncm": "84716053",
            "cfop": "5102",
            "unidade": "UN",
            "emitente_cnpj": "23.524.449/0001-54",
            "inscricao_estadual": "0012345670089",
            "regime_tributario": "1 - Simples Nacional",
            "uf": "MG",
            "codigo_municipio": "3156700",
            "numero": 12,
            "serie": 1,
        }

        xml = gerar_xml_nfe_produto_400(faturamento, itens, dados)
        root = ET.fromstring(xml)
        inf = root.find(f"{{{NFE_NS}}}infNFe")

        self.assertTrue(root.tag.endswith("NFe"))
        self.assertIsNotNone(inf)
        self.assertEqual(len(inf.attrib["Id"].replace("NFe", "")), 44)
        self.assertIn(b"<vProd>50.00</vProd>", xml)
        self.assertEqual(validar_xml_nfe_produto_minimo(xml, dados, itens), [])


if __name__ == "__main__":
    unittest.main()

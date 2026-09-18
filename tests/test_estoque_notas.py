import unittest

from dsystem_erp.pages.estoque import sugerir_produto_nota
from dsystem_erp.services.estoque_notas import (
    interpretar_xml_nfe, validar_saida_com_cliente, preparar_entrada_rapida,
)


XML_NFE = b'''<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">
  <NFe><infNFe Id="NFe31260912345678000199550010000001231234567890">
    <ide><serie>1</serie><nNF>123</nNF><dhEmi>2026-09-09T10:00:00-03:00</dhEmi></ide>
    <emit><CNPJ>12345678000199</CNPJ><xNome>Fornecedor Teste Ltda</xNome></emit>
    <det nItem="1"><prod><cProd>ABC-1</cProd><cEAN>SEM GTIN</cEAN>
      <xProd>Mouse sem fio</xProd><NCM>84716053</NCM><CFOP>5102</CFOP>
      <uCom>UN</uCom><qCom>2.000</qCom><vUnCom>50.25</vUnCom><vProd>100.50</vProd>
    </prod></det>
  </infNFe></NFe>
  <protNFe><infProt><chNFe>31260912345678000199550010000001231234567890</chNFe></infProt></protNFe>
</nfeProc>'''


class EstoqueNotasTests(unittest.TestCase):
    def test_interpreta_cabecalho_e_itens_da_nfe(self):
        nota = interpretar_xml_nfe(XML_NFE)

        self.assertEqual(nota["fornecedor"], "Fornecedor Teste Ltda")
        self.assertEqual(nota["numero_nota"], "123")
        self.assertEqual(nota["data_compra"], "2026-09-09")
        self.assertEqual(nota["itens"][0]["descricao"], "Mouse sem fio")
        self.assertEqual(nota["itens"][0]["quantidade"], 2.0)
        self.assertEqual(nota["itens"][0]["valor_unitario"], 50.25)

    def test_xml_sem_nfe_e_rejeitado(self):
        with self.assertRaisesRegex(ValueError, "infNFe"):
            interpretar_xml_nfe(b"<arquivo />")

    def test_saida_exige_cliente_e_estoque_suficiente(self):
        self.assertIn("cliente", validar_saida_com_cliente(None, "", 1, 5))
        self.assertIn("disponível", validar_saida_com_cliente(7, "Cliente", 6, 5))
        self.assertIsNone(validar_saida_com_cliente(7, "Cliente", 2, 5))

    def test_sugere_produto_por_codigo_ou_nome(self):
        produtos = [
            {"id": 8, "codigo_entrada": "ABC-1", "modelo": "Mouse sem fio"},
            {"id": 9, "codigo_entrada": "XYZ", "nome_generico": "Teclado"},
        ]
        self.assertEqual(sugerir_produto_nota({"codigo_fornecedor": "ABC-1"}, produtos), 8)
        self.assertEqual(sugerir_produto_nota({"descricao": "TECLADO"}, produtos), 9)

    def test_nao_vincula_camera_ao_teclado_por_palavra_mini(self):
        produtos = [{
            "id": 929,
            "codigo_entrada": "01.01.929",
            "modelo": "MINI",
            "nome_generico": "MINI TECLADO COM TOUCHPAD",
        }]
        item_xml = {
            "codigo_fornecedor": "4560041",
            "codigo_barras": "7899298649878",
            "descricao": "CAMERA DOME - VHD 3220 MINI BLACK",
        }
        self.assertIsNone(sugerir_produto_nota(item_xml, produtos))

    def test_sugere_por_modelo_composto_contido_na_descricao(self):
        produtos = [{"id": 950, "modelo": "VHD 3220"}]
        self.assertEqual(
            sugerir_produto_nota({"descricao": "CAMERA DOME - VHD 3220 MINI BLACK"}, produtos),
            950,
        )

    def test_entrada_rapida_prepara_reposicao_com_historico(self):
        entrada = preparar_entrada_rapida(
            produto_id=947, descricao="Fonte", quantidade=4,
            fornecedor="Fornecedor Teste", data_compra="14/09/2026",
            com_nota=False, valor_unitario=75,
        )
        self.assertEqual(entrada["data_compra"], "2026-09-14")
        self.assertEqual(entrada["itens"][0]["quantidade"], 4)
        self.assertEqual(entrada["itens"][0]["valor_total"], 300)
        self.assertTrue(entrada["numero_nota"].startswith("SEM-NOTA-947-"))

    def test_entrada_rapida_com_nota_exige_numero(self):
        with self.assertRaisesRegex(ValueError, "número da nota"):
            preparar_entrada_rapida(
                produto_id=947, descricao="Fonte", quantidade=1,
                fornecedor="Fornecedor", data_compra="2026-09-14",
                com_nota=True,
            )


if __name__ == "__main__":
    unittest.main()

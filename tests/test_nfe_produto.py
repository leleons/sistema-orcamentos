from datetime import date
import unittest
from contextlib import nullcontext
from unittest.mock import patch, MagicMock

from xml.etree import ElementTree as ET

from dsystem_erp.services.nfe_produto import (
    NFE_NS,
    gerar_xml_nfe_produto_400,
    gerar_xml_nfe_produto_rascunho,
    validar_prontidao_envio_nfe_produto,
    validar_xml_nfe_produto_minimo,
    montar_envelope_nfe_autorizacao,
    analisar_retorno_nfe_produto,
    enviar_xml_nfe_produto,
    endpoint_autorizacao_nfe,
    assinar_xml_nfe_produto,
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
        self.assertTrue(any("destinatário" in p for p in validar_xml_nfe_produto_minimo(xml, dados, itens)))

    def exemplo(self):
        dados = dict(ambiente="homologacao", ncm="84716053", cfop="5102", emitente_cnpj="23524449000154",
                     inscricao_estadual="0026483460031", regime_tributario="3", uf="MG", codigo_municipio="3106200",
                     numero=20, serie=1, destinatario=dict(logradouro="Rua Teste", numero="1", bairro="Centro",
                     municipio="Belo Horizonte", uf="MG", codigo_municipio="3106200"))
        itens = [dict(desc="Mouse", qtd=2, vunit=50, vtotal=100,
                      tributos=dict(base_icms=100, icms=18, base_pis=100, pis=1.65, base_cofins=100, cofins=7.6),
                      ibscbs=dict(cst="000", classificacao="000001", base=100, uf=0.1, municipal=0, cbs=0.9))]
        fat = dict(id=20, cliente="Teste", cnpj="23524449000154")
        return fat, itens, dados

    def test_totais_impostos_e_endereco(self):
        fat, itens, dados = self.exemplo()
        xml = gerar_xml_nfe_produto_400(fat, itens, dados)
        root = ET.fromstring(xml)
        ns = {"n": NFE_NS}
        for campo, esperado in (("vBC", "100.00"), ("vICMS", "18.00"), ("vPIS", "1.65"), ("vCOFINS", "7.60")):
            self.assertEqual(root.findtext(f".//n:ICMSTot/n:{campo}", namespaces=ns), esperado)
        self.assertEqual(root.findtext(".//n:IBSCBSTot/n:gCBS/n:vCBS", namespaces=ns), "0.90")
        self.assertEqual(root.findtext(".//n:dest/n:enderDest/n:cMun", namespaces=ns), "3106200")
        self.assertIn(b"SEM VALOR FISCAL", xml)
        self.assertEqual(validar_xml_nfe_produto_minimo(xml, dados, itens), [])

    def test_bloqueia_ncm_com_letra_tributos_ausentes_e_total_incorreto(self):
        fat, itens, dados = self.exemplo()
        itens[0].update(ncm="12345678Z", tributos={}, ibscbs={}, vtotal=90)
        erros = validar_xml_nfe_produto_minimo(gerar_xml_nfe_produto_400(fat, itens, dados), dados, itens)
        for parte in ("NCM", "base_icms", "IBS/CBS", "total difere"):
            self.assertTrue(any(parte in erro for erro in erros), erros)

    def test_envelope_contem_lote_sincrono_sem_declaracao_interna(self):
        fat, itens, dados = self.exemplo()
        xml = gerar_xml_nfe_produto_400(fat, itens, dados)
        envelope = montar_envelope_nfe_autorizacao(xml)
        self.assertEqual(envelope.count(b"<?xml"), 1)
        root = ET.fromstring(envelope)
        lote = root.find(f".//{{{NFE_NS}}}enviNFe")
        self.assertEqual(lote.findtext(f"{{{NFE_NS}}}indSinc"), "1")
        self.assertIsNotNone(lote.find(f"{{{NFE_NS}}}NFe"))

    def test_retorno_prioriza_protocolo_sobre_lote(self):
        for codigo, esperado in (("100", "Autorizada"), ("305", "Rejeitada")):
            xml = f'<retEnviNFe xmlns="{NFE_NS}"><cStat>104</cStat><xMotivo>Lote processado</xMotivo><protNFe><infProt><cStat>{codigo}</cStat><xMotivo>Resultado da nota</xMotivo><nProt>123</nProt></infProt></protNFe></retEnviNFe>'
            info = analisar_retorno_nfe_produto(xml)
            self.assertEqual(info["status"], esperado)
            self.assertEqual(info["cstat"], codigo)
            self.assertEqual(info["protocolo"], "123")

    def test_conexao_usa_context_manager_e_bloqueia_ambiente_trocado(self):
        fat, itens, dados = self.exemplo()
        xml = gerar_xml_nfe_produto_400(fat, itens, dados)
        contexto = object()
        resposta = MagicMock()
        resposta.__enter__.return_value.read.return_value = b"retorno"
        with patch("dsystem_erp.services.nfse_soap.contexto_ssl_certificado_pfx", return_value=nullcontext(contexto)) as cert, patch("urllib.request.urlopen", return_value=resposta) as abrir:
            self.assertEqual(enviar_xml_nfe_produto(endpoint_autorizacao_nfe("MG", "homologacao"), xml, "teste.pfx", "segredo"), b"retorno")
            self.assertIs(abrir.call_args.kwargs["context"], contexto)
            with self.assertRaisesRegex(ValueError, "Ambiente"):
                enviar_xml_nfe_produto(endpoint_autorizacao_nfe("MG", "producao"), xml, "teste.pfx", "segredo")
            self.assertEqual(abrir.call_count, 1)

    def test_assinatura_valida_e_envelope_preserva_documento(self):
        import tempfile
        from pathlib import Path
        from datetime import datetime, timedelta, timezone
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives.serialization import pkcs12
        from lxml import etree
        import base64
        from cryptography.hazmat.primitives.asymmetric import padding
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Teste local NF-e")])
        now = datetime.now(timezone.utc)
        cert = (x509.CertificateBuilder().subject_name(nome).issuer_name(nome).public_key(key.public_key())
                .serial_number(1).not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=1))
                .sign(key, hashes.SHA256()))
        fat, itens, dados = self.exemplo()
        with tempfile.TemporaryDirectory() as diretorio:
            caminho = Path(diretorio) / "teste.pfx"
            caminho.write_bytes(pkcs12.serialize_key_and_certificates(b"teste", key, cert, None, serialization.NoEncryption()))
            assinado = assinar_xml_nfe_produto(gerar_xml_nfe_produto_400(fat, itens, dados), str(caminho), "")
        self.assertNotIn(b"<ds:Signature", assinado)
        root = etree.fromstring(assinado)
        ds = "http://www.w3.org/2000/09/xmldsig#"
        info = root.find(f".//{{{ds}}}SignedInfo")
        assinatura = base64.b64decode(root.findtext(f".//{{{ds}}}SignatureValue"))
        cert.public_key().verify(assinatura, etree.tostring(info, method="c14n"), padding.PKCS1v15(), hashes.SHA1())
        digest = hashes.Hash(hashes.SHA1())
        digest.update(etree.tostring(root.find(f"{{{NFE_NS}}}infNFe"), method="c14n"))
        self.assertEqual(base64.b64decode(info.findtext(f".//{{{ds}}}DigestValue")), digest.finalize())
        # A SEFAZ extrai o documento do transporte SOAP antes de verificar a assinatura.
        documento = assinado.decode("utf-8").split("?>", 1)[-1].strip().encode("utf-8")
        self.assertIn(documento, montar_envelope_nfe_autorizacao(assinado))


if __name__ == "__main__":
    unittest.main()

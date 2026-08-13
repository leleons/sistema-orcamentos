import base64
import gzip
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from lxml import etree

from dsystem_erp.services.nfse_nacional import (
    NS_DSIG,
    NS_NFSE,
    assinar_xml_dps_nacional,
    compactar_xml_base64,
    descompactar_xml_base64,
    endpoint_nacional,
    gerar_xml_dps_nacional,
    montar_id_dps,
)


class NfseNacionalTest(unittest.TestCase):
    def setUp(self):
        self.faturamento = {
            "id": 123,
            "cnpj": "12.345.678/0001-95",
            "cliente": "Cliente Teste",
            "telefone": "31999999999",
            "email": "cliente@example.com",
        }
        self.dados = {
            "ambiente": "homologacao",
            "cnpj_prestador": "23.524.449/0001-54",
            "inscricao_municipal": "07395930011",
            "codigo_municipio": "3106200",
            "serie_dps": 1,
            "numero_dps": 123,
            "competencia": date(2026, 8, 3),
            "data_hora_emissao": "2026-08-03T15:00:00-03:00",
            "codigo_tributacao_nacional": "010701",
            "descricao": "Suporte tecnico em informatica",
            "valor": 150.5,
            "opcao_simples_nacional": "1",
            "regime_especial_tributacao": "0",
        }

    def test_monta_id_dps_com_45_posicoes(self):
        identificador = montar_id_dps("3106200", "23524449000154", 1, 123)
        self.assertEqual(identificador, "DPS310620022352444900015400001000000000000123")
        self.assertEqual(len(identificador), 45)

    def test_gera_dps_101_sem_prefixo_de_namespace(self):
        xml = gerar_xml_dps_nacional(self.faturamento, self.dados)
        root = etree.fromstring(xml)
        ns = {"n": NS_NFSE}
        self.assertEqual(root.get("versao"), "1.01")
        self.assertEqual(root.findtext("n:infDPS/n:tpAmb", namespaces=ns), "2")
        self.assertEqual(root.findtext("n:infDPS/n:serv/n:cServ/n:cTribNac", namespaces=ns), "010701")
        self.assertEqual(root.findtext("n:infDPS/n:valores/n:vServPrest/n:vServ", namespaces=ns), "150.50")
        self.assertNotIn(b"ns0:", xml)

    def test_exige_regime_do_simples_explicitamente(self):
        self.dados["opcao_simples_nacional"] = ""
        with self.assertRaisesRegex(ValueError, "Simples Nacional"):
            gerar_xml_dps_nacional(self.faturamento, self.dados)

    def test_gzip_base64_faz_roundtrip(self):
        xml = gerar_xml_dps_nacional(self.faturamento, self.dados)
        compactado = compactar_xml_base64(xml)
        self.assertEqual(descompactar_xml_base64(compactado), xml)
        self.assertEqual(gzip.decompress(base64.b64decode(compactado)), xml)

    def test_endpoints_oficiais_por_ambiente(self):
        self.assertIn("producaorestrita", endpoint_nacional("homologacao"))
        self.assertEqual(endpoint_nacional("producao"), "https://sefin.nfse.gov.br/SefinNacional")

    def test_assina_infdps_com_assinatura_envelopada(self):
        chave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Teste")])
        certificado = (
            x509.CertificateBuilder()
            .subject_name(nome)
            .issuer_name(nome)
            .public_key(chave.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.now(timezone.utc) - timedelta(days=1))
            .not_valid_after(datetime.now(timezone.utc) + timedelta(days=1))
            .sign(chave, hashes.SHA256())
        )
        pfx = pkcs12.serialize_key_and_certificates(
            b"teste", chave, certificado, None, serialization.BestAvailableEncryption(b"senha")
        )
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "teste.pfx"
            caminho.write_bytes(pfx)
            assinado = assinar_xml_dps_nacional(
                gerar_xml_dps_nacional(self.faturamento, self.dados), str(caminho), "senha"
            )
        root = etree.fromstring(assinado)
        assinatura = root.find(f"{{{NS_DSIG}}}Signature")
        self.assertIsNotNone(assinatura)
        referencia = assinatura.find(f".//{{{NS_DSIG}}}Reference")
        self.assertEqual(referencia.get("URI"), "#" + root.find(f"{{{NS_NFSE}}}infDPS").get("Id"))
        self.assertNotIn(b"ds:Signature", assinado)


if __name__ == "__main__":
    unittest.main()

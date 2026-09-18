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
    normalizar_emissao_dps,
)


class NfseNacionalTest(unittest.TestCase):
    def test_emissao_utc_convertida_sem_alterar_instante(self):
        instante = datetime(2026, 9, 14, 21, 5, 56, tzinfo=timezone.utc)
        local = normalizar_emissao_dps(instante)
        self.assertEqual(local.isoformat(), "2026-09-14T18:05:56-03:00")
        self.assertEqual(local, instante)
        self.assertEqual(normalizar_emissao_dps(instante.isoformat()), local)

    def test_emissao_sem_fuso_rejeitada(self):
        with self.assertRaises(ValueError):
            normalizar_emissao_dps("2026-09-14T21:05:56")

    def test_emissao_padrao_fuso_brasil(self):
        self.assertEqual(normalizar_emissao_dps().utcoffset(), timedelta(hours=-3))

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
            "totais_tributos": {"federal": 10.0, "estadual": 0, "municipal": 3.0},
            "regime_especial_tributacao": "0",
        }

    def test_monta_id_dps_com_45_posicoes(self):
        identificador = montar_id_dps("3106200", "23524449000154", 1, 123)
        self.assertEqual(identificador, "DPS310620022352444900015400001000000000000123")
        self.assertEqual(len(identificador), 45)

    def test_omitir_im_nao_altera_emitente(self):
        self.dados["inscricao_municipal"] = ""
        root = etree.fromstring(gerar_xml_dps_nacional(self.faturamento, self.dados))
        ns = {"n": NS_NFSE}
        self.assertIsNone(root.find("n:infDPS/n:prest/n:IM", ns))
        self.assertEqual(root.findtext("n:infDPS/n:prest/n:CNPJ", namespaces=ns), "23524449000154")
        self.assertEqual(root.findtext("n:infDPS/n:cLocEmi", namespaces=ns), "3106200")

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

    def test_nao_optante_envia_valores_sem_indicador_simples(self):
        xml = gerar_xml_dps_nacional(self.faturamento, self.dados)
        self.assertNotIn(b"indTotTrib", xml)
        self.assertNotIn(b"pTotTribSN", xml)
        self.assertIn(b"<vTotTrib><vTotTribFed>10.00</vTotTribFed><vTotTribEst>0.00</vTotTribEst><vTotTribMun>3.00</vTotTribMun></vTotTrib>", xml)

    def test_nao_optante_nao_presume_totais(self):
        self.dados.pop("totais_tributos")
        with self.assertRaisesRegex(ValueError, "valores aproximados"):
            gerar_xml_dps_nacional(self.faturamento, self.dados)

    def test_totais_invalidos_bloqueados(self):
        for valor in (None, "", -1, float("nan"), float("inf")):
            with self.subTest(valor=valor):
                self.dados["totais_tributos"]["federal"] = valor
                with self.assertRaisesRegex(ValueError, "tributo federal"):
                    gerar_xml_dps_nacional(self.faturamento, self.dados)

    def test_mei_preserva_indicador_sem_valores(self):
        self.dados["opcao_simples_nacional"] = "2"
        self.dados.pop("totais_tributos")
        xml = gerar_xml_dps_nacional(self.faturamento, self.dados)
        self.assertIn(b"<indTotTrib>0</indTotTrib>", xml)
        self.assertNotIn(b"vTotTribFed", xml)

    def test_gzip_base64_faz_roundtrip(self):
        xml = gerar_xml_dps_nacional(self.faturamento, self.dados)
        compactado = compactar_xml_base64(xml)
        self.assertEqual(descompactar_xml_base64(compactado), xml)
        self.assertEqual(gzip.decompress(base64.b64decode(compactado)), xml)

    def test_me_epp_exige_apuracao_e_inclui_escolha(self):
        self.dados["opcao_simples_nacional"] = "3"
        with self.assertRaisesRegex(ValueError, "apuracao"):
            gerar_xml_dps_nacional(self.faturamento, self.dados)
        self.dados["regime_apuracao_simples"] = "2"
        self.dados["percentual_tributos_simples"] = "6.25"
        xml = gerar_xml_dps_nacional(self.faturamento, self.dados)
        self.assertIn(b"<regApTribSN>2</regApTribSN>", xml)
        self.assertIn(b"<pTotTribSN>6.25</pTotTribSN>", xml)
        self.assertNotIn(b"indTotTrib", xml)

    def test_me_epp_exige_percentual_do_simples_valido(self):
        self.dados["opcao_simples_nacional"] = "3"
        self.dados["regime_apuracao_simples"] = "1"
        for valor in (None, "", -1, 101, float("nan")):
            with self.subTest(valor=valor):
                self.dados["percentual_tributos_simples"] = valor
                with self.assertRaisesRegex(ValueError, "percentual aproximado"):
                    gerar_xml_dps_nacional(self.faturamento, self.dados)

    def test_codigo_municipal_nao_e_truncado(self):
        self.dados["codigo_tributacao_municipal"] = "010701"
        with self.assertRaisesRegex(ValueError, "3 digitos"):
            gerar_xml_dps_nacional(self.faturamento, self.dados)
        self.dados["codigo_tributacao_municipal"] = "001"
        self.assertIn(b"<cTribMun>001</cTribMun>", gerar_xml_dps_nacional(self.faturamento, self.dados))

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

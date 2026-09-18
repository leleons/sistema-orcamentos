import unittest

from dsystem_erp.services.nfse_sequencia import maior_numero_fiscal_nos_xmls


class NfseSequenciaTests(unittest.TestCase):
    def test_recupera_maior_dps_da_mesma_serie(self):
        xmls = [
            {"xml_envio": '<DPS><infDPS><serie>1</serie><nDPS>1</nDPS></infDPS></DPS>'},
            {"xml_envio": '<DPS><infDPS><serie>1</serie><nDPS>7</nDPS></infDPS></DPS>'},
            {"xml_envio": '<DPS><infDPS><serie>2</serie><nDPS>20</nDPS></infDPS></DPS>'},
        ]
        self.assertEqual(maior_numero_fiscal_nos_xmls(xmls, tipo="dps", serie=1), 7)

    def test_recupera_maior_lote_abr_asf(self):
        xmls = [
            b'<EnviarLoteRpsEnvio><LoteRps><NumeroLote>3</NumeroLote></LoteRps></EnviarLoteRpsEnvio>',
            b'<EnviarLoteRpsEnvio><LoteRps><NumeroLote>9</NumeroLote></LoteRps></EnviarLoteRpsEnvio>',
        ]
        self.assertEqual(maior_numero_fiscal_nos_xmls(xmls, tipo="lote"), 9)

    def test_ignora_xml_invalido(self):
        self.assertEqual(maior_numero_fiscal_nos_xmls(["invalido", ""], tipo="dps", serie=1), 0)


if __name__ == "__main__":
    unittest.main()

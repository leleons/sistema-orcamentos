import tempfile
import unittest
from pathlib import Path
from unittest import mock

from dsystem_erp.services.nfse_pdf import gerar_pdf_nota_autorizada_simples
from dsystem_erp.services.nfse_retorno import analisar_retorno_nfse, texto_tag_xml
from dsystem_erp.services.nfse_settings import get_nfse_settings
from dsystem_erp.services.nfse_signature import assinar_xml_nfse_bh
from dsystem_erp.services.nfse_soap import _resumo_bloqueio_gocache, consultar_protocolo_nfse, montar_envelope_soap_nfse
from dsystem_erp.services.nfse_validacao import validar_xml_nfse_basico
from dsystem_erp.services.nfse_workflow import enviar_nfse, executar_fluxo_emissao_nfse, validar_nfse


class NfseModulesTests(unittest.TestCase):
    def test_monta_envelope_soap(self):
        envelope = montar_envelope_soap_nfse("<GerarNfseEnvio><Teste>ok</Teste></GerarNfseEnvio>").decode("utf-8")

        self.assertIn("<soapenv:Envelope", envelope)
        self.assertIn('xmlns:ws="http://ws.bhiss.pbh.gov.br"', envelope)
        self.assertIn("<ws:GerarNfseRequest>", envelope)
        self.assertIn("<nfseCabecMsg>", envelope)
        self.assertIn("<nfseDadosMsg>", envelope)
        self.assertIn("</ws:GerarNfseRequest>", envelope)
        self.assertIn("<cabecalho versao=\"1.00\">", envelope)
        self.assertIn("GerarNfseEnvio", envelope)
        self.assertIn("<Teste>ok</Teste>", envelope)

    def test_analisa_retorno_autorizado(self):
        xml = """
        <Retorno>
            <NumeroNfse>123</NumeroNfse>
            <CodigoVerificacao>ABC</CodigoVerificacao>
            <Protocolo>P1</Protocolo>
        </Retorno>
        """

        info = analisar_retorno_nfse(xml)

        self.assertEqual(info["status"], "Autorizada")
        self.assertEqual(info["numero_nfse"], "123")
        self.assertEqual(info["chave_acesso"], "ABC")

    def test_texto_tag_xml_tem_fallback_regex(self):
        self.assertEqual(texto_tag_xml("<ns:Mensagem>Erro teste</ns:Mensagem>", ["Mensagem"]), "Erro teste")

    def test_validacao_basica_aponta_pendencias(self):
        erros = validar_xml_nfse_basico("<GerarNfseEnvio><ValorServicos>1</ValorServicos></GerarNfseEnvio>")

        self.assertTrue(any("CpfCnpj" in erro for erro in erros))

    def test_gera_pdf_nota_autorizada(self):
        try:
            pdf = gerar_pdf_nota_autorizada_simples(
                {"cliente": "Cliente", "valor_servicos": 10, "descricao": "Servico"},
                {"status": "Autorizada", "numero_nfse": "1"},
            )
        except RuntimeError as ex:
            self.skipTest(str(ex))

        self.assertTrue(pdf.startswith(b"%PDF"))

    def test_assinatura_exige_certificado_existente(self):
        with self.assertRaises(FileNotFoundError):
            assinar_xml_nfse_bh(b"<GerarNfseEnvio />", cert_path="certificado_inexistente.pfx", cert_password="1")

    def test_settings_le_configuracao(self):
        with mock.patch("dsystem_erp.services.nfse_settings.config_val", side_effect=lambda nome, padrao=None: {"NFSE_CNPJ": "1", "NFSE_ENDPOINT_SOAP": "http://x"}.get(nome, padrao)):
            settings = get_nfse_settings()

        self.assertEqual(settings.cnpj, "1")
        self.assertEqual(settings.endpoint_soap, "http://x")

    def test_validacao_xsd_informa_xsd_invalido(self):
        from dsystem_erp.services.nfse_validacao import validar_xml_com_xsd

        with tempfile.TemporaryDirectory() as tmp:
            xsd = Path(tmp) / "schema.xsd"
            xsd.write_text("invalido", encoding="utf-8")
            erros = validar_xml_com_xsd("<root />", xsd)

        self.assertTrue(erros)

    def test_workflow_completo_emite_com_mocks(self):
        with mock.patch("dsystem_erp.services.nfse_workflow.assinar_nfse", return_value=b"<GerarNfseEnvio><CpfCnpj/><ValorServicos>10</ValorServicos><InfRps/></GerarNfseEnvio>"), \
             mock.patch("dsystem_erp.services.nfse_workflow.enviar_nfse", return_value=(b"<Retorno><NumeroNfse>9</NumeroNfse></Retorno>", {"status": "Autorizada", "numero_nfse": "9", "mensagem": "ok"})):
            resultado = executar_fluxo_emissao_nfse(
                {"id": 1, "cliente": "Cliente", "cnpj": "12345678901"},
                "Servico",
                {"valor": 10, "descricao": "Servico", "aliquota_iss": 0},
                endpoint="https://prefeitura.example",
                cert_path="cert.pfx",
                cert_password="1",
            )

        self.assertEqual(resultado.status, "Autorizada")
        self.assertTrue(resultado.aprovado)
        self.assertEqual(resultado.retorno_info["numero_nfse"], "9")

    def test_enviar_nfse_repassa_certificado_para_webservice(self):
        retorno = b"<Retorno><NumeroNfse>9</NumeroNfse></Retorno>"
        with mock.patch("dsystem_erp.services.nfse_workflow.chamar_webservice_nfse", return_value=retorno) as chamar:
            xml_retorno, info = enviar_nfse(
                "https://prefeitura.example",
                b"<xml />",
                timeout=15,
                cert_path="certificado.pfx",
                cert_password="1",
            )

        self.assertEqual(xml_retorno, retorno)
        self.assertEqual(info["status"], "Autorizada")
        chamar.assert_called_once_with(
            "https://prefeitura.example",
            b"<xml />",
            timeout=15,
            operacao="GerarNfse",
            cabecalho_xml=mock.ANY,
            cert_path="certificado.pfx",
            cert_password="1",
        )

    def test_consulta_protocolo_usa_operacao_e_xml_do_manual_pbh(self):
        with mock.patch("dsystem_erp.services.nfse_soap.chamar_webservice_nfse", return_value=b"<Retorno />") as chamar:
            consultar_protocolo_nfse(
                "https://prefeitura.example",
                "PROTOCOLO1",
                cnpj="23524449000154",
                inscricao_municipal="07395930011",
            )

        _, xml_consulta = chamar.call_args.args[:2]
        self.assertIn("ConsultarLoteRpsEnvio", xml_consulta)
        self.assertIn("<Protocolo>PROTOCOLO1</Protocolo>", xml_consulta)
        self.assertEqual(chamar.call_args.kwargs["operacao"], "ConsultarLoteRps")

    def test_resume_bloqueio_gocache(self):
        html = "<html><body>Acesso bloqueado ID da requisi&ccedil;&atilde;o: abc123 Seu endere&ccedil;o IP:</b> 1.2.3.4</body></html>"

        resumo = _resumo_bloqueio_gocache(html)

        self.assertIn("GoCache", resumo)
        self.assertIn("abc123", resumo)
        self.assertIn("1.2.3.4", resumo)

    def test_validar_nfse_retorna_xsd_ausente(self):
        erros = validar_nfse(b"<GerarNfseEnvio><CpfCnpj/><ValorServicos>1</ValorServicos><InfRps/></GerarNfseEnvio>", "faltando.xsd")

        self.assertTrue(any("XSD" in erro for erro in erros))


if __name__ == "__main__":
    unittest.main()

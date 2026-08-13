import unittest

from dsystem_erp.services.email import SMTPConfig, criar_mensagem, enviar_mensagem


class FakeSMTP:
    instancia = None

    def __init__(self, host, port, timeout):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.tls = False
        self.login_args = None
        self.mensagem = None
        FakeSMTP.instancia = self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def starttls(self):
        self.tls = True

    def login(self, user, password):
        self.login_args = (user, password)

    def send_message(self, mensagem):
        self.mensagem = mensagem


class EmailServiceTests(unittest.TestCase):
    def setUp(self):
        self.config = SMTPConfig(
            host="smtp.example.com",
            port=587,
            user="usuario@example.com",
            password="segredo",
            sender="sistema@example.com",
        )

    def test_exige_configuracao_completa(self):
        with self.assertRaises(RuntimeError):
            criar_mensagem(SMTPConfig("", 587, "", "", ""), "a@b.com", "Assunto", "Corpo")

    def test_monta_mensagem_com_anexo(self):
        mensagem = criar_mensagem(
            self.config,
            "cliente@example.com",
            "Orçamento",
            "Segue o documento.",
            nome_arquivo="orcamento.pdf",
            arquivo=b"PDF",
        )

        self.assertEqual(mensagem["From"], "sistema@example.com")
        self.assertEqual(mensagem["To"], "cliente@example.com")
        anexos = list(mensagem.iter_attachments())
        self.assertEqual(len(anexos), 1)
        self.assertEqual(anexos[0].get_filename(), "orcamento.pdf")

    def test_envia_com_tls_e_autenticacao(self):
        mensagem = criar_mensagem(self.config, "cliente@example.com", "Teste", "Corpo")
        enviar_mensagem(self.config, mensagem, smtp_factory=FakeSMTP)

        smtp = FakeSMTP.instancia
        self.assertTrue(smtp.tls)
        self.assertEqual(smtp.login_args, ("usuario@example.com", "segredo"))
        self.assertIs(smtp.mensagem, mensagem)


if __name__ == "__main__":
    unittest.main()

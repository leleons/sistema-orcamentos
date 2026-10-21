import unittest

from dsystem_erp.pages.login import renderizar_login


class FakeContainer:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class FakeStreamlit:
    def __init__(self, entrar=False):
        self.session_state = {}
        self.titulos = []
        self.entrar = entrar
        self.inputs = iter(("usuario", "senha"))
        self.rerun_chamado = False

    def title(self, texto):
        self.titulos.append(texto)

    def container(self):
        return FakeContainer()

    def form(self, *args, **kwargs):
        return FakeContainer()

    def form_submit_button(self, *args, **kwargs):
        return self.entrar

    def text_input(self, *args, **kwargs):
        return next(self.inputs)

    def button(self, *args, **kwargs):
        return self.entrar

    def rerun(self):
        self.rerun_chamado = True


class FakeCursor:
    def __init__(self, usuario):
        self.usuario = usuario
        self.comandos = []

    def execute(self, sql, params):
        self.comandos.append((sql, params))

    def fetchone(self):
        return self.usuario


class FakeConnection:
    def __init__(self, usuario):
        self.cursor_fake = FakeCursor(usuario)
        self.fechada = False

    def cursor(self, **kwargs):
        return self.cursor_fake

    def close(self):
        self.fechada = True


class LoginPageTests(unittest.TestCase):
    def test_login_funcionario_usa_senha_individual_e_vinculo_empresa(self):
        from unittest.mock import MagicMock
        st = FakeStreamlit(entrar=True)
        st.inputs = iter(('ANA@TESTE', 'senha-pessoal'))
        conexao = MagicMock()
        conexao.cursor.return_value.fetchone.side_effect = [None, None, {
            'id': 10, 'nome': 'Empresa', 'portal_conta_id': 3,
            'username': 'ana@teste', 'portal_usuario_nome': 'Ana',
            'portal_tipo_usuario': 'Funcionário', 'conta_password': 'hash-individual',
            'portal_password': 'hash-da-empresa', 'trocar_senha': 0,
            'twofa_secret': 'individual', 'twofa_ativo': 1,
        }]
        verificar = MagicMock(return_value=True)
        renderizar_login({
            'st': st, 'exibir_logo_dsystem': lambda *args: None,
            'conectar_banco': lambda: conexao, 'verificar_senha': verificar,
            'senha_esta_com_hash': lambda valor: True,
            'normalizar_documento_cliente': lambda valor: '',
            'registrar_tentativa_login': lambda *args: None,
        })
        verificar.assert_called_once_with('senha-pessoal', 'hash-individual')
        pendente = st.session_state['cliente_login_pendente']
        self.assertEqual(pendente['id'], 10)
        self.assertEqual(pendente['portal_username'], 'ana@teste')
        self.assertEqual(pendente['portal_tipo_usuario'], 'Funcionário')
        self.assertEqual(pendente['portal_2fa_secret'], 'individual')
        self.assertIn('p.ativo=1', conexao.cursor.return_value.execute.call_args.args[0])

    def test_renderiza_formulario_sem_acessar_banco_antes_do_botao(self):
        st = FakeStreamlit()
        logos = []

        renderizar_login({"st": st, "exibir_logo_dsystem": logos.append})

        self.assertEqual(logos, ["210"])
        self.assertEqual(st.titulos, ["Acesso ao Sistema Dsystem ERP"])

    def test_login_interno_preenche_sessao_sem_senha(self):
        st = FakeStreamlit(entrar=True)
        conexao = FakeConnection(
            {"id": 7, "username": "usuario", "password": "hash", "trocar_senha": 0}
        )
        tentativas = []

        renderizar_login(
            {
                "st": st,
                "exibir_logo_dsystem": lambda largura: None,
                "conectar_banco": lambda: conexao,
                "verificar_senha": lambda digitada, salva: True,
                "senha_esta_com_hash": lambda valor: True,
                "registrar_tentativa_login": lambda *args: tentativas.append(args),
                "registrar_evento_sistema": lambda *args: None,
            }
        )

        self.assertTrue(st.session_state["autenticado"])
        self.assertEqual(st.session_state["username"], "usuario")
        self.assertNotIn("password", st.session_state)
        self.assertTrue(st.rerun_chamado)
        self.assertTrue(conexao.fechada)
        self.assertEqual(len(conexao.cursor_fake.comandos), 1)
        self.assertEqual(tentativas[0][1], "usuario")


if __name__ == "__main__":
    unittest.main()

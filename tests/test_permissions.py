import unittest

from dsystem_erp.services.permissions import (
    carregar_submodulos,
    flags_legadas,
    permissoes_do_usuario,
    usuario_tem_alguma_permissao,
    usuario_tem_permissao,
    usuario_eh_gerencial,
)


class PermissionsTests(unittest.TestCase):
    def test_login_gerencial_ou_admin_visualiza_dados_internos(self):
        self.assertTrue(usuario_eh_gerencial({"modulo_gerencial": 1}))
        self.assertTrue(usuario_eh_gerencial({"is_admin": 1}))
        self.assertFalse(usuario_eh_gerencial({"modulo_gerencial": 0}))
        self.assertFalse(usuario_eh_gerencial({"modulo_gerencial": "0", "is_admin": "0"}))
        self.assertFalse(usuario_eh_gerencial({"tipo_login": "cliente", "is_admin": 1}))

    def test_carrega_lista_e_mapa_de_permissoes(self):
        self.assertEqual(carregar_submodulos('["clientes.view"]'), {"clientes.view"})
        self.assertEqual(
            carregar_submodulos('{"clientes.view": true, "clientes.delete": false}'),
            {"clientes.view"},
        )

    def test_admin_e_cliente_respeitam_escopos(self):
        self.assertTrue(usuario_tem_permissao("qualquer.acao", {"is_admin": 1}))
        cliente = {"tipo_login": "cliente"}
        self.assertTrue(usuario_tem_permissao("cliente.chamados", cliente))
        self.assertFalse(usuario_tem_permissao("estoque.view", cliente))

    def test_permissoes_novas_e_legadas(self):
        usuario = {"submodulos": '["infra.rede"]', "perm_clientes": 1}
        permissoes = permissoes_do_usuario(usuario)

        self.assertIn("clientes.view", permissoes)
        self.assertTrue(usuario_tem_alguma_permissao("infra", usuario))
        self.assertEqual(flags_legadas(permissoes)["perm_clientes"], 1)

    def test_usuario_legado_de_orcamentos_pode_abrir_para_edicao(self):
        usuario = {"perm_orcamentos": 1}

        self.assertTrue(usuario_tem_permissao("orcamentos.view", usuario))
        self.assertTrue(usuario_tem_permissao("orcamentos.edit", usuario))

    def test_visualizacao_de_senhas_exige_permissao_especifica(self):
        sem_permissao = {"submodulos": '["infra.view", "infra.edit"]'}
        com_permissao = {"submodulos": '["infra.view", "infra.senhas.view"]'}

        self.assertFalse(usuario_tem_permissao("infra.senhas.view", sem_permissao))
        self.assertTrue(usuario_tem_permissao("infra.senhas.view", com_permissao))
        self.assertFalse(usuario_tem_permissao("infra.senhas.view", {"is_admin": 1}))
        self.assertTrue(usuario_tem_permissao(
            "infra.senhas.view", {"is_admin": 1, "submodulos": '["infra.senhas.view"]'}
        ))

    def test_daniel_administrador_visualiza_senhas_sem_flag_legada(self):
        for nome in ("Daniel.fabio", "daniel.fabio", " Daniel.Fabio "):
            self.assertTrue(usuario_tem_permissao(
                "infra.senhas.view", {"username": nome, "is_admin": 1, "submodulos": "[]"}
            ))

    def test_excecao_principal_nao_libera_usuario_comum_ou_portal(self):
        for usuario in (
            {"username": "Daniel.fabio", "is_admin": 0},
            {"username": "Daniel.fabio", "is_admin": "0"},
            {"username": "outro", "is_admin": 1},
            {"username": "Daniel.fabio", "is_admin": 1, "tipo_login": "cliente"},
        ):
            self.assertFalse(usuario_tem_permissao("infra.senhas.view", usuario))


if __name__ == "__main__":
    unittest.main()

import unittest

from dsystem_erp.services.permissions import (
    carregar_submodulos,
    flags_legadas,
    permissoes_do_usuario,
    usuario_tem_alguma_permissao,
    usuario_tem_permissao,
)


class PermissionsTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()

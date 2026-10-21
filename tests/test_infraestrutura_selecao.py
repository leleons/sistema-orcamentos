import unittest
from pathlib import Path

from dsystem_erp.pages.infraestrutura import (
    CAMPOS_COMPOSTOS_INFRA,
    abrir_email_infraestrutura,
    abrir_ficha_infraestrutura,
    fechar_novos_emails_infraestrutura,
    fechar_email_infraestrutura,
    garantir_colunas_infra_acesso_remoto,
    ids_emails_cadastrados,
    buscar_senha_email_selecionado,
    anexar_grupo_infra,
    anexar_itens_infra,
    anexar_setores_infra,
    compor_item_composto_infra,
    decompor_item_composto_infra,
)


class InfraestruturaSelecaoTests(unittest.TestCase):
    def test_editor_busca_senha_que_nao_esta_na_listagem(self):
        from unittest.mock import MagicMock
        conectar = MagicMock()
        conn = conectar.return_value
        cursor = conn.cursor.return_value
        cursor.fetchone.return_value = {"senha": "senha-ficticia"}
        self.assertEqual(buscar_senha_email_selecionado(conectar, {"id": 97}, True), "senha-ficticia")
        cursor.execute.assert_called_once_with("SELECT senha FROM emails_clientes WHERE id=?", (97,))
        conn.close.assert_called_once()

    def test_senha_nao_e_consultada_sem_permissao_ou_selecao(self):
        from unittest.mock import MagicMock
        conectar = MagicMock()
        self.assertEqual(buscar_senha_email_selecionado(conectar, {"id": 97}, False), "")
        self.assertEqual(buscar_senha_email_selecionado(conectar, None, True), "")
        conectar.assert_not_called()

    def test_banco_antigo_recebe_colunas_de_acesso_remoto_antes_da_tela(self):
        class ConexaoFalsa:
            def __init__(self):
                self.comandos = []
                self.commits = 0
                self.fechada = False

            def cursor(self):
                return self

            def execute(self, sql, params=None):
                self.comandos.append((sql, params))

            def fetchone(self):
                return None

            def commit(self):
                self.commits += 1

            def close(self):
                self.fechada = True

        conexao = ConexaoFalsa()
        garantir_colunas_infra_acesso_remoto(lambda: conexao)
        alters = [sql for sql, _ in conexao.comandos if sql.startswith("ALTER TABLE")]
        self.assertEqual(len(alters), 5)
        self.assertTrue(any("serv_anydesk" in sql for sql in alters))
        self.assertTrue(any("impressoras_acessos" in sql for sql in alters))
        self.assertEqual(conexao.commits, 1)
        self.assertTrue(conexao.fechada)

    def test_clique_abre_ficha_e_atualiza_seletor_antigo(self):
        estado = {"infra_item_editar_id": 1, "edit_inf_id_selecao": 1,
                  "infra_acao_ficha": "Excluir Ficha"}
        abrir_ficha_infraestrutura(estado, 2)
        self.assertEqual(estado["infra_item_editar_id"], 2)
        self.assertEqual(estado["infra_editar_id"], 2)
        self.assertEqual(estado["edit_inf_id_selecao"], 2)
        self.assertEqual(estado["infra_acao_ficha"], "Editar Ficha Completa")
        self.assertEqual(estado["infra_grade_versao"], 1)

    def test_novo_clique_renova_grade_sem_apagar_outros_campos(self):
        estado = {"infra_grade_versao": 3, "outro_campo": "preservar"}
        abrir_ficha_infraestrutura(estado, "7")
        self.assertEqual(estado["infra_grade_versao"], 4)
        self.assertEqual(estado["edit_inf_id_selecao"], 7)
        self.assertEqual(estado["outro_campo"], "preservar")

    def test_email_clicado_consome_selecao_da_grade(self):
        estado = {"infra_email_grade_versao": 2, "infra_email_editar_id": 80,
                  "infra_email_senha_liberada_80": True,
                  "infra_email_senha_valor_80": "segredo"}
        abrir_email_infraestrutura(estado, "81")
        self.assertEqual(estado["infra_email_editar_id"], 81)
        self.assertEqual(estado["infra_email_grade_versao"], 3)
        self.assertNotIn("infra_email_senha_liberada_80", estado)
        self.assertNotIn("infra_email_senha_valor_80", estado)
        self.assertIn("infra_edit_em_senha_80", estado["_infra_widgets_para_limpar"])

    def test_fechar_email_limpa_edicao_e_consome_selecao(self):
        estado = {"infra_email_editar_id": 81, "infra_email_grade_versao": 3,
                  "infra_email_senha_liberada_81": True,
                  "infra_email_senha_valor_81": "segredo",
                  "infra_email_confirmar_senha_81": "segredo"}
        fechar_email_infraestrutura(estado)
        self.assertNotIn("infra_email_editar_id", estado)
        self.assertEqual(estado["infra_email_grade_versao"], 4)
        self.assertNotIn("infra_email_senha_liberada_81", estado)
        self.assertNotIn("infra_email_senha_valor_81", estado)
        self.assertIn("infra_email_confirmar_senha_81", estado["_infra_widgets_para_limpar"])

    def test_salvar_fecha_novos_emails_e_renova_campos(self):
        estado = {"infra_novos_emails_versao": 4}
        fechar_novos_emails_infraestrutura(estado)
        self.assertEqual(estado["infra_novos_emails_versao"], 5)

    def test_exclusao_em_massa_usa_somente_ids_validos_e_unicos(self):
        registros = [{"id": "7"}, {"id": 7}, {"id": 9}, {"id": None}, {}, "inválido"]
        self.assertEqual(ids_emails_cadastrados(registros), [7, 9])

    def test_exclusao_em_massa_aparece_antes_do_formulario_de_edicao(self):
        fonte = (Path(__file__).resolve().parents[1] / "dsystem_erp" / "pages" / "infraestrutura.py").read_text(encoding="utf-8")
        exclusao = fonte.index('with st.expander("Apagar todos os e-mails cadastrados deste cliente"')
        edicao = fonte.index('with st.expander(f"Editando: {email_editar.get(\'email\')}"')
        self.assertLess(exclusao, edicao)

    def test_senha_de_email_usa_permissao_sem_reconfirmar_login(self):
        fonte = (Path(__file__).resolve().parents[1] / "dsystem_erp" / "pages" / "infraestrutura.py").read_text(encoding="utf-8")
        self.assertIn('tem_permissao("infra.senhas.view")', fonte)
        self.assertIn("Senha cadastrada (use o olho para visualizar):", fonte)
        self.assertNotIn("Confirme a senha do usuário conectado", fonte)

    def test_novo_item_tecnico_e_anexado_sem_substituir_existentes(self):
        self.assertEqual(
            anexar_itens_infra("DVR antigo||DVR dois", ["DVR novo"]),
            "DVR antigo||DVR dois||DVR novo",
        )

    def test_grupo_tecnico_preserva_linhas_e_campos_vazios(self):
        ficha = {"serv_nome": "Servidor A|Servidor B", "serv_ip": "10.0.0.1|10.0.0.2", "serv_sen": "senha-a|senha-b"}
        resultado = anexar_grupo_infra(ficha, {
            "serv_nome": ["Servidor C"], "serv_ip": [""], "serv_sen": ["senha-c"],
        })
        self.assertEqual(resultado["serv_nome"], "Servidor A|Servidor B|Servidor C")
        self.assertEqual(resultado["serv_ip"], "10.0.0.1|10.0.0.2|")
        self.assertEqual(resultado["serv_sen"], "senha-a|senha-b|senha-c")

    def test_grupo_vazio_nao_cria_item_nem_apaga_historico(self):
        resultado = anexar_grupo_infra(
            {"sys_dados": "Sistema existente", "sys_serial": "ABC"},
            {"sys_dados": [""], "sys_serial": [""]},
        )
        self.assertEqual(resultado, {"sys_dados": "Sistema existente", "sys_serial": "ABC"})

    def test_setor_novo_e_acrescentado_ao_json_existente(self):
        resultado = anexar_setores_infra('[{"nome": "Comercial"}]', [{"nome": "TI"}])
        self.assertEqual([item["nome"] for item in __import__("json").loads(resultado)], ["Comercial", "TI"])

    def test_edicao_tecnica_nao_usa_mais_campos_em_bloco(self):
        fonte = (Path(__file__).resolve().parents[1] / "dsystem_erp" / "pages" / "infraestrutura.py").read_text(encoding="utf-8")
        self.assertIn("2. Registros técnicos — edição individual", fonte)
        self.assertIn("Salvar somente este item", fonte)
        self.assertNotIn('with st.expander("Editar demais blocos técnicos"', fonte)

    def test_hospedagem_legada_e_separada_em_campos_editaveis(self):
        valores = decompor_item_composto_infra(
            "hospedagem_acessos",
            "Provedor: Exemplo | Site Provedor: painel.exemplo | Login Hospedagem: daniel "
            "| Senha Hospedagem: segredo | 2FA Hospedagem: Sim | Local 2FA Hospedagem: celular "
            "| Domínio: exemplo.com.br | Registrado em: Registro.br | Site Registro Domínio: registro.br "
            "| Login Domínio: conta | Senha Domínio: outra | 2FA Domínio: Não | Local 2FA Domínio: ",
        )
        self.assertEqual(valores["provedor"], "Exemplo")
        self.assertEqual(valores["senha_hospedagem"], "segredo")
        self.assertEqual(valores["dominio"], "exemplo.com.br")
        self.assertEqual(valores["senha_dominio"], "outra")

    def test_formato_antigo_de_pc_separa_email_e_nome_remoto(self):
        valores = decompor_item_composto_infra(
            "pcs_acessos",
            "Notebook | Financeiro | AnyDesk: 123 / senha | Remote: ti@empresa.com / PC-FIN",
        )
        self.assertEqual(valores["tipo"], "Notebook")
        self.assertEqual(valores["nome"], "Financeiro")
        self.assertEqual(valores["anydesk"], "123 / senha")
        self.assertEqual(valores["remote_email"], "ti@empresa.com")
        self.assertEqual(valores["remote_nome"], "PC-FIN")
        self.assertEqual(valores["informacoes"], "")
        self.assertEqual(valores["usuario"], "")
        self.assertEqual(valores["senha"], "")

    def test_item_composto_regravado_mantem_marcadores_dos_campos(self):
        texto = compor_item_composto_infra("faixas_ip", {
            "faixa": "192.168.1.0/24",
            "informacao": "Rede administrativa",
        })
        self.assertEqual(texto, "Faixa: 192.168.1.0/24 | Informação: Rede administrativa")

    def test_todos_os_blocos_serializados_possuem_campos_individuais(self):
        esperados = {
            "faixas_ip", "dvr_acessos", "cameras_acessos", "alarmes_acessos",
            "serv_anydesk", "serv_radmin", "cert_log", "pfsense_acessos",
            "vpn_acessos", "impressoras_acessos", "antivirus_acessos",
            "pcs_acessos", "hospedagem_acessos", "aplicativos_acessos",
        }
        self.assertTrue(esperados.issubset(CAMPOS_COMPOSTOS_INFRA))
        self.assertTrue(all(CAMPOS_COMPOSTOS_INFRA[campo] for campo in esperados))

    def test_campos_simples_do_editor_usam_grade_como_email(self):
        fonte = (Path(__file__).resolve().parents[1] / "dsystem_erp" / "pages" / "infraestrutura.py").read_text(encoding="utf-8")
        self.assertIn("colunas_campos_simples = st.columns(3)", fonte)
        self.assertIn("with colunas_campos_simples[posicao_campo_simples % 3]", fonte)


if __name__ == "__main__":
    unittest.main()

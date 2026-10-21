import unittest
from unittest.mock import MagicMock
from dsystem_erp.services.nfe_item_cadastro import buscar_ncm_item, sugestoes_por_nome


class ItemCadastroTests(unittest.TestCase):
    def consulta(self, item, produtos, entradas, catalogo=None):
        conn = MagicMock()
        conn.cursor.return_value.fetchall.side_effect = [produtos, entradas]
        result = buscar_ncm_item(lambda: conn, item, catalogo or [])
        conn.close.assert_called_once()
        return result, conn

    def test_id_vinculado_tem_prioridade_e_nao_copia_cfop(self):
        result, conn = self.consulta({'estoque_id': 5, 'desc': 'Outro nome'}, [{'id': 5}],
                                    [{'ncm': '8471.60.53', 'cfop': '6102'}])
        self.assertEqual(result['ncm'], '84716053')
        self.assertNotIn('cfop', result)
        self.assertEqual(conn.cursor.return_value.execute.call_args_list[0].args[1], (5,))

    def test_nome_exato_unico(self):
        result, _ = self.consulta({'desc': ' MOUSE USB '},
                                 [{'id': 5, 'produto': 'Mouse USB'}, {'id': 6, 'produto': 'Mouse wireless'}],
                                 [{'ncm': '84716053'}])
        self.assertEqual(result['ncm'], '84716053')

    def test_nome_duplicado_ou_parcial_nao_escolhe(self):
        for nome, produtos in [('Mouse', [{'id': 5, 'produto': 'Mouse USB'}]),
                               ('Mouse', [{'id': 5, 'produto': 'Mouse'}, {'id': 6, 'produto': 'Mouse'}])]:
            result, _ = self.consulta({'desc': nome}, produtos, [])
            self.assertEqual(result['ncm'], '')

    def test_ncm_divergente_nao_escolhe(self):
        result, _ = self.consulta({'estoque_id': 5}, [{'id': 5}],
                                 [{'ncm': '84716053'}, {'ncm': '84716052'}])
        self.assertEqual(result['ncm'], '')

    def test_preserva_ncm_do_item(self):
        connect = MagicMock()
        self.assertEqual(buscar_ncm_item(connect, {'ncm': '84716053'})['ncm'], '84716053')
        connect.assert_not_called()

    def test_nome_generico_apenas_sugere(self):
        catalogo = [{'nome': 'Notebook até 3,5 kg', 'ncm': '84713012'},
                    {'nome': 'Notebook/outro portátil', 'ncm': '84713019'}]
        self.assertEqual(len(sugestoes_por_nome({'desc': 'Notebook'}, catalogo)), 2)
        self.assertEqual(sugestoes_por_nome({'desc': 'ddd'}, catalogo), [])

    def test_catalogo_nome_exato_preenche_sem_estoque(self):
        result, _ = self.consulta({'desc': '  CÂMERA USB  '}, [], [],
                                  [{'nome': 'Câmera USB', 'ncm': '8525.89.29'}])
        self.assertEqual(result['ncm'], '85258929')
        self.assertIn('automaticamente', result['mensagem'])

    def test_catalogo_nao_adivinha_nem_substitui_entrada_divergente(self):
        for produtos, entradas, catalogo in [
            ([], [], [{'nome': 'Mouse USB', 'ncm': '84716053'}]),
            ([], [], [{'nome': 'Mouse', 'ncm': '84716053'}, {'nome': 'Mouse', 'ncm': '84716052'}]),
            ([], [], [{'nome': 'Mouse', 'ncm': '84716053', 'ativo': 'Não'}]),
            ([{'id': 1, 'produto': 'Mouse'}], [{'ncm': '84716053'}, {'ncm': '84716052'}], [{'nome': 'Mouse', 'ncm': '84716053'}]),
        ]:
            result, _ = self.consulta({'desc': 'Mouse'}, produtos, entradas, catalogo)
            self.assertEqual(result['ncm'], '')

    def test_ncm_invalido_nao_remove_letras_para_inventar_codigo(self):
        result, _ = self.consulta({'estoque_id': 1}, [{'id': 1}], [{'ncm': '84716053X'}])
        self.assertEqual(result['ncm'], '')
        self.assertEqual(buscar_ncm_item(MagicMock(), {'ncm': '84716053X'})['ncm'], '')

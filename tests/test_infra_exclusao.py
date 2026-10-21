import json
import sqlite3
import unittest
from unittest.mock import Mock
from tests.test_fiscal_automatico import Connection
from dsystem_erp.pages.infraestrutura import excluir_item_salvo_infra


class ExclusaoInfraTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.row_factory = sqlite3.Row
        self.addCleanup(self.db.close)
        self.db.executescript('''CREATE TABLE infra_v4 (id INTEGER PRIMARY KEY,
            sys_dados TEXT,sys_senha TEXT,dvr_acessos TEXT,setores TEXT,fin_b1 TEXT,fin_b2 TEXT);
            CREATE TABLE infra_item_fotos (ficha_id INTEGER,tipo_item TEXT,item_indice INTEGER);
            INSERT INTO infra_v4 VALUES (1,'Sistema A|Sistema B','teste-a|teste-b','DVR A||DVR B','[]','Banco A','Banco B');
            INSERT INTO infra_item_fotos VALUES (1,'DVR',1),(1,'DVR',2),(2,'DVR',1),(1,'Câmera',1);''')
        self.conectar = lambda: Connection(self.db)

    def ficha(self):
        return dict(self.db.execute('SELECT * FROM infra_v4 WHERE id=1').fetchone())

    def test_exclui_so_posicao_escolhida_preservando_alinhamento(self):
        campos = [('sys_dados', 'Nome', '|'), ('sys_senha', 'Senha', '|')]
        excluir_item_salvo_infra(self.conectar, self.ficha(), campos, 0, True)
        atual = self.ficha()
        self.assertEqual(atual['sys_dados'], '|Sistema B')
        self.assertEqual(atual['sys_senha'], '|teste-b')
        self.assertEqual(atual['fin_b1'], 'Banco A')
        with self.assertRaises(ValueError): excluir_item_salvo_infra(self.conectar, atual, campos, 0, True)

    def test_remove_fotos_apenas_do_item_sem_renumerar_outros(self):
        excluir_item_salvo_infra(self.conectar, self.ficha(), [('dvr_acessos','DVR','||')], 0, True)
        self.assertEqual(self.ficha()['dvr_acessos'], '||DVR B')
        restantes = [tuple(r) for r in self.db.execute('SELECT * FROM infra_item_fotos')]
        self.assertEqual(restantes, [(1,'DVR',2),(2,'DVR',1),(1,'Câmera',1)])

    def test_setor_exclui_so_o_escolhido(self):
        setores = [{'nome':'A','softwares':[{'nome':'Teste'}]}, {'nome':'B'}]
        self.db.execute('UPDATE infra_v4 SET setores=?', (json.dumps(setores),))
        self.db.commit()
        excluir_item_salvo_infra(self.conectar, self.ficha(), [('setores','Setores','')], 0, True)
        self.assertEqual(json.loads(self.ficha()['setores']), [setores[1]])

    def test_banco_individual_nao_apaga_outros(self):
        excluir_item_salvo_infra(self.conectar, self.ficha(), [('fin_b1','Banco 1','||')], 0, True)
        self.assertEqual(self.ficha()['fin_b1'], '')
        self.assertEqual(self.ficha()['fin_b2'], 'Banco B')

    def test_ficha_alterada_impede_excluir_posicao_desatualizada(self):
        ficha = self.ficha()
        self.db.execute("UPDATE infra_v4 SET sys_dados='Outro'")
        self.db.commit()
        with self.assertRaisesRegex(ValueError, 'alterada'):
            excluir_item_salvo_infra(self.conectar, ficha, [('sys_dados','Nome','|')], 0, True)
        self.assertEqual(self.ficha()['sys_dados'], 'Outro')

    def test_sem_permissao_nao_abre_banco(self):
        conectar = Mock()
        with self.assertRaises(PermissionError): excluir_item_salvo_infra(conectar, self.ficha(), [('sys_dados','Nome','|')], 0, False)
        conectar.assert_not_called()

import sqlite3
import tempfile
import unittest
from pathlib import Path

from dsystem_erp.repositories.uber import TIPOS_CORRIDA, validar_corrida, salvar_corrida, listar_corridas


class UberTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'test.db'
        conn = self.conectar()
        conn.executescript('''
            CREATE TABLE clientes (id INTEGER PRIMARY KEY, nome TEXT);
            INSERT INTO clientes VALUES (1, 'Cliente A'), (2, 'Cliente B');
            CREATE TABLE uber_corridas (
                id INTEGER PRIMARY KEY AUTOINCREMENT, data_corrida TEXT, finalidade TEXT,
                valor_total NUMERIC, colaboradores TEXT, produtos TEXT, origem TEXT, destino TEXT,
                observacoes TEXT, status TEXT DEFAULT 'Registrada', criado_por TEXT, criado_em TEXT,
                alterado_por TEXT, alterado_em TEXT);
            CREATE TABLE uber_corrida_clientes (
                corrida_id INTEGER, cliente_id INTEGER, cliente_nome TEXT,
                PRIMARY KEY(corrida_id, cliente_id));
        ''')
        conn.close()
        self.dados = dict(data_corrida='03/09/2026', valor_total=45.50,
                          finalidade=TIPOS_CORRIDA[0], cliente_ids=[1, 2, 1], produtos='Impressora')

    def conectar(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def test_multiplos_clientes_valor_unico_e_edicao(self):
        id_ = salvar_corrida(self.conectar, self.dados, 'tecnico', clientes_permitidos=[1, 2])
        registros = listar_corridas(self.conectar)
        self.assertEqual(len(registros), 1)
        self.assertEqual(len(registros[0]['clientes']), 2)
        self.assertEqual(registros[0]['valor_total'], 45.5)
        salvar_corrida(self.conectar, dict(self.dados, cliente_ids=[2], valor_total=50), 'gestor', id_, [1, 2])
        atual = listar_corridas(self.conectar)
        self.assertEqual(len(atual), 1)
        self.assertEqual([c['cliente_id'] for c in atual[0]['clientes']], [2])
        self.assertEqual(atual[0]['valor_total'], 50)
        self.assertEqual(atual[0]['alterado_por'], 'gestor')

    def test_validacao(self):
        for alteracao in (dict(valor_total=0), dict(valor_total='NaN'), dict(cliente_ids=[]),
                          dict(produtos=''), dict(data_corrida='invalida'),
                          dict(finalidade=TIPOS_CORRIDA[2], colaboradores=[])):
            with self.subTest(alteracao=alteracao), self.assertRaises(ValueError):
                validar_corrida(dict(self.dados, **alteracao))
        dados = validar_corrida(dict(self.dados, finalidade=TIPOS_CORRIDA[2], colaboradores=['tecnico'], produtos=''))
        self.assertEqual(dados['colaboradores'], ['tecnico'])

    def test_cliente_inexistente_nao_salva_parcial(self):
        with self.assertRaises(ValueError):
            salvar_corrida(self.conectar, dict(self.dados, cliente_ids=[1, 99]), 'tecnico')
        self.assertEqual(listar_corridas(self.conectar), [])

    def test_permissao_todos_os_clientes(self):
        with self.assertRaises(ValueError):
            salvar_corrida(self.conectar, self.dados, 'tecnico', clientes_permitidos=[1])
        id_ = salvar_corrida(self.conectar, self.dados, 'gestor', clientes_permitidos=[1, 2])
        with self.assertRaises(ValueError):
            salvar_corrida(self.conectar, dict(self.dados, cliente_ids=[1]), 'tecnico', id_, [1])
        self.assertEqual(len(listar_corridas(self.conectar)[0]['clientes']), 2)

    def test_rollback_se_vinculo_falhar(self):
        id_ = salvar_corrida(self.conectar, self.dados, 'tecnico')
        conn = self.conectar()
        conn.execute("CREATE TRIGGER falhar BEFORE INSERT ON uber_corrida_clientes BEGIN SELECT RAISE(ABORT, 'falha'); END")
        conn.commit()
        conn.close()
        with self.assertRaises(sqlite3.IntegrityError):
            salvar_corrida(self.conectar, dict(self.dados, cliente_ids=[1], valor_total=90), 'tecnico', id_)
        atual = listar_corridas(self.conectar)[0]
        self.assertEqual(atual['valor_total'], 45.5)
        self.assertEqual(len(atual['clientes']), 2)

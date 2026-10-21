"""Ledger Inter transacional; usa a fábrica MySQL do ERP, sem criar schema ao importar.

O adaptador SQLite é exclusivo de simulações/testes. Nenhuma tabela financeira
é copiada ou migrada automaticamente. Todos os registros têm empresa e ambiente.
"""
from contextlib import contextmanager
import json
import sqlite3


DDL = (
    '''CREATE TABLE IF NOT EXISTS inter_empresas (
        id INTEGER PRIMARY KEY, nome VARCHAR(180) NOT NULL, cnpj VARCHAR(14) NOT NULL UNIQUE)''',
    '''CREATE TABLE IF NOT EXISTS inter_acessos (
        empresa_id INTEGER NOT NULL, usuario VARCHAR(120) NOT NULL,
        PRIMARY KEY (empresa_id, usuario))''',
    '''CREATE TABLE IF NOT EXISTS inter_contas (
        empresa_id INTEGER NOT NULL, ambiente VARCHAR(12) NOT NULL,
        conta VARCHAR(30) NOT NULL, credencial_secret TEXT NOT NULL,
        PRIMARY KEY (empresa_id, ambiente))''',
    '''CREATE TABLE IF NOT EXISTS inter_operacoes (
        id VARCHAR(36) PRIMARY KEY, empresa_id INTEGER NOT NULL, ambiente VARCHAR(12) NOT NULL,
        chave VARCHAR(120) NOT NULL, tipo VARCHAR(40) NOT NULL, payload_secret LONGTEXT NOT NULL,
        digest VARCHAR(64) NOT NULL, estado VARCHAR(32) NOT NULL, criado_por VARCHAR(120) NOT NULL,
        aprovado_por VARCHAR(120), externo VARCHAR(80), resposta_secret LONGTEXT,
        erro VARCHAR(80), criado_em VARCHAR(40) NOT NULL,
        UNIQUE(empresa_id, ambiente, chave))''',
    '''CREATE TABLE IF NOT EXISTS inter_auditoria (
        id VARCHAR(36) PRIMARY KEY, empresa_id INTEGER NOT NULL, ambiente VARCHAR(12) NOT NULL,
        operacao_id VARCHAR(36), usuario VARCHAR(120) NOT NULL,
        evento VARCHAR(80) NOT NULL, criado_em VARCHAR(40) NOT NULL)''',
    '''CREATE TABLE IF NOT EXISTS inter_vinculos_financeiros (
        empresa_id INTEGER NOT NULL, ambiente VARCHAR(12) NOT NULL,
        operacao_id VARCHAR(36) NOT NULL UNIQUE, tabela VARCHAR(32) NOT NULL,
        titulo_id INTEGER NOT NULL, valor VARCHAR(30) NOT NULL,
        UNIQUE(ambiente, tabela, titulo_id))''',
    '''CREATE TABLE IF NOT EXISTS inter_liquidacoes (
        empresa_id INTEGER NOT NULL, ambiente VARCHAR(12) NOT NULL,
        evento_id VARCHAR(120) NOT NULL, operacao_id VARCHAR(36) NOT NULL,
        valor VARCHAR(30) NOT NULL, data_liquidacao VARCHAR(40) NOT NULL,
        PRIMARY KEY(empresa_id, ambiente, evento_id),
        UNIQUE(empresa_id, ambiente, operacao_id))''',
    '''CREATE TABLE IF NOT EXISTS inter_titulos_empresas (
        tabela VARCHAR(32) NOT NULL, titulo_id INTEGER NOT NULL,
        empresa_id INTEGER NOT NULL, PRIMARY KEY(tabela,titulo_id))''',
    '''CREATE TABLE IF NOT EXISTS inter_painel (
        empresa_id INTEGER PRIMARY KEY, snapshot_secret LONGTEXT,
        credencial_digest VARCHAR(64), atualizado_em VARCHAR(40),
        tentativa_em VARCHAR(40), erro VARCHAR(80), ultimo_slot VARCHAR(40),
        lock_token VARCHAR(36), lock_ate VARCHAR(40))''',
    '''CREATE TABLE IF NOT EXISTS inter_painel_agenda (
        empresa_id INTEGER PRIMARY KEY, usuario VARCHAR(120) NOT NULL,
        ativo INTEGER NOT NULL DEFAULT 0, configurado_em VARCHAR(40) NOT NULL)''',
)


class RepositorioInter:
    def __init__(self, conectar, *, sqlite=False, financeiro_teste=False):
        self.conectar, self.sqlite, self.financeiro_teste = conectar, sqlite, financeiro_teste

    @contextmanager
    def transacao(self):
        conn = self.conectar()
        try:
            if self.sqlite:
                conn.row_factory = sqlite3.Row
                conn.execute('BEGIN IMMEDIATE')
                cursor = conn.cursor()
            else:
                cursor = conn.cursor(dictionary=True)
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def executar(self, cursor, sql, params=()):
        return cursor.execute(sql.replace('%s', '?') if self.sqlite else sql, params)

    def schema(self):
        """Chamada administrativa explícita; nunca executada pelo startup do ERP."""
        with self.transacao() as c:
            for sql in DDL:
                self.executar(c, sql + ('' if self.sqlite else ' ENGINE=InnoDB'))

    def empresas(self, usuario):
        with self.transacao() as c:
            self.executar(c, '''SELECT e.* FROM inter_empresas e JOIN inter_acessos a
                ON a.empresa_id=e.id WHERE a.usuario=%s ORDER BY e.nome''', (usuario,))
            return [dict(r) for r in c.fetchall()]

    def exigir_empresa(self, cursor, empresa, usuario):
        self.executar(cursor, 'SELECT empresa_id FROM inter_acessos WHERE empresa_id=%s AND usuario=%s', (empresa, usuario))
        if not cursor.fetchone():
            raise PermissionError('Usuário sem vínculo com esta empresa bancária.')

    def operacao(self, cursor, empresa, ambiente, identificador, *, travar=False):
        sql = 'SELECT * FROM inter_operacoes WHERE empresa_id=%s AND ambiente=%s AND id=%s'
        if travar and not self.sqlite:
            sql += ' FOR UPDATE'
        self.executar(cursor, sql, (empresa, ambiente, identificador))
        registro = cursor.fetchone()
        if not registro:
            raise PermissionError('Operação não encontrada neste ambiente/empresa.')
        return dict(registro)

    def listar(self, empresa, ambiente, usuario):
        with self.transacao() as c:
            self.exigir_empresa(c, empresa, usuario)
            self.executar(c, '''SELECT id, tipo, estado, criado_por, aprovado_por, externo, erro, criado_em
                FROM inter_operacoes WHERE empresa_id=%s AND ambiente=%s ORDER BY criado_em DESC''', (empresa, ambiente))
            return [dict(r) for r in c.fetchall()]

    def registrar(self, cursor, empresa, ambiente, usuario, evento, operacao=None):
        from uuid import uuid4
        from datetime import datetime, timezone
        self.executar(cursor, '''INSERT INTO inter_auditoria
            (id, empresa_id, ambiente, usuario, evento, operacao_id, criado_em) VALUES (%s,%s,%s,%s,%s,%s,%s)''',
            (str(uuid4()), empresa, ambiente, usuario, evento, operacao, datetime.now(timezone.utc).isoformat()))


def criar_repositorio_demo(caminho, usuario):
    """Banco isolado, sem abrir a conexão real configurada no ERP."""
    repo = RepositorioInter(lambda: sqlite3.connect(caminho, timeout=10), sqlite=True)
    repo.schema()
    with repo.transacao() as c:
        c.execute('INSERT OR IGNORE INTO inter_empresas VALUES (1,?,?)', ('Empresa fictícia — DEMO', '00000000000000'))
        c.execute('INSERT OR IGNORE INTO inter_acessos VALUES (1,?)', (usuario,))
    return repo

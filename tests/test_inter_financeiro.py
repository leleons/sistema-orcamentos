from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from dsystem_erp.repositories.inter import RepositorioInter
from dsystem_erp.services.inter_api import InterSimulado, InterErro
from dsystem_erp.services.inter_financeiro import FinanceiroInter, dinheiro
from dsystem_erp.services.inter_conciliacao import vincular_titulo, conciliar_operacao, sincronizar_vinculados, liquidacao_confirmada
from dsystem_erp.services.permissions import usuario_tem_permissao


PERMISSOES = ['inter.'+p for p in ('view','preparar','aprovar','executar','conciliar','configurar')]


def usuario(nome):
    return {'username':nome,'autenticado':True,'tipo_login':'interno','submodulos':PERMISSOES}


class InterFinanceiroTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.caminho = Path(self.tmp.name)/'teste.sqlite'
        self.repo = RepositorioInter(lambda:sqlite3.connect(self.caminho,timeout=10),sqlite=True,financeiro_teste=True)
        self.repo.schema()
        self.a, self.b = usuario('preparador'), usuario('aprovador')
        self.sim = InterSimulado()
        self.servico = FinanceiroInter(self.repo,self.sim,b'x'*32)
        with self.repo.transacao() as c:
            c.executemany('INSERT INTO inter_empresas VALUES (?,?,?)',[(1,'A','00000000000001'),(2,'B','00000000000002')])
            c.executemany('INSERT INTO inter_acessos VALUES (?,?)',[(1,'preparador'),(1,'aprovador'),(2,'outro')])
            for tabela in ('contas_pagar','contas_receber'):
                c.execute(f'''CREATE TABLE {tabela} (id INTEGER PRIMARY KEY,valor_total TEXT,valor_baixado TEXT,
                    status TEXT,data_baixa TEXT,observacao_baixa TEXT,baixado_por TEXT,conciliado TEXT,data_conciliacao TEXT)''')
                c.execute(f"INSERT INTO {tabela} VALUES (1,'10.00','0','Aberto',NULL,NULL,NULL,'Nao',NULL)")
                c.execute('INSERT INTO inter_titulos_empresas VALUES (?,1,1)',(tabela,))

    def preparar(self, chave='unica', tipo='pix_enviar', payload=None, identificador=None):
        return self.servico.criar(1,self.a,tipo,payload or {'valor':10,'destinatario':{'tipo':'CHAVE','chave':'ficticia'}},chave,identificador)

    def aprovar(self, uid):
        d = self.servico.detalhes(1,self.a,uid)
        self.servico.aprovar(1,self.b,uid,d['digest'],'CONFIRMAR '+uid)

    def enviar(self):
        uid = self.preparar()
        self.aprovar(uid)
        self.assertEqual(self.servico.executar(1,self.a,uid),'ENVIADA')
        return uid

    def liquidar_simulado(self, uid, valor='10.00'):
        externo = self.servico.detalhes(1,self.a,uid)['externo']
        self.sim.resultados[(1,externo)] = {'transacaoPix':{'status':'EFETIVADO','codigoSolicitacao':externo,
            'endToEnd':'E-ficticio-unico','valor':valor,'dataHoraMovimento':'2026-10-16T10:00:00-03:00'}}

    def test_idempotencia_conflito_e_dados_cifrados(self):
        uid = self.preparar()
        self.assertEqual(self.preparar(),uid)
        with self.assertRaises(ValueError):
            self.preparar(payload={'valor':11,'destinatario':{'tipo':'CHAVE','chave':'ficticia'}})
        self.assertNotIn(b'ficticia',self.caminho.read_bytes())
        self.assertEqual(len(self.repo.listar(1,'simulacao','preparador')),1)

    def test_admin_precisa_permissao_explicita(self):
        self.assertFalse(usuario_tem_permissao('inter.executar',{'is_admin':1,'username':'Daniel.fabio'}))
        for u in ({**self.a,'autenticado':False},{**self.a,'tipo_login':'cliente'},{**self.a,'submodulos':[]}):
            with self.assertRaises(PermissionError):
                self.servico.criar(1,u,'pix_enviar',{'valor':10,'destinatario':{'tipo':'CHAVE','chave':'x'}},'x')

    def test_isolamento_empresa_e_ambiente(self):
        uid = self.preparar()
        for e, u in [(2,self.a),(2,usuario('outro')),(1,usuario('outro'))]:
            with self.assertRaises(PermissionError):
                self.servico.detalhes(e,u,uid)
        with self.repo.transacao() as c:
            with self.assertRaises(PermissionError):
                self.repo.operacao(c,1,'sandbox',uid)
        self.assertEqual(self.sim.chamadas,[])

    def test_confirmacao_digest_e_dupla_aprovacao(self):
        uid = self.preparar()
        d = self.servico.detalhes(1,self.a,uid)
        for ator, digest, texto, erro in [(self.a,d['digest'],'CONFIRMAR '+uid,PermissionError),
            (self.b,'errado','CONFIRMAR '+uid,ValueError),(self.b,d['digest'],'sim',ValueError)]:
            with self.assertRaises(erro):
                self.servico.aprovar(1,ator,uid,digest,texto)
        with self.assertRaises(ValueError):
            self.servico.executar(1,self.a,uid)
        self.aprovar(uid)
        self.assertEqual(self.servico.detalhes(1,self.a,uid)['estado'],'APROVADA')

    def test_envio_concorrente_exatamente_uma_chamada(self):
        uid = self.preparar()
        self.aprovar(uid)
        def enviar(_):
            try:
                return self.servico.executar(1,self.a,uid)
            except ValueError:
                return 'BLOQUEADA'
        with ThreadPoolExecutor(2) as pool:
            self.assertCountEqual(list(pool.map(enviar,range(2))),['ENVIADA','BLOQUEADA'])
        self.assertEqual(len(self.sim.chamadas),1)

    def test_timeout_nao_reenvia(self):
        uid = self.preparar()
        self.aprovar(uid)
        with patch.object(self.sim,'chamar',side_effect=InterErro('TIMEOUT',incerto=True)) as chamar:
            self.assertEqual(self.servico.executar(1,self.a,uid),'INCERTA')
            with self.assertRaises(ValueError):
                self.servico.executar(1,self.a,uid)
            self.assertEqual(chamar.call_count,1)

    def test_baixa_somente_liquidada_uma_vez(self):
        uid = self.enviar()
        vincular_titulo(self.servico,1,self.a,uid,1)
        self.assertEqual(conciliar_operacao(self.servico,1,self.a,uid),'AGUARDANDO_LIQUIDACAO')
        self.liquidar_simulado(uid)
        self.assertEqual(conciliar_operacao(self.servico,1,self.a,uid),'CONCILIADA')
        self.assertEqual(conciliar_operacao(self.servico,1,self.a,uid),'JA_CONCILIADA')
        with self.repo.transacao() as c:
            r = c.execute('SELECT * FROM contas_pagar').fetchone()
            self.assertEqual((r['status'],r['valor_baixado'],r['conciliado']),('Pago','10.00','Sim'))
            self.assertEqual(c.execute('SELECT COUNT(*) FROM inter_liquidacoes').fetchone()[0],1)

    def test_divergencia_nao_baixa(self):
        uid = self.enviar()
        vincular_titulo(self.servico,1,self.a,uid,1)
        self.liquidar_simulado(uid,'9.00')
        self.assertEqual(conciliar_operacao(self.servico,1,self.a,uid),'REVISAO_VALOR_OU_VINCULO')
        with self.repo.transacao() as c:
            self.assertEqual(c.execute('SELECT status FROM contas_pagar').fetchone()[0],'Aberto')

    def test_sem_empresa_validada_nao_vincula(self):
        uid = self.preparar()
        with self.repo.transacao() as c:
            c.execute('UPDATE inter_titulos_empresas SET empresa_id=2')
        with self.assertRaises(PermissionError):
            vincular_titulo(self.servico,1,self.a,uid,1)

    def test_polling_so_vinculados_sem_escrita_bancaria(self):
        uid = self.enviar()
        vincular_titulo(self.servico,1,self.a,uid,1)
        self.liquidar_simulado(uid)
        self.assertEqual(sincronizar_vinculados(self.servico,1,self.a),{uid:'CONCILIADA'})
        self.assertEqual(sincronizar_vinculados(self.servico,1,self.a),{})
        self.assertEqual(len([c for c in self.sim.chamadas if c[1]=='pix_enviar']),1)

    def test_baixa_rollback_integral(self):
        uid = self.enviar()
        vincular_titulo(self.servico,1,self.a,uid,1)
        self.liquidar_simulado(uid)
        original = self.repo.executar
        def falhar(c,sql,params=()):
            if 'INSERT INTO inter_liquidacoes' in sql:
                raise RuntimeError('falha simulada')
            return original(c,sql,params)
        with patch.object(self.repo,'executar',side_effect=falhar):
            with self.assertRaises(RuntimeError):
                conciliar_operacao(self.servico,1,self.a,uid)
        with self.repo.transacao() as c:
            self.assertEqual(c.execute('SELECT status FROM contas_pagar').fetchone()[0],'Aberto')

    def test_marcado_recebido_nao_e_liquidacao(self):
        d = {'tipo':'boleto_emitir','externo':'abc'}
        self.assertIsNone(liquidacao_confirmada(d,{'cobranca':{'situacao':'MARCADO_RECEBIDO','codigoSolicitacao':'abc'}}))

    def test_pagamento_boleto_exige_realizado_e_autenticacao(self):
        d = {'tipo':'conta_pagar','externo':'abc'}
        r = [{'codigoTransacao':'abc','statusPagamento':'REALIZADO','autenticacao':'banco', 'valorPago':10,'dataPagamento':'2026-10-16'}]
        self.assertEqual(liquidacao_confirmada(d,r),('pagamento:abc','10.00','2026-10-16'))
        r[0]['statusPagamento'] = 'APROVADO'
        self.assertIsNone(liquidacao_confirmada(d,r))

    def test_pix_automatico_exige_autorizacao_devedor(self):
        uid = self.preparar(tipo='rec_cobrar',payload={'idRec':'rec123','recebedor':{'conta':'123'},'valor':{'original':'10.00'},'calendario':{'dataDeVencimento':'2026-12-01'}},identificador='a'*26)
        self.aprovar(uid)
        self.assertEqual(self.servico.executar(1,self.a,uid),'RECUSADA')
        self.assertEqual([c[1] for c in self.sim.chamadas],['rec_consultar'])

    def test_folha_pix_individual_idempotente(self):
        itens = [{'funcionario_id':i,'payload':{'valor':10,'destinatario':{'tipo':'CHAVE','chave':f'ficticia-{i}'}}} for i in (1,2)]
        ids = self.servico.criar_folha_pix(1,self.a,'2026-10',itens)
        self.assertEqual(ids,self.servico.criar_folha_pix(1,self.a,'2026-10',itens))
        self.assertEqual(len(set(ids)),2)
        self.assertEqual(self.sim.chamadas,[])

    def test_valores_invalidos(self):
        for valor in ('NaN','Infinity','0','-1','0.001'):
            with self.assertRaises(ValueError):
                dinheiro(valor)

    def test_titulo_alterado_impede_envio_aprovado(self):
        uid = self.preparar()
        vincular_titulo(self.servico,1,self.a,uid,1)
        self.aprovar(uid)
        with self.repo.transacao() as c:
            c.execute("UPDATE contas_pagar SET status='Pago'")
        with self.assertRaisesRegex(ValueError,'Título alterado'):
            self.servico.executar(1,self.a,uid)
        self.assertEqual(self.sim.chamadas,[])

    def test_preparar_titulo_reutiliza_dados_e_vincula(self):
        from dsystem_erp.services.inter_titulos import preparar_titulo
        with self.repo.transacao() as c:
            c.execute('ALTER TABLE contas_pagar ADD COLUMN chave_pix TEXT')
            c.execute("UPDATE contas_pagar SET chave_pix='chave-do-cadastro'")
        uid = preparar_titulo(self.servico,1,self.a,'contas_pagar',1,'pix_enviar')
        self.assertEqual(preparar_titulo(self.servico,1,self.a,'contas_pagar',1,'pix_enviar'),uid)
        d = self.servico.detalhes(1,self.a,uid)
        self.assertEqual(d['payload']['destinatario']['chave'],'chave-do-cadastro')
        self.assertEqual(d['payload']['valor'],10)
        self.assertEqual(d['estado'],'PENDENTE_APROVACAO')

    def test_sem_ambiente_financeiro_teste_nunca_baixa(self):
        uid = self.enviar()
        self.repo.financeiro_teste = False
        with self.assertRaises(PermissionError):
            conciliar_operacao(self.servico,1,self.a,uid)
        with self.assertRaises(PermissionError):
            vincular_titulo(self.servico,1,self.a,uid,1)

    def boleto(self):
        return {'seuNumero':'1','valorNominal':10,'dataVencimento':'2027-01-10','numDiasAgenda':30,
                'pagador':{'cpfCnpj':'00000000000000','tipoPessoa':'JURIDICA','nome':'Ficticio',
                'endereco':'Rua teste','bairro':'Centro','cidade':'Sabara','uf':'MG','cep':'00000000'},
                'formasRecebimento':['BOLETO','PIX']}

    def test_boleto_recebido_baixa_contas_receber(self):
        uid = self.preparar(tipo='boleto_emitir',payload=self.boleto())
        self.aprovar(uid)
        self.servico.executar(1,self.a,uid)
        vincular_titulo(self.servico,1,self.a,uid,1)
        externo = self.servico.detalhes(1,self.a,uid)['externo']
        self.sim.resultados[(1,externo)] = {'cobranca':{'situacao':'RECEBIDO','codigoSolicitacao':externo,
            'valorTotalRecebido':10,'dataSituacao':'2026-10-16'}}
        self.assertEqual(conciliar_operacao(self.servico,1,self.a,uid),'CONCILIADA')
        with self.repo.transacao() as c:
            self.assertEqual(c.execute('SELECT status FROM contas_receber').fetchone()[0],'Recebido')
            self.assertEqual(c.execute('SELECT status FROM contas_pagar').fetchone()[0],'Aberto')

    def test_recorrencia_mensal_sem_duplicar_competencia(self):
        uid = self.servico.cobranca_mensal(1,self.a,1,'2026-10',self.boleto())
        self.assertEqual(self.servico.cobranca_mensal(1,self.a,1,'2026-10',self.boleto()),uid)
        outro = self.servico.cobranca_mensal(1,self.a,1,'2026-11',self.boleto())
        self.assertNotEqual(outro,uid)
        self.assertEqual(self.sim.chamadas,[])

    def test_pix_recebido_identidade_e_devolucao(self):
        d = {'tipo':'pix_receber','externo':'a'*26}
        r = {'status':'CONCLUIDA','txid':'a'*26,'pix':[{'endToEndId':'E123','valor':'10.00','horario':'2026-10-16'}]}
        self.assertEqual(liquidacao_confirmada(d,r),('E123','10.00','2026-10-16'))
        r['txid'] = 'b'*26
        self.assertIsNone(liquidacao_confirmada(d,r))
        r['txid'] = 'a'*26
        r['pix'][0]['devolucoes'] = [{'id':'d1'}]
        self.assertIsNone(liquidacao_confirmada(d,r))

    def test_titulo_de_recebimento_usa_cadastro_cliente(self):
        from dsystem_erp.services.inter_titulos import preparar_titulo
        with self.repo.transacao() as c:
            c.execute('ALTER TABLE contas_receber ADD COLUMN cliente_id INTEGER')
            c.execute('ALTER TABLE contas_receber ADD COLUMN data_vencimento TEXT')
            c.execute("UPDATE contas_receber SET cliente_id=3,data_vencimento='10/01/2027'")
            c.execute('''CREATE TABLE clientes (id INTEGER PRIMARY KEY, nome TEXT, cnpj TEXT,
                endereco TEXT, numero TEXT, bairro TEXT, cidade_estado TEXT, uf TEXT, cep TEXT)''')
            c.execute("INSERT INTO clientes VALUES (3,'Cliente ficticio','00000000000000','Rua teste','1','Centro','Sabara/MG','MG','00000000')")
        uid = preparar_titulo(self.servico,1,self.a,'contas_receber',1,'boleto_emitir')
        d = self.servico.detalhes(1,self.a,uid)
        self.assertEqual(d['payload']['pagador']['nome'],'Cliente ficticio')
        self.assertEqual(d['payload']['pagador']['cidade'],'Sabara')
        self.assertEqual(d['payload']['dataVencimento'],'2027-01-10')


if __name__ == '__main__':
    unittest.main()

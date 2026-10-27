"""Produção exercitada somente com credenciais fictícias, SQLite e HTTP simulado."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch

import requests

from dsystem_erp.repositories.inter import RepositorioInter
from dsystem_erp.services.inter_api import ClienteInter, CredencialInter, OPERACOES, MOVIMENTACOES_PRODUCAO, CONSULTAS_PRODUCAO, cifrar_credencial
from dsystem_erp.services.inter_financeiro import FinanceiroInter
from dsystem_erp.services.inter_producao import ProducaoInter, OrigemFaturamento, hoje
from dsystem_erp.services.inter_runtime import configurar_movimentacoes, movimentacao_producao_liberada
from tests.test_inter_api import resposta
from tests.test_inter_financeiro import usuario


class ProducaoTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.pasta = Path(tmp.name)
        self.repo = RepositorioInter(lambda: sqlite3.connect(self.pasta/'inter.sqlite', timeout=10), sqlite=True)
        self.repo.schema()
        self.usuarios = {n: dict(usuario(n), is_admin=1 if n == 'preparador' else 0) for n in ('preparador','aprovador','outro')}
        self.a, self.b = self.usuarios['preparador'], self.usuarios['aprovador']
        cert = self.pasta/'ficticio.pem'
        cert.touch()
        escopos = sorted({v[2] for v in OPERACOES.values()})
        self.cred = CredencialInter(1, '12345', 'id-ficticio', 'secret-ficticio', str(cert), str(cert), frozenset(escopos), 'producao')
        self.dados_cred = dict(conta='12345',client_id='id-ficticio',client_secret='secret-ficticio',certificado=str(cert),chave=str(cert),escopos=escopos)
        self.secret = cifrar_credencial(self.dados_cred, 1, b'x'*32, 'credencial:producao')
        with self.repo.transacao() as c:
            c.executemany('INSERT INTO inter_empresas VALUES (?,?,?)', [(1,'Fictícia','00000000000001'),(2,'Outra','00000000000002')])
            c.executemany('INSERT INTO inter_acessos VALUES (?,?)', [(1,'preparador'),(1,'aprovador'),(2,'outro')])
            c.execute('INSERT INTO inter_contas VALUES (1,?,?,?)', ('producao','12345',self.secret))
            c.execute('INSERT INTO inter_habilitacoes VALUES (1,1)')
        self.http = Mock()
        self.http.request.side_effect = [resposta({'access_token':'fake','expires_in':3600}),resposta({'codigoSolicitacao':'id-ficticio'})]
        self.cliente = ClienteInter(self.cred, permitir_producao_movimentacao=True, session=self.http)
        self.origem = Mock()
        self.linha = dict(payload=dict(seuNumero='CR1',valorNominal=50.0,dataVencimento=hoje().isoformat(),numDiasAgenda=30,
                                     pagador=dict(cpfCnpj='12345678000190',tipoPessoa='JURIDICA',nome='Fictícia',endereco='Rua A',bairro='B',cidade='C',uf='MG',cep='30000000'),formasRecebimento=['BOLETO','PIX']),
                          origem=dict(faturamento_id=1,titulo_id=1,documento='FAT-1',notas=['chave-teste'],cliente_id=1),rotulo='1/1')
        self.origem.carregar.return_value = [deepcopy(self.linha)]
        self.s = ProducaoInter(self.repo,self.cliente,b'x'*32,carregar=lambda n:dict(self.usuarios[n]),origem=self.origem)
        self.s.credencial_digest = sha256(self.secret.encode()).hexdigest()
        p = patch('dsystem_erp.services.inter_runtime.config_val', return_value='')
        p.start(); self.addCleanup(p.stop)
        # Qualquer uso acidental de HTTP/DB reais falha, mesmo que uma asserção seja perdida.
        for target in ('requests.Session.request', 'mysql.connector.connect'):
            p = patch(target, side_effect=AssertionError('Acesso real proibido no teste'))
            p.start(); self.addCleanup(p.stop)

    def pagamento(self, referencia='cp-1'):
        return self.s.preparar_pagamento(1,self.a,'pix_enviar',dict(valor=50.0,dataPagamento=hoje().isoformat(),destinatario=dict(tipo='CHAVE',chave='ficticia@example.invalid')),referencia,'Fornecedor fictício','12345678000190')

    def aprovar(self, uid):
        d = self.s.detalhes(1,self.a,uid)
        self.s.aprovar(1,self.b,uid,d['digest'],'CONFIRMAR '+uid)
        return d

    def enviar(self, uid):
        d = self.s.detalhes(1,self.a,uid)
        return self.s.executar(1,self.a,uid,confirmacao='ENVIAR '+uid,digest=d['digest'])

    def test_rede_apenas_apos_dupla_aprovacao_e_confirmacao(self):
        uid = self.pagamento()
        d = self.s.detalhes(1,self.a,uid)
        with self.assertRaises(PermissionError):
            self.s.aprovar(1,self.a,uid,d['digest'],'CONFIRMAR '+uid)
        self.aprovar(uid)
        for args in ({},{'confirmacao':'ENVIAR '+uid,'digest':'alterado'}):
            with self.assertRaises(ValueError):
                self.s.executar(1,self.a,uid,**args)
        self.http.request.assert_not_called()
        self.assertEqual(self.enviar(uid),'ENVIADA')
        self.assertEqual(self.http.request.call_count,2)
        self.assertEqual(self.http.request.call_args.kwargs['headers']['x-id-idempotente'],uid)
        with self.assertRaises(ValueError): self.enviar(uid)
        self.assertEqual(self.http.request.call_count,2)

    def test_duplicado_mesma_referencia_e_outra_referencia(self):
        uid = self.pagamento()
        self.assertEqual(self.pagamento(),uid)
        with self.assertRaisesRegex(ValueError,'idêntico'): self.pagamento('cp-outro')
        self.http.request.assert_not_called()

    def test_duas_sessoes_nao_duplicam(self):
        def preparar(ref):
            try: return self.pagamento(ref)
            except ValueError: return None
        with ThreadPoolExecutor(2) as pool:
            resultados = list(pool.map(preparar,['cp-1','cp-2']))
        self.assertEqual(sum(r is not None for r in resultados),1)
        self.assertEqual(len(self.s.listar(1,self.a)),1)

    def test_boleto_puxa_parcela_e_reutiliza_operacao(self):
        uid = self.s.preparar_parcela(1,self.a,1,1)
        self.assertEqual(self.s.preparar_parcela(1,self.a,1,1),uid)
        d = self.s.detalhes(1,self.a,uid)
        self.assertEqual(d['payload'],self.linha['payload'])
        self.assertEqual(d['contexto']['origem']['titulo_id'],1)
        self.s.aprovar(1,self.a,uid,d['digest'],'CONFIRMAR '+uid)
        self.assertEqual(self.enviar(uid),'ENVIADA')
        self.assertTrue(self.http.request.call_args.args[1].endswith('/cobranca/v3/cobrancas'))

    def test_parcela_alterada_ou_encerrada_bloqueia_envio(self):
        uid = self.s.preparar_parcela(1,self.a,1,1)
        self.aprovar(uid)
        self.origem.carregar.return_value = []
        with self.assertRaisesRegex(ValueError,'mudou'): self.enviar(uid)
        self.http.request.assert_not_called()
        self.assertEqual(self.s.detalhes(1,self.a,uid)['estado'],'APROVADA')

    def test_empresa_e_revogacao_dos_tres_papeis(self):
        uid = self.pagamento()
        self.aprovar(uid)
        with self.assertRaises(PermissionError): self.s.detalhes(2,self.usuarios['outro'],uid)
        for login, permissao in [('preparador','inter.executar'),('preparador','inter.preparar'),('aprovador','inter.aprovar')]:
            original = self.usuarios[login]['submodulos']
            self.usuarios[login]['submodulos'] = [p for p in original if p != permissao]
            with self.assertRaises(PermissionError): self.enviar(uid)
            self.usuarios[login]['submodulos'] = original
        self.http.request.assert_not_called()

    def test_bloqueio_da_empresa_apos_aprovacao(self):
        uid = self.pagamento(); self.aprovar(uid)
        with self.repo.transacao() as c: c.execute('UPDATE inter_habilitacoes SET ativo=0')
        with self.assertRaises(PermissionError): self.enviar(uid)
        self.http.request.assert_not_called()

    def test_troca_credencial_bloqueia_aprovacao_e_envio(self):
        uid = self.pagamento(); self.aprovar(uid)
        with self.repo.transacao() as c: c.execute("UPDATE inter_contas SET credencial_secret='outra-conta'")
        with self.assertRaises(PermissionError): self.enviar(uid)
        self.http.request.assert_not_called()

    def test_envio_incerto_nao_reenvia(self):
        uid = self.pagamento(); self.aprovar(uid)
        self.http.request.side_effect = [resposta({'access_token':'fake','expires_in':3600}),requests.Timeout('segredo')]
        self.assertEqual(self.enviar(uid),'INCERTA')
        with self.assertRaises(ValueError): self.enviar(uid)
        self.assertEqual(self.http.request.call_count,2)

    def test_falha_gravacao_apos_envio_nao_repete(self):
        uid = self.pagamento(); self.aprovar(uid)
        original = self.repo.executar
        def executar(c,sql,params=()):
            if 'SET estado=%s, externo=%s' in sql: raise RuntimeError('Disco indisponível')
            return original(c,sql,params)
        with patch.object(self.repo,'executar',side_effect=executar):
            with self.assertRaises(RuntimeError): self.enviar(uid)
        self.assertEqual(self.s.detalhes(1,self.a,uid)['estado'],'ENVIO_INICIADO')
        with self.assertRaises(ValueError): self.enviar(uid)

    def test_sem_politica_e_contexto_nao_envia(self):
        with self.assertRaises(ValueError): FinanceiroInter(self.repo,self.cliente,b'x'*32,ambiente='producao')
        with self.assertRaises(ValueError): FinanceiroInter(self.repo,self.cliente,b'x'*32,ambiente='sandbox')
        with self.assertRaises(PermissionError):
            self.s.criar(1,self.a,'boleto_emitir',self.linha['payload'],'livre')
        self.http.request.assert_not_called()

    def test_instalacao_anterior_sem_tabela_fica_bloqueada(self):
        with self.repo.transacao() as c: c.execute('DROP TABLE inter_habilitacoes')
        self.assertFalse(movimentacao_producao_liberada(self.repo,1))
        with self.assertRaises(PermissionError): self.pagamento()
        self.http.request.assert_not_called()

    def test_allowlist_tambem_no_http(self):
        for op in OPERACOES.keys() - MOVIMENTACOES_PRODUCAO - CONSULTAS_PRODUCAO:
            with self.assertRaises(PermissionError): self.cliente.chamar(op,empresa_id=1)
        for method,path in [('POST','/banking/v2/pagamento/lote'),('DELETE','/banking/v2/pagamento/x'),('GET','/pix/v2/pix')]:
            with self.assertRaises(PermissionError): self.cliente._http(method,path)
        self.http.request.assert_not_called()

    def test_pdf_e_status_somente_ids_da_empresa(self):
        with self.assertRaises(PermissionError):
            self.s.consultar(1,self.a,'boleto_pdf',identificador='de-outra-empresa')
        self.http.request.assert_not_called()

    def test_habilitacao_admin_reutiliza_chaves_sem_rede(self):
        with patch('dsystem_erp.services.inter_painel.carregar_usuario',side_effect=lambda n,c=None:dict(self.usuarios[n])), patch('dsystem_erp.services.inter_runtime.chave_mestra',return_value=b'x'*32):
            with self.assertRaises(PermissionError): configurar_movimentacoes(self.repo,1,self.b,True,['extrato.read'],'CONFIGURAR 1')
            self.assertTrue(configurar_movimentacoes(self.repo,1,self.a,True,['extrato.read','pagamento-pix.read','pagamento-pix.write'],'CONFIGURAR 1'))
            self.assertTrue(movimentacao_producao_liberada(self.repo,1))
            configurar_movimentacoes(self.repo,1,self.a,False,[],'CONFIGURAR 1')
            self.assertFalse(movimentacao_producao_liberada(self.repo,1))
        self.http.request.assert_not_called()

    def test_tela_producao_prepara_sem_token_ou_envio(self):
        from streamlit.testing.v1 import AppTest
        codigo = '''
import streamlit as st
from dsystem_erp.pages.banco_inter import renderizar_banco_inter
st.session_state.update(USUARIO)
st.session_state['inter_ambiente'] = 'Produção — boletos e pagamentos'
renderizar_banco_inter()
'''.replace('USUARIO',repr(self.a))
        with patch('dsystem_erp.services.inter_runtime.repositorio_configuracao',return_value=self.repo), patch('dsystem_erp.services.inter_runtime.abrir_producao_movimentacao',return_value=self.s):
            app = AppTest.from_string(codigo,default_timeout=20).run()
            self.assertEqual(len(app.exception),0)
            self.http.request.assert_not_called()
            valores = {'Referência do pagamento':'cp-tela','Nome / razão social do favorecido':'Fictício',
                       'CPF/CNPJ do favorecido':'12345678000190','Valor a pagar (R$)':'50,00','Chave Pix':'ficticia@example.invalid'}
            for campo in app.text_input:
                if campo.label in valores: campo.set_value(valores[campo.label])
            next(b for b in app.button if b.label=='Preparar pagamento — não enviar').click().run()
            self.assertEqual(len(app.exception),0)
            self.http.request.assert_not_called()
            self.assertEqual(self.s.listar(1,self.a)[0]['estado'],'PENDENTE_APROVACAO')
            self.assertTrue(any('Digite CONFIRMAR' in t.label for t in app.text_input))
            self.assertFalse(any('Executar operação' in b.label for b in app.button))

    def test_configuracao_impede_rotacao_com_operacao_pendente_mas_permite_bloquear(self):
        self.pagamento()
        with patch('dsystem_erp.services.inter_painel.carregar_usuario',side_effect=lambda n,c=None:dict(self.usuarios[n])), patch('dsystem_erp.services.inter_runtime.chave_mestra',return_value=b'x'*32):
            with self.assertRaisesRegex(ValueError,'pendentes'):
                configurar_movimentacoes(self.repo,1,self.a,True,['extrato.read'],'CONFIGURAR 1')
            configurar_movimentacoes(self.repo,1,self.a,False,[],'CONFIGURAR 1')
        self.assertFalse(movimentacao_producao_liberada(self.repo,1))

    def test_pagamento_boleto_envia_cpf_beneficiario_e_data_sem_baixar_erp(self):
        payload = dict(valorPagar='50.00',dataPagamento=hoje().isoformat(),dataVencimento=hoje().isoformat(),
                       codBarraLinhaDigitavel='1'*47,cpfCnpjBeneficiario='12345678000190')
        uid = self.s.preparar_pagamento(1,self.a,'conta_pagar',payload,'cp-boleto','Fornecedor fictício','12345678000190')
        self.aprovar(uid)
        self.assertEqual(self.enviar(uid),'ENVIADA')
        self.assertEqual(self.http.request.call_args.kwargs['json'],payload)
        self.assertTrue(self.http.request.call_args.args[1].endswith('/banking/v2/pagamento'))
        self.assertFalse(self.repo.financeiro_teste)

    def test_pdf_retornado_e_consulta_de_status_nao_executam_outro_pagamento(self):
        import base64
        from dsystem_erp.services.inter_api import pdf_da_resposta
        uid = self.s.preparar_parcela(1,self.a,1,1); self.aprovar(uid); self.enviar(uid)
        self.http.request.side_effect = [resposta({'access_token':'fake','expires_in':3600}),
            resposta({'cobranca':{'codigoSolicitacao':'id-ficticio','situacao':'A_RECEBER'},'pix':{'pixCopiaECola':'codigo-ficticio'}}),
            resposta({'pdf':base64.b64encode(b'%PDF-1.4 ficticio').decode()})]
        status = self.s.atualizar(1,self.a,uid)
        self.assertEqual(status['cobranca']['situacao'],'A_RECEBER')
        pdf = self.s.consultar(1,self.a,'boleto_pdf',identificador='id-ficticio')
        self.assertTrue(pdf_da_resposta(pdf).startswith(b'%PDF-'))
        chamadas_escrita = [c for c in self.http.request.call_args_list if c.args[0] != 'GET' and not c.args[1].endswith('/oauth/v2/token')]
        self.assertEqual(len(chamadas_escrita),1)


class CursorSQLite:
    def __init__(self, c): self.c = c
    def execute(self, sql, args=()): return self.c.execute(sql.replace('%s','?'), args)
    def fetchone(self): return self.c.fetchone()
    def fetchall(self): return self.c.fetchall()
    def close(self): self.c.close()


class ConexaoSQLite:
    def __init__(self, path):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
    def cursor(self, **kwargs): return CursorSQLite(self.conn.cursor())
    def close(self): self.conn.close()


class OrigemTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.path = str(Path(tmp.name)/'erp.sqlite')
        self.db = sqlite3.connect(self.path); self.addCleanup(self.db.close)
        self.empresa = '00000000000001'
        self.chave = '1'*44
        self.xml = f'''<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe"><NFe><infNFe Id="NFe{self.chave}">
        <ide><tpAmb>1</tpAmb><dhEmi>{hoje().isoformat()}T10:00:00-03:00</dhEmi><nNF>12</nNF><serie>1</serie></ide>
        <emit><CNPJ>{self.empresa}</CNPJ><CRT>1</CRT></emit><dest><CNPJ>12345678000190</CNPJ></dest>
        <total><ICMSTot><vNF>100.00</vNF></ICMSTot></total></infNFe></NFe>
        <protNFe><infProt><cStat>100</cStat><chNFe>{self.chave}</chNFe><tpAmb>1</tpAmb></infProt></protNFe></nfeProc>'''
        self.db.executescript('''
        CREATE TABLE faturamento(id INTEGER, status TEXT,forma_pag TEXT,cnpj TEXT,valor_total TEXT,parcelas TEXT,vencimento TEXT);
        CREATE TABLE notas_fiscais(id INTEGER,faturamento_id INTEGER,status TEXT,tipo_nota TEXT,chave_acesso TEXT,xml_autorizado TEXT);
        CREATE TABLE clientes(id INTEGER,cnpj TEXT,documento_chave TEXT,nome TEXT,endereco TEXT,numero TEXT,bairro TEXT,cidade_estado TEXT,uf TEXT,cep TEXT);
        CREATE TABLE contas_receber(id INTEGER,numero_documento TEXT,cpf_cnpj TEXT,valor_total TEXT,forma_recebimento TEXT,status TEXT,valor_baixado TEXT,conciliado TEXT,vencimento TEXT);
        INSERT INTO clientes VALUES(1,'12.345.678/0001-90','12345678000190','Fictícia','Rua A','10','Centro','Sabará / MG','MG','30000-000');
        ''')
        self.db.execute('INSERT INTO faturamento VALUES(1,?,?,?,?,?,?)',('Faturado','Boleto','12345678000190','100.00','2x',hoje().isoformat()))
        self.db.execute('INSERT INTO notas_fiscais VALUES(1,1,?,?,?,?)',('Autorizada','Produto',self.chave,self.xml))
        for i in (1,2):
            self.db.execute('INSERT INTO contas_receber VALUES(?,?,?,?,?,?,?,?,?)',(i,f'FAT-1-P{i:02d}-02','12345678000190','50.00','Boleto','Aberto','0','Não',hoje().isoformat()))
        self.db.commit()
        self.origem = OrigemFaturamento(lambda:ConexaoSQLite(self.path))

    def mudar(self, sql, args=()): self.db.execute(sql,args); self.db.commit()

    def test_dados_reais_do_cadastro_e_parcelas(self):
        linhas = self.origem.carregar(1,self.empresa)
        self.assertEqual(len(linhas),2)
        self.assertEqual(linhas[0]['payload']['pagador']['cidade'],'Sabará')
        self.assertEqual(linhas[1]['payload']['notaFiscal']['parcela'],2)
        self.assertEqual(linhas[0]['payload']['valorNominal'],50)

    def test_outra_empresa_homologacao_cancelamento_total_destinatario(self):
        with self.assertRaises(ValueError): self.origem.carregar(1,'00000000000002')
        for xml in (self.xml.replace('<tpAmb>1','<tpAmb>2'),self.xml.replace('12345678000190','99999999000199'),self.xml.replace('100.00','150.00')):
            self.mudar('UPDATE notas_fiscais SET xml_autorizado=?',(xml,))
            with self.assertRaises(ValueError): self.origem.carregar(1,self.empresa)
        self.mudar('UPDATE notas_fiscais SET xml_autorizado=?,status=?',(self.xml,'Cancelada'))
        with self.assertRaises(ValueError): self.origem.carregar(1,self.empresa)

    def test_pago_parcial_e_parcela_duplicada(self):
        self.mudar("UPDATE contas_receber SET status='Recebido' WHERE id=1")
        self.assertEqual(len(self.origem.carregar(1,self.empresa)),1)
        self.mudar("UPDATE contas_receber SET valor_baixado='1' WHERE id=2")
        self.assertEqual(self.origem.carregar(1,self.empresa),[])
        self.mudar('INSERT INTO contas_receber SELECT * FROM contas_receber WHERE id=1')
        with self.assertRaisesRegex(ValueError,'duplicada'): self.origem.carregar(1,self.empresa)

    def test_cadastro_ambiguo_nao_usa_nome_como_fallback(self):
        self.mudar('INSERT INTO clientes SELECT * FROM clientes')
        with self.assertRaisesRegex(ValueError,'único'): self.origem.carregar(1,self.empresa)

    def test_nfse_nacional_nao_e_enviada_como_chave_nfe(self):
        xml = f'''<NFSe xmlns="http://www.sped.fazenda.gov.br/nfse"><infNFSe Id="NFSchave-servico">
        <nNFSe>99</nNFSe><DPS><infDPS><tpAmb>1</tpAmb><dCompet>{hoje().isoformat()}</dCompet>
        <prest><CNPJ>{self.empresa}</CNPJ><regTrib><opSimpNac>3</opSimpNac></regTrib></prest>
        <toma><CNPJ>12345678000190</CNPJ></toma><valores><vServPrest><vServ>100.00</vServ></vServPrest></valores>
        </infDPS></DPS></infNFSe></NFSe>'''
        self.mudar('UPDATE notas_fiscais SET tipo_nota=?,chave_acesso=?,xml_autorizado=?',('Serviço','chave-servico',xml))
        linhas = self.origem.carregar(1,self.empresa)
        self.assertNotIn('notaFiscal',linhas[0]['payload'])
        self.assertEqual(linhas[0]['origem']['notas'],['chave-servico'])


if __name__ == '__main__':
    unittest.main()

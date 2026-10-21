import base64
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from uuid import uuid4

import requests

from dsystem_erp.services.inter_api import (
    ClienteInter, CredencialInter, InterErro, SANDBOX, cifrar_credencial,
    decifrar_credencial, pdf_da_resposta, PRODUCAO, OPERACOES, CONSULTAS_PRODUCAO,
)


def resposta(dados, status=200):
    return Mock(status_code=status, content=b'json', json=Mock(return_value=dados))


class InterAPITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        cert = Path(self.tmp.name)/'cert.pem'
        cert.touch()
        self.cred = CredencialInter(1, '12345', 'client-secreto', 'segredo', str(cert), str(cert),
            frozenset({'extrato.read', 'pagamento-pix.write'}))
        self.session = Mock()
        self.cliente = ClienteInter(self.cred, permitir_sandbox=True, session=self.session)

    def test_producao_e_rede_sem_optin_bloqueadas(self):
        for c, optin in [(self.cred, False), (replace(self.cred, ambiente='producao'), True)]:
            with self.assertRaises(InterErro):
                ClienteInter(c, permitir_sandbox=optin, session=self.session)
        self.session.request.assert_not_called()

    def test_empresa_e_escopo_antes_da_rede(self):
        for empresa, op in [(2, 'saldo'), (1, 'boleto_emitir')]:
            with self.assertRaises(PermissionError):
                self.cliente.chamar(op, empresa_id=empresa)
        self.session.request.assert_not_called()

    def test_producao_consulta_exige_optin_e_usa_host_real(self):
        cliente = ClienteInter(replace(self.cred, ambiente='producao', conta=''),
                              permitir_producao_consulta=True, session=self.session)
        self.session.request.side_effect = [resposta({'access_token':'token','expires_in':3600}), resposta({'disponivel':12})]
        self.assertEqual(cliente.chamar('saldo', empresa_id=1)['disponivel'], 12)
        self.assertEqual(self.session.request.call_args.args, ('GET', PRODUCAO+'/banking/v2/saldo'))
        self.assertNotIn('x-conta-corrente', self.session.request.call_args.kwargs['headers'])
        self.assertEqual(self.session.request.call_args_list[0].kwargs['data']['scope'], 'extrato.read')

    def test_producao_bloqueia_todas_operacoes_fora_allowlist_antes_token(self):
        cliente = ClienteInter(replace(self.cred, ambiente='producao', escopos=frozenset(o[2] for o in OPERACOES.values())),
                              permitir_producao_consulta=True, session=self.session)
        for operacao in OPERACOES.keys() - CONSULTAS_PRODUCAO:
            with self.subTest(operacao=operacao), self.assertRaises(PermissionError):
                cliente.chamar(operacao, empresa_id=1, identificador='teste', payload={}, idempotencia=str(uuid4()))
        for metodo, caminho, kwargs in [('POST','/banking/v2/pix',{}), ('DELETE','/banking/v2/pagamento/teste',{}),
                ('POST','/oauth/v2/token',{'data':{'scope':'pagamento-pix.write'}}), ('GET','/pix/v2/pix',{})]:
            with self.assertRaises(PermissionError):
                cliente._http(metodo, caminho, **kwargs)
        self.session.request.assert_not_called()

    def test_conta_opcional_mas_numero_invalido_nao_passa(self):
        for conta in ('0123', '12-3', ' ', None):
            with self.assertRaises(ValueError):
                ClienteInter(replace(self.cred, conta=conta), permitir_sandbox=True, session=self.session)
        self.session.request.assert_not_called()

    def test_token_mtls_cache_tls_e_sem_redirect(self):
        self.session.request.side_effect = [resposta({'access_token':'token', 'expires_in':3600}), resposta({'disponivel':12}), resposta({'disponivel':12})]
        self.assertEqual(self.cliente.chamar('saldo', empresa_id=1)['disponivel'], 12)
        self.cliente.chamar('saldo', empresa_id=1)
        self.assertEqual(self.session.request.call_count, 3)
        for chamada in self.session.request.call_args_list:
            self.assertTrue(chamada.args[1].startswith(SANDBOX+'/'))
            self.assertEqual(chamada.kwargs['cert'], (self.cred.certificado,self.cred.chave))
            self.assertTrue(chamada.kwargs['verify'])
            self.assertFalse(chamada.kwargs['allow_redirects'])
            self.assertEqual(chamada.kwargs['timeout'], (5,30))
        self.assertFalse(self.session.trust_env)
        self.assertEqual(self.session.request.call_args.kwargs['headers']['x-conta-corrente'],'12345')

    def test_timeout_sem_retry_e_idempotencia_pix(self):
        self.session.request.side_effect = [resposta({'access_token':'token','expires_in':3600}), requests.Timeout('segredo')]
        uid = str(uuid4())
        with self.assertRaises(InterErro) as e:
            self.cliente.chamar('pix_enviar', empresa_id=1, payload={'valor':10}, idempotencia=uid)
        self.assertTrue(e.exception.incerto)
        self.assertNotIn('segredo', str(e.exception))
        self.assertEqual(self.session.request.call_count, 2)
        self.assertEqual(self.session.request.call_args.kwargs['headers']['x-id-idempotente'],uid)

    def test_resposta_erro_nao_expoe_segredos(self):
        self.session.request.return_value = resposta({'client_secret':'sensivel'}, 500)
        with self.assertRaisesRegex(InterErro, '^INTER_HTTP_500$'):
            self.cliente.chamar('saldo', empresa_id=1)

    def test_cipher_isolado_por_empresa_ambiente_e_integridade(self):
        chave = b'x'*32
        cifrado = cifrar_credencial({'secret':'protegido'},1,chave)
        self.assertNotIn('protegido',cifrado)
        self.assertEqual(decifrar_credencial(cifrado,1,chave),{'secret':'protegido'})
        for empresa, contexto, k in [(2,'credencial:sandbox',chave),(1,'outro',chave),(1,'credencial:sandbox',b'y'*32)]:
            with self.assertRaises(InterErro):
                decifrar_credencial(cifrado,empresa,k,contexto)

    def test_pdf_apenas_documento_do_banco(self):
        self.assertEqual(pdf_da_resposta({'pdf':base64.b64encode(b'%PDF-1.4 teste').decode()}),b'%PDF-1.4 teste')
        with self.assertRaises(InterErro):
            pdf_da_resposta({})

    def test_repr_nao_mostra_credenciais(self):
        self.assertNotIn('client-secreto',repr(self.cred))
        self.assertNotIn('segredo',repr(self.cred))

    def test_runtime_rejeita_nome_producao_sem_conectar(self):
        from unittest.mock import patch
        from dsystem_erp.services.inter_runtime import repositorio_teste
        with patch.dict('os.environ', {'DSYSTEM_INTER_TEST_DATABASE':'orcamento'}), patch('dsystem_erp.services.inter_runtime.conectar_mysql') as conectar:
            with self.assertRaises(PermissionError):
                repositorio_teste()
        conectar.assert_not_called()

    def test_runtime_usa_configuracao_central_e_nao_so_environ(self):
        from unittest.mock import patch
        from dsystem_erp.services.inter_runtime import repositorio_configuracao, chave_mestra
        configuracao = {
            'DSYSTEM_INTER_CONFIG_DATABASE': 'validacao_inter_config',
            'DSYSTEM_INTER_MASTER_KEY': base64.b64encode(b'x'*32).decode(),
        }
        with patch('dsystem_erp.services.inter_runtime.config_val', side_effect=lambda k, d=None: configuracao.get(k,d)), \
                patch('dsystem_erp.services.inter_runtime._repositorio_isolado') as criar:
            self.assertIs(repositorio_configuracao(), criar.return_value)
            criar.assert_called_once_with('validacao_inter_config', financeiro_teste=False)
            self.assertEqual(chave_mestra(), b'x'*32)

    @unittest.skipUnless(__import__('os').name == 'nt', 'Cofre DPAPI é exclusivo do Windows')
    def test_cofre_explicito_independe_do_localappdata_redirecionado(self):
        from unittest.mock import patch
        from dsystem_erp.services.inter_pendente import pasta_local
        with patch('dsystem_erp.config.config_val', return_value=self.tmp.name), \
                patch.dict('os.environ', {'LOCALAPPDATA': str(Path(self.tmp.name)/'outro-perfil-de-app')}):
            self.assertEqual(pasta_local(), Path(self.tmp.name).resolve())
        with patch('dsystem_erp.config.config_val', return_value='pasta-relativa'):
            with self.assertRaises(ValueError):
                pasta_local()
        with patch('dsystem_erp.config.config_val', return_value=str(Path(__file__).resolve().parents[1])):
            with self.assertRaises(ValueError):
                pasta_local()

    def test_expiracao_token_renova(self):
        self.cliente.clock = Mock(side_effect=[0,4000,4000])
        self.session.request.side_effect = [resposta({'access_token':'primeiro','expires_in':3600}), resposta({}),
                                           resposta({'access_token':'segundo','expires_in':3600}), resposta({})]
        self.cliente.chamar('saldo',empresa_id=1)
        self.cliente.chamar('saldo',empresa_id=1)
        self.assertEqual(self.session.request.call_args.kwargs['headers']['Authorization'],'Bearer segundo')

    def test_identificador_malicioso_nao_vai_para_rede(self):
        self.cliente.credencial = replace(self.cred,escopos=frozenset({'pagamento-pix.read'}))
        with self.assertRaises(ValueError):
            self.cliente.chamar('pix_consultar',empresa_id=1,identificador='../outro?x=1')
        self.session.request.assert_not_called()


class InterConfiguracaoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from datetime import datetime, timedelta, timezone
        chave = rsa.generate_private_key(public_exponent=65537,key_size=2048)
        nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Teste ficticio')])
        agora = datetime.now(timezone.utc)
        cert = (x509.CertificateBuilder().subject_name(nome).issuer_name(nome)
                .public_key(chave.public_key()).serial_number(x509.random_serial_number())
                .not_valid_before(agora-timedelta(days=1)).not_valid_after(agora+timedelta(days=1))
                .sign(chave,hashes.SHA256()))
        cls.certificado = cert.public_bytes(serialization.Encoding.PEM)
        cls.privada = chave.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())

    def setUp(self):
        from unittest.mock import patch
        from dsystem_erp.repositories.inter import criar_repositorio_demo
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)
        self.repo = criar_repositorio_demo(self.raiz/'demo.sqlite','configurador')
        self.usuario = {'username':'configurador','autenticado':True,'submodulos':['inter.configurar']}
        self.dados = {'conta':'12345','client_id':'id-sensivel','client_secret':'secret-sensivel','escopos':['extrato.read']}
        env = patch.dict('os.environ',{'DSYSTEM_INTER_MASTER_KEY':base64.b64encode(b'x'*32).decode(),
            'DSYSTEM_INTER_CERT_DIR':str(self.raiz),'DSYSTEM_INTER_ALLOW_SANDBOX':'0'})
        env.start()
        self.addCleanup(env.stop)

    def test_upload_valida_cifra_e_nao_chama_banco(self):
        from unittest.mock import patch
        from dsystem_erp.services.inter_runtime import salvar_credencial_upload, status_configuracao
        with patch('requests.Session.request',side_effect=AssertionError('rede proibida')):
            self.assertTrue(salvar_credencial_upload(self.repo,1,self.usuario,self.dados,self.certificado,self.privada))
        with self.repo.transacao() as c:
            row = c.execute('SELECT * FROM inter_contas').fetchone()
        self.assertNotIn('secret-sensivel',row['credencial_secret'])
        d = decifrar_credencial(row['credencial_secret'],1,b'x'*32)
        self.assertEqual(Path(d['chave']).read_bytes(),self.privada)
        self.assertEqual(Path(d['certificado']).read_bytes(),self.certificado)
        self.assertEqual(status_configuracao(self.repo,1,self.usuario),{'configurada':True,'conta_final':'2345'})

    def test_upload_invalido_sem_persistir(self):
        from dsystem_erp.services.inter_runtime import salvar_credencial_upload
        for cert, chave in [(b'invalido',self.privada),(self.certificado,b'invalido'),(b'x'*131073,self.privada)]:
            with self.assertRaises(ValueError):
                salvar_credencial_upload(self.repo,1,self.usuario,self.dados,cert,chave)
        self.assertEqual(list(self.raiz.glob('inter-*')),[])

    def test_producao_salva_separada_com_aad_propria_e_sem_conta(self):
        from dsystem_erp.services.inter_runtime import salvar_credencial_upload, status_configuracao
        from unittest.mock import patch
        with patch('requests.Session.request',side_effect=AssertionError('rede proibida')):
            salvar_credencial_upload(self.repo,1,self.usuario,{**self.dados,'conta':''},self.certificado,self.privada,ambiente='producao')
        with self.repo.transacao() as c:
            row = c.execute('SELECT * FROM inter_contas').fetchone()
        self.assertEqual(row['ambiente'],'producao')
        self.assertEqual(decifrar_credencial(row['credencial_secret'],1,b'x'*32,'credencial:producao')['conta'],'')
        with self.assertRaises(InterErro):
            decifrar_credencial(row['credencial_secret'],1,b'x'*32)
        self.assertFalse(status_configuracao(self.repo,1,self.usuario)['configurada'])
        self.assertTrue(status_configuracao(self.repo,1,self.usuario,ambiente='producao')['configurada'])

    def test_producao_nao_salva_escopo_pagamento(self):
        from dsystem_erp.services.inter_runtime import salvar_credencial_upload
        with self.assertRaises(ValueError):
            salvar_credencial_upload(self.repo,1,self.usuario,{**self.dados,'escopos':['pagamento-pix.write']},self.certificado,self.privada,ambiente='producao')
        self.assertEqual(list(self.raiz.glob('inter-*')),[])

    def test_zip_valido_e_rejeicao_de_arquivos_ambiguos_e_grandes(self):
        from io import BytesIO
        from zipfile import ZipFile
        from dsystem_erp.services.inter_runtime import ler_zip_certificado
        def pacote(itens):
            buf = BytesIO()
            with ZipFile(buf,'w') as z:
                for nome, conteudo in itens:
                    z.writestr(nome,conteudo)
            return buf.getvalue()
        itens = [('cert.crt',self.certificado),('privada.key',self.privada)]
        self.assertEqual(ler_zip_certificado(pacote(itens)),(self.certificado,self.privada))
        for bruto in (b'invalido', b'x'*524289, pacote(itens+[('extra.crt',self.certificado)]),
                      pacote([('cert.crt',b'x'*131073),itens[1]]), pacote(itens[:1])):
            with self.assertRaises(ValueError):
                ler_zip_certificado(bruto)

    def test_servico_producao_revalida_permissao_empresa_e_operacao(self):
        from unittest.mock import patch
        from dsystem_erp.services.inter_runtime import ConsultasInterProducao, salvar_credencial_upload
        salvar_credencial_upload(self.repo,1,self.usuario,self.dados,self.certificado,self.privada,ambiente='producao')
        servico = ConsultasInterProducao(self.repo)
        usuario = {**self.usuario,'submodulos':['inter.view']}
        with patch('dsystem_erp.services.inter_runtime.ClienteInter') as cliente:
            for empresa, user, op in [(2,usuario,'saldo'),(1,{**usuario,'tipo_login':'cliente'},'saldo'),
                                     (1,self.usuario,'saldo'),(1,usuario,'pix_enviar')]:
                with self.assertRaises(PermissionError):
                    servico.consultar(empresa,user,op)
            cliente.assert_not_called()
            cliente.return_value.chamar.return_value = {'disponivel':12}
            self.assertEqual(servico.consultar(1,usuario,'saldo'),{'disponivel':12})
            self.assertTrue(cliente.call_args.kwargs['permitir_producao_consulta'])
            servico.consultar(1,usuario,'extrato')
            self.assertEqual(cliente.call_count,1)  # Mantém o cache OAuth da sessão.
            with self.repo.transacao() as c:
                c.execute('DELETE FROM inter_acessos WHERE empresa_id=1')
            with self.assertRaises(PermissionError):
                servico.consultar(1,usuario,'saldo')
            self.assertEqual(cliente.return_value.chamar.call_count,2)

    def test_admin_delega_e_revoga_consulta_sem_liberar_pagamentos(self):
        from dsystem_erp.services.inter_acessos import salvar_acessos
        admin = {**self.usuario,'is_admin':1,'submodulos':['inter.view','inter.configurar']}
        conectar = Mock()
        conectar.return_value.cursor.return_value.fetchall.return_value = [
            {'username':'configurador','submodulos':['inter.view','inter.configurar']},
            {'username':'leitor','submodulos':['inter.view']},
            {'username':'sem_permissao','submodulos':[]}]
        self.assertTrue(salvar_acessos(self.repo,1,admin,conectar,['leitor']))
        self.assertEqual(len(self.repo.empresas('leitor')),1)
        self.assertEqual(len(self.repo.empresas('configurador')),1)
        salvar_acessos(self.repo,1,admin,conectar,[])
        self.assertEqual(self.repo.empresas('leitor'),[])
        for chamada in conectar.return_value.cursor.return_value.execute.call_args_list:
            self.assertTrue(chamada.args[0].startswith('SELECT '))

    def test_delegacao_rejeita_usuario_nao_admin_e_outro_tenant(self):
        from dsystem_erp.services.inter_acessos import salvar_acessos
        conectar = Mock()
        for empresa, user in [(1,self.usuario),(2,{**self.usuario,'is_admin':1}),
                              (1,{**self.usuario,'is_admin':1,'tipo_login':'cliente'})]:
            with self.assertRaises(PermissionError):
                salvar_acessos(self.repo,empresa,user,conectar,[])
        conectar.assert_not_called()

    def test_delegacao_exige_permissao_previa_do_cadastro(self):
        from dsystem_erp.services.inter_acessos import salvar_acessos
        conectar=Mock()
        conectar.return_value.cursor.return_value.fetchall.return_value = [
            {'username':'configurador','submodulos':['inter.view']},
            {'username':'sem_permissao','submodulos':[]}]
        with self.assertRaises(ValueError):
            salvar_acessos(self.repo,1,{**self.usuario,'is_admin':1},conectar,['sem_permissao'])
        self.assertEqual(self.repo.empresas('sem_permissao'),[])

    def test_pacote_local_cifrado_nao_expoe_nem_sobrescreve(self):
        import os
        if os.name != 'nt':
            self.skipTest('DPAPI pertence ao Windows')
        from io import BytesIO
        from zipfile import ZipFile
        from unittest.mock import patch
        from dsystem_erp.services.inter_pendente import preparar_pendente, ler_pendente, chave_mestra_local, pasta_local
        buf = BytesIO()
        with ZipFile(buf,'w') as z:
            z.writestr('cert.crt',self.certificado)
            z.writestr('privada.key',self.privada)
        with patch.dict('os.environ',{'LOCALAPPDATA':str(self.raiz), 'DSYSTEM_INTER_VAULT_DIR':str(self.raiz/'cofre-teste')}), patch('requests.Session.request',side_effect=AssertionError('rede proibida')):
            self.assertTrue(preparar_pendente('fake-id','fake-secret',buf.getvalue())['preparada'])
            self.assertEqual(ler_pendente()[0]['client_secret'],'fake-secret')
            mestra = chave_mestra_local()
            self.assertEqual(len(mestra),32)
            with patch.dict('os.environ', {'LOCALAPPDATA':str(self.raiz/'app-redirecionado')}):
                self.assertEqual(chave_mestra_local(), mestra)
                self.assertEqual(ler_pendente()[0]['client_secret'],'fake-secret')
            bruto = (pasta_local()/'credenciais_pendentes.dpapi').read_bytes()
            for sensivel in (b'fake-id',b'fake-secret',b'PRIVATE KEY'):
                self.assertNotIn(sensivel,bruto)
            with self.assertRaises(FileExistsError):
                preparar_pendente('outro-id','outro-secret',buf.getvalue())
            self.assertEqual(ler_pendente()[0]['client_secret'],'fake-secret')

    def test_outro_tenant_ou_sem_permissao_nao_salva(self):
        from dsystem_erp.services.inter_runtime import salvar_credencial_upload
        for empresa, usuario in [(2,self.usuario),(1,{**self.usuario,'submodulos':[]})]:
            with self.assertRaises(PermissionError):
                salvar_credencial_upload(self.repo,empresa,usuario,self.dados,self.certificado,self.privada)
        self.assertEqual(list(self.raiz.glob('inter-*')),[])

    def test_falha_protecao_nao_grava_chave(self):
        from unittest.mock import patch
        from dsystem_erp.services.inter_runtime import salvar_credencial_upload
        with patch('dsystem_erp.services.inter_runtime._proteger_pasta_certificados',side_effect=PermissionError('ACL recusada')):
            with self.assertRaises(PermissionError):
                salvar_credencial_upload(self.repo,1,self.usuario,self.dados,self.certificado,self.privada)
        self.assertEqual(list(self.raiz.glob('inter-*')),[])


if __name__ == '__main__':
    unittest.main()

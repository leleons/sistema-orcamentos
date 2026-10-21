import hashlib
import io
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock
from pypdf import PdfReader
from streamlit.testing.v1 import AppTest
from dsystem_erp.services.contratos_pj import (
    MODELO_PJ, eh_pj, tipos_contrato_funcionario, cnpj_pj_valido, cadastro_empresa_pj, salvar_empresa_pj,
)


BASE_TELA = '''
import streamlit as st
from unittest.mock import MagicMock
from dsystem_erp.pages.contratos_gerar import renderizar_gerador
st.session_state.setdefault('is_admin',True)
st.session_state.setdefault('banco_teste',MagicMock())
conn = st.session_state['banco_teste']
conn.cursor.return_value.lastrowid = 77
pessoas = {
    1:dict(id=1,username='pessoa.a',funcionario_nome='Pessoa A',funcionario_cpf='11122233344',funcionario_tipo_contrato='PJ',funcionario_pj_razao_social='Empresa PJ A',funcionario_pj_cnpj='11.222.333/0001-44',funcionario_pj_endereco='Rua da Empresa A, 10, Contagem / MG'),
    2:dict(id=2,username='pessoa.b',funcionario_nome='Pessoa B',funcionario_cpf='55566677788',funcionario_tipo_contrato='Contrato terceirizado',funcionario_pj_razao_social='Empresa PJ B',funcionario_pj_cnpj='22.333.444/0001-55',funcionario_pj_endereco='Rua da Empresa B, 20, Belo Horizonte / MG')}
id_pessoa = st.selectbox('Pessoa de teste',[1,2],key='pessoa_teste')
pessoa = dict(pessoas[id_pessoa])
if st.session_state.get('sem_empresa'):
    pessoa['funcionario_pj_razao_social'] = ''
    pessoa['funcionario_pj_cnpj'] = ''
    pessoa['funcionario_pj_endereco'] = ''
config = dict(DSYSTEM_NOME='Dsystem Teste',NFSE_CNPJ='33.444.555/0001-66',DSYSTEM_ENDERECO='Rua da Dsystem, 30',DSYSTEM_CIDADE_UF='Sabará / MG')
ctx = dict(st=st,tem_permissao=lambda p:st.session_state.get('permitido',True),conectar_banco=lambda:conn,agora_br=lambda:'08/10/2026',config_sistema_val=lambda k,p='':config.get(k,p))
renderizar_gerador(ctx,prestador_pj=pessoa)
'''

TELA_USUARIOS = '''
import streamlit as st
import json, re, mysql.connector
from datetime import datetime
from unittest.mock import MagicMock
from dsystem_erp.pages.usuarios import renderizar_gerenciador_usuarios
st.session_state.setdefault('is_admin',True)
st.session_state.setdefault('banco_teste',MagicMock())
conn = st.session_state['banco_teste']
usuario = dict(id=4,username='pessoa.teste',password='hash ficticio',is_admin=0,modulo_gerencial=0,funcionario_nome='Pessoa Teste',funcionario_cpf='12345678900',funcionario_tipo_contrato='Contrato terceirizado',funcionario_pj_razao_social='Prestadora Exemplo',funcionario_pj_cnpj='11.222.333/0001-44',funcionario_pj_endereco='Rua da Prestadora, 100',funcionario_telefone='31',funcionario_email='pessoa@example.com')
c = conn.cursor.return_value
c.lastrowid = 88
c.fetchall.return_value = [usuario]
def executar(sql,*args):
    c.fetchone.return_value = usuario if 'WHERE id=?' in sql and args[0][0] == 4 else None
c.execute.side_effect = executar
cfg = dict(DSYSTEM_NOME='Dsystem Teste',NFSE_CNPJ='33.444.555/0001-66',DSYSTEM_ENDERECO='Rua da Dsystem, 30',DSYSTEM_CIDADE_UF='Sabará / MG')
ctx = dict(st=st,tem_permissao=lambda p:True,conectar_banco=lambda:conn,buscar_clientes=lambda **kwargs:[],
    agora_br=lambda:'08/10/2026',config_sistema_val=lambda k,p='':cfg.get(k,p),
    editor_permissoes=lambda *args:set(),flags_legadas=lambda *args:{},
    tabela_clicavel_id=lambda *args:None,carregar_submodulos=lambda *args:[],
    criar_hash_senha=lambda *args:'hash ficticio',json=json,re=re,datetime=datetime,mysql=mysql)
renderizar_gerenciador_usuarios(ctx)
'''


class FuncionarioPjTests(unittest.TestCase):
    def test_atualiza_defaults_sem_apagar_ajuste_do_contrato(self):
        from dsystem_erp.services.contratos_pj import sincronizar_campo_cadastro
        estado = {'nome': ''}
        sincronizar_campo_cadastro(estado, 'nome', 'Cadastro A')
        self.assertEqual(estado['nome'], 'Cadastro A')
        sincronizar_campo_cadastro(estado, 'nome', 'Cadastro atualizado')
        self.assertEqual(estado['nome'], 'Cadastro atualizado')
        estado['nome'] = 'Ajuste no contrato'
        sincronizar_campo_cadastro(estado, 'nome', 'Outro cadastro')
        self.assertEqual(estado['nome'], 'Ajuste no contrato')

    def test_dsystem_representante_e_funcionario_preenchidos(self):
        tela = BASE_TELA.replace("ctx = dict(st=st", "config['DSYSTEM_REPRESENTANTE_LEGAL'] = 'Representante Dsystem'\nctx = dict(st=st")
        app = AppTest.from_string(tela).run()
        self.assertFalse(app.exception)
        valores = [campo.value for campo in app.text_input]
        for valor in ['Representante Dsystem', 'Pessoa A', '11122233344', 'Empresa PJ A', '33.444.555/0001-66']:
            self.assertIn(valor, valores)

    def test_tipos_novos_apenas_pj_estagio_preservam_legados(self):
        self.assertEqual(tipos_contrato_funcionario(),['PJ','Estágio'])
        self.assertEqual(tipos_contrato_funcionario('Contrato terceirizado'),['PJ','Estágio','Contrato terceirizado'])
        self.assertIn('CLT',tipos_contrato_funcionario('CLT'))
        self.assertTrue(eh_pj('Contrato terceirizado'))
        self.assertTrue(eh_pj(' pj '))
        self.assertFalse(eh_pj('Estágio'))
        self.assertFalse(eh_pj('RPA'))

    def test_empresa_nao_inventa_razao_cnpj_ou_endereco_pelo_cpf(self):
        usuario = dict(id=1,funcionario_nome='Pessoa',funcionario_cpf='12345678900',funcionario_endereco='Casa da pessoa',funcionario_rj='12345678900')
        dados = cadastro_empresa_pj(usuario)
        self.assertEqual((dados['nome'],dados['cnpj'],dados['endereco']),('','',''))
        usuario['funcionario_rj'] = '11.222.333/0001-44'
        self.assertEqual(cadastro_empresa_pj(usuario)['cnpj'],'11.222.333/0001-44')

    def test_formato_cnpj_nao_aceita_cpf(self):
        self.assertTrue(cnpj_pj_valido('11.222.333/0001-44'))
        self.assertTrue(cnpj_pj_valido('AB.CDE.123/0001-45'))
        self.assertFalse(cnpj_pj_valido('123.456.789-00'))
        self.assertFalse(cnpj_pj_valido(''))

    def test_salva_empresa_pj_no_usuario_correto_sem_converter_tipo(self):
        c = MagicMock()
        salvar_empresa_pj(c,9,dict(funcionario_pj_razao_social=' Empresa Teste ',funcionario_pj_cnpj='11.222.333/0001-44',funcionario_pj_endereco=' Rua A '))
        sql,args = c.execute.call_args.args
        self.assertEqual(args,('Empresa Teste','11.222.333/0001-44','Rua A',9))
        self.assertNotIn('funcionario_tipo_contrato',sql)

    def test_modelo_corresponde_exatamente_ao_anexo(self):
        from dsystem_erp.services.contratos_modelos import abrir_modelo
        self.assertEqual(hashlib.sha256(abrir_modelo(MODELO_PJ)).hexdigest(),'599ae9a3783f42a10429253d7f6fd8db3730d731bd551ebea33ba473f4ed17f6')

    def nova_tela(self):
        app = AppTest.from_string(BASE_TELA,default_timeout=15).run()
        self.assertFalse(app.exception)
        return app

    def preencher(self,app):
        for campo in app.text_input:
            if not campo.value:
                campo.set_value('Dado confirmado para teste')
        app.run()

    def test_tela_autopreenche_partes_certas_e_gera_pdf_na_central(self):
        app = self.nova_tela()
        prefixo = f'central_contrato_{MODELO_PJ}_1_pj_empresa_1'
        valores = [i.value for i in app.text_input]
        self.assertIn('33.444.555/0001-66',valores)
        self.assertIn('Empresa PJ A',valores)
        self.assertIn('11.222.333/0001-44',valores)
        self.assertIn('11122233344',valores)  # CPF apenas do representante legal
        app.date_input(key=f'central_contrato_{MODELO_PJ}_1_pj_inicio').set_value(date(2026,10,8))
        self.preencher(app)
        botao = app.button(key=prefixo+'_gerar')
        self.assertFalse(botao.disabled)
        botao.click().run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        resultado = app.session_state['central_contrato_resultado']
        self.assertEqual(resultado['mime'],'application/pdf')
        texto = '\n'.join(p.extract_text() for p in PdfReader(io.BytesIO(resultado['arquivo'])).pages)
        self.assertIn('CONTRATANTE: DSystem',texto)
        self.assertIn('CONTRATADA: Empresa PJ A',texto)
        self.assertIn('11.222.333/0001-44',texto)
        self.assertIn('11122233344',texto)
        self.assertIn('1 ano, de 08/10/2026 a 08/10/2027',' '.join(texto.split()))
        args = app.session_state['banco_teste'].cursor.return_value.execute.call_args.args[1]
        self.assertEqual(args[:4],(MODELO_PJ,'Funcionário',1,'Pessoa A'))
        self.assertEqual(args[9:11],('08/10/2026','08/10/2027'))
        app.run()
        self.assertTrue(app.button(key=prefixo+'_gerar').disabled)

    def test_troca_pessoa_pj_ou_terceirizado_sem_misturar_empresa(self):
        app = self.nova_tela()
        self.preencher(app)
        app.selectbox(key='pessoa_teste').select(2).run()
        self.assertFalse(app.exception)
        valores = [i.value for i in app.text_input]
        self.assertIn('Empresa PJ B',valores)
        self.assertNotIn('Empresa PJ A',valores)
        app.session_state['banco_teste'].commit.assert_not_called()

    def test_sem_cnpj_bloqueia_e_nao_substitui_pelo_cpf(self):
        app = self.nova_tela()
        app.session_state['sem_empresa'] = True
        # Outra pessoa usa novas chaves, sem aproveitar dados preenchidos antes.
        app.selectbox(key='pessoa_teste').select(2).run()
        self.preencher(app)
        cnpj = next(i for i in app.text_input if i.label == 'CNPJ da empresa prestadora')
        cnpj.set_value('55566677788').run()
        self.assertTrue(next(b for b in app.button if b.label == 'Gerar e salvar na aba Contratos').disabled)
        app.session_state['banco_teste'].commit.assert_not_called()

    def test_exige_permissao_contrato_e_acesso_gerencial(self):
        for chave in ('permitido','is_admin'):
            app = self.nova_tela()
            app.session_state[chave] = False
            app.run()
            self.assertFalse(app.exception)
            self.assertFalse(app.button)
            app.session_state['banco_teste'].commit.assert_not_called()

    def test_campos_empresa_pj_na_edicao_e_sem_perder_dados_no_estagio(self):
        fonte = '''
import streamlit as st
from dsystem_erp.pages.funcionario_pj import campos_empresa_pj
usuario = dict(id=9,funcionario_pj_razao_social='Empresa salva',funcionario_pj_cnpj='11.222.333/0001-44',funcionario_pj_endereco='Rua da empresa')
tipo = st.selectbox('Tipo',['PJ','Estágio'])
st.session_state['dados_empresa'] = campos_empresa_pj(st,tipo,'edit_9',usuario)
'''
        app = AppTest.from_string(fonte,default_timeout=15).run()
        self.assertEqual(app.text_input(key='edit_9_pj_razao').value,'Empresa salva')
        app.text_input(key='edit_9_pj_razao').set_value('Empresa editada').run()
        self.assertEqual(app.session_state['dados_empresa']['funcionario_pj_razao_social'],'Empresa editada')
        app.selectbox[0].select('Estágio').run()
        self.assertFalse(app.text_input)
        self.assertEqual(app.session_state['dados_empresa']['funcionario_pj_razao_social'],'Empresa salva')

    def test_pela_tela_usuarios_abre_pj_no_lugar_do_aviso_antigo(self):
        app = AppTest.from_string(TELA_USUARIOS,default_timeout=15).run()
        self.assertFalse(app.exception)
        tipo_novo = next(s for s in app.selectbox if s.label == 'Tipo de Contrato:')
        self.assertEqual(tipo_novo.options,['PJ','Estágio'])
        app.selectbox(key='contrato_funcionario').select('4 - Pessoa Teste').run()
        self.assertFalse(app.exception)
        self.assertIn('Prestadora Exemplo',[i.value for i in app.text_input])
        self.assertFalse(any('modelos somente' in w.value for w in app.warning))
        app.session_state['banco_teste'].commit.assert_not_called()

    def test_edicao_usuario_salva_dados_empresa_sem_mexer_no_vinculo(self):
        app = AppTest.from_string(TELA_USUARIOS,default_timeout=15).run()
        app.session_state['usuario_edicao_selecionado'] = 4
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(app.text_input(key='edit_usuario_4_pj_razao').value,'Prestadora Exemplo')
        app.text_input(key='edit_usuario_4_pj_razao').set_value('Prestadora Editada')
        app.button(key='btn_save_u_4').click().run()
        self.assertFalse(app.exception)
        chamadas = app.session_state['banco_teste'].cursor.return_value.execute.call_args_list
        salvos = [c.args[1] for c in chamadas if c.args[0].startswith('UPDATE usuarios SET funcionario_pj_razao_social')]
        self.assertEqual(salvos[-1],('Prestadora Editada','11.222.333/0001-44','Rua da Prestadora, 100',4))
        app.session_state['banco_teste'].commit.assert_called_once()

    def test_novo_usuario_salva_empresa_com_id_da_insercao(self):
        app = AppTest.from_string(TELA_USUARIOS,default_timeout=15).run()
        next(i for i in app.text_input if i.label == 'Nome:').set_value('Pessoa Nova')
        next(i for i in app.text_input if i.label == 'CPF:').set_value('98765432100')
        next(i for i in app.text_input if i.label == 'Login:').set_value('pessoa.nova')
        next(i for i in app.text_input if i.label == 'Senha:').set_value('Senha ficticia')
        app.text_input(key='novo_usuario_pj_razao').set_value('Prestadora Nova')
        app.text_input(key='novo_usuario_pj_cnpj').set_value('22.333.444/0001-55')
        app.text_area(key='novo_usuario_pj_endereco').set_value('Rua Nova, 20')
        next(b for b in app.button if b.label == 'Criar Usuário no Sistema').click().run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        chamadas = app.session_state['banco_teste'].cursor.return_value.execute.call_args_list
        salvos = [c.args[1] for c in chamadas if c.args[0].startswith('UPDATE usuarios SET funcionario_pj_razao_social')]
        self.assertEqual(salvos[-1],('Prestadora Nova','22.333.444/0001-55','Rua Nova, 20',88))
        app.session_state['banco_teste'].commit.assert_called_once()

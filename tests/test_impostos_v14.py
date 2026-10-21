"""Regras, isolamento, telas e bloqueios fiscais; sem MySQL ou rede."""
import copy
import json
import unittest
from datetime import date
from decimal import Decimal as D
from unittest.mock import patch
from lxml import etree
from streamlit.testing.v1 import AppTest

from dsystem_erp.services import impostos_simples as calc
from dsystem_erp.services import impostos_cadastro as cadastro
from dsystem_erp.services import impostos_notas as notas
from dsystem_erp.services import fiscal_automatico as auto


class CalculoTests(unittest.TestCase):
    def test_prolabore_dois_modos_sem_percentual_implicito(self):
        self.assertEqual(calc.valor_prolabore('fixo', '3000', 10000), D('3000.00'))
        self.assertEqual(calc.valor_prolabore('percentual', '12.5', 10000), D('1250.00'))
        self.assertEqual(calc.valor_prolabore('percentual', 20, 0), D('0.00'))
        for modo, valor in [('percentual', 101), ('fixo', -1), ('fixo', 'NaN'), ('outro', 1)]:
            with self.subTest(modo=modo, valor=valor), self.assertRaises(ValueError):
                calc.valor_prolabore(modo, valor, 10000)

    def test_inss_teto_outros_vinculos_e_irpf_reducao(self):
        p = calc.encargos_prolabore(10000, ano=2026)
        self.assertEqual(p['inss'], D('932.31'))
        self.assertEqual(calc.encargos_prolabore(3000, ano=2026, base_inss_outros='8475.55')['inss'], 0)
        self.assertEqual(calc.encargos_prolabore(3000, ano=2026, base_inss_outros='8000')['inss'], D('52.31'))
        self.assertEqual(calc.encargos_prolabore(5000, ano=2026)['irpf'], 0)
        p = calc.encargos_prolabore(6000, ano=2026)
        self.assertEqual(p['inss'], D('660.00'))
        self.assertEqual(p['irpf'], D('380.02'))
        self.assertEqual(p['reducao_irpf'], D('179.75'))
        self.assertEqual(p['liquido'], D('4959.98'))

    def test_deducao_mais_favoravel_e_regras_por_ano(self):
        self.assertEqual(calc.encargos_prolabore(3000, ano=2026)['deducao_irpf'], D('607.20'))
        self.assertEqual(calc.encargos_prolabore(3000, ano=2026, dependentes=3)['deducao_irpf'], D('898.77'))
        with self.assertRaises(ValueError): calc.encargos_prolabore(3000, ano=2027)
        with self.assertRaises(ValueError): calc.encargos_prolabore(3000, ano=2026, dependentes=1.5)

    def test_anexos_progressivos_e_fator_r_limite_exato(self):
        self.assertEqual(calc.aliquota_simples('I', 300000, ano=2026)['aliquota'], D('.0532'))
        self.assertEqual(calc.aliquota_simples('III', 300000, ano=2026)['aliquota'], D('.0808'))
        self.assertEqual(calc.aliquota_simples('Fator R', 300000, 84000, ano=2026)['anexo'], 'III')
        self.assertEqual(calc.aliquota_simples('Fator R', 300000, '83999.99', ano=2026)['anexo'], 'V')
        _, total = calc.estimar_simples({'I':10000,'III':10000}, 300000, ano=2026)
        self.assertEqual(total, D('1340.00'))
        for anexo, rbt, fs in [('I',0,0),('I',3600001,0),('IV',100000,0),('Fator R',100000,None)]:
            with self.subTest(anexo=anexo,rbt=rbt), self.assertRaises(ValueError):
                calc.aliquota_simples(anexo,rbt,fs,ano=2026)

    def test_totais_nao_duplicam_retencoes(self):
        p = calc.encargos_prolabore(6000, ano=2026)
        t = calc.totais(1000, [p])
        self.assertEqual(t['desembolso'], 7000)
        self.assertEqual(t['total_recolher'], D('2040.02'))
        self.assertEqual(t['prolabore_liquido']+t['total_recolher'], t['desembolso'])


class CadastroTests(unittest.TestCase):
    def setUp(self):
        from tests.test_fiscal_automatico import AutomaticoTests
        self.f = AutomaticoTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)

    def test_cadastro_isolado_por_empresa_tipo_e_nome(self):
        self.assertEqual(cadastro.chave_item('23524449000154','Produto','MOUSE'), cadastro.chave_item('23.524.449/0001-54','Produto',' Mouse '))
        self.assertNotEqual(cadastro.chave_item('23524449000154','Produto','Mouse'), cadastro.chave_item('23524449000235','Produto','Mouse'))
        self.assertNotEqual(cadastro.chave_item('23524449000154','Produto','Mouse'), cadastro.chave_item('23524449000154','Serviço','Mouse'))
        with self.assertRaises(PermissionError):
            cadastro.salvar_regra(self.f.conectar, '23524449000154', {}, {'tipo_login':'cliente','is_admin':1})
        for codigo, tamanho in [('8471605Z3',8),('01/02/4751',7),('010701X',6)]:
            with self.assertRaises(ValueError): cadastro.codigo_fiscal(codigo,tamanho,'Código')

    def test_aplica_taxas_antes_de_assinar_sem_mutar_origem(self):
        f = self.f
        antes = copy.deepcopy(f.prod_itens)
        dados, itens, snapshot = cadastro.preparar_cadastro(f.conectar, f.prod_dados['emitente_cnpj'], f.prod_itens, 'Produto', f.prod_dados)
        self.assertEqual(itens[0]['ncm'], '84716053')
        self.assertEqual(itens[0]['tributos']['pis'], '1.65')
        self.assertEqual(f.prod_itens, antes)
        self.assertEqual(snapshot[0]['regra']['anexo'], 'I')

    def test_cadastro_iss_nao_forca_tag_paliq_em_todos_os_regimes(self):
        f = self.f
        origem = json.loads(f.fat['itens'])
        dados, _, _ = cadastro.preparar_cadastro(f.conectar,f.serv_dados['cnpj_prestador'],origem,'Serviço',f.serv_dados)
        self.assertFalse(dados['informar_aliquota'])
        regra = next(r for r in cadastro.listar_regras(f.conectar,'23524449000154') if r['tipo']=='Serviço')
        regra.update(aliquota_iss=2,informar_aliquota=True)
        cadastro.salvar_regra(f.conectar,'23524449000154',regra,dict(username='contador',is_admin=1))
        dados, _, _ = cadastro.preparar_cadastro(f.conectar,'23524449000154',origem,'Serviço',f.serv_dados)
        self.assertTrue(dados['informar_aliquota'])
        self.assertIn(b'<pAliq>2.00</pAliq>',auto.gerar_xml_dps_nacional(f.fat,dados))

    def test_falta_cadastro_bloqueia_antes_da_rede(self):
        f = self.f
        f.db.execute("DELETE FROM configuracoes_sistema WHERE chave LIKE 'IMPOSTO_ITEM_%'")
        with self.assertRaisesRegex(ValueError, 'Cadastre os impostos'), patch.object(auto, 'enviar_xml_nfe_produto') as enviar:
            f.preparar('Produto')
        enviar.assert_not_called()
        self.assertEqual(f.db.execute('SELECT count(*) FROM fiscal_emissoes_auto').fetchone()[0], 0)

    def test_alteracao_de_regra_nao_muda_plano_aprovado_silenciosamente(self):
        f = self.f
        f.preparar('Produto'); f.faturar()
        regras = cadastro.listar_regras(f.conectar, f.prod_dados['emitente_cnpj'])
        r = next(r for r in regras if r['tipo']=='Produto')
        r['pis'] = '2.00'
        cadastro.salvar_regra(f.conectar, r['empresa'], r, {'username':'contador','is_admin':1})
        with self.assertRaisesRegex(ValueError, 'alterado após'):
            auto._reivindicar(f.conectar, 1, 'Produto')
        self.assertEqual(f.db.execute('SELECT count(*) FROM notas_fiscais').fetchone()[0], 0)

    def test_snapshot_no_envio_manual_e_nao_ha_alteracao_posterior(self):
        f = self.f
        f.preparar('Produto'); f.faturar()
        plano = json.loads(f.db.execute("SELECT plano_json FROM fiscal_emissoes_auto").fetchone()[0])
        f.db.execute('UPDATE faturamento SET emitir_automaticamente=0')
        f.db.execute("INSERT INTO notas_fiscais (id,faturamento_id,tipo_nota,status) VALUES (11,1,'Produto','Pendente')")
        f.db.commit()
        auto.iniciar_envio_manual(f.conectar,1,11,plano_impostos=plano)
        snap = cadastro.ler_cursor(f.conectar().cursor(),'IMPOSTO_NOTA_23524449000154_11')
        self.assertEqual(snap['itens'][0]['valor'],'100.00')
        with self.assertRaises(ValueError): auto.iniciar_envio_manual(f.conectar,1,11,plano_impostos=plano)

    def test_csosn_especial_nao_convertido_ou_inss_omitido(self):
        f = self.f
        regras = cadastro.listar_regras(f.conectar, f.prod_dados['emitente_cnpj'])
        r = next(r for r in regras if r['tipo']=='Produto')
        r.update(csosn='500', crt='1')
        cadastro.salvar_regra(f.conectar, r['empresa'], r, {'username':'contador','is_admin':1})
        with self.assertRaisesRegex(ValueError, 'ICMS-ST'):
            cadastro.preparar_cadastro(f.conectar,r['empresa'],f.prod_itens,'Produto',dict(f.prod_dados,regime_tributario='1'))
        r = next(r for r in regras if r['tipo']=='Serviço')
        r['retencao_inss'] = 11
        cadastro.salvar_regra(f.conectar,r['empresa'],r,{'username':'contador','is_admin':1})
        with self.assertRaisesRegex(ValueError, 'INSS'):
            cadastro.preparar_cadastro(f.conectar,r['empresa'],json.loads(f.fat['itens']),'Serviço',f.serv_dados)

    def test_classificacao_historica_exige_total_permissao_e_preserva_xml(self):
        f = self.f
        nota = BaseNotasTests().nfe()
        f.db.execute("INSERT INTO notas_fiscais (id,tipo_nota,status,xml_autorizado,chave_acesso) VALUES (50,'Produto','Autorizada',?,?)",
                     (nota['xml_autorizado'],nota['chave_acesso']))
        f.db.commit()
        usuario = dict(username='contador',is_admin=1)
        with self.assertRaisesRegex(ValueError,'soma'):
            notas.classificar_historica(f.conectar,'23524449000154',50,[dict(nome='Mouse',valor=99)],usuario)
        with self.assertRaises(PermissionError):
            notas.classificar_historica(f.conectar,'23524449000154',50,[dict(nome='Mouse',valor=100)],dict(tipo_login='cliente'))
        notas.classificar_historica(f.conectar,'23524449000154',50,[dict(nome='Mouse',valor=100)],usuario)
        with self.assertRaisesRegex(ValueError,'preservado'):
            notas.classificar_historica(f.conectar,'23524449000154',50,[dict(nome='Mouse',valor=100)],usuario)
        self.assertEqual(f.db.execute('SELECT xml_autorizado FROM notas_fiscais WHERE id=50').fetchone()[0],nota['xml_autorizado'])

    def test_gerador_nao_ignora_csosn_nao_suportado(self):
        f = self.f
        with self.assertRaisesRegex(ValueError,'CSOSN'):
            auto.gerar_xml_nfe_produto_400(f.fat,[dict(f.prod_itens[0],csosn='500')],dict(f.prod_dados,regime_tributario='1'))

    def test_operacao_especial_nao_e_emitida_como_comum(self):
        f = self.f
        r = next(r for r in cadastro.listar_regras(f.conectar,f.prod_dados['emitente_cnpj']) if r['tipo']=='Produto')
        r['operacao_especial'] = True
        cadastro.salvar_regra(f.conectar,r['empresa'],r,dict(username='contador',is_admin=1))
        with self.assertRaisesRegex(ValueError,'especial'):
            f.preparar('Produto')


class BaseNotasTests(unittest.TestCase):
    def nfe(self, *, ambiente='1', empresa='23524449000154', chave='1'*44, total='100', status='Autorizada'):
        xml = f'''<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe"><NFe><infNFe Id="NFe{chave}">
        <ide><tpAmb>{ambiente}</tpAmb><dhEmi>2026-10-01T10:00:00-03:00</dhEmi></ide><emit><CNPJ>{empresa}</CNPJ><CRT>1</CRT></emit>
        <det><prod><xProd>Mouse</xProd><vProd>{total}</vProd></prod></det><total><ICMSTot><vNF>{total}</vNF></ICMSTot></total>
        </infNFe></NFe><protNFe><infProt><tpAmb>{ambiente}</tpAmb><cStat>100</cStat><chNFe>{chave}</chNFe></infProt></protNFe></nfeProc>'''
        return dict(id=1,tipo_nota='Produto',status=status,xml_autorizado=xml,chave_acesso=chave)

    def test_apenas_producao_autorizada_emitente_mes_sem_duplicidade(self):
        normal = self.nfe()
        entradas = [normal, dict(normal,id=2), self.nfe(ambiente='2'),self.nfe(empresa='23524449000235'),self.nfe(status='Rejeitada')]
        base, erros = notas.base_mensal(entradas,'23524449000154',date(2026,10,1))
        self.assertEqual(len(base),1); self.assertEqual(erros,[])
        self.assertEqual(base[0]['total'],100)
        self.assertEqual(notas.base_mensal(entradas,'23524449000154',date(2026,9,1))[0],[])
        self.assertEqual(notas.base_mensal([normal,self.nfe(status='Cancelada')],'23524449000154',date(2026,10,1))[0],[])

    def test_xml_faltante_errado_ou_entidade_fica_pendente(self):
        for xml in ('', '<bad>', '<!DOCTYPE x><x/>', self.nfe()['xml_autorizado'].replace('<cStat>100','<cStat>297')):
            with self.subTest(xml=xml):
                b, p = notas.base_mensal([dict(self.nfe(),xml_autorizado=xml)],'23524449000154',date(2026,10,1))
                self.assertFalse(b); self.assertTrue(p)

    def test_regime_normal_nao_e_apurado_como_simples(self):
        nota = self.nfe()
        nota['xml_autorizado'] = nota['xml_autorizado'].replace('<CRT>1</CRT>','<CRT>3</CRT>')
        n = notas.extrair_nota(nota,'23524449000154')
        receitas, erros = notas.segregar([n],{},[],permitir_cadastro_atual=True)
        self.assertFalse(receitas)
        self.assertIn('regime',erros[0])

    def test_nfse_producao_competencia_e_mei_excluido_do_das(self):
        xml = '''<NFSe xmlns="http://www.sped.fazenda.gov.br/nfse"><infNFSe Id="NFS123"><nNFSe>1</nNFSe>
        <DPS><infDPS><tpAmb>1</tpAmb><dCompet>2026-10-01</dCompet><prest><CNPJ>23524449000154</CNPJ>
        <regTrib><opSimpNac>3</opSimpNac></regTrib></prest><valores><vServPrest><vServ>150.00</vServ></vServPrest></valores>
        </infDPS></DPS></infNFSe></NFSe>'''
        row = dict(id=5,tipo_nota='Serviço',status='Autorizada',xml_autorizado=xml,chave_acesso='123')
        n = notas.extrair_nota(row,'23524449000154')
        self.assertEqual(n['competencia'],date(2026,10,1))
        self.assertEqual(n['total'],D('150'))
        self.assertTrue(n['simples'])
        row['xml_autorizado'] = xml.replace('<opSimpNac>3','<opSimpNac>2')
        self.assertFalse(notas.extrair_nota(row,'23524449000154')['simples'])

    def test_protocolo_homologacao_nao_comprova_xml_producao(self):
        row = self.nfe()
        row['xml_autorizado'] = row['xml_autorizado'].replace('<infProt><tpAmb>1','<infProt><tpAmb>2')
        with self.assertRaisesRegex(ValueError,'Ambiente'):
            notas.extrair_nota(row,'23524449000154')

    def test_seg_das_exige_total_exato_e_nao_calcula_retencao_como_comum(self):
        n = notas.extrair_nota(self.nfe(),'23524449000154')
        r = dict(nome='Mouse', tipo='Produto', anexo='I', confirmado=True)
        receitas, erros = notas.segregar([n],{},[r])
        self.assertEqual(receitas,{}); self.assertTrue(erros)
        receitas, erros = notas.segregar([n],{},[r],permitir_cadastro_atual=True)
        self.assertEqual(receitas,{'I':D('100.00')}); self.assertFalse(erros)
        receitas, erros = notas.segregar([n],{'1':[dict(nome='Mouse',valor=99,regra=r)]},[])
        self.assertEqual(receitas,{}); self.assertTrue(erros)
        receitas, erros = notas.segregar([n],{'1':[dict(nome='Mouse',valor=100,regra=dict(r,csosn='500'))]},[])
        self.assertEqual(receitas,{}); self.assertTrue(erros)


class PaginaTests(unittest.TestCase):
    def app(self, permissao=True, cadastro=False):
        codigo = '''
import streamlit as st
from datetime import date
from dsystem_erp.pages.impostos import renderizar_impostos, renderizar_cadastro_impostos
st.session_state.update(autenticado=True,username='teste',tipo_login='interno',submodulos=PERMISSOES)
st.session_state.setdefault('impostos_competencia',date(2026,10,1))
def salvar(chave,valor,descricao): st.session_state['salvo_teste'] = (chave,valor)
ctx = {'config_sistema_val':lambda chave,padrao='': '23524449000154' if chave=='NFSE_CNPJ' else padrao,
       'conectar_banco':lambda: (_ for _ in ()).throw(AssertionError('banco proibido')), 'salvar_config_sistema':salvar}
FUNCAO(ctx)
'''.replace('PERMISSOES',repr(['impostos.view','impostos.edit'] if permissao else [])).replace('FUNCAO','renderizar_cadastro_impostos' if cadastro else 'renderizar_impostos')
        return AppTest.from_string(codigo,default_timeout=20)

    def test_sem_permissao_nao_consulta(self):
        with patch('dsystem_erp.pages.impostos.carregar_base') as carregar:
            app = self.app(False).run()
            self.assertFalse(app.exception)
            carregar.assert_not_called()

    def test_mudar_modo_preserva_valores_e_salva_mes(self):
        with patch('dsystem_erp.pages.impostos.carregar_base',return_value=([],{},[])), patch('dsystem_erp.pages.impostos.listar_regras',return_value=[]):
            app = self.app().run()
            self.assertFalse(app.exception)
            p = 'IMPOSTOS_MES_23524449000154_202610_p0_'
            app.text_input(key=p+'nome').set_value('Sócio A')
            app.number_input(key=p+'fixo').set_value(3000).run()
            self.assertFalse(app.exception)
            app.radio(key=p+'modo').set_value('percentual').run()
            self.assertEqual(app.number_input(key=p+'percentual').value,0)
            app.number_input(key=p+'percentual').set_value(10).run()
            app.radio(key=p+'modo').set_value('fixo').run()
            self.assertEqual(app.number_input(key=p+'fixo').value,3000)
            app.checkbox(key='IMPOSTOS_MES_23524449000154_202610_confirmado').check().run()
            next(b for b in app.button if 'Salvar parâmetros' in b.label).click().run()
            self.assertFalse(app.exception)
            chave, texto = app.session_state['salvo_teste']
            self.assertEqual(chave,'IMPOSTOS_MES_23524449000154_202610')
            b = json.loads(texto)['beneficiarios'][0]
            self.assertEqual((b['modo'],b['fixo'],b['percentual']),('fixo',3000,10))

    def test_form_cadastro_nao_salva_por_enter_ou_sem_confirmacao(self):
        with patch('dsystem_erp.pages.impostos.listar_regras',return_value=[]):
            app = self.app(cadastro=True).run()
            self.assertFalse(app.exception)
            self.assertIn('Nome exato no faturamento',[w.label for w in app.text_input])
            next(b for b in app.button if 'Salvar cadastro' in b.label).click().run()
            self.assertFalse(app.exception)
            self.assertTrue(app.error)


if __name__ == '__main__':
    unittest.main()

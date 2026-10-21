"""Clique A faturar -> assinatura/SOAP -> persistência -> PDFs, sem rede real."""
import ast
import base64
import io
import json
import unittest
from contextlib import nullcontext
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from lxml import etree
from pypdf import PdfReader

from tests.test_fiscal_automatico import Connection, Cursor
from tests import test_fiscal_automatico as fixtures, test_nfe_produto as nfe_fixtures
from tests.preview_danfse_local import xml_exemplo, CHAVE
from dsystem_erp.services import fiscal_automatico as auto
from dsystem_erp.services.fiscal_documentos import consultar_documentos_fiscais
from dsystem_erp.services.fiscal_modelos import criar_modelo
from dsystem_erp.services.nfe_produto import NFE_NS, validar_assinatura_nfe_produto
from dsystem_erp.services.nfse_nacional import NfseNacionalResult, NS_NFSE
from dsystem_erp.services.pacote_faturamento import juntar_documentos_pdf


class CompatCursor(Cursor):
    def execute(self, sql, params=()):
        return super().execute(sql.replace('%s', '?'), params)


class CompatConnection(Connection):
    def cursor(self, **kwargs):
        return CompatCursor(self.db)


class FaturarAtePdfsTests(unittest.TestCase):
    def setUp(self):
        self.f = f = fixtures.AutomaticoTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        f.conectar = lambda: CompatConnection(f.db)
        for coluna in ('alterado_por', 'alterado_em'):
            f.db.execute(f'ALTER TABLE faturamento ADD COLUMN {coluna} TEXT')
        for coluna in ('numero_nota', 'protocolo', 'numero_lote', 'xml_retorno', 'emitido_em', 'atualizado_em'):
            f.db.execute(f'ALTER TABLE notas_fiscais ADD COLUMN {coluna} TEXT')
        campos = ('cliente cpf_cnpj numero_documento tipo_receita categoria centro_receita '
                  'data_emissao data_competencia data_vencimento valor_original valor_total '
                  'forma_recebimento nota_fiscal boleto status observacoes criado_por criado_em '
                  'parcelado quantidade_parcelas meio_parcelamento parcelas_detalhes').split()
        f.db.execute('CREATE TABLE contas_receber (id INTEGER PRIMARY KEY, ' + ','.join(c + ' TEXT' for c in campos) + ')')
        f.db.execute('CREATE TABLE clientes (id INTEGER PRIMARY KEY, nome TEXT, cnpj TEXT, telefone TEXT, email TEXT)')
        f.db.execute('INSERT INTO clientes VALUES (1,?,?,?,?)', (f.fat['cliente'], f.fat['cnpj'], '', ''))
        f.db.execute('CREATE TABLE estoque (id INTEGER PRIMARY KEY, produto TEXT, quantidade INTEGER)')
        f.db.execute("INSERT INTO estoque VALUES (1,'Mouse',10)")
        f.db.commit()
        # Configuração inicial autorizada; o novo clique não tem planos individuais.
        f.serv_dados['totais_tributos'] = dict(federal=0, estadual=0, municipal=0)
        f.preparar('Serviço'); f.preparar('Produto')
        modelos = [criar_modelo(f.fat, r, 'teste', por_item=True) for r in auto.listar_emissoes(f.conectar, 1)]
        self.configs = {m['chave']: json.dumps(m) for m in modelos}
        for chave, valor in self.configs.items():
            f.db.execute('INSERT INTO configuracoes_sistema (chave,valor) VALUES (?,?)', (chave, valor))
        self.configs['NFSE_CNPJ'] = f.serv_dados['cnpj_prestador']
        f.db.execute('DELETE FROM fiscal_emissoes_auto')
        f.db.commit()
        parcela = dict(documento='FAT-1', quantidade=1, rotulo='1/1', valor=250.5, vencimento='2026-10-03')
        def localizar(c, item):
            c.execute('SELECT * FROM estoque WHERE id=1')
            return c.fetchone()
        self.ctx = dict(date=date, json=json, base64=base64, st=SimpleNamespace(session_state={'username': 'teste'}),
            conectar_banco=f.conectar, itens_faturamento_lista=json.loads,
            agora_br=lambda: '2026-10-03', data_para_banco_br=str,
            gerar_parcelas_faturamento=lambda fat: [parcela], registrar_evento_sistema=Mock(),
            localizar_produto_estoque=localizar, registrar_movimentacao=Mock(), config_sistema_val=self.configs.get)
        arvore = ast.parse((Path(__file__).resolve().parents[1] / 'orcamento.py').read_text(encoding='utf-8-sig'))
        funcoes = [n for n in arvore.body if isinstance(n, ast.FunctionDef) and n.name in
                   ('faturar_lancamento_com_integracoes', 'salvar_retorno_nota_fiscal')]
        exec(compile(ast.Module(body=funcoes, type_ignores=[]), '<fluxo-isolado>', 'exec'), self.ctx)

    def servico(self, fat, dados, **kwargs):
        xml = auto.gerar_xml_dps_nacional(fat, dados)
        kwargs['antes_envio'](xml)
        root = etree.fromstring(xml_exemplo().encode())
        inf = root.find(f'{{{NS_NFSE}}}infNFSe')
        inf.remove(inf.find(f'{{{NS_NFSE}}}DPS'))
        inf.append(etree.fromstring(xml))
        for campo in ('vBC', 'vLiq'):
            inf.find(f'{{{NS_NFSE}}}valores/{{{NS_NFSE}}}{campo}').text = '150.50'
        return NfseNacionalResult('Autorizada', 'RETORNO SIMULADO, SEM TRANSMISSÃO', xml, xml, {}, etree.tostring(root), CHAVE, '', '2')

    def sefaz_simulada(self, req, **kwargs):
        self.assertIn('hnfe.fazenda.mg.gov.br', req.full_url)
        validar_assinatura_nfe_produto(req.data)  # XML real que seria transmitido.
        nfe = etree.fromstring(req.data).find(f'.//{{{NFE_NS}}}NFe')
        self.assertEqual(nfe.findtext(f'.//{{{NFE_NS}}}tpAmb'), '2')
        chave = nfe.find(f'{{{NFE_NS}}}infNFe').get('Id')[3:]
        retorno = f'''<retEnviNFe xmlns="{NFE_NS}"><cStat>104</cStat><protNFe versao="4.00"><infProt>
          <tpAmb>2</tpAmb><chNFe>{chave}</chNFe><cStat>100</cStat><nProt>000000000000000</nProt>
          <dhRecbto>2026-10-03T12:00:00-03:00</dhRecbto><xMotivo>TESTE SIMULADO</xMotivo>
          </infProt></protNFe></retEnviNFe>'''.encode()
        return nullcontext(SimpleNamespace(read=lambda: retorno))

    def test_clique_misto_entrega_dois_pdfs_reais_e_nao_repete_efeitos(self):
        self.exercitar_clique()

    def test_clique_corrige_taxas_fixas_de_preparacao_antiga_antes_de_assinar(self):
        f = self.f
        f.preparar('Serviço'); f.preparar('Produto')
        registro = next(r for r in auto.listar_emissoes(f.conectar,1) if r['tipo'] == 'Produto')
        plano = json.loads(registro['plano_json'])
        plano['itens'][0]['ibscbs'].update(uf=2,municipal=2,cbs=2)
        f.db.execute('UPDATE fiscal_emissoes_auto SET plano_json=? WHERE id=?',
                     (json.dumps(plano),registro['id']))
        f.db.commit()
        self.exercitar_clique()
        xml = f.db.execute("SELECT xml_envio FROM notas_fiscais WHERE tipo_nota='Produto'").fetchone()[0]
        root = etree.fromstring(xml.encode())
        self.assertEqual(root.findtext(f'.//{{{NFE_NS}}}pIBSUF'), '0.1000')
        self.assertEqual(root.findtext(f'.//{{{NFE_NS}}}pIBSMun'), '0.0000')
        self.assertEqual(root.findtext(f'.//{{{NFE_NS}}}pCBS'), '0.9000')

    def test_classificacao_financeira_copiada_do_registro_atual(self):
        f = self.f
        for campo in ('categoria', 'centro', 'plano_contas', 'conta_bancaria'):
            f.db.execute(f'ALTER TABLE faturamento ADD COLUMN {campo} TEXT')
        for campo in ('plano_contas', 'conta_bancaria'):
            f.db.execute(f'ALTER TABLE contas_receber ADD COLUMN {campo} TEXT')
        f.db.execute("UPDATE faturamento SET categoria='Serviços',centro='TI',plano_contas='Receitas',conta_bancaria='Banco A'")
        f.db.commit()
        self.exercitar_clique()
        registros = f.db.execute('SELECT categoria,centro_receita,plano_contas,conta_bancaria FROM contas_receber').fetchall()
        self.assertTrue(registros)
        self.assertTrue(all(tuple(r) == ('Serviços','TI','Receitas','Banco A') for r in registros))

    def test_nova_combinacao_busca_codigo_por_nome_e_entrega_pdfs(self):
        f = self.f
        originais = json.loads(f.fat['itens'])
        produto = next(i for i in originais if i['tipo_item'] == 'Produto')
        # Novo conjunto de linhas, sem informar NCM, CFOP ou impostos nos itens.
        linhas = [i for i in originais if i['tipo_item'] == 'Serviço'] + [
            dict(desc=produto['desc'].upper(), tipo_item='Produto', qtd=1, vunit=50, vtotal=50),
            dict(desc=produto['desc'], tipo_item='Produto', qtd=1, vunit=50, vtotal=50)]
        f.fat['itens'] = json.dumps(linhas)
        f.db.execute('UPDATE faturamento SET itens=? WHERE id=1', (f.fat['itens'],))
        f.db.commit()
        self.configs = {'NFSE_CNPJ': self.configs['NFSE_CNPJ']}
        self.ctx['config_sistema_val'] = self.configs.get
        self.exercitar_clique()
        xml = f.db.execute("SELECT xml_envio FROM notas_fiscais WHERE tipo_nota='Produto'").fetchone()[0]
        codigos = etree.fromstring(xml.encode()).findall(f'.//{{{NFE_NS}}}NCM')
        self.assertEqual([n.text for n in codigos], ['84716053', '84716053'])

    def exercitar_clique(self):
        f = self.f
        with patch('dsystem_erp.services.fiscal_modelos.completar_destinatario', return_value={'dados': f.prod_dados['destinatario']}), \
             patch.object(auto, 'assinar_xml_nfe_produto', side_effect=lambda xml, *a: nfe_fixtures.NFeProdutoTests().xml_assinado_teste(xml)[0]), \
             patch.object(auto, 'executar_fluxo_nfse_nacional', side_effect=self.servico) as servico, \
             patch('dsystem_erp.services.nfse_soap.contexto_ssl_certificado_pfx', return_value=nullcontext(object())), \
             patch('urllib.request.urlopen', side_effect=self.sefaz_simulada) as rede:
            resultado = self.ctx['faturar_lancamento_com_integracoes'](f.fat, emitir_automaticamente=True)
            self.assertTrue(resultado['ok'], resultado)
            self.assertTrue(resultado['fiscal_pronto'], resultado)
            self.assertEqual(f.db.execute('SELECT count(*) FROM contas_receber').fetchone()[0], 1)
            self.assertEqual(f.db.execute('SELECT quantidade FROM estoque').fetchone()[0], 8)
            estado = consultar_documentos_fiscais(f.conectar, 1)
            self.assertTrue(estado['pronto'], estado['pendencias'])
            self.assertEqual(len(estado['documentos']), 2)
            textos = [PdfReader(io.BytesIO(d.arquivo)).pages[0].extract_text() for d in estado['documentos']]
            self.assertTrue(any('DANFSe' in t for t in textos))
            self.assertTrue(any('Mouse' in t and 'SEM VALOR FISCAL' in t for t in textos))
            pacote = juntar_documentos_pdf(estado['documentos'], 1, f.fat['cliente'])
            self.assertEqual(len(PdfReader(io.BytesIO(pacote)).pages), 3)  # capa + serviço + produto
            repetido = self.ctx['faturar_lancamento_com_integracoes'](f.fat, emitir_automaticamente=True)
            self.assertFalse(repetido['ok'])
            auto.processar_emissoes(f.conectar, 1, self.configs.get, self.ctx['salvar_retorno_nota_fiscal'])
            self.assertEqual(servico.call_count, 1)
            self.assertEqual(rede.call_count, 1)
            self.assertEqual(f.db.execute('SELECT count(*) FROM contas_receber').fetchone()[0], 1)
            self.assertEqual(f.db.execute('SELECT quantidade FROM estoque').fetchone()[0], 8)

    def test_sem_modelo_produto_nao_fatura_nem_envia_servico(self):
        self.configs.clear()
        with patch('urllib.request.urlopen') as rede, patch.object(auto, 'executar_fluxo_nfse_nacional') as servico:
            resultado = self.ctx['faturar_lancamento_com_integracoes'](self.f.fat, emitir_automaticamente=True)
        self.assertFalse(resultado['ok'])
        self.assertIn('Produto', resultado['mensagem'])
        self.assertEqual(self.f.db.execute('SELECT count(*) FROM contas_receber').fetchone()[0], 0)
        self.assertEqual(self.f.db.execute('SELECT quantidade FROM estoque').fetchone()[0], 10)
        rede.assert_not_called(); servico.assert_not_called()

"""Testa persistência/estados com SQLite isolado, sem servidor fiscal ou banco real."""
import json
import re
import sqlite3
import unittest
from contextlib import ExitStack
from unittest.mock import patch
from lxml import etree

from dsystem_erp.services import fiscal_automatico as auto
from dsystem_erp.services.nfse_nacional import NfseNacionalResult, ENDPOINT_HOMOLOGACAO
from dsystem_erp.services.nfe_produto import endpoint_autorizacao_nfe, NFE_NS
from tests import test_nfse_nacional, test_nfe_produto

reservar_numero_produto_real = auto.reservar_numero_produto

class Cursor:
    def __init__(self, db):
        self.raw = db.cursor()

    def execute(self, sql, params=()):
        sql = sql.replace(' FOR UPDATE', '')
        if 'ON DUPLICATE KEY UPDATE' in sql:
            inicio, fim = sql.split('ON DUPLICATE KEY UPDATE', 1)
            fim = re.sub(r'VALUES\((\w+)\)', r'excluded.\1', fim)
            alvo = 'chave' if 'INTO nfse_sequencias' in inicio else 'faturamento_id,tipo'
            sql = inicio + f' ON CONFLICT({alvo}) DO UPDATE SET ' + fim
        self.raw.execute(sql, params)
        return self

    def fetchone(self):
        row = self.raw.fetchone()
        return dict(row) if row else None

    def fetchall(self):
        return [dict(r) for r in self.raw.fetchall()]

    @property
    def lastrowid(self):
        return self.raw.lastrowid


class Connection:
    def __init__(self, db): self.db = db
    def cursor(self): return Cursor(self.db)
    def commit(self): self.db.commit()
    def rollback(self): self.db.rollback()
    def close(self): pass


class AutomaticoTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
            CREATE TABLE configuracoes_sistema (chave TEXT PRIMARY KEY, valor TEXT);
            CREATE TABLE faturamento (id INTEGER PRIMARY KEY, cliente TEXT, cnpj TEXT, itens TEXT, obs_nota TEXT,
                valor_total REAL, emite_nf TEXT, documentos_entrega TEXT, emitir_automaticamente INTEGER, status TEXT);
            CREATE TABLE fiscal_emissoes_auto (id INTEGER PRIMARY KEY, faturamento_id INTEGER, tipo TEXT, estado TEXT,
                nota_id INTEGER, plano_json TEXT, origem_hash TEXT, mensagem TEXT, xml_envio TEXT, xml_retorno TEXT,
                autorizado_por TEXT, atualizado_em TEXT, UNIQUE(faturamento_id,tipo));
            CREATE TABLE notas_fiscais (id INTEGER PRIMARY KEY, faturamento_id INTEGER, cliente TEXT, cpf_cnpj TEXT,
                tipo_nota TEXT, status TEXT, valor_servicos REAL, descricao TEXT, data_competencia TEXT,
                criado_por TEXT, criado_em TEXT, xml_envio TEXT, mensagem_retorno TEXT,
                xml_autorizado TEXT, pdf_base64 TEXT, link_nota TEXT, chave_acesso TEXT);
        ''')
        exemplo = test_nfse_nacional.NfseNacionalTest()
        exemplo.setUp()
        self.serv_dados = exemplo.dados
        _, itens_prod, self.prod_dados = test_nfe_produto.NFeProdutoTests().exemplo()
        self.prod_dados.update(emitente_logradouro='Rua', emitente_numero='1', emitente_bairro='Centro',
                              emitente_municipio='Belo Horizonte', emitente_cep='31000000')
        self.prod_itens = [{**i, 'tipo_item': 'Produto'} for i in itens_prod]
        itens = [dict(desc='Suporte', tipo_item='Serviço', qtd=1, vunit=150.5, vtotal=150.5)] + self.prod_itens
        self.fat = dict(id=1, cliente=exemplo.faturamento['cliente'], cnpj=exemplo.faturamento['cnpj'],
                        itens=json.dumps(itens), obs_nota='', valor_total=250.5, emite_nf='Sim',
                        documentos_entrega='Nota e espelho', emitir_automaticamente=1, status='Aberto')
        self.db.execute('INSERT INTO faturamento VALUES (?,?,?,?,?,?,?,?,?,?)', tuple(self.fat.values()))
        self.db.commit()
        self.conectar = lambda: Connection(self.db)
        # Cadastro obrigatório da versão 1.4, somente no SQLite isolado.
        from dsystem_erp.services.impostos_cadastro import salvar_regra
        usuario = {'username': 'contador_teste', 'is_admin': 1}
        salvar_regra(self.conectar, self.serv_dados['cnpj_prestador'], dict(
            tipo='Serviço', nome='Suporte', cnae='6209100', anexo='Fator R', confirmado=True,
            codigo_tributacao_nacional=self.serv_dados['codigo_tributacao_nacional'],
            codigo_tributacao_municipal='', aliquota_iss=0, tipo_retencao_issqn='1'), usuario)
        for item in self.prod_itens:
            salvar_regra(self.conectar, self.prod_dados['emitente_cnpj'], dict(
                tipo='Produto', nome=item['desc'], cnae='4751201', anexo='I', confirmado=True,
                crt=str(self.prod_dados['regime_tributario']), csosn='102',
                ncm=item.get('ncm') or self.prod_dados['ncm'], cfop=item.get('cfop') or self.prod_dados['cfop'],
                unidade='UN', origem='0', **{k:item['tributos'][k] for k in ('icms', 'pis', 'cofins')}), usuario)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.addCleanup(self.db.close)
        self.stack.enter_context(patch('dsystem_erp.services.nfse_certificado.inspecionar_certificado_pfx', return_value={'documentos': ['23524449000154']}))
        self.stack.enter_context(patch.object(auto, 'proximo_numero_nfse', return_value=123))
        self.stack.enter_context(patch.object(auto, 'reservar_numero_produto', return_value=20))
        self.stack.enter_context(patch.object(auto, 'assinar_xml_nfe_produto', side_effect=lambda xml, *a: xml))

    def preparar(self, tipo):
        dados, itens, endpoint = (self.serv_dados, [], ENDPOINT_HOMOLOGACAO) if tipo == 'Serviço' else (self.prod_dados, self.prod_itens, endpoint_autorizacao_nfe('MG', 'homologacao'))
        auto.salvar_plano(self.conectar, 1, tipo, dados, itens, self.fat, endpoint, 'usuario_teste')

    def faturar(self):
        self.db.execute("UPDATE faturamento SET status='Faturado'")
        self.db.commit()

    def salvar(self, nota_id, xml, retorno, info):
        self.db.execute('UPDATE notas_fiscais SET status=? WHERE id=?', (info['status'], nota_id))
        self.db.commit()

    def retorno_servico(self, fat, dados, **kwargs):
        xml = auto.gerar_xml_dps_nacional(fat, dados)
        kwargs['antes_envio'](xml)
        ns = 'http://www.sped.fazenda.gov.br/nfse'
        root = etree.Element(f'{{{ns}}}NFSe', nsmap={None: ns})
        chave = '1' * 50
        inf = etree.SubElement(root, f'{{{ns}}}infNFSe', Id='NFS' + chave)
        etree.SubElement(inf, f'{{{ns}}}nNFSe').text = '5'
        inf.append(etree.fromstring(xml))
        return NfseNacionalResult('Autorizada', 'Autorizada no teste simulado', xml, xml, {}, etree.tostring(root), chave, '', '5')

    def retorno_produto(self, endpoint, xml, *args, **kwargs):
        self.assertEqual(kwargs.get('sha256_assinado'), auto.sha256_nfe_assinada(xml))
        ns = {'n': NFE_NS}
        chave = etree.fromstring(xml).find('n:infNFe', ns).get('Id')[3:]
        return f'<retEnviNFe xmlns="{NFE_NS}"><cStat>104</cStat><protNFe versao="4.00"><infProt><tpAmb>2</tpAmb><chNFe>{chave}</chNFe><cStat>100</cStat><nProt>123</nProt><xMotivo>Autorizado no teste</xMotivo></infProt></protNFe></retEnviNFe>'.encode()

    def processar(self):
        return auto.processar_emissoes(self.conectar, 1, lambda *args: '', self.salvar)

    def test_misto_autoriza_uma_vez_e_preserva_apos_novo_clique(self):
        self.preparar('Serviço'); self.preparar('Produto'); self.faturar()
        with patch.object(auto, 'executar_fluxo_nfse_nacional', side_effect=self.retorno_servico) as serv, \
             patch.object(auto, 'enviar_xml_nfe_produto', side_effect=self.retorno_produto) as prod:
            estados = self.processar()
            self.assertEqual({r['estado'] for r in estados}, {'Autorizada'})
            self.processar()
            self.assertEqual(serv.call_count, 1)
            self.assertEqual(prod.call_count, 1)
            self.assertEqual(self.db.execute('SELECT count(*) FROM notas_fiscais').fetchone()[0], 2)

    def test_timeout_nao_reenvia_e_nao_bloqueia_outro_tipo(self):
        self.preparar('Serviço'); self.preparar('Produto'); self.faturar()
        def timeout(fat, dados, **kwargs):
            kwargs['antes_envio'](auto.gerar_xml_dps_nacional(fat, dados))
            raise TimeoutError('conexão incerta')
        with patch.object(auto, 'executar_fluxo_nfse_nacional', side_effect=timeout) as serv, \
             patch.object(auto, 'enviar_xml_nfe_produto', side_effect=self.retorno_produto):
            estados = {r['tipo']: r for r in self.processar()}
            self.assertEqual(estados['Serviço']['estado'], 'Conferir')
            self.assertTrue(estados['Serviço']['xml_envio'])
            self.assertEqual(estados['Produto']['estado'], 'Autorizada')
            self.processar()
            self.assertEqual(serv.call_count, 1)
            with self.assertRaises(ValueError): self.preparar('Serviço')

    def test_dados_alterados_exigem_nova_conferencia(self):
        self.preparar('Serviço'); self.faturar()
        self.db.execute("UPDATE faturamento SET cnpj='outro'")
        self.db.commit()
        with patch.object(auto, 'executar_fluxo_nfse_nacional') as serv:
            self.assertEqual(self.processar()[1]['estado'], 'Pendente')
            serv.assert_not_called()

    def test_sem_preparacao_gera_pendencias_sem_envio(self):
        self.faturar()
        estados = self.processar()
        self.assertEqual(len(estados), 2)
        self.assertEqual({r['estado'] for r in estados}, {'Pendente'})

    def test_desativado_ou_so_espelho_nao_emite(self):
        self.preparar('Serviço'); self.faturar()
        for campo, valor in [('emitir_automaticamente', 0), ('documentos_entrega', 'Somente espelho')]:
            self.db.execute(f'UPDATE faturamento SET {campo}=?', (valor,))
            self.db.commit()
            with patch.object(auto, 'executar_fluxo_nfse_nacional') as serv:
                self.processar(); serv.assert_not_called()
            self.db.execute('UPDATE faturamento SET emitir_automaticamente=1')

    def test_aberto_nao_envia(self):
        self.preparar('Serviço')
        with patch.object(auto, 'executar_fluxo_nfse_nacional') as serv:
            self.processar(); serv.assert_not_called()

    def test_e0314_antigo_libera_edicao_sem_reenviar(self):
        self.preparar('Serviço'); self.faturar()
        registro, plano, nota_id = auto._reivindicar(self.conectar, 1, 'Serviço')
        mensagem = 'API Nacional retornou HTTP 400: E0314 - Código municipal inválido. Consulte o resultado antes de qualquer novo envio.'
        self.db.execute("UPDATE fiscal_emissoes_auto SET estado='Conferir',mensagem=?", (mensagem,))
        self.db.execute("UPDATE notas_fiscais SET status='Conferir'")
        self.db.commit()
        auto.liberar_correcao(self.conectar, 1, 'Serviço', True)
        registro = auto.listar_emissoes(self.conectar, 1)[0]
        self.assertEqual(registro['estado'], 'Pendente')
        self.assertIn('E0314', registro['mensagem'])
        with patch.object(auto, 'executar_fluxo_nfse_nacional') as envio:
            self.processar()
            envio.assert_not_called()
        self.preparar('Serviço')
        self.assertEqual(next(r for r in auto.listar_emissoes(self.conectar,1) if r['tipo']=='Serviço')['estado'], 'Pronta')

    def test_timeout_e_autorizada_nao_liberam_correcao(self):
        self.preparar('Serviço'); self.faturar()
        auto._reivindicar(self.conectar, 1, 'Serviço')
        for estado, mensagem in [('Conferir', 'Timeout'), ('Autorizada', 'Autorizada')]:
            self.db.execute('UPDATE fiscal_emissoes_auto SET estado=?,mensagem=?', (estado,mensagem))
            self.db.commit()
            with self.assertRaises(ValueError): auto.liberar_correcao(self.conectar,1,'Serviço',True)

    def test_correcao_verifica_autorizacao_e_permissao(self):
        self.preparar('Serviço'); self.faturar()
        auto._reivindicar(self.conectar,1,'Serviço')
        self.db.execute("UPDATE fiscal_emissoes_auto SET estado='Rejeitada'")
        self.db.execute("UPDATE notas_fiscais SET status='Autorizada'")
        self.db.commit()
        with self.assertRaises(ValueError): auto.liberar_correcao(self.conectar,1,'Serviço',True)
        with self.assertRaises(PermissionError): auto.liberar_correcao(self.conectar,1,'Serviço',False)

    def test_e0314_corrigivel_mas_rejeicao_desconhecida_nao(self):
        self.assertTrue(auto.rejeicao_nfse_corrigivel({'erros':[{'Codigo':'E0314'}]}))
        self.assertFalse(auto.rejeicao_nfse_corrigivel({'erros':[{'Codigo':'E0314'},{'Codigo':'E9999'}]}))

    def test_preparacao_nao_grava_senha_e_preserva_ambiente(self):
        self.serv_dados['senha'] = 'segredo'
        self.preparar('Serviço')
        plano = auto.listar_emissoes(self.conectar, 1)[0]['plano_json']
        self.assertNotIn('segredo', plano)
        self.assertEqual(json.loads(plano)['dados']['ambiente'], 'homologacao')

    def test_trava_duravel_nao_reivindica_duas_vezes(self):
        self.preparar('Serviço'); self.faturar()
        self.assertIsNotNone(auto._reivindicar(self.conectar, 1, 'Serviço'))
        self.assertIsNone(auto._reivindicar(self.conectar, 1, 'Serviço'))
        with self.assertRaises(ValueError): self.preparar('Serviço')

    def test_edicao_sem_mudar_dados_nao_invalida_preparacao(self):
        self.preparar('Serviço')
        equivalente = dict(self.fat, valor_total='250.5000', obs_nota=None)
        itens = json.loads(equivalente['itens'])
        for item in itens:
            item.update(estoque_id=None, origem_item='', vunit=float(item['vunit']), qtd=float(item['qtd']))
        equivalente['itens'] = itens
        self.assertEqual(auto.hash_origem(equivalente), auto.hash_origem(self.fat))

    def test_numeracao_produto_separa_ambiente_e_serie(self):
        reservar = lambda dados: reservar_numero_produto_real(self.conectar, dados)
        inicial = int(self.prod_dados['numero'])
        self.assertEqual(reservar(self.prod_dados), inicial)
        self.assertEqual(reservar(self.prod_dados), inicial + 1)
        self.assertEqual(reservar(dict(self.prod_dados, serie=2)), inicial)
        self.assertEqual(reservar(dict(self.prod_dados, ambiente='producao')), inicial)

    def test_numeracao_recupera_ultima_nota_salva(self):
        xml = auto.gerar_xml_nfe_produto_400(self.fat, self.prod_itens, dict(self.prod_dados, numero=50))
        self.db.execute("INSERT INTO notas_fiscais (tipo_nota,xml_envio) VALUES ('Produto',?)", (xml.decode(),))
        self.db.commit()
        self.assertEqual(reservar_numero_produto_real(self.conectar, self.prod_dados), 51)

    def test_rejeicao_duplicidade_nao_libera_novo_envio(self):
        self.preparar('Produto'); self.faturar()
        retorno = f'<retEnviNFe xmlns="{NFE_NS}"><cStat>204</cStat><xMotivo>Duplicidade</xMotivo></retEnviNFe>'.encode()
        with patch.object(auto, 'enviar_xml_nfe_produto', return_value=retorno) as envio:
            estado = next(r for r in self.processar() if r['tipo'] == 'Produto')
            self.assertEqual(estado['estado'], 'Conferir')
            self.assertEqual(self.db.execute('SELECT status FROM notas_fiscais').fetchone()[0], 'Conferir')
            self.processar()
            self.assertEqual(envio.call_count, 1)

    def test_certificado_invalido_nao_transmite(self):
        self.preparar('Produto'); self.faturar()
        with patch('dsystem_erp.services.nfse_certificado.inspecionar_certificado_pfx', side_effect=ValueError('Certificado ausente')), \
             patch.object(auto, 'enviar_xml_nfe_produto') as envio:
            estado = next(r for r in self.processar() if r['tipo'] == 'Produto')
            self.assertEqual(estado['estado'], 'Pendente')
            envio.assert_not_called()

    def test_manual_e_automatico_nao_podem_reivindicar_mesma_nota(self):
        self.preparar('Produto'); self.faturar()
        self.db.execute("INSERT INTO notas_fiscais (id,faturamento_id,tipo_nota,status) VALUES (20,1,'Produto','Pendente')")
        self.db.commit()
        with self.assertRaises(ValueError): auto.iniciar_envio_manual(self.conectar, 1, 20)
        self.db.execute('UPDATE faturamento SET emitir_automaticamente=0')
        self.db.commit()
        plano = json.loads(self.db.execute("SELECT plano_json FROM fiscal_emissoes_auto WHERE tipo='Produto'").fetchone()[0])
        auto.iniciar_envio_manual(self.conectar, 1, 20, plano_impostos=plano)
        with self.assertRaises(ValueError): auto.iniciar_envio_manual(self.conectar, 1, 20)
        auto.registrar_xml_manual(self.conectar, 20, b'<teste/>')
        auto.registrar_falha_manual(self.conectar, 20, TimeoutError('incerto'), True)
        self.db.execute('UPDATE faturamento SET emitir_automaticamente=1')
        self.db.commit()
        self.assertIsNone(auto._reivindicar(self.conectar, 1, 'Produto'))
        self.assertEqual(self.db.execute('SELECT status FROM notas_fiscais WHERE id=20').fetchone()[0], 'Conferir')

    def test_falha_apos_salvar_autorizacao_preserva_nota(self):
        self.preparar('Produto'); self.faturar()
        def salvar_com_falha(*args):
            self.salvar(*args)
            raise RuntimeError('Falhou uma operação depois de persistir autorização')
        with patch.object(auto, 'enviar_xml_nfe_produto', side_effect=self.retorno_produto):
            auto.processar_emissoes(self.conectar, 1, lambda *args: '', salvar_com_falha)
        self.assertEqual(self.db.execute('SELECT status FROM notas_fiscais').fetchone()[0], 'Autorizada')

    def test_recuperar_pdf_nao_emite_nova_nota(self):
        from tests.test_nfe_documento import exemplo_processado
        xml, retorno = exemplo_processado()
        processado = auto.montar_nfe_processada(xml, retorno).decode()
        self.db.execute("INSERT INTO notas_fiscais (id,faturamento_id,tipo_nota,status,xml_autorizado) VALUES (20,1,'Produto','Autorizada',?)", (processado,))
        self.db.commit()
        with patch.object(auto, 'enviar_xml_nfe_produto') as envio:
            self.assertEqual(auto.recuperar_pdfs(self.conectar, 1), 1)
            self.assertEqual(auto.recuperar_pdfs(self.conectar, 1), 0)
            envio.assert_not_called()
        self.assertTrue(self.db.execute('SELECT pdf_base64 FROM notas_fiscais').fetchone()[0])

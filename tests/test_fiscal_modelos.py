import copy
import json
import unittest
from unittest.mock import patch

from tests import test_fiscal_automatico
from dsystem_erp.services import fiscal_automatico as auto
from dsystem_erp.services.fiscal_modelos import criar_modelo, chave_modelo, montar_do_modelo, montar_modelo_por_itens


class ModelosTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_fiscal_automatico.AutomaticoTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def modelo_item(self, nome, *, tipo='Produto', codigo='84716053', vinculo=None):
        f = self.fixture
        dados = copy.deepcopy(f.prod_dados if tipo == 'Produto' else f.serv_dados)
        item = copy.deepcopy(f.prod_itens[0] if tipo == 'Produto' else json.loads(f.fat['itens'])[0])
        item['desc'] = nome
        if vinculo:
            item['estoque_id' if tipo == 'Produto' else 'servico_id'] = vinculo
        if tipo == 'Produto':
            item['ncm'] = codigo
            endpoint = auto.endpoint_autorizacao_nfe('MG', 'homologacao')
        else:
            dados['codigo_tributacao_nacional'] = codigo
            dados['totais_tributos'] = dict(federal=0, estadual=0, municipal=0)
            endpoint = test_fiscal_automatico.ENDPOINT_HOMOLOGACAO
        fat = dict(f.fat, itens=[item], valor_total=item['vtotal'])
        plano = dict(faturamento=fat, dados=dados, itens=[item] if tipo == 'Produto' else [], endpoint=endpoint)
        return criar_modelo(fat, dict(tipo=tipo, estado='Pronta', plano_json=json.dumps(plano, default=str)), 'gerente', por_item=True)

    def test_nova_combinacao_reconhece_nomes_e_mantem_ncm_de_cada_produto(self):
        mouse = self.modelo_item('Mouse USB', codigo='84716053')
        teclado = self.modelo_item('Teclado USB', codigo='84716052')
        itens = [dict(desc='  MOUSE USB ', tipo_item='Produto', qtd=4, vunit=50, vtotal=200),
                 dict(desc='Teclado USB', tipo_item='Produto', qtd=1, vunit=50, vtotal=50)]
        fat = dict(self.fixture.fat, itens=itens, valor_total=250)
        m = montar_modelo_por_itens(fat, 'Produto', [mouse, teclado], self.fixture.prod_dados['emitente_cnpj'])
        with patch('dsystem_erp.services.fiscal_modelos.completar_destinatario', return_value={'dados':self.fixture.prod_dados['destinatario']}):
            plano = montar_do_modelo(fat, 'Produto', m, {'cnpj':fat['cnpj']}, lambda k, default='': self.fixture.prod_dados['emitente_cnpj'] if k == 'NFSE_CNPJ' else default)
        self.assertEqual([i['ncm'] for i in plano['itens']], ['84716053', '84716052'])
        self.assertEqual([i['tributos']['base_icms'] for i in plano['itens']], [200, 50])

    def test_nao_reutiliza_aprovacao_antiga_outro_cliente_ou_emitente(self):
        modelo = self.modelo_item('Mouse')
        fat = dict(self.fixture.fat, itens=[dict(desc='Mouse', tipo_item='Produto')])
        emitente = self.fixture.prod_dados['emitente_cnpj']
        self.assertIsNone(montar_modelo_por_itens(fat, 'Produto', [dict(modelo, reutilizar_por_item=False)], emitente))
        self.assertIsNone(montar_modelo_por_itens(dict(fat, cnpj='99999999000199'), 'Produto', [modelo], emitente))
        self.assertIsNone(montar_modelo_por_itens(fat, 'Produto', [modelo], '99999999000199'))

    def test_nome_ambiguo_ou_apenas_parecido_nao_escolhe_codigo(self):
        modelos = [self.modelo_item('Mouse USB', vinculo=1), self.modelo_item('Mouse USB', vinculo=2)]
        fat = dict(self.fixture.fat, itens=[dict(desc='Mouse USB', tipo_item='Produto')])
        with self.assertRaisesRegex(ValueError, 'ambíguo'):
            montar_modelo_por_itens(fat, 'Produto', modelos, self.fixture.prod_dados['emitente_cnpj'])
        fat['itens'][0]['estoque_id'] = 2
        fat['itens'][0]['desc'] = 'Descrição livre do item vinculado'
        self.assertIsNotNone(montar_modelo_por_itens(fat, 'Produto', modelos, self.fixture.prod_dados['emitente_cnpj']))
        fat['itens'] = [dict(desc='Mouse', tipo_item='Produto')]
        with self.assertRaisesRegex(ValueError, 'falta configuração'):
            montar_modelo_por_itens(fat, 'Produto', modelos, self.fixture.prod_dados['emitente_cnpj'])

    def test_codigo_informado_e_modelos_conflitantes_bloqueiam(self):
        modelo = self.modelo_item('Mouse')
        fat = dict(self.fixture.fat, itens=[dict(desc='Mouse', tipo_item='Produto')])
        emitente = self.fixture.prod_dados['emitente_cnpj']
        for campo, valor in [('ambiente', 'producao'), ('regime_tributario', '1'), ('natureza_operacao', 'Devolução')]:
            outro = copy.deepcopy(modelo)
            outro['plano']['dados'][campo] = valor
            with self.subTest(campo=campo), self.assertRaisesRegex(ValueError, 'divergentes'):
                montar_modelo_por_itens(fat, 'Produto', [modelo, outro], emitente)
        fat['itens'][0]['ncm'] = '99999999'
        with self.assertRaisesRegex(ValueError, 'ncm difere'):
            montar_modelo_por_itens(fat, 'Produto', [modelo], emitente)

    def test_servicos_conhecidos_puxam_codigo_mas_codigos_diferentes_nao_misturam(self):
        suporte = self.modelo_item('Suporte técnico', tipo='Serviço', codigo='010701')
        remoto = self.modelo_item('Suporte remoto', tipo='Serviço', codigo='010701')
        manutencao = self.modelo_item('Manutenção', tipo='Serviço', codigo='140101')
        fat = dict(self.fixture.fat, itens=[dict(desc=' SUPORTE TECNICO ', tipo_item='Serviço'), dict(desc='Suporte remoto', tipo_item='Serviço')])
        emitente = self.fixture.serv_dados['cnpj_prestador']
        modelo = montar_modelo_por_itens(fat, 'Serviço', [suporte, remoto, manutencao], emitente)
        self.assertEqual(modelo['plano']['dados']['codigo_tributacao_nacional'], '010701')
        fat['itens'][1]['desc'] = 'Manutenção'
        with self.assertRaisesRegex(ValueError, 'separação das notas'):
            montar_modelo_por_itens(fat, 'Serviço', [suporte, remoto, manutencao], emitente)

    def test_faturar_monta_envia_servico_sem_preparacao_individual_e_nao_duplica(self):
        f = self.fixture
        f.serv_dados['totais_tributos'] = dict(federal=0, estadual=0, municipal=0)
        f.preparar('Serviço')
        registro = auto.listar_emissoes(f.conectar, 1)[0]
        modelo = criar_modelo(f.fat, registro, 'gerente')
        f.db.execute('DELETE FROM fiscal_emissoes_auto')
        f.db.execute('CREATE TABLE clientes (cnpj TEXT, telefone TEXT, email TEXT)')
        f.db.execute('INSERT INTO clientes VALUES (?,?,?)', (f.fat['cnpj'], '', ''))
        f.faturar()
        config = lambda k, default='': json.dumps(modelo) if k == modelo['chave'] else f.serv_dados['cnpj_prestador'] if k == 'NFSE_CNPJ' else default
        with patch.object(auto, 'executar_fluxo_nfse_nacional', side_effect=f.retorno_servico) as enviar:
            estados = auto.processar_emissoes(f.conectar, 1, config, f.salvar)
            servico = next(r for r in estados if r['tipo'] == 'Serviço')
            self.assertEqual(servico['estado'], 'Autorizada', servico['mensagem'])
            auto.processar_emissoes(f.conectar, 1, config, f.salvar)
            self.assertEqual(enviar.call_count, 1)

    def test_modelo_produto_atualiza_base_e_preserva_aliquota(self):
        f = self.fixture
        f.preparar('Produto')
        registro = auto.listar_emissoes(f.conectar, 1)[0]
        modelo = criar_modelo(f.fat, registro, 'gerente')
        fat = copy.deepcopy(f.fat)
        itens = json.loads(fat['itens'])
        for i in itens:
            if i['tipo_item'] == 'Produto':
                i['qtd'] *= 2
                i['vtotal'] *= 2
        fat['itens'] = itens
        config = lambda k, default='': f.prod_dados['emitente_cnpj'] if k == 'NFSE_CNPJ' else default
        destino = modelo['plano']['dados']['destinatario']
        with patch('dsystem_erp.services.fiscal_modelos.completar_destinatario', return_value={'dados':destino}):
            plano = montar_do_modelo(fat, 'Produto', modelo, {'cnpj':fat['cnpj']}, config)
        self.assertEqual(plano['itens'][0]['tributos']['base_icms'], plano['itens'][0]['vtotal'])
        self.assertEqual(plano['itens'][0]['tributos']['icms'], modelo['plano']['itens'][0]['tributos']['icms'])

    def test_cliente_e_item_diferentes_nao_reutilizam_modelo(self):
        f = self.fixture
        self.assertNotEqual(chave_modelo(f.fat, 'Serviço'), chave_modelo(dict(f.fat, cnpj='outro'), 'Serviço'))
        fat = dict(f.fat, itens=[dict(desc='Outro serviço', tipo_item='Serviço')])
        self.assertNotEqual(chave_modelo(f.fat, 'Serviço'), chave_modelo(fat, 'Serviço'))

    def test_misto_monta_as_duas_notas_sem_preparacao_individual(self):
        f = self.fixture
        f.serv_dados['totais_tributos'] = dict(federal=0, estadual=0, municipal=0)
        f.preparar('Serviço')
        f.preparar('Produto')
        modelos = [criar_modelo(f.fat, r, 'gerente') for r in auto.listar_emissoes(f.conectar, 1)]
        configs = {m['chave']: json.dumps(m) for m in modelos}
        configs['NFSE_CNPJ'] = f.serv_dados['cnpj_prestador']
        f.db.execute('DELETE FROM fiscal_emissoes_auto')
        f.db.execute('CREATE TABLE clientes (cnpj TEXT, telefone TEXT, email TEXT)')
        f.db.execute('INSERT INTO clientes VALUES (?,?,?)', (f.fat['cnpj'], '', ''))
        f.faturar()
        with patch('dsystem_erp.services.fiscal_modelos.completar_destinatario', return_value={'dados':f.prod_dados['destinatario']}), \
             patch.object(auto, 'executar_fluxo_nfse_nacional', side_effect=f.retorno_servico) as serv, \
             patch.object(auto, 'enviar_xml_nfe_produto', side_effect=f.retorno_produto) as prod:
            estados = auto.processar_emissoes(f.conectar, 1, configs.get, f.salvar)
            self.assertEqual({r['estado'] for r in estados}, {'Autorizada'}, [r['mensagem'] for r in estados])
            auto.processar_emissoes(f.conectar, 1, configs.get, f.salvar)
            self.assertEqual(serv.call_count, 1)
            self.assertEqual(prod.call_count, 1)

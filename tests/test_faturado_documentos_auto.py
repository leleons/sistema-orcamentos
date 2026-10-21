import unittest
from unittest.mock import patch
from dsystem_erp.pages import faturado_documentos as pagina


class DocumentosAutomaticosTests(unittest.TestCase):
    def setUp(self):
        self.fat = dict(id=1, orc_ref='ORC-42', cnpj='12.345.678/0001-90', status='Faturado')

    def test_agrupa_mesmo_orcamento_cliente_e_permissoes(self):
        parceiro = dict(self.fat, id=2, cnpj='12345678000190')
        registros = [self.fat, parceiro, dict(self.fat, id=3, cnpj='99999999000199'),
                     dict(self.fat, id=4, status='Cancelado'), dict(self.fat, id=5, orc_ref='OUTRO'),
                     dict(self.fat, id=6, status='Aberto')]
        self.assertEqual([r['id'] for r in pagina._grupo_orcamento(self.fat, registros)], [1, 2])
        # Lista recebida já passou pelo filtro de acesso da página: não busca fora dela.
        self.assertEqual(pagina._grupo_orcamento(self.fat, [self.fat]), [self.fat])

    def test_sem_referencia_ou_documento_nao_agrupa(self):
        for campo in ('orc_ref', 'cnpj'):
            fat = dict(self.fat, **{campo: ''})
            self.assertEqual(pagina._grupo_orcamento(fat, [fat, dict(fat, id=2)]), [fat])

    def test_pacote_fica_pendente_ate_ambas_notas_terem_pdf(self):
        import base64
        from dsystem_erp.services.pacote_faturamento import pdf_de_referencia
        from tests.test_fiscal_automatico import AutomaticoTests
        caso = AutomaticoTests()
        caso.setUp()
        self.addCleanup(caso.doCleanups)
        with patch.object(pagina, 'conectar_banco', caso.conectar, create=True):
            self.assertEqual(len(pagina._pendencias_notas([caso.fat])), 2)
            pdf = base64.b64encode(pdf_de_referencia('TESTE SIMULADO', 'Não transmitido', '')).decode()
            caso.db.execute("INSERT INTO notas_fiscais (faturamento_id,tipo_nota,status,pdf_base64) VALUES (1,'Serviço','Autorizada',?)", (pdf,))
            caso.db.execute("UPDATE notas_fiscais SET link_nota='https://www.producaorestrita.nfse.gov.br/ConsultaPublica/TESTE' WHERE tipo_nota='Serviço'")
            caso.db.execute("INSERT INTO notas_fiscais (faturamento_id,tipo_nota,status,pdf_base64) VALUES (1,'Produto','Rejeitada',?)", (pdf,))
            self.assertEqual(pagina._pendencias_notas([caso.fat]), ['#1 — Produto: Rejeitada'])
            caso.db.execute("UPDATE notas_fiscais SET status='Autorizada' WHERE tipo_nota='Produto'")
            self.assertEqual(pagina._pendencias_notas([caso.fat]), [])
            caso.db.execute("UPDATE notas_fiscais SET pdf_base64='corrompido' WHERE tipo_nota='Produto'")
            self.assertIn('PDF ainda não está disponível', pagina._pendencias_notas([caso.fat])[0])

    def test_somente_espelho_nao_exige_autorizacao(self):
        from tests.test_fiscal_automatico import AutomaticoTests
        caso = AutomaticoTests()
        caso.setUp()
        self.addCleanup(caso.doCleanups)
        with patch.object(pagina, 'conectar_banco', caso.conectar, create=True):
            self.assertEqual(pagina._pendencias_notas([dict(caso.fat, documentos_entrega='Somente espelho')]), [])

    def test_falha_de_um_pdf_nao_perde_o_outro_nem_reemite(self):
        from tests.test_fiscal_automatico import AutomaticoTests
        from dsystem_erp.services.fiscal_automatico import recuperar_pdfs
        caso = AutomaticoTests()
        caso.setUp()
        self.addCleanup(caso.doCleanups)
        for tipo in ('Serviço', 'Produto'):
            caso.db.execute("INSERT INTO notas_fiscais (faturamento_id,tipo_nota,status,xml_autorizado) VALUES (1,?,'Autorizada','xml')", (tipo,))
        caso.db.commit()
        with patch('dsystem_erp.services.danfse.conferir_xml_nacional', side_effect=ValueError('falha PDF serviço')), \
             patch('dsystem_erp.services.nfe_documento.gerar_danfe_autorizado', return_value=b'%PDF-produto'), \
             patch('dsystem_erp.services.fiscal_automatico.enviar_xml_nfe_produto') as enviar:
            with self.assertRaisesRegex(ValueError, 'PDF pendente'):
                recuperar_pdfs(caso.conectar, 1)
            enviar.assert_not_called()
        rows = {r['tipo_nota']: dict(r) for r in caso.db.execute('SELECT * FROM notas_fiscais')}
        self.assertTrue(rows['Produto']['pdf_base64'])
        self.assertEqual(rows['Serviço']['status'], 'Autorizada')

    def test_finalizacao_automatica_chama_geracao_de_pdfs(self):
        from tests.test_fiscal_automatico import AutomaticoTests
        from dsystem_erp.services import fiscal_automatico as auto
        caso = AutomaticoTests()
        caso.setUp()
        self.addCleanup(caso.doCleanups)
        caso.preparar('Serviço'); caso.preparar('Produto'); caso.faturar()
        with patch.object(auto, 'executar_fluxo_nfse_nacional', side_effect=caso.retorno_servico), \
             patch.object(auto, 'enviar_xml_nfe_produto', side_effect=caso.retorno_produto), \
             patch.object(auto, 'recuperar_pdfs', return_value=2) as pdfs:
            estados = caso.processar()
            self.assertEqual({r['estado'] for r in estados}, {'Autorizada'})
            pdfs.assert_called_once_with(caso.conectar, 1)

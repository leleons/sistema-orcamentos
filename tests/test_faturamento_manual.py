import ast
import json
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import Mock, patch
import unittest

from dsystem_erp.pages.faturamento_manual import renderizar_modo_manual, exibir_resultado_manual
from dsystem_erp.services.fiscal_automatico import desativar_emissao_automatica, iniciar_envio_manual
from tests import test_fiscal_automatico as fixtures


class Tela:
    def __init__(self, clicar=False):
        self.session_state = {}
        self.clicar = clicar
        self.mensagens = []
        self.recarregou = False
    def info(self, m): self.mensagens.append(m)
    warning = error = success = caption = info
    def button(self, *args, **kwargs): return self.clicar and not kwargs.get('disabled')
    def rerun(self): self.recarregou = True
    def expander(self, *args, **kwargs): return nullcontext()
    def code(self, *args, **kwargs): pass


class ManualTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.AutomaticoTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.f.preparar('Produto')
        self.f.faturar()

    def test_troca_preserva_planos_retorno_e_bloqueio_de_duplicidade(self):
        f = self.f
        f.db.execute("INSERT INTO notas_fiscais (id,faturamento_id,tipo_nota,status,xml_envio) VALUES (3,1,'Produto','Rejeitada','xml-rejeitado')")
        f.db.commit()
        plano = f.db.execute('SELECT plano_json FROM fiscal_emissoes_auto').fetchone()[0]
        desativar_emissao_automatica(f.conectar, 1)
        self.assertEqual(f.db.execute('SELECT emitir_automaticamente FROM faturamento').fetchone()[0], 0)
        self.assertEqual(f.db.execute('SELECT xml_envio FROM notas_fiscais').fetchone()[0], 'xml-rejeitado')
        self.assertEqual(f.db.execute('SELECT plano_json FROM fiscal_emissoes_auto').fetchone()[0], plano)
        iniciar_envio_manual(f.conectar, 1, 3, plano_impostos=json.loads(plano))
        with self.assertRaises(ValueError): iniciar_envio_manual(f.conectar, 1, 3)

    def test_troca_nao_libera_emissao_com_resultado_incerto(self):
        f = self.f
        for estado in ('Transmitindo', 'Conferir', 'Desconhecido'):
            f.db.execute('UPDATE fiscal_emissoes_auto SET estado=?', (estado,)); f.db.commit()
            with self.subTest(estado=estado), self.assertRaises(ValueError):
                desativar_emissao_automatica(f.conectar, 1)
            self.assertEqual(f.db.execute('SELECT emitir_automaticamente FROM faturamento').fetchone()[0], 1)

    def test_troca_nao_libera_nota_manual_incerta(self):
        f = self.f
        f.db.execute("INSERT INTO notas_fiscais (id,faturamento_id,tipo_nota,status) VALUES (3,1,'Produto','Conferir')"); f.db.commit()
        with self.assertRaises(ValueError): desativar_emissao_automatica(f.conectar, 1)
        self.assertEqual(f.db.execute('SELECT emitir_automaticamente FROM faturamento').fetchone()[0], 1)

    def test_tela_exige_clique_e_permissao_sem_emitir_ou_faturar(self):
        fat = dict(id=1, status='Aberto', emitir_automaticamente=1)
        for clicar, permissao, esperado in ((False, True, False), (True, False, False), (True, True, True)):
            st = Tela(clicar)
            with patch('dsystem_erp.pages.faturamento_manual.desativar_emissao_automatica') as mudar:
                renderizar_modo_manual(st, fat, self.f.conectar, permissao)
                self.assertEqual(mudar.called, esperado)
                self.assertEqual(st.recarregou, esperado)
            self.assertTrue(any('primeiro marque' in m for m in st.mensagens))

    def test_resultado_manual_persiste_e_nao_vaza_para_outro_faturamento(self):
        st = Tela()
        st.session_state['nf_resultado_manual_1_Produto'] = dict(nivel='warning', mensagem='1026: rejeitada', xml_retorno='<ret/>')
        for _ in range(2): exibir_resultado_manual(st, 1, 'Produto')
        self.assertEqual(st.mensagens, ['1026: rejeitada'] * 2)
        exibir_resultado_manual(st, 2, 'Produto')
        self.assertEqual(len(st.mensagens), 2)

    def test_clique_manual_envia_sem_preparacao_automatica_e_persiste_resultado(self):
        # Executa o ramo real do botão da página, sem carregar entrypoint/banco real.
        arvore = ast.parse((Path(__file__).resolve().parents[1] / 'dsystem_erp/pages/faturamento.py').read_text(encoding='utf-8-sig'))
        ramo = next(n for n in ast.walk(arvore) if isinstance(n, ast.If) and isinstance(n.test, ast.Call)
                    and any(k.arg == 'key' and isinstance(k.value, ast.Constant) and k.value.value == 'enviar_nfe_produto_sefaz' for k in n.test.keywords))
        st = Tela(clicar=True)
        ctx = dict(st=st, fila_col2=st, automatico_ativado=False, pendencias_xml_nfe=[], envio_confirmado=True,
            fat_nf_faturado=dict(id=1,status='Faturado'), nfe_endpoint='https://exemplo.invalid', nf_competencia_faturado=None,
            conectar_banco=Mock(), preparar_nota_fiscal_por_tipo=Mock(return_value=(3,False)), iniciar_envio_manual=Mock(),
            dados_nfe_produto={}, cadastro_produto_snapshot=[], reservar_numero_produto=Mock(return_value=44), itens_nfe_produto=[],
            gerar_xml_nfe_produto_400=Mock(return_value=b'xml'), assinar_xml_nfe_produto=Mock(return_value=b'assinado'),
            sha256_nfe_assinada=Mock(return_value='hash'), registrar_xml_manual=Mock(), nfe_cert_path='',nfe_cert_password='',nfe_timeout=30,
            enviar_xml_nfe_produto=Mock(return_value=b'<ret/>'), analisar_retorno_nfe_produto=Mock(return_value=dict(status='Rejeitada',mensagem='1026: rejeitada')),
            salvar_retorno_nota_fiscal=Mock(), registrar_falha_manual=Mock())
        exec(compile(ast.Module(body=[ramo], type_ignores=[]), '<clique-manual>', 'exec'), ctx)
        ctx['enviar_xml_nfe_produto'].assert_called_once_with('https://exemplo.invalid',b'assinado','','',timeout=30,sha256_assinado='hash')
        self.assertEqual(st.session_state['nf_resultado_manual_1_Produto']['mensagem'], '1026: rejeitada')
        ctx['iniciar_envio_manual'].side_effect = ValueError('Nota já autorizada')
        exec(compile(ast.Module(body=[ramo], type_ignores=[]), '<clique-manual>', 'exec'), ctx)
        self.assertEqual(ctx['enviar_xml_nfe_produto'].call_count, 1)
        self.assertIn('Nota já autorizada', st.session_state['nf_resultado_manual_1_Produto']['mensagem'])

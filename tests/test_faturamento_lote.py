import unittest
from unittest.mock import Mock, patch
from streamlit.testing.v1 import AppTest
from dsystem_erp.pages.faturamento_lote import processar_selecao


def app_lote():
    import streamlit as st
    from dsystem_erp.pages.faturamento_lote import renderizar_acoes_faturar
    rows = [dict(id=i,cliente=f'Cliente {i}',status='Aberto',valor_total=10,emite_nf='Sim',
                 itens=[dict(tipo_item='Serviço')]) for i in (1,2)]
    def faturar(fat, emitir_automaticamente=None):
        st.session_state.setdefault('processados', []).append((fat['id'], emitir_automaticamente))
        return dict(ok=True,mensagem='Processado no teste')
    renderizar_acoes_faturar(dict(st=st, tem_permissao=lambda p: st.session_state.get('pode',True),
        formatar_moeda_br=lambda v: f'R$ {v}', faturar_lancamento_com_integracoes=faturar), rows)


class LoteFaturamentoTests(unittest.TestCase):
    def test_lote_isola_falha_e_nao_repete_id(self):
        rows = [dict(id=1,status='Aberto'),dict(id=2,status='Aberto'),dict(id=3,status='Faturado')]
        faturar = Mock(side_effect=[RuntimeError('Estoque insuficiente'),dict(ok=True,mensagem='feito')])
        emitir = Mock(return_value=dict(ok=True,mensagem='Emitida sem refaturar'))
        resultados = processar_selecao(rows,[1,1,2,3],True,faturar,emitir)
        self.assertEqual([r['ok'] for r in resultados], [False,True,True])
        self.assertEqual(faturar.call_count,2)
        emitir.assert_called_once_with(rows[2])

    def test_recusa_cancelado_principal_e_id_fora_dos_permitidos(self):
        rows = [dict(id=1,status='Cancelado'),dict(id=2,modalidade_faturamento='Por medição')]
        faturar, emitir = Mock(), Mock()
        resultados = processar_selecao(rows,[1,2,99],True,faturar,emitir)
        self.assertFalse(any(r['ok'] for r in resultados))
        faturar.assert_not_called(); emitir.assert_not_called()

    def test_tela_seleciona_dois_so_processa_apos_confirmar(self):
        app = AppTest.from_function(app_lote, default_timeout=15).run()
        next(b for b in app.button if b.key=='fat_lote_alternar').click().run()
        self.assertEqual(len(app.exception),0)
        app.multiselect[0].set_value([1,2]).run()
        self.assertTrue(next(b for b in app.button if b.key=='fat_lote_processar').disabled)
        next(c for c in app.checkbox if c.key=='fat_lote_emitir').check().run()
        next(c for c in app.checkbox if c.key=='fat_lote_confirmar').check().run()
        next(b for b in app.button if b.key=='fat_lote_processar').click().run()
        self.assertEqual(len(app.exception),0)
        self.assertEqual(app.session_state['processados'],[(1,True),(2,True)])
        self.assertEqual(len(app.success),2)

    def test_tela_sem_permissao_bloqueia_acoes(self):
        app = AppTest.from_function(app_lote,default_timeout=15)
        app.session_state['pode'] = False
        app.run()
        self.assertEqual(len(app.exception),0)
        self.assertTrue(all(b.disabled for b in app.button))

    def test_pendencia_fiscal_aparece_como_aviso_e_sem_download(self):
        app = AppTest.from_function(app_lote, default_timeout=15)
        app.session_state['fat_lote_resultados'] = [dict(id=1, ok=True, fiscal_pronto=False, mensagem='Produto: PDF pendente')]
        app.run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.success), 0)
        self.assertIn('PDF pendente', app.warning[0].value)
        self.assertEqual(len(app.get('download_button')), 0)

    def test_resultado_pronto_exibe_download_conjunto_e_individuais(self):
        from dsystem_erp.services.pacote_faturamento import DocumentoFaturamento, pdf_de_referencia
        from dsystem_erp.pages import faturamento_lote as pagina
        docs = [DocumentoFaturamento(f'nota:{i}', f'Nota {tipo}', 'Nota fiscal',
                pdf_de_referencia('TESTE SIMULADO', tipo, ''), f'{i}.pdf') for i, tipo in enumerate(('Serviço', 'Produto'))]
        app = AppTest.from_function(app_lote, default_timeout=15)
        app.session_state['fat_lote_resultados'] = [dict(id=1, ok=True, fiscal_pronto=True, mensagem='PDFs prontos')]
        with patch.object(pagina, 'consultar_documentos_fiscais', return_value=dict(pronto=True, documentos=docs)), \
             patch.object(pagina, 'conectar_banco', lambda: None, create=True):
            app.run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(len(app.get('download_button')), 3)
            app.run()
            self.assertEqual(len(app.get('download_button')), 3)  # Não desaparecem no rerun.
            app.session_state['fat_lote_resultados'] = [dict(id=999, ok=True, fiscal_pronto=True, mensagem='Não permitido')]
            app.run()
            self.assertEqual(len(app.get('download_button')), 0)

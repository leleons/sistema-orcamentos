import io
import json
import sqlite3
import unittest
from urllib.parse import urlsplit, parse_qs
from unittest.mock import Mock, patch

from dsystem_erp.services.recepcao_kanban import (
    alvo_qr_equipamento, buscar_equipamento_qr, dados_qr_equipamento,
    encaminhar_qr_equipamento, gerar_etiqueta_equipamento, servicos_equipamento,
    validar_url_etiqueta,
    atualizar_equipamentos_os,
    configuracao_etiqueta_os,
)


class QRDinamicoTests(unittest.TestCase):
    def setUp(self):
        self.item = dict(id=5, os_id=7, numero_item="00007-A", cliente="Cliente teste",
                         equipamento="Câmera da entrada", servico="Trocar conector",
                         configuracao=json.dumps({"backup": "Sim", "chave_so": "SEGREDO"}))
        self.url = "https://erp.example.test"

    def test_url_nao_contem_dados_pessoais_nem_servico(self):
        link = dados_qr_equipamento(self.item, self.url)
        self.assertEqual(parse_qs(urlsplit(link).query), {"pagina": ["Recepção e Kanban"], "equipamento_id": ["5"]})
        self.assertNotIn("Cliente", link)
        self.assertNotIn("SEGREDO", link)

    def test_editar_nao_muda_link(self):
        antes = dados_qr_equipamento(self.item, self.url)
        self.item.update(servico="Trocar fonte", equipamento="Câmera atualizada", cliente="Outro nome")
        self.assertEqual(antes, dados_qr_equipamento(self.item, self.url))

    def test_editor_preserva_ids_e_imagens_e_rejeita_troca_de_os(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        self.addCleanup(conn.close)
        conn.executescript("""
            CREATE TABLE equipamentos_os(id INTEGER PRIMARY KEY AUTOINCREMENT, os_id INTEGER,
                numero_item TEXT, equipamento TEXT, marca TEXT, avaria TEXT, servico TEXT,
                numero_serie TEXT, configuracao TEXT, letra_equipamento TEXT, etiqueta_codigo TEXT,
                kanban_status TEXT, foto BLOB);
            INSERT INTO equipamentos_os(id,os_id,numero_item,foto,kanban_status) VALUES(5,7,'00007-A',X'0102','Em execução');
        """)
        numero = lambda os, i: f"{os:05d}-{chr(65+i)}"
        letra = lambda i: chr(65+i)
        itens = [dict(id=5, e="Câmera revisada", servico="Trocar fonte", configuracao={"backup": "Sim"})]
        atualizar_equipamentos_os(conn.cursor(), 7, itens, numero, letra)
        salvo = dict(conn.execute("SELECT * FROM equipamentos_os WHERE id=5").fetchone())
        self.assertEqual(salvo["servico"], "Trocar fonte")
        self.assertEqual(salvo["numero_item"], "00007-A")
        self.assertEqual(salvo["foto"], b"\x01\x02")
        self.assertEqual(salvo["kanban_status"], "Em execução")
        itens.append(dict(e="Outro aparelho"))
        atualizar_equipamentos_os(conn.cursor(), 7, itens, numero, letra)
        self.assertEqual(conn.execute("SELECT numero_item FROM equipamentos_os WHERE id=6").fetchone()[0], "00007-B")
        with self.assertRaises(ValueError):
            atualizar_equipamentos_os(conn.cursor(), 8, itens, numero, letra)
        with self.assertRaises(ValueError):
            atualizar_equipamentos_os(conn.cursor(), 7, [], numero, letra)

    def test_ficha_le_banco_atual_inclusive_arquivado(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        self.addCleanup(conn.close)
        conn.executescript("""
            CREATE TABLE ordens_servico(os_id INTEGER, cliente TEXT, atendente TEXT, tecnico_extra TEXT, chamado_id INTEGER);
            INSERT INTO ordens_servico VALUES(7, 'Cliente teste', '', '', NULL);
            CREATE TABLE equipamentos_os(id INTEGER, os_id INTEGER, numero_item TEXT, servico TEXT, kanban_arquivado INTEGER);
            INSERT INTO equipamentos_os VALUES(5, 7, '00007-A', 'Trocar conector', 1);
        """)
        alvo = ("id", 5)
        self.assertEqual(buscar_equipamento_qr(conn.cursor(), alvo)["servico"], "Trocar conector")
        conn.execute("UPDATE equipamentos_os SET servico='Trocar fonte' WHERE id=5")
        self.assertEqual(buscar_equipamento_qr(conn.cursor(), alvo)["servico"], "Trocar fonte")
        self.assertEqual(buscar_equipamento_qr(conn.cursor(), ("item", 7, "00007-A"))["id"], 5)
        conn.execute("DELETE FROM equipamentos_os WHERE id=5")
        self.assertIsNone(buscar_equipamento_qr(conn.cursor(), alvo))

    def test_roteamento_respeita_permissoes_e_nao_prende_navegacao(self):
        params = dict(pagina="Recepção e Kanban", equipamento_id="5")
        estado = {"pagina_atual": "Início"}
        encaminhar_qr_equipamento(estado, params, ["Início"])
        self.assertEqual(estado["pagina_atual"], "Início")
        encaminhar_qr_equipamento(estado, params, ["Recepção e Kanban"])
        self.assertEqual(estado["pagina_atual"], "Recepção e Kanban")
        estado["pagina_atual"] = "Início"
        encaminhar_qr_equipamento(estado, params, ["Recepção e Kanban"])
        self.assertEqual(estado["pagina_atual"], "Início")

    def test_parametros_legados_e_invalidos(self):
        self.assertEqual(alvo_qr_equipamento(dict(pagina="Recepção e Kanban", os="7", item="00007-A", servico="falso")), ("item", 7, "00007-A"))
        for valor in ("-1", "0", "abc", "1 OR 1=1", "9"*100):
            self.assertIsNone(alvo_qr_equipamento(dict(pagina="Recepção e Kanban", equipamento_id=valor)))

    def test_checklist_sem_expor_chaves(self):
        texto = servicos_equipamento(self.item)
        self.assertIn("Trocar conector", texto)
        self.assertIn("Fazer backup", texto)
        self.assertNotIn("SEGREDO", texto)
        for invalido in ("{", "null", "[]"):
            self.assertEqual(servicos_equipamento(dict(servico="Conferir", configuracao=invalido)), "Conferir")

    def test_url_deve_ser_acessivel_sem_credenciais(self):
        for url in ("", "localhost:8501", "http://localhost:8501", "http://127.0.0.1:8501", "https://user:pass@example.test", "javascript:alert(1)"):
            with self.assertRaises(ValueError):
                validar_url_etiqueta(url)
        self.assertEqual(validar_url_etiqueta("http://192.168.2.148:8501/"), "http://192.168.2.148:8501")

    def test_pdf_uma_pagina_tamanho_fisico_e_servico(self):
        from pypdf import PdfReader
        for largura, altura in ((100, 50), (70, 40), (150, 150)):
            pdf = PdfReader(io.BytesIO(gerar_etiqueta_equipamento(self.item, self.url, largura, altura)))
            self.assertEqual(len(pdf.pages), 1)
            self.assertAlmostEqual(float(pdf.pages[0].mediabox.width), largura * 72 / 25.4, places=3)
            self.assertAlmostEqual(float(pdf.pages[0].mediabox.height), altura * 72 / 25.4, places=3)
            self.assertIn("Fazer:", pdf.pages[0].extract_text())
        with self.assertRaises(ValueError):
            gerar_etiqueta_equipamento(self.item, self.url, 20, 10)

    def test_elgin_i8_padrao_ignora_medidas_antigas(self):
        config = configuracao_etiqueta_os(lambda chave, padrao: {"ETIQUETA_OS_LARGURA_MM": "100", "ETIQUETA_OS_ALTURA_MM": "50"}.get(chave, padrao))
        self.assertEqual(config, dict(perfil="elgin_i8", largura_mm=80.0, altura_mm=60.0, margem_mm=4.0))
        config_custom = configuracao_etiqueta_os(lambda chave, padrao: "personalizado" if chave == "ETIQUETA_OS_PERFIL" else padrao)
        self.assertEqual(config_custom["largura_mm"], 100)
        self.assertEqual(config_custom["altura_mm"], 50)

    def test_download_i8_tem_80_por_60_sem_enviar_impressao(self):
        from pypdf import PdfReader
        from dsystem_erp.pages.etiquetas_os import renderizar_etiquetas_os
        st = Mock()
        renderizar_etiquetas_os(st, [self.item], lambda k, v: v, self.url, "teste")
        st.download_button.assert_called_once()
        pdf = PdfReader(io.BytesIO(st.download_button.call_args.kwargs["data"]))
        self.assertAlmostEqual(float(pdf.pages[0].mediabox.width), 80*72/25.4, places=3)
        self.assertAlmostEqual(float(pdf.pages[0].mediabox.height), 60*72/25.4, places=3)
        self.assertIn("Elgin i8", st.download_button.call_args.args[0])
        self.assertIn("cupons", st.warning.call_args.args[0])

    def test_perfil_invalido_nao_imprime(self):
        with self.assertRaises(ValueError):
            configuracao_etiqueta_os(lambda chave, padrao: "invalido")

    def test_sem_url_avisa_e_nao_oferece_qr_estatico(self):
        from dsystem_erp.pages.etiquetas_os import renderizar_etiquetas_os
        st = Mock()
        renderizar_etiquetas_os(st, [self.item], lambda k, v: v, "", "teste")
        st.warning.assert_called_once()
        st.download_button.assert_not_called()

    def test_sem_permissao_nao_consulta_qr(self):
        from dsystem_erp.pages import recepcao_kanban as pagina
        st = Mock()
        st.stop.side_effect = RuntimeError("stop")
        banco = Mock()
        with patch.dict(pagina.__dict__, {"st": st, "tem_permissao": lambda _: False, "conectar_banco": banco}):
            with self.assertRaisesRegex(RuntimeError, "stop"):
                pagina.renderizar_recepcao_kanban({})
        banco.assert_not_called()

    def test_tela_qr_edita_e_reabre_mesmo_equipamento(self):
        from streamlit.testing.v1 import AppTest
        fonte = '''
import streamlit as st
from unittest.mock import MagicMock
from dsystem_erp.pages.recepcao_kanban import renderizar_recepcao_kanban
st.session_state['kanban_estrutura_verificada'] = True
if 'item_teste' not in st.session_state:
    st.session_state['item_teste'] = dict(id=5, os_id=7, numero_item='00007-A',
        equipamento='Câmera', cliente='Teste', servico='Trocar conector', configuracao='{}')
item = st.session_state['item_teste']
conn = MagicMock()
conn.cursor.return_value.fetchone.return_value = dict(item)
def executar(sql, valores):
    if sql.startswith('UPDATE equipamentos_os'):
        item['servico'] = valores[0]
conn.cursor.return_value.execute.side_effect = executar
ctx = dict(st=st, conectar_banco=lambda:conn, tem_permissao=lambda _:True,
           obter_query_param=lambda nome:st.query_params.get(nome, ''), agora_br=lambda:'2026-10-11')
renderizar_recepcao_kanban(ctx)
'''
        app = AppTest.from_string(fonte, default_timeout=15)
        app.query_params.update(pagina="Recepção e Kanban", equipamento_id="5")
        app.run()
        self.assertFalse(app.exception)
        self.assertIn("Trocar conector", app.text[0].value)
        app.text_area[0].set_value("Trocar fonte e testar")
        next(b for b in app.button if b.label == "Salvar instruções do equipamento").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['item_teste']['servico'], "Trocar fonte e testar")
        self.assertIn("Trocar fonte e testar", app.text[0].value)
        self.assertEqual(app.query_params['equipamento_id'], ['5'])


if __name__ == "__main__":
    unittest.main()

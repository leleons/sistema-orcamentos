import unittest

from dsystem_erp.services.recepcao_kanban import (
    alteracoes_do_quadro,
    alteracoes_do_quadro_registros,
    dados_qr_equipamento,
    gerar_etiqueta_equipamento,
    montar_quadro_equipamentos,
    montar_quadro_registros,
    proximo_status,
)


class RecepcaoKanbanTests(unittest.TestCase):
    def test_avanca_e_recua_status(self):
        self.assertEqual(proximo_status("Recebido"), "Triagem / Diagnóstico")
        self.assertEqual(proximo_status("Recebido", -1), "Recebido")

    def test_qr_contem_vinculos(self):
        texto = dados_qr_equipamento({"os_id": 7, "numero_item": "00007-A", "cliente": "ACME", "chamado_id": 3})
        self.assertIn("00007-A", texto)
        self.assertIn("CHAMADO: 3", texto)

    def test_etiqueta_pdf(self):
        pdf = gerar_etiqueta_equipamento({"os_id": 7, "numero_item": "00007-A", "cliente": "ACME", "equipamento": "Notebook"})
        self.assertTrue(pdf.startswith(b"%PDF"))

    def test_monta_quadro_e_detecta_movimentacao(self):
        equipamentos = [
            {"id": 10, "os_id": 7, "numero_item": "00007-A", "cliente": "ACME", "kanban_status": "Recebido", "kanban_ordem": 0},
            {"id": 11, "os_id": 8, "numero_item": "00008-A", "cliente": "Beta", "kanban_status": "Em execução", "kanban_ordem": 0},
        ]
        quadro, mapa = montar_quadro_equipamentos(equipamentos)
        cartao_movido = quadro[0]["items"].pop(0)
        coluna_execucao = next(coluna for coluna in quadro if coluna["header"] == "Em execução")
        coluna_execucao["items"].append(cartao_movido)

        alteracoes = alteracoes_do_quadro(quadro, equipamentos, mapa)

        movimento = next(item for item in alteracoes if item["id"] == 10)
        self.assertEqual(movimento["status_anterior"], "Recebido")
        self.assertEqual(movimento["status"], "Em execução")
        self.assertEqual(movimento["ordem"], 1)

    def test_ignora_cartao_desconhecido_sem_apagar_equipamento(self):
        equipamentos = [{"id": 10, "os_id": 7, "numero_item": "00007-A", "kanban_status": "Recebido"}]
        quadro, mapa = montar_quadro_equipamentos(equipamentos)
        quadro[0]["items"].append("Cartão externo")

        alteracoes = alteracoes_do_quadro(quadro, equipamentos, mapa)

        self.assertFalse(any(item["id"] == 0 for item in alteracoes))

    def test_quadro_unifica_os_atendimento_e_chamado(self):
        registros = [
            {"_chave": "os:10", "_origem": "O.S.", "_origem_codigo": "os", "_registro_id": 10,
             "_cliente": "ACME", "_titulo": "Notebook", "kanban_status": "Recebido", "kanban_ordem": 0},
            {"_chave": "atendimento:20", "_origem": "Atendimento", "_origem_codigo": "atendimento",
             "_registro_id": 20, "_cliente": "Beta", "_titulo": "Preventiva",
             "kanban_status": "Triagem / Diagnóstico", "kanban_ordem": 0},
            {"_chave": "chamado:30", "_origem": "Chamado", "_origem_codigo": "chamado",
             "_registro_id": 30, "_cliente": "Gama", "_titulo": "Sem internet",
             "kanban_status": "Aguardando peça", "kanban_ordem": 0},
        ]
        quadro, mapa = montar_quadro_registros(registros)
        self.assertEqual(len(mapa), 3)
        textos = "\n".join(texto for coluna in quadro for texto in coluna["items"])
        self.assertIn("O.S. #00010", textos)
        self.assertIn("Atendimento #00020", textos)
        self.assertIn("Chamado #00030", textos)

        origem = next(coluna for coluna in quadro if coluna["header"] == "Recebido")
        destino = next(coluna for coluna in quadro if coluna["header"] == "Em execução")
        destino["items"].append(origem["items"].pop())
        alteracoes = alteracoes_do_quadro_registros(quadro, registros, mapa)
        movimento = next(item for item in alteracoes if item["chave"] == "os:10")
        self.assertEqual(movimento["origem"], "os")
        self.assertEqual(movimento["status"], "Em execução")

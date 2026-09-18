import unittest
from datetime import date

from dsystem_erp.services.cobrancas_recorrentes import (
    _valor_decimal,
    criar_ou_atualizar_cobranca_contrato,
    proximo_vencimento,
    vencimentos_no_periodo,
)


class _CursorContrato:
    def __init__(self, recorrencia_existente=None):
        self.recorrencia_existente = recorrencia_existente
        self.resultado = None
        self.lastrowid = 91
        self.comandos = []

    def execute(self, sql, params=()):
        self.comandos.append((" ".join(sql.split()), params))
        if "FROM clientes" in sql:
            self.resultado = {"id": 7, "nome": "Cliente Contrato"}
        elif "FROM cobrancas_recorrentes" in sql:
            self.resultado = self.recorrencia_existente
        else:
            self.resultado = None

    def fetchone(self):
        return self.resultado


class _ConexaoContrato:
    def __init__(self, recorrencia_existente=None):
        self.cursor_teste = _CursorContrato(recorrencia_existente)

    def cursor(self):
        return self.cursor_teste


class CobrancasRecorrentesTests(unittest.TestCase):
    def test_valor_recorrente_aceita_formato_brasileiro(self):
        self.assertEqual(_valor_decimal("R$ 1.234,56"), 1234.56)

    def test_contrato_assinado_cria_uma_recorrencia_vinculada(self):
        conexao = _ConexaoContrato()
        cobranca_id, criada = criar_ou_atualizar_cobranca_contrato(conexao, {
            "id": 12, "parte_id": 7, "parte_nome": "Cliente Contrato",
            "assinado": "Sim", "gerar_recorrencia": "Sim",
            "recorrencia_valor": "1.250,00", "recorrencia_primeiro_vencimento": "10/10/2026",
            "recorrencia_fim": "10/10/2027", "recorrencia_periodicidade": "Mensal",
            "recorrencia_tipo": "Contrato de suporte", "recorrencia_pagamento": "Boleto",
        })
        self.assertTrue(criada)
        self.assertEqual(cobranca_id, 91)
        comandos = conexao.cursor_teste.comandos
        self.assertEqual(sum("INSERT INTO cobrancas_recorrentes" in sql for sql, _ in comandos), 1)
        self.assertTrue(any("UPDATE contratos SET cobranca_recorrente_id" in sql for sql, _ in comandos))

    def test_contrato_com_recorrencia_existente_atualiza_sem_duplicar(self):
        conexao = _ConexaoContrato({"id": 33})
        cobranca_id, criada = criar_ou_atualizar_cobranca_contrato(conexao, {
            "id": 12, "parte_id": 7, "parte_nome": "Cliente Contrato",
            "assinado": "Sim", "gerar_recorrencia": "Sim", "recorrencia_valor": 250,
            "recorrencia_primeiro_vencimento": "2026-10-10", "recorrencia_fim": "2027-10-10",
        })
        self.assertFalse(criada)
        self.assertEqual(cobranca_id, 33)
        comandos = conexao.cursor_teste.comandos
        self.assertEqual(sum("INSERT INTO cobrancas_recorrentes" in sql for sql, _ in comandos), 0)
        self.assertEqual(sum("UPDATE cobrancas_recorrentes" in sql for sql, _ in comandos), 1)

    def test_mensal_ajusta_fim_do_mes(self):
        self.assertEqual(proximo_vencimento(date(2026, 1, 31), "Mensal"), date(2026, 2, 28))

    def test_vencimentos_respeitam_vigencia(self):
        cobranca = {
            "data_cobranca": "10/08/2026",
            "vigencia_fim": "10/10/2026",
            "periodicidade": "Mensal",
        }
        self.assertEqual(
            vencimentos_no_periodo(cobranca, date(2026, 12, 31)),
            [date(2026, 8, 10), date(2026, 9, 10), date(2026, 10, 10)],
        )


if __name__ == "__main__":
    unittest.main()

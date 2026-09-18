import json
import unittest

from dsystem_erp.services.dados_publicos import (
    ConsultaDadosPublicosErro,
    cnpj_valido,
    consultar_cep,
    consultar_cnpj,
)
from dsystem_erp.services.usuarios import cpf_em_uso, filtrar_usuarios


class _Resposta:
    def __init__(self, dados):
        self.dados = dados

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return json.dumps(self.dados).encode("utf-8")


def _opener(dados):
    return lambda *_args, **_kwargs: _Resposta(dados)


class DadosPublicosTests(unittest.TestCase):
    def test_cnpj_mapeia_dados_para_o_cadastro(self):
        dados = consultar_cnpj(
            "12.345.678/0001-95",
            opener=_opener({
                "razao_social": "Empresa Teste Ltda", "nome_fantasia": "Empresa Teste",
                "logradouro": "Rua Um", "numero": "10", "bairro": "Centro",
                "municipio": "Sabará", "uf": "MG", "cep": "34505000",
                "ddd_telefone_1": "3133334444", "opcao_pelo_simples": True,
            }),
        )
        self.assertEqual(dados["nome"], "Empresa Teste Ltda")
        self.assertEqual(dados["cidade_estado"], "Sabará / MG")
        self.assertEqual(dados["optante_simples_nacional"], "SIM")

    def test_cep_mapeia_endereco(self):
        dados = consultar_cep(
            "34505-000",
            opener=_opener({
                "cep": "34505-000", "logradouro": "Rua Dois", "bairro": "Centro",
                "localidade": "Sabará", "uf": "MG", "ibge": "3156700",
            }),
        )
        self.assertEqual(dados["endereco"], "Rua Dois")
        self.assertEqual(dados["codigo_ibge"], "3156700")

    def test_rejeita_documentos_com_tamanho_invalido(self):
        with self.assertRaises(ConsultaDadosPublicosErro):
            consultar_cnpj("123")
        with self.assertRaises(ConsultaDadosPublicosErro):
            consultar_cep("123")

    def test_valida_digitos_verificadores_do_cnpj(self):
        self.assertTrue(cnpj_valido("12.345.678/0001-95"))
        self.assertFalse(cnpj_valido("12.345.678/9122-22"))
        with self.assertRaisesRegex(ConsultaDadosPublicosErro, "CNPJ inválido"):
            consultar_cnpj("12.345.678/9122-22")

    def test_filtro_e_unicidade_de_cpf(self):
        usuarios = [
            {"id": 1, "username": "maria", "funcionario_nome": "Maria Silva", "funcionario_cpf": "123.456.789-00"},
            {"id": 2, "username": "joao", "funcionario_nome": "João Souza", "funcionario_cpf": "987.654.321-00"},
        ]
        self.assertEqual([u["id"] for u in filtrar_usuarios(usuarios, "Maria")], [1])
        self.assertEqual([u["id"] for u in filtrar_usuarios(usuarios, "987654")], [2])
        self.assertTrue(cpf_em_uso(usuarios, "12345678900"))
        self.assertFalse(cpf_em_uso(usuarios, "12345678900", ignorar_id=1))


if __name__ == "__main__":
    unittest.main()

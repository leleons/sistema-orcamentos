"""Consultas de dados cadastrais públicos usadas nos cadastros do ERP."""

from __future__ import annotations

import json
import re
from dsystem_erp.services.simples import situacao_da_consulta
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ConsultaDadosPublicosErro(RuntimeError):
    """Erro legível para falhas de validação ou indisponibilidade das consultas."""


def somente_digitos(valor: object) -> str:
    return re.sub(r"\D", "", str(valor or ""))


def cnpj_valido(valor: object) -> bool:
    """Valida os dois dígitos verificadores de um CNPJ numérico."""
    documento = somente_digitos(valor)
    if len(documento) != 14 or documento == documento[0] * 14:
        return False

    def calcular_digito(base: str, pesos: list[int]) -> str:
        resto = sum(int(digito) * peso for digito, peso in zip(base, pesos)) % 11
        return "0" if resto < 2 else str(11 - resto)

    primeiro = calcular_digito(documento[:12], [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    segundo = calcular_digito(documento[:12] + primeiro, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    return documento[-2:] == primeiro + segundo


def _consultar_json(url: str, *, timeout: int = 10, opener=urlopen) -> dict:
    requisicao = Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "Dsystem-ERP/1.0"},
    )
    try:
        with opener(requisicao, timeout=timeout) as resposta:
            conteudo = resposta.read().decode("utf-8")
    except HTTPError as ex:
        if ex.code == 400:
            raise ConsultaDadosPublicosErro(
                "A consulta recusou o número informado. Confira o CNPJ e tente novamente."
            ) from ex
        if ex.code == 404:
            raise ConsultaDadosPublicosErro("Cadastro não encontrado.") from ex
        raise ConsultaDadosPublicosErro(f"O serviço respondeu com erro HTTP {ex.code}.") from ex
    except (URLError, TimeoutError, OSError) as ex:
        raise ConsultaDadosPublicosErro("Serviço de consulta indisponível no momento.") from ex

    try:
        dados = json.loads(conteudo)
    except (TypeError, ValueError) as ex:
        raise ConsultaDadosPublicosErro("O serviço retornou uma resposta inválida.") from ex
    if not isinstance(dados, dict):
        raise ConsultaDadosPublicosErro("O serviço retornou uma resposta inesperada.")
    return dados


def consultar_cnpj(cnpj: object, *, timeout: int = 10, opener=urlopen) -> dict:
    """Consulta uma empresa na BrasilAPI e devolve os campos usados pelo ERP."""
    documento = somente_digitos(cnpj)
    if len(documento) != 14:
        raise ConsultaDadosPublicosErro("Informe um CNPJ com 14 dígitos.")
    if not cnpj_valido(documento):
        raise ConsultaDadosPublicosErro(
            "CNPJ inválido. Confira os números, inclusive os dois últimos dígitos verificadores."
        )

    dados = _consultar_json(
        f"https://brasilapi.com.br/api/cnpj/v1/{documento}",
        timeout=timeout,
        opener=opener,
    )
    cidade = dados.get("municipio") or ""
    uf = dados.get("uf") or ""
    return {
        "cnpj": documento,
        "situacao_simples_nacional": situacao_da_consulta(dados),
        "nome": dados.get("razao_social") or "",
        "fantasia": dados.get("nome_fantasia") or "",
        "telefone": dados.get("ddd_telefone_1") or dados.get("telefone") or "",
        "telefone_secundario": dados.get("ddd_telefone_2") or "",
        "email": dados.get("email") or "",
        "endereco": dados.get("logradouro") or "",
        "numero": dados.get("numero") or "",
        "complemento": dados.get("complemento") or "",
        "bairro": dados.get("bairro") or "",
        "cidade_estado": " / ".join(parte for parte in (cidade, uf) if parte),
        "cep": somente_digitos(dados.get("cep")),
        "uf": uf,
        "pessoa": "Jurídica",
        "ramo_atividade": dados.get("cnae_fiscal_descricao") or "",
        "optante_simples_nacional": (
            "SIM" if dados.get("opcao_pelo_simples") is True
            else "NÃO" if dados.get("opcao_pelo_simples") is False
            else ""
        ),
        "situacao_cadastral": dados.get("descricao_situacao_cadastral") or "",
    }


def consultar_cep(cep: object, *, timeout: int = 10, opener=urlopen) -> dict:
    """Consulta um CEP no ViaCEP e devolve os campos de endereço do ERP."""
    codigo = somente_digitos(cep)
    if len(codigo) != 8:
        raise ConsultaDadosPublicosErro("Informe um CEP com 8 dígitos.")

    dados = _consultar_json(
        f"https://viacep.com.br/ws/{codigo}/json/",
        timeout=timeout,
        opener=opener,
    )
    if dados.get("erro"):
        raise ConsultaDadosPublicosErro("CEP não encontrado.")
    cidade = dados.get("localidade") or ""
    uf = dados.get("uf") or ""
    return {
        "cep": somente_digitos(dados.get("cep")) or codigo,
        "endereco": dados.get("logradouro") or "",
        "complemento": dados.get("complemento") or "",
        "bairro": dados.get("bairro") or "",
        "cidade_estado": " / ".join(parte for parte in (cidade, uf) if parte),
        "codigo_ibge": dados.get("ibge") or "",
        "uf": uf,
    }

"""Consultas de dados cadastrais públicos usadas nos cadastros do ERP."""

from __future__ import annotations

import json
import re
from time import sleep
from dsystem_erp.services.simples import situacao_da_consulta
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ConsultaDadosPublicosErro(RuntimeError):
    """Erro legível para falhas de validação ou indisponibilidade das consultas."""


class ConsultaDadosPublicosIndisponivel(ConsultaDadosPublicosErro):
    """Falha transitória; repetir apenas consultas GET, nunca emissões fiscais."""

    def __init__(self, mensagem, *, repetir=True):
        super().__init__(mensagem)
        self.repetir = repetir


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
        if ex.code == 429:
            raise ConsultaDadosPublicosIndisponivel(
                "O serviço atingiu o limite de consultas. Aguarde alguns minutos antes de tentar novamente. Seus dados foram preservados.",
                repetir=False,
            ) from ex
        if ex.code in (408, 500, 502, 503, 504):
            raise ConsultaDadosPublicosIndisponivel(
                "Serviço de consulta temporariamente indisponível.",
                repetir=not bool(ex.headers and ex.headers.get('Retry-After')),
            ) from ex
        raise ConsultaDadosPublicosErro(f"O serviço respondeu com erro HTTP {ex.code}.") from ex
    except (URLError, TimeoutError, OSError) as ex:
        raise ConsultaDadosPublicosIndisponivel("Serviço de consulta indisponível no momento.") from ex

    try:
        dados = json.loads(conteudo)
    except (TypeError, ValueError) as ex:
        raise ConsultaDadosPublicosErro("O serviço retornou uma resposta inválida.") from ex
    if not isinstance(dados, dict):
        raise ConsultaDadosPublicosErro("O serviço retornou uma resposta inesperada.")
    return dados


def _consultar_cnpj_ws(documento, *, timeout, opener):
    """Adapta a API pública alternativa ao formato da BrasilAPI, sem inferir regime."""
    try:
        resposta = _consultar_json(f"https://publica.cnpj.ws/cnpj/{documento}", timeout=timeout, opener=opener)
        estabelecimento = resposta.get('estabelecimento')
        if (not isinstance(estabelecimento, dict)
                or somente_digitos(estabelecimento.get('cnpj')) != documento
                or not resposta.get('razao_social')):
            raise ConsultaDadosPublicosErro('Resposta cadastral inválida da alternativa.')
        def objeto(valor):
            return valor if isinstance(valor, dict) else {}
        def opcao(valor):
            return {'Sim': True, 'Não': False}.get(valor)
        simples = objeto(resposta.get('simples'))
        dados = dict(estabelecimento)
        dados.update({
            'razao_social': resposta['razao_social'],
            'municipio': objeto(estabelecimento.get('cidade')).get('nome'),
            'uf': objeto(estabelecimento.get('estado')).get('sigla'),
            'logradouro': ' '.join(str(estabelecimento.get(k) or '') for k in ('tipo_logradouro', 'logradouro')).strip(),
            'ddd_telefone_1': ''.join(str(estabelecimento.get(k) or '') for k in ('ddd1', 'telefone1')) if estabelecimento.get('telefone1') else '',
            'ddd_telefone_2': ''.join(str(estabelecimento.get(k) or '') for k in ('ddd2', 'telefone2')) if estabelecimento.get('telefone2') else '',
            'cnae_fiscal_descricao': objeto(estabelecimento.get('atividade_principal')).get('descricao'),
            'descricao_situacao_cadastral': estabelecimento.get('situacao_cadastral'),
            'opcao_pelo_simples': opcao(simples.get('simples')),
            'opcao_pelo_mei': opcao(simples.get('mei')),
        })
        return dados
    except ConsultaDadosPublicosErro as ex:
        raise ConsultaDadosPublicosIndisponivel(
            'BrasilAPI e CNPJ.ws não conseguiram concluir a consulta. Os dados preenchidos foram preservados. '
            'Aguarde alguns minutos ou complete o cadastro manualmente.', repetir=False,
        ) from ex


def consultar_cnpj(cnpj: object, *, timeout: int = 10, opener=urlopen) -> dict:
    """Consulta BrasilAPI; em indisponibilidade tenta uma vez a CNPJ.ws."""
    documento = somente_digitos(cnpj)
    if len(documento) != 14:
        raise ConsultaDadosPublicosErro("Informe um CNPJ com 14 dígitos.")
    if not cnpj_valido(documento):
        raise ConsultaDadosPublicosErro(
            "CNPJ inválido. Confira os números, inclusive os dois últimos dígitos verificadores."
        )

    # Até dois GETs na BrasilAPI e um na alternativa. Nunca repete 429
    # no mesmo provedor nem envia documentos inválidos à alternativa.
    for tentativa in range(2):
        try:
            dados = _consultar_json(
                f"https://brasilapi.com.br/api/cnpj/v1/{documento}",
                timeout=timeout,
                opener=opener,
            )
            break
        except ConsultaDadosPublicosIndisponivel as ex:
            if not ex.repetir:
                dados = _consultar_cnpj_ws(documento, timeout=timeout, opener=opener)
                break
            if tentativa == 1:
                dados = _consultar_cnpj_ws(documento, timeout=timeout, opener=opener)
                break
            sleep(0.5)
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

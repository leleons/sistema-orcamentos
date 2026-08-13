"""Diagnostico local do certificado A1/PFX usado na NFS-e."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re

from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID, ObjectIdentifier

from dsystem_erp.utils.formatadores import somente_digitos


OID_CPF = ObjectIdentifier("2.16.76.1.3.1")
OID_CNPJ = ObjectIdentifier("2.16.76.1.3.3")


def _atributo_texto(certificado, oid) -> str:
    try:
        attrs = certificado.subject.get_attributes_for_oid(oid)
    except Exception:
        attrs = []
    return str(attrs[0].value) if attrs else ""


def _documentos_do_texto(texto: str) -> list[str]:
    return re.findall(r"\d{11,14}", somente_digitos(texto))


def inspecionar_certificado_pfx(cert_path: str, cert_password: str | None) -> dict:
    caminho = Path(cert_path or "")
    if not caminho.exists():
        raise FileNotFoundError(f"Certificado PFX nao encontrado: {caminho}")
    if not cert_password:
        raise ValueError("Senha do certificado nao informada.")

    private_key, certificate, _ = pkcs12.load_key_and_certificates(
        caminho.read_bytes(),
        str(cert_password).encode("utf-8"),
    )
    if private_key is None or certificate is None:
        raise ValueError("Nao foi possivel extrair chave e certificado do PFX.")

    subject = certificate.subject.rfc4514_string()
    issuer = certificate.issuer.rfc4514_string()
    nome = _atributo_texto(certificate, NameOID.COMMON_NAME)
    cnpj_oid = somente_digitos(_atributo_texto(certificate, OID_CNPJ))
    cpf_oid = somente_digitos(_atributo_texto(certificate, OID_CPF))

    documentos = []
    for valor in [cnpj_oid, cpf_oid, *_documentos_do_texto(subject), *_documentos_do_texto(issuer)]:
        if valor and valor not in documentos:
            documentos.append(valor)

    agora = datetime.now(certificate.not_valid_after.tzinfo)
    return {
        "arquivo": str(caminho),
        "nome": nome,
        "subject": subject,
        "issuer": issuer,
        "documentos": documentos,
        "cnpj": next((doc for doc in documentos if len(doc) == 14), ""),
        "cpf": next((doc for doc in documentos if len(doc) == 11), ""),
        "valido_de": certificate.not_valid_before.isoformat(),
        "valido_ate": certificate.not_valid_after.isoformat(),
        "vencido": certificate.not_valid_after < agora,
    }


def certificado_bate_com_cnpj(info_certificado: dict, cnpj_prestador: str) -> bool:
    cnpj_limpo = somente_digitos(cnpj_prestador)
    return bool(cnpj_limpo and cnpj_limpo in set(info_certificado.get("documentos") or []))

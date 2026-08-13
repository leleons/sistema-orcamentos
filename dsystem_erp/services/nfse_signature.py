"""Assinatura XML da NFS-e com certificado A1/PFX."""

from __future__ import annotations

import time
from pathlib import Path

from dsystem_erp.config import config_val


def assinar_xml_nfse_bh(xml_bytes: bytes | str, cert_path: str | None = None, cert_password: str | None = None) -> bytes:
    cert_path = cert_path or config_val("NFSE_CERT_PFX_PATH", "")
    cert_password = cert_password if cert_password is not None else config_val("NFSE_CERT_PASSWORD", "")
    cert_file = Path(cert_path)
    if not cert_file.exists():
        raise FileNotFoundError(f"Certificado nao encontrado em: {cert_file}")
    if not cert_password:
        raise ValueError("Senha do certificado nao configurada.")

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.serialization import pkcs12
    from lxml import etree
    from signxml import XMLSigner, methods

    class LegacyXMLSigner(XMLSigner):
        def check_deprecated_methods(self):
            return None

    pfx_data = cert_file.read_bytes()
    private_key, certificate, _ = pkcs12.load_key_and_certificates(pfx_data, cert_password.encode("utf-8"))
    if private_key is None or certificate is None:
        raise ValueError("Nao foi possivel ler chave e certificado do arquivo PFX.")

    key_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    cert_pem = certificate.public_bytes(serialization.Encoding.PEM)

    xml_data = xml_bytes if isinstance(xml_bytes, bytes) else str(xml_bytes).encode("utf-8")
    parser = etree.XMLParser(remove_blank_text=True)
    root = etree.fromstring(xml_data, parser=parser)
    ns = {"nfse": "http://www.abrasf.org.br/nfse.xsd"}
    lote = root.find(".//nfse:LoteRps", namespaces=ns)
    if lote is None:
        lote = root.find(".//LoteRps")
    if lote is None:
        raise ValueError("Tag LoteRps nao encontrada para assinatura.")
    lote_id = lote.get("Id")
    if not lote_id:
        lote_id = f"L{int(time.time())}"
        lote.set("Id", lote_id)

    signature_algorithm = config_val("NFSE_SIGNATURE_ALGORITHM", "rsa-sha1")
    digest_algorithm = config_val("NFSE_DIGEST_ALGORITHM", "sha1")
    signer_class = LegacyXMLSigner if "sha1" in f"{signature_algorithm} {digest_algorithm}".lower() else XMLSigner
    signer = signer_class(
        method=methods.detached,
        signature_algorithm=signature_algorithm,
        digest_algorithm=digest_algorithm,
        c14n_algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315",
    )
    assinatura = signer.sign(
        lote,
        key=key_pem,
        cert=cert_pem,
        reference_uri=f"#{lote_id}",
        id_attribute="Id",
    )
    root.append(assinatura)
    return etree.tostring(root, encoding="utf-8", xml_declaration=True, pretty_print=True)

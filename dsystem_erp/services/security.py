from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import struct
import time
from urllib.parse import quote


SENSITIVE_TERMS = ("senha", "password", "secret", "token", "cert", "pfx", "key")
HASH_PREFIX = "pbkdf2_sha256"
HASH_ITERATIONS = 260_000


def criar_hash_senha(senha: object, iteracoes: int = HASH_ITERATIONS) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        str(senha).encode("utf-8"),
        salt.encode("utf-8"),
        iteracoes,
    )
    return f"{HASH_PREFIX}${iteracoes}${salt}${digest.hex()}"


def senha_esta_com_hash(valor: object) -> bool:
    return isinstance(valor, str) and valor.startswith(f"{HASH_PREFIX}$")


def verificar_senha(senha_digitada: object, senha_salva: object) -> bool:
    senha_digitada = "" if senha_digitada is None else str(senha_digitada)
    senha_salva = "" if senha_salva is None else str(senha_salva)
    if senha_esta_com_hash(senha_salva):
        try:
            _, iteracoes, salt, digest_salvo = senha_salva.split("$", 3)
            digest = hashlib.pbkdf2_hmac(
                "sha256",
                senha_digitada.encode("utf-8"),
                salt.encode("utf-8"),
                int(iteracoes),
            ).hex()
            return secrets.compare_digest(digest, digest_salvo)
        except (TypeError, ValueError):
            return False
    return secrets.compare_digest(senha_digitada, senha_salva)


def gerar_secret_2fa() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def codigo_totp(
    secret: str,
    intervalo: int = 30,
    digitos: int = 6,
    momento: int | float | None = None,
) -> str:
    if not secret:
        return ""
    momento_inteiro = int(time.time() if momento is None else momento)
    contador = int(momento_inteiro // intervalo)
    padding = "=" * ((8 - len(secret) % 8) % 8)
    chave = base64.b32decode((secret + padding).upper())
    mensagem = struct.pack(">Q", contador)
    digest = hmac.new(chave, mensagem, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    codigo = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(codigo % (10**digitos)).zfill(digitos)


def verificar_totp(secret: str, codigo: object, janela: int = 1, momento: int | None = None) -> bool:
    codigo_normalizado = re.sub(r"\D", "", str(codigo or ""))
    if len(codigo_normalizado) != 6:
        return False
    agora = int(time.time() if momento is None else momento)
    return any(
        secrets.compare_digest(
            codigo_totp(secret, momento=agora + (offset * 30)),
            codigo_normalizado,
        )
        for offset in range(-janela, janela + 1)
    )


def uri_totp_cliente(usuario: object, secret: str, issuer: str = "Dsystem ERP") -> str:
    label = f"{issuer}:{usuario}"
    return (
        "otpauth://totp/"
        f"{quote(label)}?secret={secret}&issuer={quote(issuer)}&digits=6&period=30"
    )


def gerar_codigo_email_2fa() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def mascarar_segredo(valor, visiveis: int = 2) -> str:
    texto = "" if valor is None else str(valor)
    if not texto:
        return ""
    if len(texto) <= visiveis * 2:
        return "*" * len(texto)
    return f"{texto[:visiveis]}{'*' * max(4, len(texto) - (visiveis * 2))}{texto[-visiveis:]}"


def chave_parece_segredo(nome: str) -> bool:
    nome_lower = str(nome or "").lower()
    return any(term in nome_lower for term in SENSITIVE_TERMS)


def limpar_segredos_dict(dados: dict) -> dict:
    return {
        chave: mascarar_segredo(valor) if chave_parece_segredo(chave) else valor
        for chave, valor in dict(dados or {}).items()
    }

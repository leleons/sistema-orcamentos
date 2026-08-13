"""Montagem e envio de mensagens SMTP do ERP."""

from __future__ import annotations

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Callable


@dataclass(frozen=True)
class SMTPConfig:
    host: str
    port: int
    user: str
    password: str
    sender: str
    timeout: int = 20

    def validar(self) -> None:
        if not self.host or not self.user or not self.password or not self.sender:
            raise RuntimeError(
                "SMTP não configurado. Configure SMTP_HOST, SMTP_PORT, "
                "SMTP_USER, SMTP_PASSWORD e SMTP_FROM."
            )


def criar_mensagem(
    config: SMTPConfig,
    destinatario: str,
    assunto: str,
    corpo: str,
    nome_arquivo: str | None = None,
    arquivo: bytes | bytearray | memoryview | None = None,
    mime_type: str = "application/pdf",
) -> EmailMessage:
    config.validar()
    mensagem = EmailMessage()
    mensagem["From"] = config.sender
    mensagem["To"] = destinatario
    mensagem["Subject"] = assunto
    mensagem.set_content(corpo)

    if arquivo is not None:
        tipo, subtipo = (mime_type or "application/pdf").split("/", 1)
        mensagem.add_attachment(
            bytes(arquivo),
            maintype=tipo,
            subtype=subtipo,
            filename=nome_arquivo or "anexo",
        )
    return mensagem


def enviar_mensagem(
    config: SMTPConfig,
    mensagem: EmailMessage,
    smtp_factory: Callable = smtplib.SMTP,
) -> None:
    config.validar()
    with smtp_factory(config.host, config.port, timeout=config.timeout) as smtp:
        smtp.starttls()
        smtp.login(config.user, config.password)
        smtp.send_message(mensagem)


def enviar_email(config: SMTPConfig, destinatario: str, assunto: str, corpo: str) -> None:
    enviar_mensagem(config, criar_mensagem(config, destinatario, assunto, corpo))


def enviar_email_com_anexo(
    config: SMTPConfig,
    destinatario: str,
    assunto: str,
    corpo: str,
    nome_arquivo: str,
    arquivo: bytes | bytearray | memoryview,
    mime_type: str = "application/pdf",
) -> None:
    mensagem = criar_mensagem(
        config,
        destinatario,
        assunto,
        corpo,
        nome_arquivo=nome_arquivo,
        arquivo=arquivo,
        mime_type=mime_type,
    )
    enviar_mensagem(config, mensagem)

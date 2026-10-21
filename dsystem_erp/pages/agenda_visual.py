"""Cartões de agenda com conteúdo tratado como texto, nunca como HTML."""
from html import escape


def cartao_visita(visita, cor="#1a73e8"):
    def texto(campo):
        return escape(str(visita.get(campo) or "")).replace("\n", "<br>")
    return (
        '<div style="border-left:5px solid #1a73e8;border-radius:6px;'
        'padding:12px 16px;margin-bottom:8px;background:rgba(128,128,128,.12)">'
        f'<strong>{texto("cliente_nome")}</strong> — {texto("status")}'
        f'<div>{texto("data_visita")} | {texto("hora_inicio")} – {texto("hora_fim")} | {texto("tecnico")}</div>'
        f'<div>Tipo: {texto("tipo_visita")}</div><div>{texto("descricao")}</div>'
        f'<small>Visita #{texto("id")} — criado em {texto("criado_em")}</small></div>'
    )

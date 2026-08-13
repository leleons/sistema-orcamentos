"""Helpers puros do portal do cliente.

O Streamlit continua no orcamento.py, mas navegação, links e HTML pequeno ficam
aqui para reduzir duplicação e facilitar testes.
"""

from __future__ import annotations

from html import escape


MAPA_SECOES_PORTAL = {
    "inicio": "inicio",
    "chamados": "meus_chamados",
    "meus_chamados": "meus_chamados",
    "abrir_chamado": "abrir_chamado",
    "financeiro": "financeiro",
    "notas": "notas",
    "documentos": "documentos",
    "os": "os",
    "contato": "contato",
}


def normalizar_secao_portal(secao: str | None) -> str:
    secao_norm = (secao or "inicio").strip().lower()
    return MAPA_SECOES_PORTAL.get(secao_norm, secao_norm or "inicio")


def link_portal(secao: str) -> str:
    return f"?pagina=portal&secao={normalizar_secao_portal(secao)}"


def portal_card_html(secao: str, titulo: str, numero: str, descricao: str) -> str:
    secao_normalizada = normalizar_secao_portal(secao)
    return (
        f'<div class="portal-card" data-portal-section="{escape(secao_normalizada)}" data-href="{link_portal(secao_normalizada)}">'
        f"<strong>{escape(str(titulo))}</strong>"
        f'<div class="portal-number">{escape(str(numero))}</div>'
        f'<div class="portal-muted">{escape(str(descricao))}</div>'
        "</div>"
    )


def portal_mini_grid_html() -> str:
    return """
<div class="portal-section-title">Acessos rápidos</div>
<div class="portal-mini-grid">
  <div class="portal-mini"><b>Suporte</b><br><span class="portal-muted">Abra chamados com descrição, prioridade e anexos.</span></div>
  <div class="portal-mini"><b>Documentos</b><br><span class="portal-muted">Consulte propostas, contratos, notas e arquivos.</span></div>
  <div class="portal-mini"><b>Atendimento</b><br><span class="portal-muted">Acompanhe respostas e andamento dos serviços.</span></div>
</div>
"""

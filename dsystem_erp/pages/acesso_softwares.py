from __future__ import annotations

from dsystem_erp.app_context import aplicar_contexto_pagina


def renderizar_acesso_softwares(ctx: dict) -> None:
    aplicar_contexto_pagina(ctx, globals())
    st.title("Acesso Softwares")
    renderizar_pasta_dsystem()


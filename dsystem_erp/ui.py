from __future__ import annotations

from functools import wraps


BASE_CSS = """
<style>
:root {
  --ds-primary: #004b8d;
  --ds-primary-soft: #0b5aa4;
  --ds-accent: #ff4b4b;
  --ds-bg-panel: #111722;
  --ds-border: rgba(255,255,255,.14);
}
.ds-section-title {
  color: var(--ds-primary);
  font-weight: 800;
  margin: 1.2rem 0 .75rem;
}
.ds-soft-card {
  border: 1px solid var(--ds-border);
  background: var(--ds-bg-panel);
  border-radius: 8px;
  padding: 1rem;
}
</style>
"""


def injetar_css_base(st_module) -> None:
    st_module.markdown(BASE_CSS, unsafe_allow_html=True)


def configurar_campos_data_br(st_module) -> None:
    """Define DD/MM/AAAA como padrão de todos os calendários do sistema."""
    if getattr(st_module, "_dsystem_data_br_configurada", False):
        return

    date_input_original = st_module.date_input

    @wraps(date_input_original)
    def date_input_br(*args, **kwargs):
        kwargs.setdefault("format", "DD/MM/YYYY")
        return date_input_original(*args, **kwargs)

    st_module.date_input = date_input_br

    # Chamadas por colunas, como coluna.date_input, usam o DeltaGenerator.
    try:
        from streamlit.delta_generator import DeltaGenerator

        delta_original = DeltaGenerator.date_input
        if not getattr(delta_original, "_dsystem_data_br", False):
            @wraps(delta_original)
            def delta_date_input_br(self, *args, **kwargs):
                kwargs.setdefault("format", "DD/MM/YYYY")
                return delta_original(self, *args, **kwargs)

            delta_date_input_br._dsystem_data_br = True
            DeltaGenerator.date_input = delta_date_input_br
    except Exception:
        pass

    st_module._dsystem_data_br_configurada = True

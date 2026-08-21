from types import SimpleNamespace

from dsystem_erp.ui_consulta import tabela_clicavel_id


class StreamlitFalso:
    def __init__(self, celulas):
        self.celulas = celulas
        self.argumentos = None

    def dataframe(self, dados, **argumentos):
        self.argumentos = argumentos
        return SimpleNamespace(selection=SimpleNamespace(cells=self.celulas))


def test_tabela_clicavel_retorna_id_da_celula_selecionada():
    st = StreamlitFalso([(1, "Cliente")])

    selecionado = tabela_clicavel_id(
        st,
        [{"ID": 14, "Cliente": "Cliente A"}, {"ID": 15, "Cliente": "Cliente B"}],
        "orcamentos",
    )

    assert selecionado == 15
    assert st.argumentos["selection_mode"] == "single-cell"
    assert st.argumentos["on_select"] == "rerun"


def test_tabela_clicavel_sem_celula_nao_seleciona_registro():
    st = StreamlitFalso([])

    selecionado = tabela_clicavel_id(st, [{"ID": 14}], "orcamentos")

    assert selecionado is None

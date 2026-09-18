from dsystem_erp.services.estoque_importacao import (
    codigo_localizacao_valido,
    interpretar_codigo_localizacao,
    montar_codigo_localizacao,
    separar_codigo_localizacao,
)


def test_separa_as_duas_fileiras_e_a_identificacao():
    assert separar_codigo_localizacao("02.04.07") == ("02", "04", "07")


def test_preserva_o_restante_do_codigo_na_identificacao():
    assert separar_codigo_localizacao("02.04.07.03") == ("02", "04", "07.03")


def test_aceita_codigo_separado_por_barra_vertical():
    assert separar_codigo_localizacao("02 | 04 | 08") == ("02", "04", "08")


def test_rejeita_codigo_sem_as_tres_partes():
    assert separar_codigo_localizacao("02.04") == ("", "", "")
    assert not codigo_localizacao_valido("02.04")


def test_interpreta_item_novo_da_area_de_informatica():
    assert interpretar_codigo_localizacao("01.01.07") == (
        "1-01 Novo",
        "2-01 Informática",
        "07",
    )


def test_interpreta_item_usado_da_area_de_infraestrutura():
    assert interpretar_codigo_localizacao("02.04.10") == (
        "1-02 Usado",
        "2-04 Infraestrutura",
        "10",
    )


def test_rejeita_estado_ou_area_desconhecidos():
    assert not codigo_localizacao_valido("03.01.07")
    assert not codigo_localizacao_valido("01.05.07")


def test_monta_codigo_completo_com_as_tres_partes():
    assert montar_codigo_localizacao("1-01 Novo", "2-04 Infraestrutura", "10") == "01.04.10"


def test_monta_codigo_com_item_de_varias_partes():
    assert montar_codigo_localizacao("1-02 Usado", "2-02 CFTV", "07.03") == "02.02.07.03"

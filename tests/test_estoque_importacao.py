from dsystem_erp.services.estoque_importacao import (
    codigo_localizacao_valido,
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

import unittest
from unittest import mock

from dsystem_erp.services.streamlit_static import configurar_limite_arquivos_estaticos


class StreamlitStaticTest(unittest.TestCase):
    def test_configura_limite_no_modulo_que_atende_a_rota(self):
        from streamlit.web.server.starlette import starlette_routes
        from streamlit.web.server.starlette import starlette_server_config

        limite_original_rota = starlette_routes.MAX_APP_STATIC_FILE_SIZE
        limite_original_config = starlette_server_config.MAX_APP_STATIC_FILE_SIZE
        self.addCleanup(
            setattr, starlette_routes, "MAX_APP_STATIC_FILE_SIZE", limite_original_rota
        )
        self.addCleanup(
            setattr,
            starlette_server_config,
            "MAX_APP_STATIC_FILE_SIZE",
            limite_original_config,
        )

        self.assertTrue(configurar_limite_arquivos_estaticos(7 * 1024**3))
        self.assertEqual(starlette_routes.MAX_APP_STATIC_FILE_SIZE, 7 * 1024**3)
        self.assertEqual(starlette_server_config.MAX_APP_STATIC_FILE_SIZE, 7 * 1024**3)

    def test_rejeita_limite_invalido(self):
        with self.assertRaises(ValueError):
            configurar_limite_arquivos_estaticos(0)

    def test_versao_antiga_sem_starlette_nao_impede_inicializacao(self):
        with mock.patch("builtins.__import__", side_effect=ImportError):
            self.assertFalse(configurar_limite_arquivos_estaticos(1024))


if __name__ == "__main__":
    unittest.main()

"""Ajustes do servidor estático usado pela Pasta Dsystem."""

from __future__ import annotations


def configurar_limite_arquivos_estaticos(limite_bytes: int) -> bool:
    """Alinha o limite interno do Streamlit ao limite configurado da aplicação.

    O Streamlit limita ``/app/static`` a 200 MiB por padrão. A Pasta Dsystem
    armazena arquivos maiores em disco e usa essa rota para entregá-los, então
    o limite precisa ser alterado no módulo que atende a requisição.

    Retorna ``False`` se a versão instalada não usar o servidor Starlette; isso
    mantém a aplicação inicializável em versões antigas do Streamlit.
    """
    limite = int(limite_bytes)
    if limite <= 0:
        raise ValueError("O limite de arquivos estáticos deve ser positivo.")

    try:
        from streamlit.web.server.starlette import starlette_routes
        from streamlit.web.server.starlette import starlette_server_config
    except ImportError:
        return False

    # starlette_routes importa a constante por valor, portanto os dois módulos
    # devem ser atualizados. FileResponse transmite o arquivo sem lê-lo inteiro.
    starlette_server_config.MAX_APP_STATIC_FILE_SIZE = limite
    starlette_routes.MAX_APP_STATIC_FILE_SIZE = limite
    return True

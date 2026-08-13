"""Registro das telas do ERP.

A migracao das telas para arquivos separados vai ser feita por etapas. Este
registro centraliza os nomes para reduzir texto solto no arquivo principal.
"""

PAGINA_CLIENTES = "Cadastro de Clientes"
PAGINA_INFRAESTRUTURA = "Infraestrutura TI"
PAGINA_ESTOQUE = "Controle de Estoque"
PAGINA_FATURAMENTO = "Faturamento"
PAGINA_FATURADO = "Faturado"


MODULOS_PRIORITARIOS = {
    PAGINA_INFRAESTRUTURA: "modules.infraestrutura",
    PAGINA_ESTOQUE: "modules.estoque",
    PAGINA_FATURAMENTO: "modules.faturamento",
    PAGINA_FATURADO: "modules.faturamento",
}

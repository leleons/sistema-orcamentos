# Migrations do ERP Dsystem

Use esta pasta para novas alteracoes estruturais do banco.

Padrao recomendado:

```text
001_nome_da_alteracao.sql
002_outra_alteracao.sql
```

O arquivo `dsystem_erp/migrations.py` registra o que ja foi aplicado na tabela
`schema_migrations`. O `iniciar_banco()` antigo ainda existe para manter
compatibilidade, mas novas tabelas e novas colunas devem ir entrando aqui.

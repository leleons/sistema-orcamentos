# Dsystem ERP

Sistema ERP em Python e Streamlit para atendimento, ordens de serviço, estoque, compras, faturamento, financeiro, contratos e portal do cliente.

## Requisitos

- Python 3.12+
- MySQL 8+

## Configuração local

1. Crie um ambiente virtual e instale as dependências:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   ```

2. Copie `.env.example` para `.env` e substitua todos os valores de exemplo.
3. Inicie o sistema:

   ```powershell
   streamlit run orcamento.py
   ```

As tabelas e migrações são aplicadas na inicialização. Não use dados reais no repositório.

## Testes

```powershell
python scripts/verificar_repositorio_publico.py
python -m unittest discover -s tests -q
```

## Deploy

O script de deploy exige o host explicitamente:

```powershell
.\deploy.ps1 -HostName servidor.exemplo.com
```

Ou defina `DSYSTEM_DEPLOY_HOST` apenas no ambiente local. O script cria backup remoto, envia os arquivos, instala dependências, executa testes e reinicia o serviço.

## Segurança

Consulte [SECURITY.md](SECURITY.md). Não envie bancos, dumps, certificados, arquivos `.env`, backups ou credenciais ao GitHub.

# Segurança

## Relatar uma vulnerabilidade

Não publique senhas, certificados, dados de clientes ou detalhes de vulnerabilidades em uma issue pública. Use um canal privado do responsável pelo projeto.

## Segredos e dados pessoais

- Nunca versionar `.env`, `.streamlit/secrets.toml`, certificados A1/PFX, chaves privadas, bancos ou exportações SQL.
- Configurar credenciais somente por variáveis de ambiente ou `st.secrets` no servidor.
- Usar dados fictícios em testes e exemplos.
- Revogar imediatamente qualquer segredo que tenha sido incluído em um commit.
- Antes de publicar, executar os testes e revisar `git status --ignored`.

## Produção

- Usar HTTPS por meio de proxy reverso.
- Restringir SSH e MySQL por firewall.
- Manter `enableXsrfProtection = true`.
- Usar senhas exclusivas e fortes, inclusive para a conta temporária da recepção.
- Manter backups criptografados fora do repositório.

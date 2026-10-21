# Contratos: preenchimento na central e PDF

Em Contratos, abra **Gerar contrato — todos os modelos**, escolha o modelo e o
cliente/fornecedor (funcionários somente para usuários gerenciais). O cadastro
preenche nome, CPF/CNPJ, endereço e contatos. Confira os dados, representantes,
condições e demais campos na própria tela e clique em **Gerar e salvar na aba
Contratos**. Os seis modelos permitem baixar PDF e Word. A geração não altera
cadastros nem simula assinaturas. Declarações exigem escolha expressa.

Dados da própria empresa vêm das configurações DSYSTEM_NOME, NFSE_CNPJ,
DSYSTEM_ENDERECO e DSYSTEM_CIDADE_UF quando disponíveis. Em modelos com duas
partes, confira os papéis de contratante/contratada ou locatária/locadora.

## Vigência

- Suporte, CLT, estágio e tecnologia/infraestrutura: um ano calendário a partir
  da data de início. Início e término aparecem no PDF e são salvos na central.
  Em início de 29 de fevereiro, o aniversário seguinte é 28 de fevereiro.
- Locação: prazo determinado em meses ou indeterminado. As datas são calculadas
  automaticamente conforme a escolha. Não altera contratos antigos/anexados.
- Esta é a regra de preenchimento solicitada, não uma avaliação jurídica das
  cláusulas ou dos vínculos trabalhistas.

## PDFs e verificação

Os dois modelos Word são convertidos por ReportLab no próprio sistema, sem
instalar Word/LibreOffice no servidor. Conteúdo, cláusulas, ênfases e margens
preservados; fonte Vera incorporada no lugar de Aptos, com possível diferença
de paginação. Os arquivos originais permanecem inalterados.

Nos três modelos PDF, campos nativos antes ignorados estão acessíveis na tela.
A fonte ajusta-se ao espaço. Conteúdos extensos demais para uma fonte legível
aparecem integralmente em complemento, com indicação no campo correspondente.
Assinaturas e tabelas de controle sem campos nativos permanecem para registro
e assinatura posteriores; não são assinadas automaticamente pelo sistema.

Verificação local, sem banco real:

```powershell
python -m unittest tests.test_contrato_pdf tests.test_contratos_modelos tests.test_contratos_vigencia_pdf
```

## Atualização do servidor pelo usuário

O pacote atualizado inclui contratos, modelos originais e as alterações
anteriores de agenda/financeiro/taxas. Não inclui bancos, configurações,
certificados nem documentos de clientes. Faz backup do código ao aplicar.
Execute no PowerShell local; nenhum destes comandos foi executado no servidor:

```powershell
cd C:\Users\Leonel\Desktop\ProgramaPythom
python .\scripts\pacote_agenda_financeiro_taxas.py empacotar
scp .\atualizacao-agenda-financeiro-taxas.zip .\scripts\pacote_agenda_financeiro_taxas.py root@2.25.130.92:/tmp/
ssh root@2.25.130.92 "python3 /tmp/pacote_agenda_financeiro_taxas.py aplicar /tmp/atualizacao-agenda-financeiro-taxas.zip /opt/orcamento --reiniciar"
```

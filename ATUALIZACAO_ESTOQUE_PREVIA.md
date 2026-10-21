# Estoque: prévia de preço sem cadastro involuntário

No cadastro de produtos, Enter não envia mais o formulário.

1. Preencha as informações do produto e os valores de compra, deslocamento,
   impostos e lucro.
2. Clique em **Calcular / atualizar prévia** para conferir o preço, sem salvar
   um produto. Os campos e a foto permanecem preenchidos.
3. Para definir preço manual, desmarque o cálculo automático, atualize a prévia
   e preencha o valor manual.
4. Somente o botão **Salvar Produto no Estoque** cadastra o produto. Se faltar
   informação ou ocorrer erro no banco, o rascunho permanece na tela. Os campos
   são limpos apenas após gravação bem-sucedida; o QR do último produto continua
   disponível para download.

A fórmula do preço não mudou. O campo de impostos de precificação continua
sendo o percentual informado pelo usuário, não uma inferência de tributação.

## Testes locais, sem banco de produção

```powershell
python -m unittest tests.test_estoque_cadastro_formulario tests.test_precificacao_estoque tests.test_estoque_selecao
```

## Comandos para o usuário atualizar o servidor

O pacote atualizado inclui esta correção e as alterações anteriores de agenda,
financeiro, taxas e contratos. Preserva bancos, configurações e certificados;
cria backup dos arquivos substituídos. Nenhum envio foi realizado pelo agente.

```powershell
cd C:\Users\Leonel\Desktop\ProgramaPythom
python .\scripts\pacote_agenda_financeiro_taxas.py empacotar
scp .\atualizacao-agenda-financeiro-taxas.zip .\scripts\pacote_agenda_financeiro_taxas.py root@2.25.130.92:/tmp/
ssh root@2.25.130.92 "python3 /tmp/pacote_agenda_financeiro_taxas.py aplicar /tmp/atualizacao-agenda-financeiro-taxas.zip /opt/orcamento --reiniciar"
```

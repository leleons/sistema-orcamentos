# Prestadores PJ e estágio

O contrato PJ agora usa o novo arquivo Contrato_DSystem_PJ.docx enviado
pelo usuário, no modelo Prestação de Serviços PJ. As cláusulas
não foram reescritas. O preenchimento da vigência segue a regra solicitada
anteriormente: um ano a partir da data de início, com término no PDF e cadastro.

## Como preencher e gerar

1. Em Controle de Acessos, selecione a pessoa para editar o cadastro.
2. Preencha **Empresa do prestador PJ**: razão social, CNPJ e endereço da empresa.
   O CPF continua sendo o identificador da pessoa, não da empresa contratada.
3. Salve a edição. Abra **Gerar contrato do funcionário** e selecione essa pessoa.
4. Confira as partes: Dsystem contratante e empresa PJ contratada. Complete
   representante da Dsystem, valor, condições de pagamento, foro e testemunhas.
5. Clique em **Gerar e salvar na aba Contratos**. PDF e Word ficam disponíveis
para download e também na central Contratos, vinculados à pessoa selecionada.

O acesso requer perfil gerencial e permissão de editar contratos. O sistema
confere o formato do CNPJ, mas não consulta nem confirma sua situação cadastral.
Assinaturas são realizadas pelas partes posteriormente.

## Cadastro e compatibilidade

- Cadastros novos oferecem PJ e Estágio.
- O tipo antigo Contrato terceirizado também abre o modelo PJ, sem converter
  o cadastro nem apagar dados anteriores. Outros tipos legados continuam
  preservados na edição de registros existentes.
- O campo antigo PJ foi mantido como RG / identificação adicional. Um CNPJ
  com formato reconhecido nesse campo é sugerido, nunca um CPF ou texto livre.
- A inicialização do banco acrescenta três colunas TEXT em usuarios, de forma
  idempotente: funcionario_pj_razao_social, funcionario_pj_cnpj e
  funcionario_pj_endereco. Não há exclusão de contratos ou de usuários.
- Os contratos anteriores continuam intactos. O PDF novo preserva o conteúdo
  e as margens do Word, com fonte Vera incorporada no lugar de Aptos; a
  paginação pode diferir. Não exige Word/LibreOffice no servidor.

## Verificação local

```powershell
python -m unittest tests.test_funcionario_pj tests.test_contratos_modelos tests.test_contratos_vigencia_pdf
```

Os testes usam cadastros fictícios e banco simulado. Não emitem notas nem
gravam contratos de pessoas reais. A integração não representa uma avaliação
jurídica das cláusulas fornecidas.

## Comandos para aplicar no servidor pelo usuário

O pacote inclui esta alteração e as anteriores. Preserva os dados existentes
e cria backup do código substituído. Nenhum envio foi feito pelo agente.

```powershell
cd C:\Users\Leonel\Desktop\ProgramaPythom
python .\scripts\pacote_agenda_financeiro_taxas.py empacotar
scp .\atualizacao-agenda-financeiro-taxas.zip .\scripts\pacote_agenda_financeiro_taxas.py root@2.25.130.92:/tmp/
ssh root@2.25.130.92 "python3 /tmp/pacote_agenda_financeiro_taxas.py aplicar /tmp/atualizacao-agenda-financeiro-taxas.zip /opt/orcamento --reiniciar"
```

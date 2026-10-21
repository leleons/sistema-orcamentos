# Novo modelo PJ e contratos em Word

O modelo Prestação de Serviços PJ usa o arquivo Contrato_DSystem_PJ.docx
enviado pelo usuário. O original foi copiado sem mudanças para
modelos_contratos/WORD/contrato_dsystem_pj.docx. O modelo anterior Tecnologia
e Infraestrutura permanece disponível para outros contratos.

Em Controle de Acessos > Gerar contrato do funcionário, PJ e Contrato
terceirizado abrem o novo modelo. Razão social, CNPJ e endereço vêm do
cadastro da empresa PJ. Nome e CPF da pessoa são sugestões para o
representante legal, editáveis antes de gerar. CPF nunca preenche CNPJ.
Valores repetidos nas assinaturas acompanham a informação preenchida
acima. Complete os dados ausentes, remuneração, pagamento e testemunhas.
A vigência continua sendo um ano, exceto locação, conforme solicitado.

Data para assinatura: escolha Mesma data do início (padrão), Hoje ou Outra
data. A opção Hoje usa o fuso de São Paulo. Essa data aparece no fechamento
do PDF/Word sem mudar o início ou o término da vigência. A data não equivale
a uma assinatura eletrônica. Mudanças exigem gerar novamente; contratos
anteriores salvos não são alterados.

Todos os seis modelos podem ser gerados em PDF e Word (.docx). Ambos os
arquivos são salvos no mesmo registro e continuam disponíveis na central
Contratos após sair da sessão. Os modelos Word preservam as partes do
arquivo original, exceto os campos do corpo preenchidos. Modelos nativos
PDF (Suporte, Estágio e CLT legado) têm Word editável com todo o texto e
campos preenchidos; a diagramação não é idêntica ao formulário PDF.

Para contratos antigos ou anexados em PDF, clique em Preparar versão Word
deste contrato. A conversão usa o arquivo salvo, não o modelo novo, não
altera o original e não grava outro contrato. PDFs escaneados sem texto
precisam do Word original. Assinaturas digitais do PDF não são transferidas
para o Word. Downloads de funcionários continuam restritos ao perfil
gerencial. Novos cadastros continuam oferecendo apenas PJ e Estágio.

Reinicie o aplicativo local para aplicar a migração idempotente das colunas
arquivo_word (LONGBLOB) e nome_arquivo_word (TEXT) na tabela contratos.
Instale requirements.txt, que agora inclui python-docx e pdfplumber. Nada é apagado.

Verificação: testes com dados fictícios e banco simulado, conferência dos
campos, cláusulas, datas, preservação do pacote DOCX e prévias PDF. O runtime
não contém LibreOffice, então não foi possível conferir visualmente a
paginação do Word. Revise a abertura no Word antes de assinar.

## Aplicar no servidor pelo usuário

O pacote inclui também as alterações locais anteriores e cria backup do
código substituído. Não inclui bancos, certificados nem documentos de
clientes. O agente não enviou nada ao servidor.

```powershell
cd C:\Users\Leonel\Desktop\ProgramaPythom
python .\scripts\pacote_agenda_financeiro_taxas.py empacotar
scp .\atualizacao-agenda-financeiro-taxas.zip .\scripts\pacote_agenda_financeiro_taxas.py root@2.25.130.92:/tmp/
ssh root@2.25.130.92 "python3 /tmp/pacote_agenda_financeiro_taxas.py aplicar /tmp/atualizacao-agenda-financeiro-taxas.zip /opt/orcamento --reiniciar"
```

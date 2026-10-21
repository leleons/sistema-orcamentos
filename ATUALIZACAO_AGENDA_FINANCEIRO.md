# Agenda e classificação financeira — 07/10/2026

Alterações locais; ainda não publicadas no servidor.

- Calendário: compromissos clicáveis, sem limite de três por dia. O clique seleciona a visita e ajusta os filtros para abrir sua edição abaixo.
- Cartões: descrição escapada e quebras de linha seguras, sem blocos de HTML aparecendo como código.
- Abas Tipos de atendimento e Atividades rápidas não são mais interrompidas quando nenhuma visita está selecionada.
- Página inicial: Minha Agenda destacada, compromissos do usuário logado, próximos e pendentes, com botão para abrir.
- Contas a pagar/receber: categoria, centro e plano selecionados nos cadastros ativos, também na edição; valores antigos preservados.
- Recorrências: quatro classificações, com plano e conta copiados ao gerar o lançamento.
- Faturamento: quatro classificações na criação/edição, copiadas para cada parcela de contas a receber. Medições herdam a classificação do principal.
- Acesso à conta financeira continua restrito ao perfil gerencial. Não foram alterados títulos financeiros existentes.

## Publicação

Fazer backup dos arquivos atuais e do banco. Enviar os arquivos abaixo da mesma versão testada:

- `orcamento.py`
- `dsystem_erp/pages/atendimentos.py`
- `dsystem_erp/pages/agenda_visual.py` (novo)
- `dsystem_erp/pages/classificacao_financeira.py` (novo)
- `dsystem_erp/pages/financeiro.py`
- `dsystem_erp/pages/faturamento.py`
- `dsystem_erp/services/database_init.py`
- `dsystem_erp/services/faturamento_medicoes.py`
- `requirements.txt`

Instalar as dependências no ambiente virtual do servidor e reiniciar o serviço. A navegação direta para as abas requer Streamlit >= 1.58.0.
A inicialização acrescenta colunas TEXT de classificação no faturamento e plano/conta nas recorrências, sem apagar registros. Não enviar o banco local sobre o banco do servidor.

Após reiniciar, conferir calendário, clique/edição, abas auxiliares, agenda inicial com dois usuários e os seletores financeiros com perfil gerencial. Contas conciliadas continuam bloqueadas para edição.

## Comandos no PowerShell para publicar junto com as taxas

O script empacota os módulos da aplicação, dependências internas, testes, documentação e modelos originais de contratos por uma lista explícita. Não inclui banco, `.env`, certificados ou anexos de clientes. O pacote é consolidado, não uma atualização isolada da agenda.

```powershell
cd C:\Users\Leonel\Desktop\ProgramaPythom
python .\scripts\pacote_agenda_financeiro_taxas.py empacotar
scp .\atualizacao-agenda-financeiro-taxas.zip .\scripts\pacote_agenda_financeiro_taxas.py root@2.25.130.92:/tmp/
ssh root@2.25.130.92 "python3 /tmp/pacote_agenda_financeiro_taxas.py aplicar /tmp/atualizacao-agenda-financeiro-taxas.zip /opt/orcamento --reiniciar"
```

O comando de aplicação confere os arquivos por SHA-256, guarda backup do código anterior em `/opt/orcamento/backups_codigo/`, instala as dependências na `.venv` e reinicia o serviço se encontrar um único serviço deste projeto. Se não o identificar, informa que é necessário reiniciá-lo manualmente. As colunas novas do banco são acrescentadas pela inicialização do próprio ERP.

# Atualização: Inter automático e notas em produção — 23/10/2026

O pacote foi preparado localmente; nenhum comando abaixo foi executado no servidor.
Ele contém código/testes, não contém `.env`, certificados, senhas nem banco de dados.

### Se você utiliza o deploy.ps1

A versão corrigida também envia os documentos listados no pacote, inclusive este
guia. O teste do QR Code aceita o ID único retornado como texto ou lista pelo
AppTest, mantendo a verificação de que é exatamente o mesmo equipamento.
Para repetir um deploy interrompido por essas duas falhas, execute no PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\Leonel\Desktop\ProgramaPythom\deploy.ps1 -HostName 2.25.130.92
```

Não use `-SkipTests`. Esse caminho já envia o código e reinicia após os testes;
não é necessário reaplicar o ZIP em seguida. Ele não ativa os ambientes fiscais
nem instala o agendador. Para essas etapas adicionais, use os comandos específicos
das seções abaixo (a ativação fiscal é `scripts/fiscal_ativar_producao.py`).

## O que muda

- Saldo/extrato às 08:00 e 12:00 de Brasília; falhas não cancelam o horário.
- Recuperação a cada 5 minutos: consulta o Inter somente se o último horário
  estiver pendente ou se a credencial tiver invalidado o saldo salvo.
- Botão manual mantido; consultas completas evitam repetição no mesmo horário.
- NF-e de produtos passa a respeitar `NFE_AMBIENTE` salvo, em vez de sempre
  abrir em homologação. NFS-e mantém sua configuração própria.
- Ativação explícita de produção para ambas por comando administrativo atômico,
  sem emitir nota, sem alterar modelos/preparações antigas, séries ou numeração.

## 1. Enviar do PowerShell do seu computador

Use a pasta do projeto. Não é preciso liberar scripts permanentemente no Windows.

```powershell
cd C:\Users\Leonel\Desktop\ProgramaPythom
scp .\atualizacao-agenda-financeiro-taxas.zip .\scripts\pacote_agenda_financeiro_taxas.py root@2.25.130.92:/tmp/
```

Se o envio falhar, não prossiga. Estes comandos pressupõem a instalação existente
em `/opt/orcamento`, com serviço `orcamento`, como nos envios anteriores.

## 2. Aplicar, testar e ativar os ambientes de notas

Execute do mesmo PowerShell:

```powershell
ssh root@2.25.130.92 "cd /opt/orcamento && ./.venv/bin/python scripts/backup_mysql.py pre-deploy && ./.venv/bin/python /tmp/pacote_agenda_financeiro_taxas.py aplicar /tmp/atualizacao-agenda-financeiro-taxas.zip /opt/orcamento && ./.venv/bin/python -m unittest discover -s tests -q && ./.venv/bin/python scripts/fiscal_ativar_producao.py --usuario Daniel.fabio --confirmar PRODUCAO && systemctl restart orcamento && systemctl is-active orcamento"
```

O encadeamento para na primeira falha. O aplicador salva o código anterior em
`/opt/orcamento/backups_codigo`; o primeiro comando exige backup MySQL concluído.
Não use opções para ignorar testes. Se falhar após copiar os arquivos, o código
já pode estar atualizado: não interprete falha como rollback automático.

O ativador aceita o emissor NFS-e Nacional com endpoint oficial; se detectar
emissor municipal ou endpoint personalizado, para sem gravar nenhuma das três
preferências. Nesse caso, revise o destino de produção antes de continuar.
Depois, confira no site **NF-e: produção** e **NFS-e: produção**. Configuração de
ambiente não comprova autorização fiscal: certificado A1 válido no Linux,
credenciamento, tributação, série e próximo número precisam estar corretos.
Preparações/modelos antigos não são convertidos de homologação para produção.
Reprepare e confirme o ambiente de cada nota antiga antes de emitir.

## 3. Ativar a atualização automática do Inter NO servidor

### Se aparecer “Configure a base separada DSYSTEM_INTER_CONFIG_DATABASE”

O envio de código não copia o cofre do Windows. Foi preparado um comando específico
que envia somente o provisionador, sem atualizar outros módulos:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\Leonel\Desktop\ProgramaPythom\configurar_inter_servidor.ps1
```

Ele lê nome/CNPJ salvos em Configurações do Sistema → Empresa (não inventa esses
dados), valida o administrador e cria a base separada/tabelas Inter, se ausentes.
Reutiliza uma base existente quando não houver ambiguidade. Uma empresa existente
com identificação diferente bloqueia a operação. Não altera o banco financeiro
nem concede permissões de pagamentos.

O cofre gerado fica em `/etc/dsystem/inter.env` com permissão 0600, fora do projeto,
carregado pelo serviço via ajuste systemd dedicado. Uma chave existente é preservada;
dados cifrados sem chave original bloqueiam a criação de outra chave. Não apague nem
substitua esse arquivo: faça backup protegido junto à base Inter. Configurações
systemd personalizadas conflitantes interrompem o comando para revisão, sem substituição.
O script pode parar após criar parte da estrutura; corrigido o pré-requisito,
é possível repetir preservando o cofre já criado.

Depois, cadastre Client ID, Client Secret e o ZIP do certificado/chave no formulário
**Banco Inter → Configurar conta real**. Não use o HTTP público para enviar segredos.
Sem HTTPS, abra um túnel SSH no PowerShell e deixe essa janela aberta:

```powershell
ssh -N -L 18501:127.0.0.1:8501 root@2.25.130.92
```

Acesse `http://localhost:18501`, faça login e configure o Inter por esse túnel.
O comando de preparo não consulta o banco Inter e não transfere as chaves do seu PC.
Para instalar o timer depois, acrescente `--arquivo-ambiente /etc/dsystem/inter.env`
ao comando `inter_agendar_servidor.py` abaixo.

O login `Daniel.fabio`, enquanto administrador, pode consultar/configurar o Inter
sem editar o cadastro protegido do Admin Master. Outros usuários, inclusive outros
administradores, precisam de concessão explícita. Preparar, aprovar, executar e
conciliar continuam exigindo permissões próprias; nenhuma delas é concedida por
essa exceção. O vínculo à empresa é obrigatório para todos, inclusive o Master.

Primeiro confira em Banco Inter a empresa 1, o vínculo/permissões de Daniel.fabio
e as credenciais de produção do servidor. O timer não concede acesso nem liga
pagamentos. Não copie o `.env` do Windows: caminhos e cofre DPAPI são locais.

O servidor precisa ter `DSYSTEM_INTER_CONFIG_DATABASE` (base terminada em
`_inter_config`), `DSYSTEM_INTER_MASTER_KEY` (32 bytes em base64, protegida fora
do repositório) e `DSYSTEM_INTER_CERT_DIR` (diretório externo protegido), além
das configurações MySQL existentes. Preserve a chave mestra já usada no servidor;
trocar a chave impossibilita ler as credenciais já cifradas. Se ainda não houve
configuração no Linux, configure o cofre e recadastre pelo formulário do ERP as
credenciais/certificado. Nunca coloque segredos neste documento ou no terminal
compartilhado. Use HTTPS ou túnel SSH para o formulário bancário.

Após isso:

```powershell
ssh root@2.25.130.92 "cd /opt/orcamento && ./.venv/bin/python scripts/inter_agendar_servidor.py --empresa 1 --usuario Daniel.fabio --servico-erp orcamento.service --instalar"
```

O instalador identifica o usuário Linux do serviço ERP e valida acesso ao banco,
cofre e certificado nesse usuário **sem consultar a API** antes de instalar.
Se o ERP utiliza variáveis configuradas no systemd, informe também
`--arquivo-ambiente /caminho/seguro/ambiente-inter` com as mesmas configurações
necessárias, arquivo restrito `chmod 600`. O `.env` existente do projeto é lido
normalmente pelo Python; não é enviado pelo pacote.

Ao ativar o timer, ele poderá recuperar a consulta pendente. São apenas consultas
de saldo/extrato, nunca emissão de boletos, pagamentos ou baixa de títulos.

## 4. Conferir o agendador

```powershell
ssh root@2.25.130.92 "systemctl list-timers dsystem-inter-painel-1.timer --all && journalctl -u dsystem-inter-painel-1.service -n 20 --no-pager"
```

O horário exibido por `list-timers` pode estar no fuso do servidor; a agenda fiscal
do painel usa Brasília explicitamente. `ja_verificado` é normal quando a consulta
daquele horário já foi concluída. A tela lê o cache a cada 60 segundos e mostra a
data/hora da última consulta. O servidor e MySQL precisam permanecer ligados.

No Windows, reinstale a tarefa com:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\inter_agendar_painel.ps1 -Empresa 1 -Usuario Daniel.fabio
```

No Windows também é necessário manter o usuário conectado (pode bloquear a tela).
Não mantenha dois agendadores diferentes para a mesma instalação.

Referências de implementação: [timers systemd](https://www.freedesktop.org/software/systemd/man/256/systemd.timer.html)
e [documentação técnica NFS-e](https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica).

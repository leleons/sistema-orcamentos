# Banco Inter — saldo, boletos de notas e pagamentos

## Ajuste do Admin Master — 23/10/2026

O cadastro do administrador é protegido contra edição geral. Para não impedir
o acesso inicial ao Inter, `Daniel.fabio` com `is_admin` ativo recebe consulta
e configuração (`inter.view`, `inter.configurar`) pela regra de autorização.
Não é necessário editar diretamente seu cadastro nem liberar todos os admins.
O vínculo à empresa e as credenciais continuam obrigatórios, e preparar/aprovar/
executar/conciliar exigem permissões explícitas. A lista de delegação considera
também esse acesso do Master. Entradas do portal cliente nunca recebem a exceção.

## Entrega atual — 22/10/2026

Branch `codex/inter-boletos-pagamentos`, sem publicação no servidor e sem executar
transações reais durante o desenvolvimento. As seções datadas abaixo registram
o histórico: o bloqueio integral das versões anteriores foi substituído por
habilitação administrativa por empresa, mantendo saldo/extrato isolados.

- **Faturamento → documentos do faturado → Boleto Banco Inter**: prepara uma
  cobrança por parcela já existente no Contas a Receber. Exige forma Boleto,
  nota autorizada em produção, CNPJ do emitente igual ao da empresa bancária,
  destinatário e total conferidos, cadastro único do cliente e parcela aberta.
  NF-e vincula chave, número, série e parcela no campo oficial `notaFiscal`.
  NFS-e Nacional fica vinculada no ledger; não usa sua chave como chave de NF-e.
- **Banco Inter → Configuração da conta e ambientes de teste → Produção —
  boletos e pagamentos**: preparação de Pix ou boleto/conta, inclusive data
  futura, revisão, aprovação e confirmação textual de envio. O preparador não
  aprova o próprio pagamento. A autorização adicional do Internet Banking Inter,
  quando exigida pela conta, continua necessária.
- Administrador com `inter.configurar` habilita os recursos em **Configurar
  conta real → Habilitar boletos e pagamentos em produção**. Reutiliza as chaves
  protegidas, sem expor segredos, reupload ou chamada à API. Os escopos também
  precisam estar liberados pelo Inter. `DSYSTEM_INTER_PERMITIR_MOVIMENTACAO=0`
  bloqueia a instalação inteira; a configuração por empresa pode ser desativada
  mesmo com operações pendentes. Salvar configuração não envia pagamentos.
- Delegação: conceder `inter.view` e as ações desejadas (`inter.preparar`,
  `inter.aprovar`, `inter.executar`) no Gerenciador de Usuários e vincular o login
  à empresa na configuração bancária. Permissões e vínculos do preparador,
  aprovador e executor são relidos antes do envio. Não há concessão automática
  a todos os administradores ou funcionários.
- No histórico: consultar status, obter o PDF original do Inter e visualizar
  QR Code/Pix copia-e-cola quando retornados. Emissão é assíncrona: PDF e QR podem
  ficar pendentes até o processamento bancário. Consulta JSON não é comprovante.
- Idempotência local, referência estável da parcela, aprovação vinculada ao
  conteúdo/conta, trava transacional e nenhum retry de escrita. Em timeout,
  resposta sem identificador ou falha ao salvar o retorno, o envio fica bloqueado
  para revisão. Não criar outra referência para contornar um envio incerto.

Limites: pagamentos desta tela são preparados manualmente; não baixam Contas a
Pagar automaticamente. A baixa/conciliação de produção, lotes, cancelamentos e
Pix Automático continuam fora deste fluxo. A titularidade de uma chave Pix não
é consultada no DICT: nome/documento informados são para revisão humana.
Ainda é necessária homologação com o Inter; testes simulados não comprovam
aceitação, permissões bancárias ou liquidação reais.

Configuração local concluída em 22/10: recursos habilitados para a empresa
Dsystem Tecnologia e permissões `inter.preparar`, `inter.aprovar`, `inter.executar`
adicionadas somente ao administrador Daniel.fabio, preservando os demais acessos.
Nenhum outro usuário recebeu permissões. Tela verificada com a configuração local
e HTTP bloqueado: nenhuma exceção, nenhum erro e **zero operações bancárias
criadas/enviadas**. Daniel deve autorizar um segundo login para a aprovação
separada dos pagamentos que ele próprio preparar. Saldo/extrato seguem somente
leitura e o agendador nunca envia pagamentos.

Validação final desta entrega: **701 testes passaram**, incluindo 97 testes
Inter (24 novos testes do fluxo de produção, sempre com HTTP simulado).

Fontes oficiais conferidas:
[Cobrança V3](https://developers.inter.co/redocusaurus/swagger-cobranca-bolepix-yaml.yaml)
e [Banking V2](https://developers.inter.co/redocusaurus/swagger-banking-yaml.yaml).

## Atualização de 19/10/2026 — chaves reais, sem pagamentos

- OAuth2/mTLS, saldo e extrato reais validados com as credenciais fornecidas.
  O saldo e os segredos não foram impressos nos logs nem gravados no projeto.
- Certificado válido até 15/10/2027. Chaves pré-cadastradas fora do projeto, no
  cofre Windows `%LOCALAPPDATA%\DSystem\Inter`, cifradas por DPAPI do usuário.
  Isso **não substitui o vínculo da empresa e dos usuários no ERP**.
- Interface: **Banco Inter → Produção — somente consultas**. O formulário aceita
  o ZIP do Inter ou certificado/chave separados. Ambientes ficam separados tanto
  no banco quanto no contexto da cifra; credenciais reais não vão ao sandbox.
- Conta é opcional para integração vinculada a uma única conta. Se houver mais
  de uma, informe número com dígito, sem zeros iniciais, conforme
  [parâmetro oficial x-conta-corrente](https://developers.inter.co/redocusaurus/swagger-banking-yaml.yaml).
- A lista permitida de produção é verificada **antes do token e também no
  transporte HTTP**. O serviço financeiro de aprovação/envio continua restrito
  a simulação/sandbox. Não há opção de liberar pagamentos reais nesta versão.
- Por autorização do responsável, o administrador principal **Daniel.fabio**
  recebeu `inter.view` e `inter.configurar` e o vínculo com a Dsystem **apenas na
  instalação local**. Nenhuma permissão de pagamento foi concedida. A credencial
  real já está vinculada e cifrada na base local `dsystem_inter_config`.
- Para delegar: o administrador habilita **Banco Inter → Consultar banco** no
  cadastro existente do usuário. Em **Configurar chaves → Produção → Autorizar
  outros usuários**, seleciona quem poderá consultar essa empresa. Os dois
  requisitos (permissão e vínculo) são conferidos em cada consulta, inclusive
  depois de uma revogação. Delegados não ganham acesso às chaves ou pagamentos.
- Validação local: **657 testes passaram**, dos quais **54 são da integração
  Inter**. Verificada também a ausência de Client ID/Secret reais nos arquivos
  versionáveis. Nenhum pacote foi publicado no servidor.

### Correção local de 20/10/2026 — acesso ao cofre

- A tela de produção já estava habilitada; o erro informado ocorria ao abrir a
  chave mestra DPAPI. O preparador e o ERP usavam caminhos diferentes de
  `LOCALAPPDATA` devido ao redirecionamento de aplicativos empacotados do Windows.
  [Referência Microsoft sobre redirecionamento de pastas](https://learn.microsoft.com/en-us/windows/win32/api/shlobj_core/ne-shlobj_core-known_folder_flag).
- `DSYSTEM_INTER_VAULT_DIR` permite fixar o cofre em um caminho absoluto fora do
  projeto. Na instalação local, foi configurado `%USERPROFILE%\.dsystem\inter`,
  com ACL restrita ao usuário Windows. A chave mestra existente e os certificados
  foram preservados; não foi gerada uma chave substituta. Originais mantidos.
- A configuração Inter passa pelo leitor central do ERP (`.env`, ambiente e
  `st.secrets`). O `.env` local contém apenas nomes/caminhos, não Client Secret
  nem chave mestra. Reinicie o ERP se ele ainda estiver com a configuração antiga
  em memória. O cofre DPAPI continua vinculado ao mesmo usuário Windows.
- A tela abre em **Produção — somente consultas** para sessões novas e oferece
  **Acessar conta real — saldo e extrato** para sessões que ficaram em simulação.
  **Configurar conta real** abre diretamente o cadastro de produção.
- Saldo e extrato reais foram novamente validados em 20/10/2026, sem exibir
  valores ou segredos nos logs. Pagamentos continuam bloqueados; abrir a tela
  não realiza chamadas bancárias.
- Validação após a correção: **663 testes passaram**, incluindo **59 testes
  Inter** e regressão de acesso ao mesmo cofre com `LOCALAPPDATA` diferente.

### Concluir o cadastro no ERP

1. Criar uma base MySQL **separada** para configuração/auditoria, por exemplo
   `dsystem_inter_config`, e definir `DSYSTEM_INTER_CONFIG_DATABASE` com esse
   nome. Esta base não recebe os títulos financeiros nem dados reais do ERP.
2. No cadastro existente de usuários, conceder somente `inter.view` para quem
   consulta e, se necessário, `inter.configurar` para o responsável pelas chaves.
   Não conceder permissões de pagamento por causa desta configuração.
3. Provisionar a empresa e os logins explicitamente, preenchendo os valores reais:

```powershell
$env:DSYSTEM_INTER_CONFIG_DATABASE = 'dsystem_inter_config'
python -m scripts.inter_preparar_teste --confirmar-base-config dsystem_inter_config --empresa-id ID --nome "RAZAO SOCIAL" --cnpj CNPJ --usuario LOGIN_AUTORIZADO
```

4. Abrir **Configurar chaves → Produção**, selecionar a empresa correta e usar
   **Cadastrar credenciais locais protegidas nesta empresa**, confirmando o
   vínculo. No mesmo usuário Windows, chave mestra e pasta de certificados são
   carregadas do cofre local. Os arquivos não são sobrescritos silenciosamente.
5. Abrir **Produção — somente consultas** e clicar em **Consultar saldo e extrato
   reais**. A tela não consulta automaticamente ao abrir e não oferece pagamentos.

O cofre DPAPI pertence à conta Windows que o criou: **não copiar os `.dpapi` para
o servidor**. Em outro computador/Linux, configurar chave mestra e diretório
privativo conforme abaixo e enviar as credenciais pelo formulário protegido,
usando HTTPS ou túnel seguro (não HTTP público). Chaves expostas em capturas/chats
devem ser rotacionadas no Inter após a configuração, por segurança.

## O que está implementado

- Menu Financeiro → Banco Inter, com produção somente para consultas como padrão.
  Simulação local sem rede e sandbox permanecem disponíveis por seleção explícita.
- Consulta de saldo/extrato paginado; preparação de boleto com Pix, Pix de entrada,
  Pix de saída, pagamento/agendamento de boleto.
- Preparação a partir de Contas a Pagar/Receber e cadastro do cliente **na base de
  teste**, somente para títulos explicitamente associados à empresa.
- Folha como lote interno de Pix individuais; cada pagamento passa por aprovação
  de outra pessoa. A API Banking de lotes não aceita Pix: aceita boleto/DARF;
  o formulário técnico desta versão implementa lotes de boletos, não DARF.
- Boleto recorrente por contrato/competência (idempotente) e adaptadores do Pix
  Automático: recorrência, solicitação de autorização, location e cobrança.
  Cobrar requer consulta prévia indicando autorização APROVADA do devedor.
- PDF de boleto retornado pelo banco e QR Code a partir do Pix copia-e-cola
  retornado. A simulação não inventa boleto/PDF pagável.
- Histórico local, respostas cifradas, consulta de status. O JSON baixável é
  registro de consulta, **não comprovante bancário oficial**.
- Baixa/conciliation transacional por consulta autenticada de liquidação;
  repetição não baixa duas vezes. Boleto marcado manualmente como recebido,
  pagamento apenas aprovado/agendado, divergência de valor e baixa parcial não
  são automaticamente conciliados. Lotes agregados exigem conciliação individual.
- OAuth2 client credentials + mTLS, TLS verificado, sem redirects/proxy herdado,
  escopos por operação, AES-GCM com vínculo à empresa/ambiente, auditoria sem
  credenciais, confirmação textual vinculada ao conteúdo e trava de concorrência.

## Estado e limites desta entrega

As operações avançadas (folha/recorrências) usam formulário técnico JSON nesta
primeira fase. Não há agendador instalado nem webhook público. A função
`sincronizar_vinculados` executa um ciclo de polling e baixa automática somente
dos títulos previamente vinculados; pode ser chamada por um executor de teste
com usuário autorizado. Nenhuma rotina envia pagamentos sem aprovação.

Ainda é necessária homologação integrada com **credenciais sandbox**, conta,
escopos habilitados e base MySQL separada. Os testes locais não comprovam aceitação
real pelo banco. A disponibilidade de Pix Automático depende da habilitação e
elegibilidade da conta no Inter. A homologação MySQL/mTLS e o download de PDFs
reais do sandbox não foram executados. Não ativar movimentações em produção com esta entrega.

As credenciais reais foram lidas somente dos arquivos enviados pelo usuário e
guardadas no cofre externo, nunca no projeto.
No Windows, o administrador precisa restringir ACL dos arquivos à conta de
serviço; no Linux, o cadastro rejeita arquivos com acesso de grupo/outros.
Chave mestra deve permanecer fora do banco/projeto e ser guardada com segurança:
perdê-la impede decifrar operações/credenciais. Não registrar tokens/payloads
em logs externos. Os arquivos temporários da demo contêm somente dados fictícios.

## Testar sem banco ou rede

Validação local em 16/10/2026: **603 testes passaram**, incluindo **37 testes da
integração Inter** (transporte simulado, permissões, empresas, concorrência,
idempotência, liquidação, rollback, reaproveitamento de cadastros e interface
Streamlit). Os 26 métodos/caminhos do catálogo foram confrontados com as
especificações oficiais. Isso não substitui homologação bancária/MySQL.

```powershell
python -m unittest discover -s tests -p 'test_inter*.py' -v
```

No cadastro de usuários existente, conceder explicitamente os acessos necessários:
`inter.view`, `inter.preparar`, `inter.aprovar`, `inter.executar`, `inter.conciliar`,
`inter.configurar`. Administrador não recebe esses acessos automaticamente.
Clientes do portal não acessam a integração. O vínculo em `inter_acessos` também
é obrigatório em cada empresa. A demo usa uma empresa fictícia da sessão; não
permite fingir outro aprovador. A aprovação por duas pessoas é testada pela suíte
e, na homologação compartilhada, pelos dois logins reais autorizados do ERP.

## Preparar homologação (não executar no servidor de produção)

1. Configurar o conector MySQL existente para um servidor de testes. Criar uma
   base **separada**, terminada em `_inter_teste`, com as tabelas financeiras e
   cadastros do ERP preenchidos com dados fictícios. A ferramenta abaixo cria
   apenas as tabelas `inter_*`, não copia dados reais nem inicializa todo o ERP.
2. Configurar `DSYSTEM_INTER_TEST_DATABASE` com o nome dessa base. Gerar uma chave
   aleatória de 32 bytes em base64 para `DSYSTEM_INTER_MASTER_KEY` em gerenciador
   de segredos/ambiente protegido; não colar a chave em chats, commits ou logs.
3. Provisionar a empresa e os usuários, usando nomes reais de logins autorizados
   de homologação no lugar dos exemplos:

```powershell
python -m scripts.inter_preparar_teste --confirmar-base-teste dsystem_inter_teste --empresa-id 1 --nome "Empresa de homologação" --cnpj 00000000000000 --usuario preparador --usuario aprovador
```

4. Associar explicitamente os títulos fictícios à empresa em
   `inter_titulos_empresas(tabela,titulo_id,empresa_id)`. O ERP legado não possui
   escopo empresarial inequívoco em todos os títulos: não inferimos empresa pelo
   nome, cliente ou conta. Esse provisionamento é administrativo, não público.
5. Para cadastrar pelo site, configurar `DSYSTEM_INTER_CERT_DIR` com um diretório
   absoluto existente **fora do projeto**, no servidor de teste. Abrir
   **Financeiro → Banco Inter → Configurar chaves (sem conexão bancária)**.
   Selecionar a empresa, informar conta, Client ID, Client Secret e escopos, e
   anexar certificado `.crt`/`.pem` e chave `.key`/`.pem` de sandbox (PEM, até
   128 KB cada, sem senha). O sistema valida validade e correspondência do par,
   cria pasta privativa por versão (ACL da conta do serviço no Windows, 0700/0600
   no Linux) e guarda credenciais cifradas. Nunca reutiliza o nome do upload como
   caminho. O status exibe apenas o final da conta, não os segredos salvos.
   Configurar exige `inter.view`, `inter.configurar` e vínculo empresarial.
   Arquivos anteriores não são sobrescritos; rotação/limpeza de versões antigas
   deve ser administrada posteriormente. Salvar não chama o banco nem ativa nada.
   Base de teste, chave mestra e diretório seguro são pré-requisitos do servidor;
   esses segredos/configurações administrativas não são expostos no formulário.
   Definir
   `DSYSTEM_INTER_ALLOW_SANDBOX=1` somente quando autorizado a testar a rede do
   sandbox. A produção tem host fixo e adaptador exclusivo para consultas.
6. Revisar valor/destinatário/vencimento e conta, aprovar com outro login para
   débitos e executar separadamente. Consultar o resultado antes de concluir
   pagamento. `ENVIADA` não é `LIQUIDADA`.

Após timeout ou queda do processo, `INCERTA`/`ENVIO_INICIADO` bloqueia reenvio.
Consultar o banco; se faltou o identificador externo, a resolução é administrativa
após confirmação externa. Não trocar referência para contornar essa proteção.
Rotação de credenciais é bloqueada enquanto há operações não resolvidas.

## APIs oficiais verificadas em 16/10/2026

Host sandbox: `https://cdpj-sandbox.partners.uatinter.co`.
OAuth: `POST /oauth/v2/token`, conforme [OpenAPI Token](https://developers.inter.co/redocusaurus/swagger-token-yaml.yaml).

| Operações | Caminhos principais | Escopos |
|---|---|---|
| Saldo/extrato | `/banking/v2/saldo`, `/extrato/completo` sob `/banking/v2` | `extrato.read` |
| Pagamento Pix | `/banking/v2/pix`, `/pix/{codigoSolicitacao}` sob `/banking/v2` | `pagamento-pix.write/read` |
| Pagamento boleto/lotes | `/banking/v2/pagamento`, `/pagamento/lote` sob `/banking/v2` | `pagamento-boleto.write/read`, `pagamento-lote.write/read` |
| Boleto com Pix | `/cobranca/v3/cobrancas`, `/{codigoSolicitacao}`, `/{codigoSolicitacao}/pdf` | `boleto-cobranca.write/read` |
| Pix cobrança/recebidos | `/pix/v2/cob/{txid}`, `/pix/v2/pix` | `cob.write/read`, `pix.read` |
| Pix Automático | `/pix/v2/rec`, `/solicrec`, `/locrec`, `/cobr/{txid}` sob `/pix/v2` | `rec.write/read`, `solicrec.write/read`, `payloadlocationrec.write`, `cobr.write/read` |

Fontes: [Banking](https://developers.inter.co/redocusaurus/swagger-banking-yaml.yaml),
[Cobrança V3](https://developers.inter.co/redocusaurus/swagger-cobranca-bolepix-yaml.yaml),
[Pix](https://developers.inter.co/redocusaurus/swagger-api-pix-yaml.yaml),
[Pix Automático](https://developers.inter.co/redocusaurus/swagger-api-pix-automatico-yaml.yaml).
O catálogo completo de métodos/escopos está em `services/inter_api.py`.
Não se usa a cobrança boleto v2 descontinuada.

## Arquivos

`services/inter_api.py`: transporte/cifra/simulador; `repositories/inter.py`:
schema/ledger; `services/inter_financeiro.py`: aprovação/idempotência;
`services/inter_conciliacao.py`: liquidação/polling;
`services/inter_titulos.py`: títulos/cadastros existentes;
`services/inter_runtime.py`: configuração de homologação;
`pages/banco_inter.py`: interface. Menu, roteador e permissões foram ampliados sem
refatorar outros fluxos. Nenhum pacote de deploy foi gerado ou enviado.

## Painel de saldo e transações — 21/10/2026

Produção abre um painel somente de leitura com saldo disponível, entradas,
saídas e transações dos últimos 30 dias (incluindo hoje). Busca e filtros não
fazem novas requisições. **Atualizar agora** busca saldo e todas as páginas do
extrato; não é preciso escolher o número da página. A tela informa a última
consulta e a data de referência do saldo quando fornecida pelo Inter.

O cache é cifrado (AES-GCM, empresa + contexto de produção), na base isolada
`*_inter_config`, usando o mesmo cofre das credenciais. A autorização atual do
ERP e o vínculo da empresa são revalidados inclusive para ler o cache. Trocar
a credencial invalida a visualização do snapshot anterior. Respostas parciais,
paginação inconsistente ou falhas não substituem o último snapshot completo.
O limite defensivo é 25 páginas de 1.000 registros; excedê-lo mostra falha,
nunca apresenta um total parcial como completo.

### Automático às 08:00 e 12:00, horário de Brasília

No Windows, execute **na conta Windows que protegeu o cofre**:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\inter_agendar_painel.ps1 -Empresa 1 -Usuario "Daniel.fabio"
```

O script prepara apenas as tabelas `inter_*` na base isolada e registra uma
tarefa local, sem senha Windows, com execução limitada e invisível. Não chama
a API ao instalar. Exige administrador ERP com `inter.view`, `inter.configurar`
e vínculo empresarial. O fuso Windows precisa ser Brasília. O PC e o MySQL
precisam estar ligados, com o usuário Windows conectado (tela bloqueada funciona).
Não é necessário deixar o navegador ou Streamlit aberto. Um gatilho de login
recupera somente o último horário pendente do dia. A tarefa verifica pendências
a cada 5 minutos, sem consultar o Inter quando o horário já foi concluído.
Uma falha não consome o horário: há nova tentativa após pelo menos 5 minutos.
Trocar credenciais também permite recuperar o cache invalidado no mesmo horário.
Uma atualização manual bem-sucedida atende o horário corrente. Reinstale a tarefa
com o comando acima para receber o novo gatilho de recuperação.
Uma trava compartilhada evita execução simultânea por duas sessões/agendadores.

A tela verifica o **cache local** a cada 60 segundos, sem chamar a API Inter.
Se o agendador parar ou a consulta falhar, a tela avisa sobre os dados antigos.
Remover a permissão do usuário executor ou seu vínculo bloqueia novas consultas.
Para desativar a agenda sem excluir dados:

```powershell
python .\scripts\inter_atualizar_painel.py --empresa 1 --usuario "Daniel.fabio" --desativar
```

A tarefa Windows pode permanecer registrada: desativada no ERP, não acessa o banco.
Nada é instalado automaticamente no servidor remoto. No Linux, use
`scripts/inter_agendar_servidor.py` conforme `ENVIO_SERVIDOR_INTER_NOTAS.md`:
timer systemd às 08h/12h de Brasília, recuperação a cada 5 minutos e após boot.
Usar apenas **um executor** por instalação. A chave DPAPI do Windows não é
portável para Linux; configure o cofre do servidor sem substituir chaves existentes.

O SDK oficial não foi adicionado: o transporte existente já usa os endpoints
oficiais e preserva bloqueios de movimentação, mTLS e autorização por empresa.
Referências: [OpenAPI Banking](https://developers.inter.co/redocusaurus/swagger-banking-yaml.yaml),
[SDK Python oficial](https://github.com/inter-co/pj-sdk-python),
[fragmentos Streamlit](https://docs.streamlit.io/develop/api-reference/execution-flow/st.fragment),
[gatilhos Windows](https://learn.microsoft.com/en-us/powershell/module/scheduledtasks/new-scheduledtasktrigger).

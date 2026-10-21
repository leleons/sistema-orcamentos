# Emissão automática ao faturar

## Como usar

1. Em **A faturar → Histórico**, na área **Mudar status para faturado**, marque **Emitir nota automaticamente** no lançamento. Para vários, clique em **Selecionar vários lançamentos**, escolha os IDs e marque **Emitir notas automaticamente dos selecionados**.
2. Na primeira operação, confira a configuração fiscal de Serviço e/ou Produto em **Faturado → Emissão de Nota** e salve a preparação. Em **A faturar → Configurar emissão automática**, autorize a reutilização dessa configuração para o cliente e os itens. É uma configuração inicial; não precisa preparar novamente cada faturamento equivalente. O ambiente autorizado fica salvo no modelo.
3. Clique em **Faturar e emitir nota** ou confirme **Processar selecionados**. O sistema confere as duas configurações antes de dar baixa, grava financeiro/estoque, transmite cada tipo e gera seus PDFs. Sem configuração completa, o novo lançamento não é faturado. Já faturados podem ser selecionados com emissão ativada, sem repetir financeiro/estoque.
4. Quando todas as notas previstas estiverem autorizadas e os PDFs válidos estiverem salvos, aparece **Baixar notas prontas juntas**, na própria tela, além dos downloads individuais. Em **Faturado → Enviar documentos**, os documentos continuam disponíveis e podem ser reunidos com o espelho. Notas do mesmo orçamento e documento de cliente ficam agrupadas dentro dos registros permitidos ao usuário.

O envio por e-mail continua dependendo do clique do usuário; não é disparado automaticamente. No WhatsApp, o usuário anexa o PDF baixado.

## Proteções e limites

- A opção começa desativada e não atua em lançamentos configurados como somente espelho.
- NFS-e usa o fluxo DPS Nacional existente; NF-e usa o autorizador SEFAZ suportado pelo projeto (atualmente MG). O enquadramento tributário continua sujeito às validações já existentes, sem inferir NCM ou impostos apenas do cliente.
- Configuração/cadastro/certificado incompleto detectado antes do processamento impede o novo faturamento. Rejeição ou falha externa posterior não desfaz financeiro/estoque: exibe pendência, preserva autorizações existentes e não repete a baixa.
- Alteração de cliente, itens ou valores exige nova conferência. Mudanças apenas de representação numérica ou campos opcionais vazios não invalidam o plano.
- O ambiente da preparação é preservado. Mudar a configuração geral para produção não transforma automaticamente uma preparação de homologação em produção; revise-a e confirme novamente.
- A numeração é reservada no banco por emitente, ambiente e série, antes do envio. O número de produto informado na preparação é o mínimo inicial, não uma autorização para reutilizar número.
- Estados Transmitindo/Conferir e notas já autorizadas não são reenviados automaticamente. Uma interrupção pode deixar a nota nesse estado mesmo sem autorização; é necessário consultar o resultado antes de qualquer novo envio.
- Após rejeição de validação conhecida, corrija, salve novamente a preparação e use **Continuar notas preparadas**. Esse botão não repete a baixa financeira ou de estoque.
- Se somente a geração de PDF falhar, use **Gerar PDFs autorizados pendentes**, que trabalha com o XML salvo sem reemitir.
- Para passar ao modo manual, desative a emissão automática na edição. As travas de notas enviadas ou em conferência permanecem.
- A central avisa se faltar autorização ou PDF de algum tipo esperado. Enviar um pacote incompleto exige confirmação explícita.

## Atualização no servidor

Esta implementação foi alterada e testada localmente; não houve publicação no servidor nem emissão fiscal real nesta revisão.

Arquivos alterados para esta funcionalidade:

- `orcamento.py`
- `dsystem_erp/pages/faturamento.py`
- `dsystem_erp/pages/nfe_destinatario.py` (novo)
- `dsystem_erp/services/nfe_cadastro_automatico.py` (novo)
- `dsystem_erp/services/nfe_item_cadastro.py` (novo)
- `dsystem_erp/services/nfse_item_cadastro.py` (novo)
- `dsystem_erp/services/nfe_cliente.py`
- `dsystem_erp/pages/faturamento_lote.py` (novo)
- `dsystem_erp/pages/faturado_documentos.py`
- `dsystem_erp/repositories/faturamento.py`
- `dsystem_erp/services/database_init.py`
- `dsystem_erp/services/fiscal_automatico.py` (novo)
- `dsystem_erp/services/fiscal_modelos.py` (novo)
- `dsystem_erp/services/fiscal_documentos.py` (novo)
- `dsystem_erp/services/nfe_produto.py`
- `dsystem_erp/services/nfe_documento.py` (novo)
- `dsystem_erp/services/nfse_nacional.py`
- `dsystem_erp/services/faturamento_medicoes.py`
- `requirements.txt`

Essa lista pressupõe que as alterações anteriores do projeto já estejam no servidor. Como há outros arquivos locais alterados, compare a versão do servidor antes de montar uma atualização parcial. Não envie banco local, arquivos `.env`, certificados, senhas ou amostras de teste.

Antes de atualizar, faça backup do código e do banco e interrompa novas emissões. Instale as dependências na virtualenv da aplicação (inclui `BrazilFiscalReport==0.6.5`) e reinicie a aplicação. A inicialização adiciona a coluna `faturamento.emitir_automaticamente` e a tabela `fiscal_emissoes_auto`; o usuário de banco precisa ter as permissões de migração usuais. A tabela existente `nfse_sequencias` também guarda a sequência de NF-e de produto, com prefixo distinto.

## Validação

Execute `python -m unittest discover -s tests -q`.

Os testes novos usam banco SQLite isolado e retornos fiscais simulados. Cobrem separação dos tipos, repetição de cliques, falha parcial, timeout, bloqueio manual/automático, ambiente/série da numeração, documentos agrupados e recuperação de PDFs. Eles não comprovam autorização pela SEFAZ/Emissor Nacional, nem concorrência real no MySQL.

Depois da instalação, falta validar o fluxo completo em homologação com o certificado e o banco do servidor, conferir as duas autorizações e os PDFs e somente então considerar habilitar produção com dados fiscais revisados.

## Destinatário da NF-e: preenchimento automático (30/09/2026)

Ao abrir a preparação da nota de produto, os dados do cliente são reaproveitados.
Campos cadastrais ausentes podem ser consultados na BrasilAPI; o código IBGE é
obtido pelo ViaCEP somente se município e UF forem compatíveis. A consulta de IE
usa o serviço oficial CadConsultaCadastro4 de MG, com o A1 configurado e o
ambiente selecionado. Uma única inscrição ativa do CNPJ/UF confirma contribuinte
ICMS. Cadastro ausente/inativo, múltiplas inscrições, divergência ou falha de rede
não são convertidos em “não contribuinte”. CPF e outras UFs exigem confirmação
fiscal quando o cadastro não tiver essa informação.

O resultado é guardado por sessão por 30 minutos. O botão de nova consulta
preserva edições manuais e completa campos vazios. Homologação e produção têm
estados separados. Não altera o cadastro original nem emite uma nota durante
a consulta; os valores preenchidos seguem para a preparação fiscal existente.

Validação local: consulta real somente leitura em homologação para AFEB retornou
IE ativa e o ViaCEP confirmou o código IBGE de Contagem. Nenhuma NF-e foi emitida
nessa validação. Testes automatizados incluem indisponibilidade, divergências,
duplicidade de inscrições, cache e preservação de edição. A atualização continua
local, sem instalação no servidor.

Os itens de produto buscam NCM nas entradas vinculadas ao ID do estoque. Sem ID,
somente uma correspondência exata e única de nome permite buscar essas entradas.
NCMs divergentes ficam pendentes. A busca por palavras no catálogo apresenta
sugestões que exigem escolha; não atribui um NCM automaticamente pela semelhança.
CFOP e tributos da compra não são copiados para a venda. Produtos sem classificação
e operações sem enquadramento tributário continuam exigindo conferência.

## Emissão diretamente em A faturar

Em A faturar → Configurar emissão automática para os próximos faturamentos,
carregue uma referência conferida/autorizada e autorize sua reutilização. A
configuração fica no banco, sem alteração de esquema. Ela é limitada ao mesmo
CPF/CNPJ, tipo fiscal e conjunto de itens, com ambiente e emitente conferidos.
É uma configuração inicial; não se copia automaticamente qualquer nota antiga.

Depois, use **Emitir nota automaticamente → Faturar e emitir nota**. O fluxo
monta a preparação dos novos lançamentos equivalentes, atualiza valores,
quantidades, descrição, competência e bases integrais, reserva numeração e
transmite. Serviço e produto são separados, com documentos agrupados no
faturamento. Não precisa preparar cada nota individualmente. Uma operação nova
ou sem enquadramento autorizado é bloqueada antes de faturar, com o motivo informado.

O modelo não reaproveita bases reduzidas ou totais tributários fixos e bloqueia
mudança de emitente, UF/situação de ICMS do destinatário e cadastros duplicados.
Notas rejeitadas, autorizadas ou de resultado incerto não são automaticamente
recriadas pelo modelo. Produção só é utilizada quando autorizada no modelo;
esta revisão foi testada com respostas simuladas, sem emissão nem implantação.

## Correção da assinatura e finalização dos PDFs (04/10/2026)

O transporte SOAP usa namespace padrão, sem acrescentar prefixos ancestrais à
NF-e. A assinatura e o digest são verificados no envelope final antes do envio,
além da verificação após assinar. Isso corrige a alteração de contexto reproduzida
localmente para a rejeição 297. Referência técnica: [Canonical XML 1.0, W3C](https://www.w3.org/TR/2001/REC-xml-c14n-20010315).

A autorização do lote (`104`) não equivale à autorização da nota: o sistema
considera o protocolo individual. PDFs inválidos/ausentes são recuperados do XML
autorizado, sem novo envio. Uma assinatura inválida é bloqueada localmente.

O teste integrado `tests/test_faturar_ate_pdfs.py` usa banco isolado, certificado
temporário e respostas fiscais simuladas: parte do clique de faturar, reutiliza
os modelos, verifica o SOAP assinado, persiste as duas autorizações, gera os PDFs
DANFSe/DANFE com os geradores reais e reúne as páginas. Confere também que novo
clique não duplica financeiro, estoque ou transmissão. Não é homologação real.

A instalação no servidor e a confirmação de autorização real continuam sendo
etapas separadas. Uma rejeição antiga não se torna autorizada apenas ao atualizar
o código; não altere seu status manualmente. Corrija/prepare e solicite novo envio
somente após conferir o retorno definitivo da tentativa anterior.

## Reconhecimento por produto/serviço (05/10/2026)

Na preparação de produto, o NCM explícito válido tem prioridade. Sem ele, busca
as entradas do produto vinculado (ou identificado por nome único no estoque).
Sem NCM nas entradas, busca um único nome exato no cadastro fiscal de produtos.
Conflitos, cadastros duplicados, códigos inválidos e vínculos inexistentes não
são resolvidos por aproximação. A busca por palavras continua sendo sugestão,
nunca autorização automática.

Na preparação de serviço, um vínculo de cadastro ou nome exato seleciona o
código nacional salvo. Acentos, maiúsculas e espaços não fazem diferença.
Serviços distintos na mesma nota não recebem automaticamente o código do
primeiro; o enquadramento deve ser conferido. O desdobramento municipal continua
limitado à configuração do serviço, município e ambiente. Uma escolha manual
na tela é preservada enquanto os itens não mudarem.

Para usar o reconhecimento no clique **A faturar**, na configuração inicial
marque também **Autorizar cada item individualmente** e salve a referência.
Os próximos faturamentos podem conter novas combinações de itens já conhecidos,
sem informar os códigos novamente. A autorização permanece restrita ao mesmo
cliente e emitente. Ambiente, operação e configurações de documento precisam
ser compatíveis; NCM, CFOP e enquadramento específicos de cada produto são
reaproveitados de sua própria referência. Bases integrais acompanham o novo
valor. Não copia impostos da compra nem adivinha alíquotas pelo nome.

Referências antigas não são ampliadas silenciosamente para uso individual:
é necessário autorizar essa opção uma vez. Item desconhecido, nome ambíguo,
código informado divergente ou regras conflitantes impedem o automático antes
da baixa. Serviços com códigos/enquadramentos distintos exigem separação ou
conferência; o sistema não os mistura em uma única NFS-e.

Sem migração nova de banco: a autorização por item usa os modelos já armazenados
em `configuracoes_sistema`. Testes com banco isolado exercitam nome/vínculo,
ambiguidade, ambientes conflitantes, nova combinação sem códigos digitados,
XML assinado e os dois PDFs finais, sem transmissão fiscal real.

## Integridade do transporte NF-e (06/10/2026)

O envio manual e o automático capturam o SHA-256 da NFe assinada e conferem o
mesmo recorte antes do lote e no corpo HTTP. O SOAP é montado concatenando bytes,
sem reserializar a nota. A assinatura é validada no contexto final para detectar
também alterações de namespaces ancestrais, que o hash bruto sozinho não detecta.
As etapas ficam no log técnico sem expor XML ou credenciais.

Diagnóstico, comparação dos três hashes, funções alteradas e testes em
[DIAGNOSTICO_NFE_297.md](DIAGNOSTICO_NFE_297.md). Atualizar em conjunto
`services/nfe_produto.py`, `services/fiscal_automatico.py` e `pages/faturamento.py`.
Não houve implantação nem transmissão real nesta revisão.

### Complemento: causa confirmada após nova rejeição 297

Os hashes da tentativa real permaneceram iguais. O erro foi localizado no
cálculo C14N de subconjuntos pelo libxml2: ele introduzia `xmlns=""` espúrios
no SignedInfo. O assinador e o validador local repetiam o mesmo defeito.

A revisão final de `services/nfe_produto.py` canonicaliza uma cópia com o
contexto herdado materializado, sem alterar os bytes de transporte. É necessário
carregar essa revisão no processo do aplicativo e gerar nova assinatura;
a assinatura já rejeitada não é consertada retroativamente.

465 testes aprovados, incluindo validação independente .NET do XML e SOAP
com certificado de teste. A cópia dos dados da nota rejeitada passou nesse
validador após nova assinatura local. Nenhuma nota foi reenviada ou modificada
no banco; autorização SEFAZ continua dependendo de uma nova tentativa válida.

## Envio manual e rejeição IBS 1026 — 06/10/2026

A leitura do banco confirmou o faturamento 37 já Faturado, com emissão automática
ativada e nota de produto rejeitada por 1026. O XML continha IBS estadual 2%,
municipal 2% e CBS 2%, enquadramento integral 000/000001, emissão em 2026.
O faturamento 36 ainda estava Aberto. O manual exige lançamento Faturado e modo
automático desligado: assinar/salvar na fila não substitui essas etapas.

Alterações locais:

- `pages/faturamento_manual.py`: orientação de modo/estado e botão **Usar emissão
  manual neste faturamento**, restrito à permissão de edição. Resultados de envio
  de produto permanecem na sessão após outros cliques, separados por faturamento.
- `services/fiscal_automatico.py`: `desativar_emissao_automatica` altera somente a
  opção de modo, sob a mesma trava do faturamento; não apaga planos, retornos ou
  notas. Estados Transmitindo/Conferir/desconhecidos impedem a mudança. Autorização
  já existente continua impedindo novo envio da mesma nota.
- `pages/faturamento.py`: mostra por que o botão manual está indisponível; usa o
  controle acima, preserva mensagens e elimina referência indevida a variáveis
  do envio de serviço ao tratar uma falha de assinatura da prévia de produto.
  Após escolher IBS/CBS integral, as alíquotas nominais de 2026 são preenchidas
  pela tabela oficial: estadual 0,1%, municipal 0%, CBS 0,9%. Base e enquadramento
  continuam sujeitos à conferência; não se aplica essa opção a todos os itens.
- `services/nfe_produto.py`: `aliquotas_ibscbs_integral` e
  `validar_aliquotas_ibscbs_xml` conferem a regra tanto na preparação quanto no
  transporte. Configurações antigas com 2% são bloqueadas antes da rede, sem
  alterar silenciosamente o modelo salvo. A tabela não é extrapolada para 2027.

Fonte das alíquotas: [IT 2025.002 v1.50, seção 05, Portal Nacional NF-e](https://hom.nfe.fazenda.gov.br/portal/exibirArquivo.aspx?conteudo=E1nOtSqZmEI%3D).

Para o #37: em Faturado → Emissão de Nota, selecionar o lançamento e clicar
**Usar emissão manual neste faturamento**. Revisar os dados tributários, manter
homologação e confirmar o envio manual. **Não faturar novamente**: financeiro e
estoque já foram processados. Para continuar no automático, corrigir e salvar
novamente a preparação rejeitada antes de solicitar nova tentativa; esta revisão
não atualiza modelos fiscais antigos no banco sem conferência.

474 testes aprovados. Os novos testes exercitam o ramo real do clique manual
com transporte simulado, persistência das mensagens, troca de modo com bloqueio
de duplicidade/resultado incerto e os valores 2% da rejeição. Não houve emissão,
troca de modo em dados reais, nova baixa financeira/estoque nem implantação.

Publicar em conjunto os quatro arquivos de aplicação citados nesta seção.

# NF-e: assinatura e integridade do transporte — 06/10/2026

## Causa confirmada na tentativa real — revisão final

Após a nova rejeição, foram lidos o XML e o retorno da nota interna **15**,
NF-e número **36**, enviada em homologação em 06/10/2026 às 08:34:42 (-03:00).
Os logs confirmam a execução da versão com auditoria e os três hashes iguais:

`ec8adb51ce8fea3a6f44684ee7be428ac14fdf74aff4632a26c77f54e1d45e59`

Portanto, nessa tentativa não ocorreu alteração dos bytes entre assinatura e
envio. O defeito estava na própria canonicalização utilizada para assinar e
validar: lxml 6.1.1 / libxml2 2.11.9 acrescentava declarações espúrias `xmlns=""`
em descendentes de `SignedInfo` ao canonicalizar diretamente esse subconjunto
da árvore. O namespace padrão muda de NF-e para XMLDSig em `Signature`.

O cálculo anterior assinava esses bytes incorretos. A verificação local usava
o mesmo cálculo e aceitava a assinatura, ocultando a falha. O validador
independente [SignedXml do .NET](https://learn.microsoft.com/en-us/dotnet/api/system.security.cryptography.xml.signedxml.checksignature)
rejeitou o XML efetivamente enviado, sem consultar rede/cadeia de confiança.

### Correção final

Em `dsystem_erp/services/nfe_produto.py`, foi adicionada
`canonicalizar_elemento_nfe`. Ela materializa os namespaces em escopo em uma
cópia independente e preserva atributos `xml:*` herdados antes de executar
C14N 1.0. A cópia serve **somente ao cálculo**, não substitui nem reserializa
os bytes da NFe transmitida. Não elimina namespaces com substituição de texto
nem muda o algoritmo fiscal para C14N exclusivo.

Passaram a usar esse cálculo:

- `assinar_xml_nfe_produto`: DigestValue e SignatureValue;
- `validar_assinatura_nfe_produto`: verificação do digest e da assinatura;
- `registrar_integridade_nfe`: hashes do conteúdo canonicalizado.

Resultado com os dados da nota real, sem alterar o registro:

| Verificação independente | Resultado |
| --- | --- |
| XML original rejeitado pela SEFAZ | Assinatura inválida no .NET |
| XML original no validador local corrigido | Bloqueado |
| Cópia dos dados, reassinada localmente com certificado sintético | Válida no .NET |
| Essa cópia dentro do SOAP | Válida no .NET |

Não foi usado o certificado privado real nessa comprovação. Não houve envio,
alteração do XML/status no banco ou implantação no servidor.

Regressões novas em `tests/test_nfe_assinatura_interoperabilidade.py` e
`tests/verificar_nfe_dotnet.ps1`: bytes C14N esperados, preservação do contexto,
rejeição do cálculo antigo e assinatura/SOAP aceitos por outro motor XMLDSig.
O teste .NET usa o certificado público embutido apenas para verificar integridade;
não é validação de confiança, validade fiscal ou autorização SEFAZ.
Também foi corrigido `tests/test_nfe_produto.py`, que antes repetia o cálculo
defeituoso do aplicativo. Nenhuma dependência de .NET foi adicionada ao ERP.

**Suíte completa final: 465 testes aprovados**, incluindo o motor independente
no Windows e o fluxo automático com banco isolado e geração dos PDFs.

Para nova tentativa: recarregar a aplicação para carregar o módulo atualizado
e gerar uma nova assinatura. A assinatura antiga permanece inválida; não basta
reenviar o XML antigo. No fluxo manual, o botão Enviar gera a assinatura
definitiva. Manter homologação e conferir a autorização pelo protocolo da nota;
não confundir lote processado (104) com autorização. A correção ainda não foi
confirmada por uma nova autorização real da SEFAZ.

## Investigação anterior: namespace do SOAP

O SOAP antigo declarava `xmlns:soap` em um ancestral da `NFe`. A assinatura
utiliza Canonical XML 1.0 inclusivo, que incorpora esse namespace ao canonicalizar
`infNFe` e `SignedInfo`. Assim, a NFe isolada valida, mas a mesma NFe dentro desse
SOAP deixa de validar. O teste reproduz a divergência sem mudar nenhum byte do
elemento NFe. Referência: [Canonical XML 1.0, W3C](https://www.w3.org/TR/2001/REC-xml-c14n-20010315).

A troca do SOAP para namespaces padrão e a validação criptográfica do envelope
já estavam na cópia local. Nesta revisão, foi completada a proteção de transporte
com montagem exclusivamente em bytes e comparação dos hashes solicitados.
Na primeira investigação, ainda não havia sido inspecionado o XML real.
O problema do SOAP antigo foi reproduzido, mas não explicava sozinho a nova
rejeição. A revisão final acima documenta a causa encontrada na tentativa real.

## Fluxo inspecionado e alterações

- `dsystem_erp/services/nfe_produto.py`:
  - `assinar_xml_nfe_produto`: registra o hash imediatamente após a serialização
    definitiva da assinatura. O parse/serialização interno anterior à assinatura
    definitiva consolida os namespaces; depois disso o digest e a assinatura são
    recalculados. Não há reserialização de transporte após esse ponto.
  - `extrair_nfe_assinada_bytes` (nova): usa offsets do parser para recortar os
    bytes originais do elemento, inclusive do SOAP, sem `tostring`, conversão de
    encoding, limpeza de espaços ou indentação. Ignora falsas tags em comentários
    e CDATA; bloqueia DTD, múltiplas NFe e encoding diferente de UTF-8.
  - `sha256_nfe_assinada` (nova): calcula o SHA-256 do recorte original.
  - `registrar_integridade_nfe` (nova): registra etapa, tamanho, referência,
    hash da NFe, hash do documento completo e hashes C14N de infNFe/SignedInfo.
    Divergência em relação ao hash esperado bloqueia o envio.
  - `montar_envelope_nfe_autorizacao`: concatena prefixo SOAP/lote + bytes
    originais da NFe + sufixo. Não usa decode/encode ou tostring na NFe assinada.
    Mantém somente namespaces padrão nos ancestrais.
  - `enviar_xml_nfe_produto`: recebe o hash capturado após assinar, confere antes
    do lote e confere o próprio `Request.data` antes da conexão. A validação
    criptográfica existente também verifica o envelope final. Apenas parse de
    leitura e C14N para verificação: seus resultados não substituem os bytes HTTP.
- `dsystem_erp/services/fiscal_automatico.py`, `processar_emissoes`: captura o
  hash após assinar e o passa ao transporte, atravessando a persistência do XML.
- `dsystem_erp/pages/faturamento.py`, `renderizar_faturado`: mesma proteção no
  envio manual. A reserva de numeração e as travas contra duplicidade permanecem.
- `tests/test_nfe_produto.py`: regressões para os três hashes, bytes recebidos
  por urlopen simulado, namespace ancestral, alterações lexicais, indentação,
  UTF-8, BOM, CRLF, acentos, prefixos, comentários, CDATA e bloqueio sem rede.
- `tests/test_fiscal_automatico.py`: o retorno simulado confere também o hash
  fornecido pelo fluxo automático.

O botão de prévia assina uma prévia; ao enviar, o fluxo reserva o número fiscal
definitivo, gera e assina o XML definitivo. Não é correto comparar duas notas
com números distintos. A auditoria acompanha a mesma referência desde a assinatura
definitiva até o envio. O XML persistido é o definitivo; sua conversão para texto
no banco não substitui os bytes originais usados no transporte.

## Comparação inicial executada localmente (antes da correção final do C14N)

Certificado temporário, nota sintética e transporte HTTP simulado. Recorte da
NFe: **5.215 bytes** em todas as etapas. O hash muda a cada novo certificado/XML;
os valores abaixo pertencem a uma única execução do teste:

| Etapa | SHA-256 da NFe original |
| --- | --- |
| Após assinar | `328af6bcb98db576e5b192bcc16e88c770b4185c97fba1aed3e302a41d990988` |
| Antes do lote | `328af6bcb98db576e5b192bcc16e88c770b4185c97fba1aed3e302a41d990988` |
| Antes do envio (Request.data) | `328af6bcb98db576e5b192bcc16e88c770b4185c97fba1aed3e302a41d990988` |

O documento completo naturalmente tem outro hash quando recebe o SOAP. A
comparação de igualdade é do elemento NFe, excluindo declaração XML/BOM externos.
Os hashes C14N também coincidem no envelope atual. No SOAP antigo, o hash bruto
da NFe continua igual, mas os hashes C14N divergem e a verificação falha.

Nos próximos envios, as etapas `apos_assinar`, `antes_lote` e `antes_envio` ficam
em `logs/tecnico.log`, com origem `nfe_integridade`. O diagnóstico não registra
senha, chave privada ou conteúdo completo da nota.

Validação inicial: `python -m unittest discover -s tests -q` — **461 testes aprovados**.
Inclui o fluxo automático com persistência e geração dos PDFs em banco isolado.
Esse resultado não detectou o defeito comum ao assinador e ao validador local;
foi complementado pelos testes independentes da revisão final acima.

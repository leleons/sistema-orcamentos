# Consulta de CNPJ com recuperação de falhas temporárias

O ERP usa a BrasilAPI como fonte principal e a API pública gratuita CNPJ.ws
como alternativa automática. Somente o CNPJ consultado é enviado ao provedor;
não são enviados senha, certificado, notas ou dados internos do cadastro.
Uma consulta GET na BrasilAPI que falhar por timeout, conexão ou
HTTP 408/500/502/503/504 é repetida uma única vez, após 0,5 segundo.

O timeout continua valendo por tentativa (padrão de 10 segundos). Não há
repetição para CNPJ inválido, HTTP 400/404/403, limite de uso HTTP 429 ou quando
o serviço pede espera pelo cabeçalho Retry-After. Nenhuma nota fiscal é reenviada
por esse mecanismo: somente a consulta cadastral GET é repetida.

Se a BrasilAPI continuar indisponível, ou retornar 429/Retry-After, é feita uma
única tentativa na CNPJ.ws, sem repetir chamadas nesse provedor. HTTP 400/404/403
da BrasilAPI não aciona a alternativa. O limite gratuito da CNPJ.ws é de três
consultas por minuto por IP; se também falhar, o preenchimento manual continua
disponível. Até três chamadas por ação, cada uma com seu timeout.

A resposta alternativa é adaptada aos mesmos campos do formulário e seu CNPJ
é conferido antes do preenchimento. Simples/MEI ausentes permanecem desconhecidos.
Documentação: https://docs.cnpj.ws/referencia-de-api/api-publica/consultando-cnpj

No cadastro novo e na edição, o usuário vê o progresso da consulta. Se o serviço
continuar indisponível, recebe uma orientação para aguardar ou completar os
dados manualmente. Os campos existentes não são limpos; não há gravação
automática em banco nem uso silencioso de informações antigas em cache.

Isso reduz a dependência de uma única API, mas não garante disponibilidade externa.
O pacote local inclui os arquivos atualizados. Não foi aplicado no servidor.

# Contrato: dependência da API do Portal da Transparência

Consultado em 2026-11-12 no OpenAPI público (`https://api.portaldatransparencia.gov.br/v3/api-docs`).
Se a fonte mudar, este é o arquivo a revisar primeiro.

| Item | Valor |
|---|---|
| Base | `https://api.portaldatransparencia.gov.br/api-de-dados` |
| Autenticação | header `chave-api-dados: <chave>`; chave gratuita cadastrada com conta gov.br |
| Chave no Fabric | `bronze_transparencia/Files/_secrets/transparencia_api_key` (research R5) |
| Limite | ~90 req/min das 06:00 às 23:59; maior de 00:00 às 05:59 (horário de Brasília) |
| Ritmo do cliente | 0,7 s entre chamadas de dia; 0,25 s de madrugada (configurável; confirmar no quickstart §5) |
| Paginação | `pagina` obrigatório, desde 1; fim quando a resposta é lista vazia `[]` |
| Formato | lista JSON de objetos (`/emendas`); objeto JSON (`/pessoa-juridica`) |

## Endpoints usados

| Endpoint | Parâmetros | Uso | Tabela |
|---|---|---|---|
| `GET /emendas` | `ano` (opcional no OpenAPI, sempre enviado), `pagina` | todas as emendas do ano, todos os autores | `emendas` |
| `GET /pessoa-juridica` | `cnpj` (obrigatório, 14 dígitos) | cadastro de cada fornecedor da fila (research R10) | `pessoa_juridica` |

Pendências a confirmar com a chave (quickstart §5): tamanho da página de `/emendas` e a forma
como `/pessoa-juridica` responde a CNPJ inexistente. O cliente trata como "não encontrado":
HTTP 404, corpo vazio, objeto sem `cnpj` ou com todos os campos nulos.

## Erros tratados

| Código | Tratamento |
|---|---|
| 401, 403 | falha imediata, "chave da API ausente ou inválida", sem retentativa e sem exibir a chave |
| 429 | retentativa com espera (respeita `Retry-After`) |
| 5xx, timeout, conexão | retentativa com espera exponencial (15, 30, 60, 120, 240 s) |
| 404 em `/pessoa-juridica` | não é erro: registro com `_resultado = 'nao_encontrado'` |
| outros 4xx | falha imediata com o código e o corpo truncado em 300 caracteres |

## Fora do escopo desta feature

`/emendas/documentos/{codigo}`, contratos, licitações, servidores, viagens, CEIS/CNEP,
`/pessoa-fisica` (CPFs de fornecedores pessoa física não são consultados).

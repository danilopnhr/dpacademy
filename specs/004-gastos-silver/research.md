# Research: Camada Silver do case gastos

**Feature**: [spec.md](./spec.md) | **Date**: 2026-11-17

## R1. Origem das despesas: arquivo anual × API (2026-11-17, prd, só leitura)

Base: arquivo Ano-2026 carregado em 2026-11-16 14:59 UTC (125.528 linhas); API de 09, 10 e 11/2026
da execução agendada de 2026-11-17 (16.518 linhas). Cruzamento por `ideDocumento` (arquivo) =
`codDocumento` (API), excluindo `ideDocumento = '0'`.

### Achados

1. `ideDocumento = '0'` é um marcador, não um id: 107.503 linhas de 2019 a 2026 (telefonia). Passagens
   aéreas (SIGEPA) repetem o mesmo `ideDocumento` em até 9 linhas (trechos e passageiros). O
   `ideDocumento` sozinho não é chave.
2. Casados (14.875): mesmo mês nas duas origens (1 exceção), |valor líquido| igual em ~99% e
   `valorDocumento` igual. **A API inverte o sinal do valor líquido**: 14.733 positivos no arquivo
   vêm negativos na API, e as 52 compensações negativas do arquivo vêm positivas. Soma: arquivo
   +R$ 21,05 mi, API −R$ 20,97 mi.
3. Só na API (1.644): 912 com `codDocumento` em GUID (sem id numérico, muitos em pares +x/−x de
   cancelamento), 731 numéricos (prováveis documentos ainda não publicados no arquivo do dia
   anterior) e 1 sem documento. Soma líquida −R$ 127 mil, mas R$ 2,8 mi em valor absoluto.
4. Só no arquivo (82, meses 9–11): quase todos despesas de liderança (`ideCadastro` vazio), que a API
   por deputado não devolve.

### Conclusão

O arquivo é a origem mais completa (inclui lideranças), tem o sinal correto e ids numéricos, custa
~20 s por ano e já absorve as republicações. A API só é ~1 dia mais recente.
Proposta: Silver de despesas só pelo arquivo; pipeline diário recarrega o arquivo dos anos cuja
versão mudou; despesas pela API saem do pipeline diário.
Pendências para o plano: chave composta da despesa (para `ideDocumento = '0'` e passagens);
detecção de mudança do arquivo (Last-Modified/ETag/tamanho ou hash).

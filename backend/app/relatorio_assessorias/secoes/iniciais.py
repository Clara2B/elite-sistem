"""Seção Iniciais (Fase 4, fonte: Iniciais).

Campos (especificação):
- Processos distribuídos no mês: DATA DE DISTRIBUIÇÃO dentro do mês,
  buscando em todas as abas mensais do ano (um caso recebido em julho
  pode ser distribuído em agosto).
- Aguardando distribuição: recebidos até o fim do mês, sem data de
  distribuição ou com PROTOCOLADO ≠ "SIM" na data de corte.
- Distribuídos em até 7 / entre 8 e 20 dias úteis: faixas de
  config/regras.yaml (rótulos confirmados pela Clara, 2026-10-08 — cobrem
  todos os casos, diferente do modelo atual que deixava intervalos de fora).
"""

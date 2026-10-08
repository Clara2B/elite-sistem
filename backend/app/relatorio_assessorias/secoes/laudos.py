"""Seção Laudos (Fase 4, fonte: Laudos).

Campos (especificação):
- Laudos elaborados no mês: linhas da assessoria na aba do mês, exceto
  ENTRADA DE LAUDO = "Cancelado".
- Entregues dentro do prazo: LAUDO PRONTO = "Sim" e dias úteis entre DATA
  e a data de pronto ≤ prazo do tipo (config/regras.yaml).
- Pendentes: LAUDO PRONTO ≠ "Sim" na data de corte.
- Pendentes atrasados: pendentes cujo prazo já venceu na data de corte.
"""

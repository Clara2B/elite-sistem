"""Seção Audiências extrajudiciais (Fase 4, fonte: Extrajudicial).

Campos (especificação):
- Enviadas pela assessoria no mês: DATA DE RECEBIMENTO dentro do mês.
- Realizadas no mês: DATA DE AGENDAMENTO dentro do mês e PRESENÇA =
  PRESENTE ou AUSENTE (exclui CANCELADO e REMARCADO).
- Pendentes para os próximos meses: DATA DE AGENDAMENTO após o fim do mês
  e DATA DE RECEBIMENTO até a data de corte.
- Clientes ausentes (lista): realizadas no mês com PRESENÇA = AUSENTE;
  total no título da seção.
- Solicitações pendentes de correção: manual na v1 (fonte não identificada
  nas planilhas).
"""

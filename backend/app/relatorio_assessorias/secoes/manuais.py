"""Campos manuais da v1 (Fase 4/8) — nenhuma das 6 planilhas contém estes
dados; são digitados na tela de revisão e guardados por mês (ver
armazenamento.py):

- Pastas revisionais: recebidas no mês, aprovadas, aguardando análise,
  aguardando correção no mês e acumulado CRM.
- Processos ativos revisionais: total e quantidade por UF — alimenta o
  mapa revisional (ver mapas.py).
- Sentenças procedentes: lista com nome, processo e UF.
- Processos ganhos por estado: tabela por UF.

Evolução futura (fora do escopo da v1): leitor via API do Google Drive
(sentenças) e leitor do CRM, substituindo esses campos manuais sem mudar a
arquitetura — cada um vira um novo leitor.
"""

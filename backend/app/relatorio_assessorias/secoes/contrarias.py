"""Seção Ações contrárias (Fase 4, fonte: Contrárias).

Campos (especificação):
- Processos incluídos no mês: DATA DE RECEBIMENTO dentro do mês.
- Processos ativos: recebidos até a data de corte (sem data de
  recebimento: entra e gera aviso), STATUS ATUAL fora da lista de
  encerrados (config/regras.yaml — padrão: ARQUIVADO), sem duplicatas pelo
  número CNJ.
- Mapa e tabela por UF: contagem dos ativos por ESTADO.
- Lista Judiciais / Lista Trabalhistas: ativos com TIPO AÇÃO = JUDICIAL /
  TRABALHISTA; nome, processo, UF, valor da causa; ordenados por data de
  recebimento.
- Sentenças favoráveis para a assessoria: manual na v1.

As abas da Procon também contêm linhas TRABALHISTA — a deduplicação pelo
número CNJ vale entre os dois arquivos (Contrárias e Procon), pra um
processo não aparecer duas vezes.
"""

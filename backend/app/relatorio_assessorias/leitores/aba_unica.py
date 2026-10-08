"""Padrão de leitura "aba única" (Fase 2) — fontes Audiências judiciais,
Audiências contrárias e Extrajudiciais (arquivos PLANILHA 2026 e
AGENDAMENTO, abas JUDICIAL / PAUTA DA SEMANA CONTRARIA / AGENDAMENTO).

Particularidades (ver config/fontes.yaml):
- JUDICIAL: coluna de data é a coluna A, sem título no cabeçalho.
- PAUTA DA SEMANA CONTRARIA: cabeçalho na linha 2 (linha 1 é só o título
  da aba, "PAUTA DA SEMANA CONTRARIA").
- Coluna "EMPRESA" duplicada: usa a 1ª ocorrência.
"""

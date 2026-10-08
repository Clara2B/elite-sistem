"""Padrão de leitura "aba única" (Fase 2) — fontes Audiências judiciais,
Audiências contrárias e Extrajudiciais (arquivos PLANILHA 2026 e
AGENDAMENTO, abas JUDICIAL / PAUTA DA SEMANA CONTRARIA / AGENDAMENTO).

Particularidades, já resolvidas de forma genérica por `leitores/base.py`
a partir de `config/fontes.yaml` (nenhum código especial aqui):
- JUDICIAL: coluna de data é a coluna A, sem título — `colunas_fixas` no
  fontes.yaml.
- PAUTA DA SEMANA CONTRARIA: cabeçalho não está na linha 1 (é só o título
  da aba) — a busca flexível de `base.localizar_cabecalho` naturalmente
  pula pra linha 2, sem precisar fixar o número.
- Coluna "EMPRESA" duplicada: usa a 1ª ocorrência (comportamento padrão de
  `base._achar_coluna`, que nunca reusa uma coluna já atribuída a outra
  canônica — como só há uma canônica "empresa", ela fica com a primeira).
"""
from __future__ import annotations

from openpyxl.workbook import Workbook

from app.relatorio_assessorias.leitores import base


def ler(wb: Workbook, nome_planilha: str, config_fonte: dict) -> list[base.LinhaBruta]:
    """Lê a aba única indicada em `config_fonte["aba"]`. Levanta
    `base.AbaNaoEncontrada` se a aba não existir no arquivo,
    `base.CabecalhoNaoEncontrado` se existir mas faltar alguma coluna."""
    nome_aba = config_fonte["aba"]
    if nome_aba not in wb.sheetnames:
        raise base.AbaNaoEncontrada(nome_planilha, nome_aba)
    linhas = list(wb[nome_aba].iter_rows(values_only=True))
    return base.ler_aba(linhas, config_fonte, nome_planilha, nome_aba)

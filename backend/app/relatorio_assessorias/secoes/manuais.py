"""Campos manuais da v1 (Fase 4/8) — nenhuma das 6 planilhas contém estes
dados; são digitados na tela de revisão e guardados por mês (ver
armazenamento.py). Não há `calcular`: este módulo só define o formato —
quem preenche os valores é a tela de revisão (Fase 8).

- Pastas revisionais: recebidas no mês, aprovadas, aguardando análise,
  aguardando correção no mês e acumulado CRM.
- Processos ativos revisionais: total e quantidade por UF — alimenta o
  mapa revisional (ver mapas.py).
- Sentenças procedentes: lista com nome, processo e UF.
- Processos ganhos por estado: tabela por UF.

Evolução futura (fora do escopo da v1): leitor via API do Google Drive
(sentenças) e leitor do CRM, substituindo esses campos manuais sem mudar a
arquitetura — cada um vira um novo leitor."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PastasRevisionais:
    recebidas_no_mes: int = 0
    aprovadas: int = 0
    aguardando_analise: int = 0
    aguardando_correcao_no_mes: int = 0
    acumulado_crm: int = 0


@dataclass
class SentencaProcedente:
    nome: str
    processo: str
    uf: str


@dataclass
class CamposManuais:
    pastas_revisionais: PastasRevisionais = field(default_factory=PastasRevisionais)
    processos_ativos_revisionais_total: int = 0
    processos_ativos_revisionais_por_uf: dict[str, int] = field(default_factory=dict)
    sentencas_procedentes: list[SentencaProcedente] = field(default_factory=list)
    processos_ganhos_por_uf: dict[str, int] = field(default_factory=dict)

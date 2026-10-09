"""Campos manuais da v1 (Fase 4/8) — nenhuma das 6 planilhas contém estes
dados; são digitados na tela de revisão e guardados por mês (ver
armazenamento.py). Não há `calcular`: este módulo só define o formato —
quem preenche os valores é a tela de revisão (Fase 8).

- Pastas revisionais: recebidas no mês, aprovadas, aguardando análise,
  aguardando correção no mês e acumulado CRM.
- Processos ativos revisionais: total e quantidade por UF — alimenta o
  mapa revisional (ver mapas.py).
- Sentenças procedentes (revisional): lista com nome, processo e UF.
- Processos ganhos por estado: tabela por UF.
- Sentenças favoráveis para a assessoria (ações contrárias): lista com
  nome, processo, UF e valor da causa — achada ao mapear o modelo contra
  o resto da especificação na Fase 7 (tabela "SENTENÇAS FAVORÁVEIS PARA
  ASSESSORIA" do `Relatório_EWS_8.docx`, seção de Ações Contrárias — mesma
  ideia das sentenças procedentes do Revisional, mas uma lista separada,
  com mais uma coluna).
- Solicitações pendentes de correção (extrajudicial): contagem — a
  especificação já citava esse campo como manual ("fonte não
  identificada"), achado no modelo dentro da mesma tabela das audiências
  extrajudiciais (Fase 7).

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
class SentencaFavoravel:
    nome: str
    processo: str
    uf: str
    valor_causa: float | None


@dataclass
class CamposManuais:
    pastas_revisionais: PastasRevisionais = field(default_factory=PastasRevisionais)
    processos_ativos_revisionais_total: int = 0
    processos_ativos_revisionais_por_uf: dict[str, int] = field(default_factory=dict)
    sentencas_procedentes: list[SentencaProcedente] = field(default_factory=list)
    processos_ganhos_por_uf: dict[str, int] = field(default_factory=dict)
    sentencas_favoraveis_contrarias: list[SentencaFavoravel] = field(default_factory=list)
    extrajudiciais_solicitacoes_pendentes_correcao: int = 0

"""Seção Audiências judiciais e contrárias (Fase 4, fonte: Planilha 2026).

Campos (especificação), ambos só do mês de referência (confirmado pela
Clara, 2026-10-27 — o código já tinha sido feito "acumulado no ano" por
engano; o relatório manual de referência batia exatamente filtrando só
o mês):
- Audiências judiciais solicitadas pelo tribunal: aba JUDICIAL, linhas da
  assessoria com data dentro do mês de referência.
- Audiências de processos contrários: aba PAUTA DA SEMANA CONTRARIA, mesma
  regra, só o mês.

Mesma regra pras duas fontes (`audiencias_judiciais` e
`audiencias_contrarias` em `config/fontes.yaml`, ambas com um campo
`data`) — por isso uma função só, chamada duas vezes por quem orquestra
as seções (Fase 8), uma pra cada fonte já filtrada pra assessoria."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.relatorio_assessorias.avisos import Aviso
from app.relatorio_assessorias.datas_utilitarias import dentro_do_mes
from app.relatorio_assessorias.leitores.base import LinhaBruta
from app.relatorio_assessorias.normalizacao import datas


@dataclass
class ResultadoAudiencias:
    quantidade: int = 0
    avisos: list[Aviso] = field(default_factory=list)


def calcular(linhas: list[LinhaBruta], mes: int, ano: int) -> ResultadoAudiencias:
    resultado = ResultadoAudiencias()

    for linha in linhas:
        data_normalizada = datas.normalizar(linha.valores.get("data"))
        if data_normalizada.aviso:
            resultado.avisos.append(Aviso(linha.origem, data_normalizada.aviso))
            continue
        if dentro_do_mes(data_normalizada.valor, mes, ano):
            resultado.quantidade += 1

    return resultado

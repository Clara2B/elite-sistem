"""Seção Audiências judiciais e contrárias (Fase 4, fonte: Planilha 2026).

Campos (especificação), ambos acumulados no ano (rótulo "(acumulado no
ano)" no relatório, pra não serem lidos como números do mês):
- Audiências judiciais solicitadas pelo tribunal: aba JUDICIAL, linhas da
  assessoria com data entre 01/01 do ano e a data de corte.
- Audiências de processos contrários: aba PAUTA DA SEMANA CONTRARIA, mesma
  regra, acumulado do ano.

Mesma regra pras duas fontes (`audiencias_judiciais` e
`audiencias_contrarias` em `config/fontes.yaml`, ambas com um campo
`data`) — por isso uma função só, chamada duas vezes por quem orquestra
as seções (Fase 8), uma pra cada fonte já filtrada pra assessoria."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.relatorio_assessorias.avisos import Aviso
from app.relatorio_assessorias.leitores.base import LinhaBruta
from app.relatorio_assessorias.normalizacao import datas


@dataclass
class ResultadoAudiencias:
    quantidade: int = 0
    avisos: list[Aviso] = field(default_factory=list)


def calcular(linhas: list[LinhaBruta], ano: int, data_corte: date) -> ResultadoAudiencias:
    inicio_do_ano = date(ano, 1, 1)
    resultado = ResultadoAudiencias()

    for linha in linhas:
        data_normalizada = datas.normalizar(linha.valores.get("data"))
        if data_normalizada.aviso:
            resultado.avisos.append(Aviso(linha.origem, data_normalizada.aviso))
            continue
        if data_normalizada.valor is not None and inicio_do_ano <= data_normalizada.valor <= data_corte:
            resultado.quantidade += 1

    return resultado

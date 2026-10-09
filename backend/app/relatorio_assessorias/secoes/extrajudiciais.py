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
  nas planilhas — ver secoes/manuais.py)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.relatorio_assessorias.avisos import Aviso
from app.relatorio_assessorias.datas_utilitarias import dentro_do_mes, ultimo_dia_do_mes
from app.relatorio_assessorias.leitores.base import LinhaBruta, Origem
from app.relatorio_assessorias.normalizacao import datas, texto
from app.utils import cell_text
from app.utils import normalize as normalizar_estrutural


@dataclass
class ClienteAusente:
    nome: str
    origem: Origem


@dataclass
class ResultadoExtrajudiciais:
    enviadas: int = 0
    realizadas: int = 0
    pendentes_proximos_meses: int = 0
    clientes_ausentes: list[ClienteAusente] = field(default_factory=list)
    avisos: list[Aviso] = field(default_factory=list)


def calcular(linhas: list[LinhaBruta], mes: int, ano: int, data_corte: date, regras: dict) -> ResultadoExtrajudiciais:
    fim_do_mes = ultimo_dia_do_mes(mes, ano)
    presencas_realizadas = {normalizar_estrutural(v) for v in regras["presenca_realizada"]}

    resultado = ResultadoExtrajudiciais()

    for linha in linhas:
        recebimento = datas.normalizar(linha.valores.get("data_recebimento"))
        if recebimento.aviso:
            resultado.avisos.append(Aviso(linha.origem, f"data de recebimento: {recebimento.aviso}"))

        agendamento = datas.normalizar(linha.valores.get("data_agendamento"))
        if agendamento.aviso:
            resultado.avisos.append(Aviso(linha.origem, f"data de agendamento: {agendamento.aviso}"))

        presenca = normalizar_estrutural(cell_text(linha.valores.get("presenca")))

        if dentro_do_mes(recebimento.valor, mes, ano):
            resultado.enviadas += 1

        if dentro_do_mes(agendamento.valor, mes, ano) and presenca in presencas_realizadas:
            resultado.realizadas += 1
            if presenca == "AUSENTE":
                nome = texto.normalizar_nome(linha.valores.get("nome_completo")).valor
                resultado.clientes_ausentes.append(ClienteAusente(nome, linha.origem))

        if (
            agendamento.valor is not None
            and agendamento.valor > fim_do_mes
            and recebimento.valor is not None
            and recebimento.valor <= data_corte
        ):
            resultado.pendentes_proximos_meses += 1

    return resultado

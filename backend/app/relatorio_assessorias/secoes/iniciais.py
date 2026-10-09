"""Seção Iniciais (Fase 4, fonte: Iniciais).

Campos (especificação):
- Processos distribuídos no mês: DATA DE DISTRIBUIÇÃO dentro do mês,
  buscando em todas as abas mensais do ano (um caso recebido em julho
  pode ser distribuído em agosto).
- Aguardando distribuição: recebidos até o fim do mês, sem data de
  distribuição ou com PROTOCOLADO ≠ "SIM" na data de corte.
- Distribuídos em até 7 / entre 8 e 20 dias úteis: faixas de
  config/regras.yaml (rótulos confirmados pela Clara, 2026-10-08 — cobrem
  todos os casos, diferente do modelo atual que deixava intervalos de fora).

Recebe `linhas` já filtradas pra uma assessoria, mas de TODAS as abas
mensais do ano (não só a do mês de referência) — é quem orquestra as
seções (Fase 8) que lê todas as abas via
`leitores.aba_mensal.encontrar_todas_abas_do_ano` e filtra por
assessoria antes de chamar `calcular`."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.relatorio_assessorias import dias_uteis
from app.relatorio_assessorias.avisos import Aviso
from app.relatorio_assessorias.datas_utilitarias import dentro_do_mes, ultimo_dia_do_mes
from app.relatorio_assessorias.leitores.base import LinhaBruta
from app.relatorio_assessorias.normalizacao import datas
from app.utils import cell_text
from app.utils import normalize as normalizar_estrutural


@dataclass
class ResultadoIniciais:
    distribuidos_no_mes: int = 0
    aguardando_distribuicao: int = 0
    faixas: dict[str, int] = field(default_factory=dict)
    avisos: list[Aviso] = field(default_factory=list)


def calcular(linhas: list[LinhaBruta], mes: int, ano: int, data_corte: date, regras: dict) -> ResultadoIniciais:
    fim_do_mes = ultimo_dia_do_mes(mes, ano)
    faixas_config = regras["faixas_dias_uteis"]
    aviso_acima_de = regras["aviso_acima_de"]

    resultado = ResultadoIniciais(faixas={faixa["rotulo"]: 0 for faixa in faixas_config})

    for linha in linhas:
        recebimento = datas.normalizar(linha.valores.get("data_recebimento"))
        if recebimento.aviso:
            resultado.avisos.append(Aviso(linha.origem, f"data de recebimento: {recebimento.aviso}"))

        bruto_distribuicao = linha.valores.get("data_distribuicao")
        distribuicao = datas.normalizar(bruto_distribuicao)
        if bruto_distribuicao is not None and distribuicao.aviso:
            resultado.avisos.append(Aviso(linha.origem, f"data de distribuição: {distribuicao.aviso}"))

        if dentro_do_mes(distribuicao.valor, mes, ano):
            resultado.distribuidos_no_mes += 1
            if recebimento.valor is not None:
                dias = dias_uteis.contar_dias_uteis(recebimento.valor, distribuicao.valor)
                colocado = False
                for faixa in faixas_config:
                    if faixa["min"] <= dias <= faixa["max"]:
                        resultado.faixas[faixa["rotulo"]] += 1
                        colocado = True
                        break
                if not colocado and dias > aviso_acima_de:
                    resultado.avisos.append(
                        Aviso(linha.origem, f"distribuído em {dias} dias úteis — acima da faixa configurada")
                    )

        if recebimento.valor is not None and recebimento.valor <= fim_do_mes:
            protocolado = normalizar_estrutural(cell_text(linha.valores.get("protocolado")))
            if distribuicao.valor is None or protocolado != "SIM":
                resultado.aguardando_distribuicao += 1

    return resultado

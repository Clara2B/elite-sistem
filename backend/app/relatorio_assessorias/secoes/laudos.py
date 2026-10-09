"""Seção Laudos (Fase 4, fonte: Laudos).

Campos (especificação):
- Laudos elaborados no mês: linhas da assessoria na aba do mês, exceto
  ENTRADA DE LAUDO = "Cancelado".
- Entregues dentro do prazo: LAUDO PRONTO = "Sim" e dias úteis entre DATA
  e a data de pronto ≤ prazo do tipo (config/regras.yaml).
- Pendentes: LAUDO PRONTO ≠ "Sim" na data de corte.
- Pendentes atrasados: pendentes cujo prazo já venceu na data de corte.

Recebe `linhas` já filtradas pra uma assessoria e um mês (a leitura via
`aba_mensal` já resolve "aba do mês certo"; o filtro de assessoria é
`normalizacao.assessoria.filtrar_linhas`, chamado por quem orquestra as
seções — Fase 8)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.relatorio_assessorias import dias_uteis
from app.relatorio_assessorias.avisos import Aviso
from app.relatorio_assessorias.leitores.base import LinhaBruta
from app.relatorio_assessorias.normalizacao import datas
from app.utils import cell_text
from app.utils import normalize as normalizar_estrutural


@dataclass
class ResultadoLaudos:
    elaborados: int = 0
    entregues_dentro_prazo: int = 0
    pendentes: int = 0
    pendentes_atrasados: int = 0
    avisos: list[Aviso] = field(default_factory=list)


def calcular(linhas: list[LinhaBruta], data_corte: date, regras: dict) -> ResultadoLaudos:
    status_cancelado = normalizar_estrutural(regras["status_cancelado"])
    laudo_pronto_valor = normalizar_estrutural(regras["laudo_pronto_valor"])
    prazo_padrao = regras["prazo_dias_uteis"]["padrao"]
    prazos_por_tipo = {normalizar_estrutural(k): v for k, v in regras["prazo_dias_uteis"]["por_tipo"].items()}

    resultado = ResultadoLaudos()

    for linha in linhas:
        if normalizar_estrutural(cell_text(linha.valores.get("entrada_laudo"))) == status_cancelado:
            continue
        resultado.elaborados += 1

        data_entrada = datas.normalizar(linha.valores.get("data"))
        if data_entrada.aviso:
            resultado.avisos.append(Aviso(linha.origem, f"data de entrada: {data_entrada.aviso}"))

        tipo = cell_text(linha.valores.get("tipo_laudo"))
        prazo = prazos_por_tipo.get(normalizar_estrutural(tipo), prazo_padrao)
        pronto = normalizar_estrutural(cell_text(linha.valores.get("laudo_pronto"))) == laudo_pronto_valor

        if not pronto:
            resultado.pendentes += 1
            if data_entrada.valor is not None:
                dias_decorridos = dias_uteis.contar_dias_uteis(data_entrada.valor, data_corte)
                if dias_decorridos > prazo:
                    resultado.pendentes_atrasados += 1
            continue

        data_pronto = datas.normalizar(linha.valores.get("data_pronto"))
        if data_pronto.aviso:
            resultado.avisos.append(Aviso(linha.origem, f"data de pronto: {data_pronto.aviso}"))
        if data_entrada.valor is not None and data_pronto.valor is not None:
            dias_para_ficar_pronto = dias_uteis.contar_dias_uteis(data_entrada.valor, data_pronto.valor)
            if dias_para_ficar_pronto <= prazo:
                resultado.entregues_dentro_prazo += 1

    return resultado

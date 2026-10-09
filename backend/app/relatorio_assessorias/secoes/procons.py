"""Seção Procons (Fase 4, fontes: Procon e Extrajudicial).

Campos (especificação):
- Mês de referência de cada procon: DATA DE RECEBIMENTO (confirmado).
- Lista Procons: linhas com TIPO AÇÃO = PROCON, EXTRAJUDICIAL ou MP,
  recebidas até o fim do mês e não encerradas; nome, processo, situação
  (STATUS ATUAL); total no título.

Processo duplicado dentro da mesma lista (conferência cruzada, Fase 5 —
mesmo caso de Contrárias, "SW"+"EWS" somando a mesma pessoa de abas
diferentes): mantém a 1ª ocorrência e avisa as demais, em vez de listar
duas vezes."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.relatorio_assessorias.avisos import Aviso
from app.relatorio_assessorias.datas_utilitarias import ultimo_dia_do_mes
from app.relatorio_assessorias.leitores.base import LinhaBruta, Origem
from app.relatorio_assessorias.normalizacao import datas, processo, texto
from app.utils import cell_text
from app.utils import normalize as normalizar_estrutural


@dataclass
class Procon:
    nome: str
    processo: str
    situacao: str
    origem: Origem


@dataclass
class ResultadoProcons:
    lista: list[Procon] = field(default_factory=list)
    avisos: list[Aviso] = field(default_factory=list)


def calcular(linhas: list[LinhaBruta], mes: int, ano: int, regras: dict) -> ResultadoProcons:
    fim_do_mes = ultimo_dia_do_mes(mes, ano)
    tipos_incluidos = {normalizar_estrutural(t) for t in regras["tipos_acao_incluidos"]}
    status_encerrados = {normalizar_estrutural(s) for s in regras["status_encerrados_padrao"]}

    resultado = ResultadoProcons()
    chaves_vistas: dict[str, Origem] = {}

    for linha in linhas:
        tipo = normalizar_estrutural(cell_text(linha.valores.get("tipo_acao")))
        if tipo not in tipos_incluidos:
            continue

        recebimento = datas.normalizar(linha.valores.get("data_recebimento"))
        if recebimento.aviso:
            resultado.avisos.append(Aviso(linha.origem, f"data de recebimento: {recebimento.aviso}"))
        if recebimento.valor is None or recebimento.valor > fim_do_mes:
            continue

        status_bruto = cell_text(linha.valores.get("status_atual"))
        if normalizar_estrutural(status_bruto) in status_encerrados:
            continue

        processo_normalizado = processo.normalizar(linha.valores.get("numero_processo"))
        if processo_normalizado.aviso:
            resultado.avisos.append(Aviso(linha.origem, processo_normalizado.aviso))

        chave = processo_normalizado.chave_comparacao
        if chave and chave in chaves_vistas:
            resultado.avisos.append(
                Aviso(linha.origem, f"processo duplicado (já contado em {chaves_vistas[chave]}) — mantido só o primeiro")
            )
            continue
        if chave:
            chaves_vistas[chave] = linha.origem

        nome = texto.normalizar_nome(linha.valores.get("nome_autor")).valor
        resultado.lista.append(Procon(nome, processo_normalizado.valor, status_bruto, linha.origem))

    return resultado

"""Seção Procons (Fase 4, fontes: Procon e Extrajudicial).

Campos (especificação):
- Mês de referência de cada procon: DATA DE RECEBIMENTO dentro do mês de
  referência (confirmado). Bug real corrigido em 2026-10-27 (mesmo
  padrão do bug de Iniciais, confirmado contra dado real da NEXUS): a
  regra antiga só tinha limite superior ("recebidas até o fim do mês"),
  sem limite inferior — um caso recebido em qualquer mês anterior e
  ainda não encerrado era contado de novo em TODO mês seguinte. Com o
  limite inferior (só o mês de referência), bate exatamente com o
  relatório manual (zerou de 25 pra 0 nos dados reais testados).
- Lista Procons: linhas com TIPO AÇÃO = PROCON, EXTRAJUDICIAL ou MP,
  recebidas dentro do mês e não encerradas; nome, processo, situação
  (STATUS ATUAL); total no título.

Processo duplicado dentro da mesma lista (conferência cruzada, Fase 5 —
mesmo caso de Contrárias, "SW"+"EWS" somando a mesma pessoa de abas
diferentes): mantém a 1ª ocorrência e avisa as demais, em vez de listar
duas vezes."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.relatorio_assessorias.avisos import Aviso
from app.relatorio_assessorias.datas_utilitarias import dentro_do_mes
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
    tipos_incluidos = {normalizar_estrutural(t) for t in regras["tipos_acao_incluidos"]}
    status_encerrados = {normalizar_estrutural(s) for s in regras["status_encerrados_padrao"]}

    resultado = ResultadoProcons()
    chaves_vistas: dict[str, tuple[Origem, str]] = {}

    for linha in linhas:
        tipo = normalizar_estrutural(cell_text(linha.valores.get("tipo_acao")))
        if tipo not in tipos_incluidos:
            continue

        recebimento = datas.normalizar(linha.valores.get("data_recebimento"))
        if recebimento.aviso:
            resultado.avisos.append(Aviso(linha.origem, f"data de recebimento: {recebimento.aviso}"))
        if not dentro_do_mes(recebimento.valor, mes, ano):
            continue

        status_bruto = cell_text(linha.valores.get("status_atual"))
        if normalizar_estrutural(status_bruto) in status_encerrados:
            continue

        processo_normalizado = processo.normalizar_protocolo_administrativo(linha.valores.get("numero_processo"))
        if processo_normalizado.aviso:
            resultado.avisos.append(Aviso(linha.origem, processo_normalizado.aviso))

        chave = processo_normalizado.chave_comparacao
        nome_comparavel = normalizar_estrutural(cell_text(linha.valores.get("nome_autor")))
        if chave and chave in chaves_vistas:
            origem_anterior, nome_anterior = chaves_vistas[chave]
            # Mesmo achado de Contrárias (2026-10-27, confirmado pela
            # Clara): número de protocolo repetido com nome de autor bem
            # diferente provavelmente não é duplicata de verdade (erro de
            # digitação do número numa das linhas) — mantém as duas e só
            # avisa, em vez de descartar.
            mesmo_autor = (
                nome_anterior and nome_comparavel and (nome_anterior in nome_comparavel or nome_comparavel in nome_anterior)
            )
            if mesmo_autor:
                resultado.avisos.append(
                    Aviso(linha.origem, f"processo duplicado (já contado em {origem_anterior}) — mantido só o primeiro")
                )
                continue
            resultado.avisos.append(
                Aviso(
                    linha.origem,
                    f"número de processo igual ao de {origem_anterior}, mas com nome de autor diferente "
                    "— confira se o número do processo está certo (as duas linhas foram mantidas)",
                )
            )
        if chave and chave not in chaves_vistas:
            chaves_vistas[chave] = (linha.origem, nome_comparavel)

        nome = texto.normalizar_nome(linha.valores.get("nome_autor")).valor
        resultado.lista.append(Procon(nome, processo_normalizado.valor, status_bruto, linha.origem))

    return resultado

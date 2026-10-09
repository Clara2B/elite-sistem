"""Seção Ações contrárias (Fase 4, fonte: Contrárias).

Campos (especificação):
- Processos incluídos no mês: DATA DE RECEBIMENTO dentro do mês.
- Processos ativos: recebidos até a data de corte (sem data de
  recebimento: entra e gera aviso), STATUS ATUAL fora da lista de
  encerrados (config/regras.yaml — padrão: ARQUIVADO), sem duplicatas pelo
  número CNJ (dentro da mesma lista — ex.: mesma pessoa nas abas SW e EWS,
  que caem na mesma assessoria depois da troca de nome; mantém a 1ª
  ocorrência, avisa as demais).
- Mapa e tabela por UF: contagem dos ativos por ESTADO.
- Lista Judiciais / Lista Trabalhistas: ativos com TIPO AÇÃO = JUDICIAL /
  TRABALHISTA; nome, processo, UF, valor da causa; ordenados por data de
  recebimento.
- Sentenças favoráveis para a assessoria: manual na v1 (ver secoes/manuais.py).

A deduplicação pelo número CNJ entre Contrárias e Procon (as abas da
Procon também têm linhas TRABALHISTA) é cross-arquivo — `calcular` aceita
`chaves_cnj_de_outras_fontes` opcional pra isso: quem orquestra as seções
(Fase 8) passa as chaves já vistas no Procon, se houver sobreposição real
(validado contra as 6 planilhas reais na Fase 4 — sem sobreposição nos
dados de agosto/2026, mas o parâmetro existe pro caso geral)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.relatorio_assessorias.avisos import Aviso
from app.relatorio_assessorias.datas_utilitarias import dentro_do_mes
from app.relatorio_assessorias.leitores.base import LinhaBruta, Origem
from app.relatorio_assessorias.normalizacao import datas, processo, texto, valores
from app.utils import cell_text
from app.utils import normalize as normalizar_estrutural


@dataclass
class ProcessoContrario:
    nome: str
    processo: str
    uf: str | None
    valor_causa: float | None
    data_recebimento: date | None
    origem: Origem


@dataclass
class ResultadoContrarias:
    incluidos_no_mes: int = 0
    ativos_total: int = 0
    ativos_por_uf: dict[str, int] = field(default_factory=dict)
    lista_judiciais: list[ProcessoContrario] = field(default_factory=list)
    lista_trabalhistas: list[ProcessoContrario] = field(default_factory=list)
    avisos: list[Aviso] = field(default_factory=list)


def calcular(
    linhas: list[LinhaBruta],
    mes: int,
    ano: int,
    data_corte: date,
    regras: dict,
    chaves_cnj_de_outras_fontes: frozenset[str] = frozenset(),
) -> ResultadoContrarias:
    status_encerrados = {normalizar_estrutural(s) for s in regras["status_encerrados_padrao"]}
    tipo_judicial = normalizar_estrutural(regras["tipos_acao"]["judicial"])
    tipo_trabalhista = normalizar_estrutural(regras["tipos_acao"]["trabalhista"])

    resultado = ResultadoContrarias()
    candidatos_ativos: list[tuple[ProcessoContrario, str]] = []
    chaves_vistas: dict[str, Origem] = {}

    for linha in linhas:
        recebimento = datas.normalizar(linha.valores.get("data_recebimento"))
        if recebimento.aviso:
            resultado.avisos.append(Aviso(linha.origem, f"data de recebimento: {recebimento.aviso}"))

        if dentro_do_mes(recebimento.valor, mes, ano):
            resultado.incluidos_no_mes += 1

        if recebimento.valor is None:
            resultado.avisos.append(
                Aviso(linha.origem, "processo sem data de recebimento — considerado ativo mesmo assim")
            )
        elif recebimento.valor > data_corte:
            continue  # recebido depois da data de corte: ainda não entra como ativo

        status = normalizar_estrutural(cell_text(linha.valores.get("status_atual")))
        if status in status_encerrados:
            continue

        processo_normalizado = processo.normalizar(linha.valores.get("numero_processo"))
        if processo_normalizado.aviso:
            resultado.avisos.append(Aviso(linha.origem, processo_normalizado.aviso))

        chave = processo_normalizado.chave_comparacao
        if chave and (chave in chaves_vistas or chave in chaves_cnj_de_outras_fontes):
            origem_anterior = chaves_vistas.get(chave)
            detalhe = f"já contado em {origem_anterior}" if origem_anterior else "já contado no Procon"
            resultado.avisos.append(Aviso(linha.origem, f"processo duplicado ({detalhe}) — mantido só o primeiro"))
            continue
        if chave:
            chaves_vistas[chave] = linha.origem

        uf_normalizada = texto.normalizar_uf(linha.valores.get("estado"))
        if uf_normalizada.aviso:
            resultado.avisos.append(Aviso(linha.origem, uf_normalizada.aviso))

        valor_normalizado = valores.normalizar(linha.valores.get("valor_causa"))

        item = ProcessoContrario(
            nome=texto.normalizar_nome(linha.valores.get("nome_autor")).valor,
            processo=processo_normalizado.valor,
            uf=uf_normalizada.valor,
            valor_causa=valor_normalizado.valor,
            data_recebimento=recebimento.valor,
            origem=linha.origem,
        )
        tipo_acao = normalizar_estrutural(cell_text(linha.valores.get("tipo_acao")))
        candidatos_ativos.append((item, tipo_acao))

    resultado.ativos_total = len(candidatos_ativos)
    for item, tipo_acao in candidatos_ativos:
        if item.uf:
            resultado.ativos_por_uf[item.uf] = resultado.ativos_por_uf.get(item.uf, 0) + 1
        if tipo_acao == tipo_judicial:
            resultado.lista_judiciais.append(item)
        elif tipo_acao == tipo_trabalhista:
            resultado.lista_trabalhistas.append(item)

    resultado.lista_judiciais.sort(key=lambda p: p.data_recebimento or date.min)
    resultado.lista_trabalhistas.sort(key=lambda p: p.data_recebimento or date.min)

    return resultado

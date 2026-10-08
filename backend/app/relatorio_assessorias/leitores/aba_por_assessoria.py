"""Padrão de leitura "aba por assessoria" (Fase 2) — fontes Contrárias e
Procons (arquivos CONTRÁRIAS - NOVO e PROCON E EXTRAJUDICIAL, uma aba por
assessoria, nomeada com o apelido dela).

Lê toda aba cujo nome corresponde a algum apelido conhecido (ex.: pra EWS,
lê as abas "SW" e "EWS" e soma os registros das duas — especificação,
"Cadastro de assessorias e apelidos"). Aba cujo nome não bate com nenhum
apelido é ignorada aqui silenciosamente — não é um erro do leitor, é
simplesmente uma aba que não é de assessoria (DASHBOARD, DADOS, ALERTAS
etc., já fora da lista de abas lidas por nome em `fontes.yaml`, mas esse
padrão não usa uma lista fixa de abas, então a checagem é "bate com algum
apelido?" em vez de "está na lista?").
"""
from __future__ import annotations

from openpyxl.workbook import Workbook

from app.relatorio_assessorias.leitores import base


def ler(
    wb: Workbook, nome_planilha: str, config_fonte: dict, nomes_por_apelido: dict[str, str]
) -> dict[str, list[base.LinhaBruta]]:
    """`nomes_por_apelido`: {apelido normalizado: nome oficial da
    assessoria} — construído a partir de `config/assessorias.yaml` +
    `EmpresaCliente` (ver `normalizacao/assessoria.py`, Fase 3; aqui o
    leitor só recebe o dicionário já pronto, pra não depender do banco).

    Devolve {nome oficial: linhas} — uma aba cujo nome bate com um
    apelido mas não tem as colunas esperadas levanta
    `base.CabecalhoNaoEncontrado` (erro bloqueante de verdade, não é
    silenciado: se a aba é de uma assessoria conhecida, o dado dela
    importa)."""
    resultado: dict[str, list[base.LinhaBruta]] = {}
    for nome_aba in wb.sheetnames:
        nome_oficial = nomes_por_apelido.get(base.normalizar_estrutural(nome_aba))
        if nome_oficial is None:
            continue
        linhas = list(wb[nome_aba].iter_rows(values_only=True))
        linhas_lidas = base.ler_aba(linhas, config_fonte, nome_planilha, nome_aba)
        resultado.setdefault(nome_oficial, []).extend(linhas_lidas)
    return resultado

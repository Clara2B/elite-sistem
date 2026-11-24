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

from app.relatorio_assessorias.avisos import Aviso
from app.relatorio_assessorias.leitores import base


def ler(
    wb: Workbook, nome_planilha: str, config_fonte: dict, nomes_por_apelido: dict[str, str]
) -> tuple[dict[str, list[base.LinhaBruta]], dict[str, list[Aviso]]]:
    """`nomes_por_apelido`: {apelido normalizado: nome oficial da
    assessoria} — construído a partir de `config/assessorias.yaml` +
    `EmpresaCliente` (ver `normalizacao/assessoria.py`, Fase 3; aqui o
    leitor só recebe o dicionário já pronto, pra não depender do banco).

    Devolve ({nome oficial: linhas}, {nome oficial: avisos}) — uma aba
    cujo nome bate com um apelido mas não tem as colunas esperadas
    levanta `base.CabecalhoNaoEncontrado` (erro bloqueante, não é
    silenciado: se a aba é de uma assessoria conhecida, o dado dela
    importa), A MENOS que a aba não tenha nenhuma linha de dado de
    verdade (`base.tem_apenas_titulo_e_cabecalho`) — aba de assessoria
    sem nenhum caso cadastrado às vezes tem o cabeçalho incompleto por
    descuido (coluna renomeada, célula em branco) e, como não há dado
    nenhum pra perder, isso não deveria travar o relatório das outras
    ~40 assessorias (bug real encontrado em planilha de Procon de
    produção, 2026-10-27); nesse caso vira só um `Aviso` pra aquela
    assessoria."""
    resultado: dict[str, list[base.LinhaBruta]] = {}
    avisos: dict[str, list[Aviso]] = {}
    for nome_aba in wb.sheetnames:
        nome_oficial = nomes_por_apelido.get(base.normalizar_estrutural(nome_aba))
        if nome_oficial is None:
            continue
        linhas = list(wb[nome_aba].iter_rows(values_only=True))
        try:
            linhas_lidas = base.ler_aba(linhas, config_fonte, nome_planilha, nome_aba)
        except base.CabecalhoNaoEncontrado as erro:
            if not base.tem_apenas_titulo_e_cabecalho(linhas):
                raise
            avisos.setdefault(nome_oficial, []).append(
                Aviso(
                    origem=None,
                    mensagem=(
                        f"'{nome_planilha}', aba '{nome_aba}': cabeçalho incompleto "
                        f"(faltam {', '.join(erro.colunas_faltando)}), mas a aba não "
                        "tem nenhum caso cadastrado — ignorada."
                    ),
                )
            )
            continue
        resultado.setdefault(nome_oficial, []).extend(linhas_lidas)
    return resultado, avisos

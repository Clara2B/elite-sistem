"""Gera `templates/relatorio.docx` (Fase 7) a partir do modelo atual
(`Relatório_EWS_8.docx`), inserindo os marcadores Jinja do docxtpl.

Roda UMA VEZ (migração do modelo pro template) — depois de gerado, o
arquivo de saída é editável direto no Word (especificação: "textos e
notas podem ser editados no Word sem mexer no código"); este script não
roda de novo em produção nem é chamado por `render.py`.

Preserva formatação: em vez de reescrever cada célula/parágrafo do zero,
abre o modelo e só troca o TEXTO de células/parágrafos específicos (pelo
texto exato que eles têm hoje — se o modelo mudar, o script falha alto
em vez de gerar um template errado silenciosamente), mantendo fonte, cor,
bordas, cabeçalho/rodapé e logo originais.

Correções feitas nesta migração (especificação, "Padronização da saída" e
"Ao preparar o template, corrigir os erros de digitação do modelo"):
- Erros de digitação do modelo: "REFRÊNCIA"→"REFERÊNCIA",
  "ASSESSSORIA"→"ASSESSORIA", "QUATIDADE"→"QUANTIDADE",
  "distribuidos"→"distribuídos".
- Rótulos de faixa de Iniciais "05 a 07"/"10 a 20" → vêm de
  `config/regras.yaml` (decisão da Clara, 2026-10-08), não mais fixos no
  texto — tabela virou um loop sobre `iniciais.faixas`.
- "(acumulado no ano)" adicionado nos dois campos acumulados (Audiências
  judiciais e Audiências de processos contrários) — a especificação pede
  esse rótulo, mas o modelo não tinha.
- Todo número isolado (não monetário) formatado com 2 dígitos e zero à
  esquerda, aplicado uniformemente (um único filtro Jinja,
  `dois_digitos`) — o modelo tinha isso só às vezes ("01", "28") e não
  outras ("0", "8", "3"), inconsistência de digitação manual, não uma
  regra; a especificação pede um único filtro consistente.
- Rodapé "Dados extraídos em {{ data_corte }}" adicionado — a
  especificação pede (exemplo de marcador, seção "Template docx e geração
  de PDF"), o modelo não tinha rodapé nenhum.
"""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.table import Table, _Cell, _Row

CAMINHO_MODELO = "/root/.claude/uploads/c7baedbe-3add-57d7-b057-a4b7965c2ad3/6426342a-Relat_rio_EWS_8.docx"
CAMINHO_SAIDA = Path(__file__).resolve().parent.parent / "app" / "relatorio_assessorias" / "templates" / "relatorio.docx"


def _definir_texto(paragrafo_ou_celula, novo_texto: str) -> None:
    """Troca o texto de um parágrafo (ou do 1º parágrafo de uma célula),
    preservando a formatação do 1º run (fonte, negrito, cor) — não usa
    `.text = ...` direto, porque isso descartaria a formatação."""
    paragrafo = paragrafo_ou_celula.paragraphs[0] if isinstance(paragrafo_ou_celula, _Cell) else paragrafo_ou_celula
    runs = paragrafo.runs
    if not runs:
        paragrafo.add_run(novo_texto)
        return
    runs[0].text = novo_texto
    for run in runs[1:]:
        run.text = ""


def _achar_paragrafo(doc: Document, texto_exato: str):
    for paragrafo in doc.paragraphs:
        if paragrafo.text.strip() == texto_exato:
            return paragrafo
    raise AssertionError(f"parágrafo não encontrado (modelo mudou?): {texto_exato!r}")


def _preparar_tabela_loop(
    tabela: Table,
    variavel_item: str,
    expressao_iteravel: str,
    colunas_celulas: list[str],
    linha_modelo_existente: _Row | None = None,
) -> None:
    """Transforma a(s) linha(s) de dado estática(s) de `tabela` num bloco
    de 3 linhas pro docxtpl repetir via `{%tr for/endfor %}`: uma linha
    'for', uma linha-modelo com os marcadores Jinja de `colunas_celulas`,
    uma linha 'endfor'. Linhas de cabeçalho (antes de
    `linha_modelo_existente`, se houver) não são tocadas. Sem linha de
    dado existente (tabela só com cabeçalho), cria a linha-modelo do
    zero."""
    if linha_modelo_existente is not None:
        linha_modelo = linha_modelo_existente
        indice = [linha._tr for linha in tabela.rows].index(linha_modelo._tr)
        for linha_extra in list(tabela.rows[indice + 1 :]):
            linha_extra._tr.getparent().remove(linha_extra._tr)
    else:
        linha_modelo = tabela.add_row()

    for celula, texto in zip(linha_modelo.cells, colunas_celulas, strict=True):
        _definir_texto(celula, texto)

    linha_for = tabela.add_row()
    linha_modelo._tr.addprevious(linha_for._tr)
    _definir_texto(linha_for.cells[0], f"{{%tr for {variavel_item} in {expressao_iteravel} %}}")

    linha_endfor = tabela.add_row()
    linha_modelo._tr.addnext(linha_endfor._tr)
    _definir_texto(linha_endfor.cells[0], "{%tr endfor %}")


def _substituir_imagem_por_marcador(paragrafo, marcador: str) -> None:
    """Remove o(s) run(s) com a imagem existente no parágrafo e põe o
    texto do marcador Jinja (`{{ mapa_x }}`) no lugar — docxtpl troca o
    marcador pela `InlineImage` na hora de renderizar."""
    for run in list(paragrafo.runs):
        run._r.getparent().remove(run._r)
    paragrafo.add_run(marcador)


def main() -> None:
    doc = Document(CAMINHO_MODELO)
    tabelas = doc.tables  # ordem de leitura do documento = ordem de doc.tables

    # --- parágrafos ---
    _definir_texto(_achar_paragrafo(doc, "EMPRESA: EWS"), "EMPRESA: {{ assessoria }}")
    _definir_texto(_achar_paragrafo(doc, "MÊS DE REFERÊNCIA: AGOSTO/2026"), "MÊS DE REFERÊNCIA: {{ mes_extenso }}/{{ ano }}")
    _definir_texto(_achar_paragrafo(doc, "SENTENÇAS PROCEDENTES – 0"), "SENTENÇAS PROCEDENTES – {{ manuais.sentencas_procedentes|length|dois_digitos }}")
    _definir_texto(
        _achar_paragrafo(
            doc,
            "NOTA: A RELAÇÃO DE PROCESSOS GANHOS É UMA ANALISE FEITA COM BASE NO ANO DE 2026 QUE TIVERAM SUAS "
            "SENTENÇAS NO MÊS DE REFRÊNCIA, ISSO NÃO IMPLICA QUE O PROCESSO GANHO TENHA SIDO DISTRIBUÍDO NO MESMO MÊS.",
        ),
        "NOTA: A RELAÇÃO DE PROCESSOS GANHOS É UMA ANALISE FEITA COM BASE NO ANO DE 2026 QUE TIVERAM SUAS "
        "SENTENÇAS NO MÊS DE REFERÊNCIA, ISSO NÃO IMPLICA QUE O PROCESSO GANHO TENHA SIDO DISTRIBUÍDO NO MESMO MÊS.",
    )
    _definir_texto(
        _achar_paragrafo(doc, "CLIENTES AUSENTES NAS AUDIÊNCIAS EXTRAJUDICIAIS - 01"),
        "CLIENTES AUSENTES NAS AUDIÊNCIAS EXTRAJUDICIAIS - {{ extrajudiciais.clientes_ausentes|length|dois_digitos }}",
    )
    _definir_texto(
        _achar_paragrafo(
            doc,
            "NOTA: PRAZO DE AGENDAMENTO DAS AUDIÊNCIAS EXTRAJUDICIAIS SÃO DE 15 DIAS ÚTEIS.\n\nNOTA: PODEM OCORRER "
            "MAIS AUDIÊNCIAS REALIZADAS EM RELAÇÃO A QUATIDADE AGENDADA DEVIDO AS AUDIÊNCIAS SEREM MARCADAS NO "
            "MÊS ANTERIOR",
        ),
        "NOTA: PRAZO DE AGENDAMENTO DAS AUDIÊNCIAS EXTRAJUDICIAIS SÃO DE 15 DIAS ÚTEIS.\n\nNOTA: PODEM OCORRER "
        "MAIS AUDIÊNCIAS REALIZADAS EM RELAÇÃO A QUANTIDADE AGENDADA DEVIDO AS AUDIÊNCIAS SEREM MARCADAS NO "
        "MÊS ANTERIOR",
    )
    _definir_texto(_achar_paragrafo(doc, "JUDICIAIS - 28"), "JUDICIAIS - {{ contrarias.lista_judiciais|length|dois_digitos }}")
    _definir_texto(_achar_paragrafo(doc, "TRABALHISTAS - 02"), "TRABALHISTAS - {{ contrarias.lista_trabalhistas|length|dois_digitos }}")
    _definir_texto(_achar_paragrafo(doc, "PROCONS - 0"), "PROCONS - {{ procons.lista|length|dois_digitos }}")
    _definir_texto(
        _achar_paragrafo(doc, "SENTENÇAS FAVORÁVEIS PARA ASSESSSORIA – 0"),
        "SENTENÇAS FAVORÁVEIS PARA ASSESSORIA – {{ manuais.sentencas_favoraveis_contrarias|length|dois_digitos }}",
    )

    # --- Tabela 0: Pastas revisionais (manual) ---
    campos_pastas = [
        "manuais.pastas_revisionais.recebidas_no_mes",
        "manuais.pastas_revisionais.aprovadas",
        "manuais.pastas_revisionais.aguardando_analise",
        "manuais.pastas_revisionais.aguardando_correcao_no_mes",
        "manuais.pastas_revisionais.acumulado_crm",
    ]
    for linha, campo in zip(tabelas[0].rows, campos_pastas, strict=True):
        _definir_texto(linha.cells[1], f"{{{{ {campo}|dois_digitos }}}}")

    # --- Tabela 1: Laudos ---
    campos_laudos = ["laudos.elaborados", "laudos.entregues_dentro_prazo", "laudos.pendentes", "laudos.pendentes_atrasados"]
    for linha, campo in zip(tabelas[1].rows, campos_laudos, strict=True):
        _definir_texto(linha.cells[1], f"{{{{ {campo}|dois_digitos }}}}")

    # --- Tabela 2: Iniciais (2 linhas fixas + faixas configuráveis em loop) ---
    tabela_iniciais = tabelas[2]
    _definir_texto(tabela_iniciais.rows[0].cells[1], "{{ iniciais.distribuidos_no_mes|dois_digitos }}")
    _definir_texto(tabela_iniciais.rows[1].cells[1], "{{ iniciais.aguardando_distribuicao|dois_digitos }}")
    _preparar_tabela_loop(
        tabela_iniciais,
        variavel_item="rotulo, quantidade",
        expressao_iteravel="iniciais.faixas.items()",
        colunas_celulas=["{{ rotulo }}", "{{ quantidade|dois_digitos }}"],
        linha_modelo_existente=tabela_iniciais.rows[2],
    )

    # --- Tabela 3: Sentenças procedentes (revisional, manual) ---
    _preparar_tabela_loop(
        tabelas[3],
        variavel_item="s",
        expressao_iteravel="manuais.sentencas_procedentes",
        colunas_celulas=["{{ s.nome }}", "{{ s.processo }}", "{{ s.uf }}"],
    )

    # --- Tabela 4: Processos ativos revisionais (manual) ---
    _definir_texto(tabelas[4].rows[0].cells[1], "{{ manuais.processos_ativos_revisionais_total|dois_digitos }}")

    # --- Tabela 5: Descritivo por estado — mapa revisional (manual) ---
    _preparar_tabela_loop(
        tabelas[5],
        variavel_item="uf, quantidade",
        expressao_iteravel="tabela_revisional_uf.items()",
        colunas_celulas=["{{ uf }}", "{{ quantidade|dois_digitos }}"],
        linha_modelo_existente=tabelas[5].rows[0],
    )

    # --- Tabela 6: Processos ganhos por estado (manual) ---
    _preparar_tabela_loop(
        tabelas[6],
        variavel_item="uf, quantidade",
        expressao_iteravel="tabela_processos_ganhos_uf.items()",
        colunas_celulas=["{{ uf }}", "{{ quantidade|dois_digitos }}"],
        linha_modelo_existente=tabelas[6].rows[0],
    )

    # --- Tabela 7: Audiências judiciais (acumulado no ano) ---
    _definir_texto(
        tabelas[7].rows[0].cells[0], "AUDIÊNCIAS Judiciais solicitadas pelo Tribunal (acumulado no ano)"
    )
    _definir_texto(tabelas[7].rows[0].cells[1], "{{ audiencias_judiciais.quantidade|dois_digitos }}")

    # --- Tabela 8: Extrajudiciais + audiências contrárias (acumulado no ano) ---
    tabela_extra = tabelas[8]
    _definir_texto(tabela_extra.rows[0].cells[1], "{{ extrajudiciais.enviadas|dois_digitos }}")
    _definir_texto(tabela_extra.rows[1].cells[1], "{{ extrajudiciais.realizadas|dois_digitos }}")
    _definir_texto(tabela_extra.rows[2].cells[1], "{{ extrajudiciais.pendentes_proximos_meses|dois_digitos }}")
    _definir_texto(tabela_extra.rows[3].cells[1], "{{ manuais.extrajudiciais_solicitacoes_pendentes_correcao|dois_digitos }}")
    _definir_texto(
        tabela_extra.rows[4].cells[0], "Quantidade de audiências de processos contrários (acumulado no ano)"
    )
    _definir_texto(tabela_extra.rows[4].cells[1], "{{ audiencias_contrarias.quantidade|dois_digitos }}")

    # --- Tabela 9: Clientes ausentes ---
    _preparar_tabela_loop(
        tabelas[9],
        variavel_item="c",
        expressao_iteravel="extrajudiciais.clientes_ausentes",
        colunas_celulas=["{{ c.nome }}"],
        linha_modelo_existente=tabelas[9].rows[1],
    )

    # --- Tabela 10: Ações contrárias — incluídos no mês / ativos ---
    _definir_texto(tabelas[10].rows[0].cells[1], "{{ contrarias.incluidos_no_mes|dois_digitos }}")
    _definir_texto(tabelas[10].rows[1].cells[1], "{{ contrarias.ativos_total|dois_digitos }}")

    # --- Tabela 11: Ativos por UF — mapa contrárias ---
    _preparar_tabela_loop(
        tabelas[11],
        variavel_item="uf, quantidade",
        expressao_iteravel="tabela_contrarias_uf.items()",
        colunas_celulas=["{{ uf }}", "{{ quantidade|dois_digitos }}"],
        linha_modelo_existente=tabelas[11].rows[0],
    )

    # --- Tabela 12: Lista judiciais ---
    _preparar_tabela_loop(
        tabelas[12],
        variavel_item="p",
        expressao_iteravel="contrarias.lista_judiciais",
        colunas_celulas=["{{ p.nome }}", "{{ p.processo }}", "{{ p.uf }}", "{{ p.valor_causa|valor_brl }}"],
        linha_modelo_existente=tabelas[12].rows[1],
    )

    # --- Tabela 13: Lista trabalhistas ---
    _preparar_tabela_loop(
        tabelas[13],
        variavel_item="p",
        expressao_iteravel="contrarias.lista_trabalhistas",
        colunas_celulas=["{{ p.nome }}", "{{ p.processo }}", "{{ p.uf }}", "{{ p.valor_causa|valor_brl }}"],
        linha_modelo_existente=tabelas[13].rows[1],
    )

    # --- Tabela 14: Procons ---
    _preparar_tabela_loop(
        tabelas[14],
        variavel_item="p",
        expressao_iteravel="procons.lista",
        colunas_celulas=["{{ p.nome }}", "{{ p.processo }}", "{{ p.situacao }}"],
    )

    # --- Tabela 15: Sentenças favoráveis para a assessoria (contrárias, manual) ---
    _preparar_tabela_loop(
        tabelas[15],
        variavel_item="s",
        expressao_iteravel="manuais.sentencas_favoraveis_contrarias",
        colunas_celulas=["{{ s.nome }}", "{{ s.processo }}", "{{ s.uf }}", "{{ s.valor_causa|valor_brl }}"],
    )

    # --- Mapas: substitui as 2 imagens existentes pelos marcadores ---
    # Só parágrafos com uma figura de verdade (`pic:pic`) — o modelo também
    # tem 2 outros `w:drawing` perto do topo (logo/cabeçalho, sem `pic:pic`,
    # só forma/texto) que não são os mapas e não devem ser tocados.
    _NS_PIC = "{http://schemas.openxmlformats.org/drawingml/2006/picture}pic"
    paragrafos_com_imagem = [p for p in doc.paragraphs if p._p.findall(".//" + _NS_PIC)]
    assert len(paragrafos_com_imagem) == 2, f"esperava 2 imagens de mapa no modelo, achei {len(paragrafos_com_imagem)}"
    _substituir_imagem_por_marcador(paragrafos_com_imagem[0], "{{ mapa_revisional }}")
    _substituir_imagem_por_marcador(paragrafos_com_imagem[1], "{{ mapa_contrarias }}")

    # --- Rodapé (o modelo não tinha nenhum) ---
    rodape = doc.sections[0].footer.paragraphs[0]
    rodape.text = "Dados extraídos em {{ data_corte }}"

    CAMINHO_SAIDA.parent.mkdir(parents=True, exist_ok=True)
    doc.save(CAMINHO_SAIDA)
    print(f"Gerado {CAMINHO_SAIDA}")


if __name__ == "__main__":
    main()

"""Versão em .xlsx dos relatórios que já existem em PDF (2026-10-05, a
pedido da Clara: "preciso que todos os relatórios do sistema tenham a
opção de serem baixados em formato de excel"). Mesmos dados de
`app/pdf_export.py`, reorganizados em tabela "plana" (uma linha por item,
sem quebra de página/seção visual) — o formato que facilita filtrar/somar
no próprio Excel, em vez de recriar o layout do PDF célula por célula.

Visual igual ao do PDF (2026-10-06, a pedido da Clara: "quero que elas
sejam geradas na mesma configuração dos PDFs, mas com o formato de
planilha para editar nomes e valores se necessário") — faixa azul no topo
com o mesmo texto que `pdf_export.py::_cabecalho_empresa` desenha, cabeçalho
da tabela com fundo navy/texto branco, linhas intercaladas e a linha de
Total numa barra navy — só que em célula de verdade (texto/número normal,
editável), não desenho. Estrutura continua "achatada" (uma linha por item,
sem as seções/múltiplas tabelas que o PDF mostra por página) — isso é
proposital, é o que torna a planilha fácil de editar/filtrar/somar; só o
visual (cores, faixa, cabeçalho) replica o PDF, não a paginação dele.

Cartas fica de fora: não é um relatório tabular (é texto de carta-convite
em PDF, que já ganhou "Copiar texto" — ver services/cartas.py). Pendências
também fica de fora: a tela de Pendências gera uma mensagem de cobrança em
texto corrido, não uma lista/tabela."""
from __future__ import annotations

import io
from typing import TYPE_CHECKING

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from app.utils import format_brl

if TYPE_CHECKING:
    from app.services.audiencias import AudienciasResult
    from app.services.correspondencias import CorrespondenciasResult
    from app.services.laudos import LaudosResult
    from app.services.processos import RelatorioGeral, RelatorioPorEmpresa

_NEGRITO = Font(bold=True)
_FORMATO_DATA = "DD/MM/YYYY"
_FORMATO_MOEDA = '"R$" #,##0.00'

# Mesma cor navy da faixa/cabeçalho do PDF (ver pdf_export.py::NAVY,
# HexColor("#152A40")) — aqui como hex "cru" (sem #), formato que o
# openpyxl espera.
_COR_NAVY = "152A40"
_COR_LINHA_ALTERNADA = "F3F5F8"
_COR_BORDA = "CBD2D9"

_FUNDO_NAVY = PatternFill(start_color=_COR_NAVY, end_color=_COR_NAVY, fill_type="solid")
_FUNDO_LINHA_ALTERNADA = PatternFill(start_color=_COR_LINHA_ALTERNADA, end_color=_COR_LINHA_ALTERNADA, fill_type="solid")
_FONTE_FAIXA_TITULO = Font(bold=True, color="FFFFFF", size=12)
_FONTE_FAIXA_EXTRA = Font(color="FFFFFF", size=10)
_FONTE_CABECALHO_TABELA = Font(bold=True, color="FFFFFF")
_FONTE_TOTAL = Font(bold=True, color="FFFFFF")
_BORDA_FINA = Border(
    left=Side(style="thin", color=_COR_BORDA), right=Side(style="thin", color=_COR_BORDA),
    top=Side(style="thin", color=_COR_BORDA), bottom=Side(style="thin", color=_COR_BORDA),
)
_CENTRO = Alignment(horizontal="center", vertical="center", wrap_text=True)
_QUEBRA = Alignment(wrap_text=True, vertical="top")


def _autosize(ws: Worksheet, linhas: list[list]) -> None:
    larguras: dict[int, int] = {}
    for linha in linhas:
        for i, valor in enumerate(linha, start=1):
            larguras[i] = max(larguras.get(i, 0), len(str(valor)) if valor is not None else 0)
    for i, largura in larguras.items():
        ws.column_dimensions[get_column_letter(i)].width = min(max(largura + 2, 10), 60)


def _faixa_titulo(ws: Worksheet, linhas: list[str], n_colunas: int) -> None:
    """Faixa azul no topo da planilha, mesmo texto/ordem que
    `pdf_export.py::_cabecalho_empresa` desenha no PDF — uma linha mesclada
    por item de `linhas` (a primeira maior/negrito, como o "Empresa: X" em
    destaque do PDF), fundo navy, texto branco centralizado."""
    for i, texto in enumerate(linhas):
        ws.append([texto])
        linha = ws.max_row
        if n_colunas > 1:
            ws.merge_cells(start_row=linha, start_column=1, end_row=linha, end_column=n_colunas)
        cel = ws.cell(row=linha, column=1)
        cel.fill = _FUNDO_NAVY
        cel.font = _FONTE_FAIXA_TITULO if i == 0 else _FONTE_FAIXA_EXTRA
        cel.alignment = _CENTRO
        ws.row_dimensions[linha].height = 22 if i == 0 else 18
    ws.append([])


def _cabecalho_tabela(ws: Worksheet, colunas: list[str]) -> None:
    ws.append(colunas)
    linha = ws.max_row
    for cel in ws[linha]:
        cel.font = _FONTE_CABECALHO_TABELA
        cel.fill = _FUNDO_NAVY
        cel.alignment = Alignment(vertical="center", wrap_text=True)
        cel.border = _BORDA_FINA
    ws.row_dimensions[linha].height = 26


def _estilizar_linhas_dados(ws: Worksheet, linha_ini: int, linha_fim: int) -> None:
    """Borda fina + quebra de texto em toda linha de dado, com fundo
    alternado (mesma ideia do `ROWBACKGROUNDS` do PDF de Correspondências
    — ver pdf_export.py::gerar_pdf_correspondencias) pra facilitar seguir
    uma linha na planilha."""
    for indice, linha in enumerate(range(linha_ini, linha_fim + 1)):
        alternada = indice % 2 == 1
        for cel in ws[linha]:
            cel.border = _BORDA_FINA
            cel.alignment = _QUEBRA
            if alternada:
                cel.fill = _FUNDO_LINHA_ALTERNADA


def _estilizar_total(ws: Worksheet, linha: int, n_colunas: int) -> None:
    """Barra navy preenchendo a linha de Total inteira, texto branco
    negrito — mesmo destaque do "Total" em barra navy que Laudos/
    Audiências/Processos já têm no PDF (ver pdf_export.py)."""
    for col in range(1, n_colunas + 1):
        cel = ws.cell(row=linha, column=col)
        cel.fill = _FUNDO_NAVY
        cel.font = _FONTE_TOTAL


def _para_bytes(wb: Workbook) -> bytes:
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def gerar_excel_laudos(result: LaudosResult) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Laudos"
    n_colunas = 5

    linhas_faixa = [f"Empresa: {result.empresa.upper()}"]
    if result.cnpj:
        linhas_faixa.append(f"CNPJ: {result.cnpj}")
    linhas_faixa.append(f"Status: {result.status}")
    _faixa_titulo(ws, linhas_faixa, n_colunas)

    _cabecalho_tabela(ws, ["Data", "Cliente", "Tipo de laudo", "Status", "Valor"])
    # Captura a linha do cabeçalho DEPOIS de escrevê-lo, nunca antes: um
    # `ws.append([])` (linha em branco, usada acima como separador) não
    # necessariamente avança `ws.max_row` do jeito previsível — calcular a
    # posição de antemão (`max_row + 1`) pode sair errado por uma linha.
    linha_cabecalho = ws.max_row
    linhas_dados = [[linha.data, linha.cliente, linha.tipo, linha.status, linha.valor] for linha in result.linhas]
    for linha in linhas_dados:
        ws.append(linha)
    if linhas_dados:
        _estilizar_linhas_dados(ws, linha_cabecalho + 1, ws.max_row)
        for row in ws.iter_rows(min_row=linha_cabecalho + 1, max_row=ws.max_row, min_col=1, max_col=1):
            row[0].number_format = _FORMATO_DATA
        for row in ws.iter_rows(min_row=linha_cabecalho + 1, max_row=ws.max_row, min_col=5, max_col=5):
            row[0].number_format = _FORMATO_MOEDA

    ws.append(["", "", "", "Total", result.total])
    _estilizar_total(ws, ws.max_row, n_colunas)
    ws[f"E{ws.max_row}"].number_format = _FORMATO_MOEDA

    _autosize(ws, [[result.empresa]] + linhas_dados + [["Tipo de laudo", "Cliente"]])
    return _para_bytes(wb)


def gerar_excel_audiencias(result: AudienciasResult) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Audiências"
    n_colunas = 2

    linhas_faixa = [f"Empresa: {result.empresa.upper()}"]
    if result.cnpj:
        linhas_faixa.append(f"CNPJ: {result.cnpj}")
    linhas_faixa.append(f"Período: {result.periodo_ini.strftime('%d/%m/%Y')} - {result.periodo_fim.strftime('%d/%m/%Y')}")
    if result.valor_unitario is not None:
        linhas_faixa.append(f"Valor por audiência: {format_brl(result.valor_unitario)}")
    linhas_faixa.append(f"Quantidade solicitada no período: {len(result.clientes)}")
    linhas_faixa.append(f"Acumulado no mês: {result.quantidade_mes}")
    _faixa_titulo(ws, linhas_faixa, n_colunas)

    _cabecalho_tabela(ws, ["#", "Cliente"])
    linha_cabecalho = ws.max_row
    for i, nome in enumerate(result.clientes, start=1):
        ws.append([i, nome.upper()])
    if result.clientes:
        _estilizar_linhas_dados(ws, linha_cabecalho + 1, ws.max_row)

    if result.total is not None:
        ws.append(["Total", result.total])
        _estilizar_total(ws, ws.max_row, n_colunas)
        ws[f"B{ws.max_row}"].number_format = _FORMATO_MOEDA

    _autosize(ws, [[result.empresa]] + [[i, n.upper()] for i, n in enumerate(result.clientes, start=1)])
    return _para_bytes(wb)


def gerar_excel_processos_geral(relatorio: RelatorioGeral) -> bytes:
    """Uma linha por processo, com Empresa como coluna — junta as duas
    partes que o PDF mostra separadas (Parte 1: Assistente/Nº processo/
    Evento/Fatal; Parte 2: Cliente/Nº processo/Último evento/Última
    observação, ver pdf_export.py::gerar_pdf_processos_geral) numa tabela
    só, casando pelo nº do processo — mais fácil de filtrar/somar no Excel
    do que duas tabelas repetindo o mesmo processo."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Processos - Geral"
    n_colunas = 7

    periodo = f"{relatorio.periodo_ini.strftime('%d/%m/%Y')} a {relatorio.periodo_fim.strftime('%d/%m/%Y')}"
    _faixa_titulo(ws, ["Empresa: ELITE MEDIAÇÕES", "Relatório geral de processos", f"Período: {periodo}"], n_colunas)

    _cabecalho_tabela(ws, ["Empresa", "Assistente", "Nº Processo", "Cliente", "Evento", "Fatal", "Observação"])
    linha_cabecalho = ws.max_row
    linhas_dados = []
    for secao in relatorio.secoes:
        resumo_por_numero = {l.numero_processo: l for l in secao.linhas_resumo}
        for l in secao.linhas:
            resumo = resumo_por_numero.get(l.numero_processo)
            linhas_dados.append([
                secao.empresa, l.assistente, l.numero_processo,
                resumo.cliente if resumo else "—", l.evento, "Sim" if l.fatal else "Não",
                resumo.observacao if resumo else "—",
            ])
    for linha in linhas_dados:
        ws.append(linha)
    if linhas_dados:
        _estilizar_linhas_dados(ws, linha_cabecalho + 1, ws.max_row)

    _autosize(ws, [["Empresa", "Assistente", "Nº Processo", "Cliente", "Evento", "Fatal", "Observação"]] + linhas_dados)
    return _para_bytes(wb)


def gerar_excel_processos_por_empresa(relatorio: RelatorioPorEmpresa) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Processos"
    n_colunas = 5

    periodo = f"{relatorio.periodo_ini.strftime('%d/%m/%Y')} a {relatorio.periodo_fim.strftime('%d/%m/%Y')}"
    titulo = f"{relatorio.total_processos} processo(s)"
    _faixa_titulo(ws, [f"Empresa: {relatorio.empresa.upper()}", titulo, f"Período: {periodo}"], n_colunas)

    _cabecalho_tabela(ws, ["Assistente", "Nº Processo", "Cliente", "Último evento", "Última observação"])
    linha_cabecalho = ws.max_row
    linhas_dados = [
        [l.assistente, l.numero_processo, l.cliente, l.evento, l.observacao] for l in relatorio.linhas
    ]
    for linha in linhas_dados:
        ws.append(linha)
    if linhas_dados:
        _estilizar_linhas_dados(ws, linha_cabecalho + 1, ws.max_row)

    _autosize(ws, [[relatorio.empresa], ["Assistente", "Nº Processo", "Cliente", "Último evento"]] + linhas_dados)
    return _para_bytes(wb)


def gerar_excel_correspondencias(result: CorrespondenciasResult) -> bytes:
    """Correspondências (Fase 9, 2026-10-05, a pedido da Clara). VALOR:
    quando a célula original era um número reconhecível, grava como número
    de verdade (dá pra somar no Excel); quando não era (ex.: "a
    combinar"), grava o texto original da planilha — mesma regra da
    versão em PDF, ver pdf_export.py::gerar_pdf_correspondencias e
    services/correspondencias.py::parse_valor."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Correspondências"
    n_colunas = 5

    _faixa_titulo(ws, [f"Empresa: {result.empresa.upper()}", f"Mês: {result.mes.title()}"], n_colunas)

    _cabecalho_tabela(ws, ["Advogado", "Autor", "Adv / Preposto", "Valor", "Tipo de ação"])
    linha_cabecalho = ws.max_row
    linhas_dados = [
        [linha.advogado, linha.autor, linha.adv_preposto, linha.valor if linha.valor is not None else linha.valor_texto, linha.tipo_acao]
        for linha in result.linhas
    ]
    for linha in linhas_dados:
        ws.append(linha)
    if linhas_dados:
        _estilizar_linhas_dados(ws, linha_cabecalho + 1, ws.max_row)
        for row in ws.iter_rows(min_row=linha_cabecalho + 1, max_row=ws.max_row, min_col=4, max_col=4):
            if isinstance(row[0].value, int | float):
                row[0].number_format = _FORMATO_MOEDA

    ws.append(["", "", "", "Total", result.total])
    _estilizar_total(ws, ws.max_row, n_colunas)
    ws[f"E{ws.max_row}"].number_format = _FORMATO_MOEDA

    _autosize(
        ws,
        [["Advogado", "Autor", "Adv / Preposto", "Valor", "Tipo de ação"]]
        + [[v if not isinstance(v, float) else "R$ 000.000,00" for v in linha] for linha in linhas_dados],
    )
    # Colunas de texto corrido ficam mais largas que o autosize padrão
    # sozinho daria (ele mede o texto inteiro numa linha só) — sem isso, a
    # coluna fica larguíssima pra caber a frase mais longa sem quebrar.
    for letra, largura in (("A", 30), ("B", 32), ("E", 28)):
        ws.column_dimensions[letra].width = min(ws.column_dimensions[letra].width or largura, largura)
    return _para_bytes(wb)

"""Geração do relatório em PDF, na folha personalizada (logo + rodapé) já
usada pela empresa — portado de core/pdf_export.py (leitor-relatorio) sem
mudança de layout."""
from __future__ import annotations

import io
from pathlib import Path
from typing import TYPE_CHECKING

from reportlab.lib.colors import HexColor, white, whitesmoke
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import Frame, Paragraph

from app.services.cartas import href_absoluto
from app.utils import format_brl

if TYPE_CHECKING:
    from app.services.audiencias import AudienciasResult
    from app.services.cartas import ConviteBanco, ConviteCliente
    from app.services.laudos import LaudosResult
    from app.services.processos import RelatorioGeral, RelatorioPorEmpresa

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
FUNDO_LAUDOS = ASSETS_DIR / "laudos_logo_0.jpeg"
FUNDO_AUDIENCIAS = ASSETS_DIR / "audiencias_logo_0.jpeg"
# Cartas reaproveita o timbrado da EXIMIA (mesma marca de Audiências) — não
# existe um fundo próprio pra Cartas e nenhum foi pedido.
FUNDO_CARTAS = FUNDO_AUDIENCIAS

NAVY = HexColor("#152A40")
VERMELHO_DESTAQUE = HexColor("#C0392B")

LARGURA, ALTURA = A4
MARGEM = 42
TOPO_CONTEUDO = ALTURA - 230
TOPO_CARTA = ALTURA - 175
RODAPE_LIMITE = 70


def _fundo(c: canvas.Canvas, caminho_imagem: Path, cobrir_rodape: bool = False):
    if caminho_imagem.exists():
        c.drawImage(
            ImageReader(str(caminho_imagem)), 0, 0, width=LARGURA, height=ALTURA,
            preserveAspectRatio=False, mask="auto",
        )
    if cobrir_rodape:
        c.setFillColor(white)
        c.rect(0, 0, LARGURA, 60, stroke=0, fill=1)


def _cabecalho_empresa(c: canvas.Canvas, y: float, empresa: str, cnpj: str | None, linhas_extra: list[str]) -> float:
    altura_linha = 18
    n_linhas = 2 + len(linhas_extra) if cnpj else 1 + len(linhas_extra)
    altura_faixa = altura_linha * n_linhas + 12
    c.setFillColor(NAVY)
    c.rect(MARGEM, y - altura_faixa, LARGURA - 2 * MARGEM, altura_faixa, stroke=0, fill=1)

    texto_y = y - 20
    c.setFillColor(whitesmoke)
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(LARGURA / 2, texto_y, f"Empresa: {empresa.upper()}")
    texto_y -= altura_linha
    if cnpj:
        c.setFont("Helvetica", 10)
        c.drawCentredString(LARGURA / 2, texto_y, f"CNPJ: {cnpj}")
        texto_y -= altura_linha
    c.setFont("Helvetica", 10)
    for linha in linhas_extra:
        c.drawCentredString(LARGURA / 2, texto_y, linha)
        texto_y -= altura_linha
    return y - altura_faixa - 14


def gerar_pdf_laudos(result: LaudosResult) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    _fundo(c, FUNDO_LAUDOS, cobrir_rodape=True)

    y = _cabecalho_empresa(c, TOPO_CONTEUDO, result.empresa, result.cnpj, [f"Status: {result.status}"])

    col_data_x = MARGEM + 6
    col_cliente_x = MARGEM + 58
    col_tipo_x = MARGEM + 311
    col_status_x = MARGEM + 396
    col_valor_x = LARGURA - MARGEM - 10

    altura_linha = 16
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(NAVY)
    y -= 6
    c.drawString(col_data_x, y, "DATA")
    c.drawString(col_cliente_x, y, "CLIENTE")
    c.drawString(col_tipo_x, y, "TIPO DE LAUDO")
    c.drawString(col_status_x, y, "STATUS")
    c.drawRightString(col_valor_x, y, "VALOR")
    y -= 6
    c.setStrokeColor(NAVY)
    c.line(MARGEM, y, LARGURA - MARGEM, y)
    y -= altura_linha

    c.setFont("Helvetica", 9)
    for linha in result.linhas:
        if y < RODAPE_LIMITE + 30:
            c.showPage()
            _fundo(c, FUNDO_LAUDOS, cobrir_rodape=True)
            y = TOPO_CONTEUDO - 20
            c.setFont("Helvetica", 9)
        c.setFillColor(HexColor("#222222"))
        c.drawString(col_data_x, y, linha.data.strftime("%d/%m/%Y"))
        c.drawString(col_cliente_x, y, str(linha.cliente)[:42])
        c.drawString(col_tipo_x, y, str(linha.tipo)[:14])
        c.drawString(col_status_x, y, str(linha.status))
        c.drawRightString(col_valor_x, y, format_brl(linha.valor))
        y -= altura_linha

    y -= 4
    c.setFillColor(NAVY)
    c.rect(MARGEM, y - 20, LARGURA - 2 * MARGEM, 22, stroke=0, fill=1)
    c.setFillColor(whitesmoke)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(col_data_x, y - 14, "Total")
    c.drawRightString(col_valor_x, y - 14, format_brl(result.total))

    c.showPage()
    c.save()
    return buffer.getvalue()


def gerar_pdf_audiencias(result: AudienciasResult) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    _fundo(c, FUNDO_AUDIENCIAS)

    linhas_extra = [f"Período: {result.periodo_ini.strftime('%d/%m/%Y')} - {result.periodo_fim.strftime('%d/%m/%Y')}"]
    if result.valor_unitario is not None:
        linhas_extra.append(f"Valor por audiência: {format_brl(result.valor_unitario)}")
    linhas_extra.append(f"Quantidade solicitada no período: {len(result.clientes)}")
    linhas_extra.append(f"Acumulado no mês: {result.quantidade_mes}")

    y = _cabecalho_empresa(c, TOPO_CONTEUDO, result.empresa, result.cnpj, linhas_extra)

    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(NAVY)
    y -= 10
    c.drawCentredString(LARGURA / 2, y, "Clientes")
    y -= 16

    altura_linha = 16
    c.setFont("Helvetica", 9)
    for i, nome in enumerate(result.clientes, start=1):
        if y < RODAPE_LIMITE + 30:
            c.showPage()
            _fundo(c, FUNDO_AUDIENCIAS)
            y = TOPO_CONTEUDO - 20
            c.setFont("Helvetica", 9)
        c.setFillColor(HexColor("#222222"))
        c.drawString(MARGEM + 6, y, f"{i} - {nome.upper()}")
        y -= altura_linha

    if result.total is not None:
        y -= 6
        c.setFillColor(NAVY)
        c.rect(MARGEM, y - 20, LARGURA - 2 * MARGEM, 22, stroke=0, fill=1)
        c.setFillColor(whitesmoke)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(MARGEM + 10, y - 14, "Total")
        c.drawRightString(LARGURA - MARGEM - 10, y - 14, format_brl(result.total))

    c.showPage()
    c.save()
    return buffer.getvalue()


def _nova_pagina_processos(c: canvas.Canvas) -> float:
    c.showPage()
    _fundo(c, FUNDO_LAUDOS, cobrir_rodape=True)
    return TOPO_CONTEUDO - 20


def _cabecalho_secao_empresa(c: canvas.Canvas, y: float, empresa: str, total_processos: int) -> float:
    """Título "EMPRESA: NOME — N processo(s)" dentro do corpo do PDF (não a
    faixa navy do topo da página, que já mostra "ELITE MEDIAÇÕES" — essa
    aqui repete uma vez por empresa, no relatório Geral)."""
    if y < RODAPE_LIMITE + 60:
        y = _nova_pagina_processos(c)
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(NAVY)
    c.drawString(MARGEM, y, f"{empresa.upper()} — {total_processos} processo(s)")
    y -= 6
    c.setStrokeColor(NAVY)
    c.line(MARGEM, y, LARGURA - MARGEM, y)
    return y - 16


def _tabela_processos(
    c: canvas.Canvas, y: float, cabecalhos: list[tuple[str, float, bool]], linhas: list[list[str]]
) -> float:
    """Desenha uma tabela simples com quebra de página automática.
    `cabecalhos`: lista de (texto, posição x, alinhar à direita?)."""
    altura_linha = 14

    def _cabecalho(y: float) -> float:
        c.setFont("Helvetica-Bold", 7.5)
        c.setFillColor(NAVY)
        for texto, x, direita in cabecalhos:
            (c.drawRightString if direita else c.drawString)(x, y, texto)
        y -= 5
        c.setStrokeColor(NAVY)
        c.line(MARGEM, y, LARGURA - MARGEM, y)
        return y - altura_linha

    y = _cabecalho(y)
    c.setFont("Helvetica", 7.5)
    for valores in linhas:
        if y < RODAPE_LIMITE + 20:
            y = _cabecalho(_nova_pagina_processos(c))
            c.setFont("Helvetica", 7.5)
        c.setFillColor(HexColor("#222222"))
        for valor, (_, x, direita) in zip(valores, cabecalhos, strict=True):
            (c.drawRightString if direita else c.drawString)(x, y, valor)
        y -= altura_linha
    return y


def gerar_pdf_processos_geral(relatorio: RelatorioGeral) -> bytes:
    """Tipo "Geral" (2026-09-25) — uma seção por empresa, com as duas
    tabelas do Bloco 1: Assistente/Nº processo/Evento/Fatal e depois
    Cliente/Nº processo/Último evento/Última observação."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    _fundo(c, FUNDO_LAUDOS, cobrir_rodape=True)

    periodo = f"Período: {relatorio.periodo_ini.strftime('%d/%m/%Y')} a {relatorio.periodo_fim.strftime('%d/%m/%Y')}"
    y = _cabecalho_empresa(c, TOPO_CONTEUDO, "ELITE MEDIAÇÕES", None, ["Relatório geral de processos", periodo])

    for secao in relatorio.secoes:
        y = _cabecalho_secao_empresa(c, y, secao.empresa, secao.total_processos)
        y = _tabela_processos(
            c, y,
            [("ASSISTENTE", MARGEM + 4, False), ("Nº PROCESSO", MARGEM + 150, False),
             ("EVENTO", MARGEM + 280, False), ("FATAL", LARGURA - MARGEM - 4, True)],
            [[l.assistente[:26], l.numero_processo, l.evento[:26], "Sim" if l.fatal else "Não"] for l in secao.linhas],
        )
        y -= 8
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(NAVY)
        if y < RODAPE_LIMITE + 30:
            y = _nova_pagina_processos(c)
        c.drawString(MARGEM, y, "Resumo por cliente")
        y -= 14
        y = _tabela_processos(
            c, y,
            [("CLIENTE", MARGEM + 4, False), ("Nº PROCESSO", MARGEM + 190, False),
             ("ÚLTIMO EVENTO", MARGEM + 320, False), ("ÚLTIMA OBSERVAÇÃO", MARGEM + 430, False)],
            [[l.cliente[:26], l.numero_processo, l.evento[:18], l.observacao[:40]] for l in secao.linhas_resumo],
        )
        y -= 18

    c.showPage()
    c.save()
    return buffer.getvalue()


def gerar_pdf_processos_por_empresa(relatorio: RelatorioPorEmpresa) -> bytes:
    """Tipo "Por empresa" (2026-09-25) — Assistente/Nº processo/Cliente/
    Último evento/Última observação, só da empresa selecionada."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    _fundo(c, FUNDO_LAUDOS, cobrir_rodape=True)

    periodo = f"Período: {relatorio.periodo_ini.strftime('%d/%m/%Y')} a {relatorio.periodo_fim.strftime('%d/%m/%Y')}"
    titulo = f"{relatorio.total_processos} processo(s)"
    y = _cabecalho_empresa(c, TOPO_CONTEUDO, relatorio.empresa, None, [titulo, periodo])

    _tabela_processos(
        c, y,
        [("ASSISTENTE", MARGEM + 4, False), ("Nº PROCESSO", MARGEM + 100, False),
         ("CLIENTE", MARGEM + 210, False), ("ÚLTIMO EVENTO", MARGEM + 330, False),
         ("ÚLTIMA OBSERVAÇÃO", MARGEM + 430, False)],
        [
            [l.assistente[:16], l.numero_processo, l.cliente[:20], l.evento[:18], l.observacao[:40]]
            for l in relatorio.linhas
        ],
    )

    c.showPage()
    c.save()
    return buffer.getvalue()


def _estilos_carta() -> dict[str, ParagraphStyle]:
    base = {"fontName": "Helvetica-Oblique", "fontSize": 10.5, "leading": 14, "textColor": HexColor("#1A1A1A")}
    return {
        "titulo": ParagraphStyle("titulo", alignment=TA_CENTER, spaceAfter=4, **base),
        "titulo_forte": ParagraphStyle(
            "titulo_forte", alignment=TA_CENTER, fontName="Helvetica-BoldOblique",
            fontSize=12, leading=15, spaceAfter=10, textColor=NAVY,
        ),
        "parte_centralizada": ParagraphStyle(
            "parte_centralizada", alignment=TA_CENTER, fontName="Helvetica-BoldOblique",
            fontSize=11, leading=15, spaceAfter=12, textColor=HexColor("#1A1A1A"),
        ),
        "corpo": ParagraphStyle("corpo", alignment=TA_JUSTIFY, spaceAfter=10, **base),
        "destaque": ParagraphStyle(
            "destaque", alignment=TA_JUSTIFY, fontName="Helvetica-Bold", fontSize=10.5,
            leading=14, spaceAfter=12, textColor=HexColor("#1A1A1A"),
        ),
        "aviso": ParagraphStyle(
            "aviso", alignment=TA_JUSTIFY, fontName="Helvetica-BoldOblique", fontSize=10,
            leading=13, spaceAfter=8, textColor=HexColor("#1A1A1A"),
        ),
        "link": ParagraphStyle(
            "link", alignment=TA_LEFT, fontName="Helvetica-BoldOblique", fontSize=10.5,
            leading=15, spaceAfter=12, textColor=VERMELHO_DESTAQUE,
        ),
        "fechamento": ParagraphStyle("fechamento", alignment=TA_LEFT, spaceAfter=6, **base),
        # Carta Banco — texto do modelo não é itálico (diferente da Cliente).
        "titulo_banco": ParagraphStyle(
            "titulo_banco", alignment=TA_CENTER, fontName="Helvetica-Bold",
            fontSize=12.5, leading=16, spaceAfter=14, textColor=NAVY,
        ),
        "link_banco": ParagraphStyle(
            "link_banco", alignment=TA_LEFT, fontName="Helvetica", fontSize=10.5,
            leading=15, spaceAfter=12, textColor=HexColor("#1A1A1A"),
        ),
        "contato_destaque": ParagraphStyle(
            "contato_destaque", alignment=TA_LEFT, fontName="Helvetica-Bold", fontSize=10.5,
            leading=14, spaceAfter=10, textColor=VERMELHO_DESTAQUE,
        ),
        "fechamento_caps": ParagraphStyle(
            "fechamento_caps", alignment=TA_LEFT, fontName="Helvetica", fontSize=10.5,
            leading=14, spaceAfter=6, textColor=HexColor("#1A1A1A"),
        ),
    }


def _preencher_carta(c: canvas.Canvas, fundo: Path, paragrafos: list[Paragraph]) -> None:
    """Desenha os parágrafos dentro da folha timbrada, com quebra de página
    automática se o texto (excepcionalmente) não couber em uma só página."""
    largura_util = LARGURA - 2 * MARGEM
    restante = list(paragrafos)
    primeira_pagina = True
    while restante:
        if not primeira_pagina:
            c.showPage()
            _fundo(c, fundo)
        frame = Frame(MARGEM, RODAPE_LIMITE, largura_util, TOPO_CARTA - RODAPE_LIMITE, showBoundary=0)
        frame.addFromList(restante, c)
        primeira_pagina = False


def gerar_pdf_carta_cliente(convite: ConviteCliente) -> bytes:
    """Carta Convite Cliente (Fase Cartas, 2026-09-25) — texto fixo do
    modelo CARTA_CONVITE_CLIENTE.pdf, com Autor/Réu/Dia/Hora/Link/plataforma
    substituídos e o telefone de contato adicionado (aprovado pela Clara)."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    _fundo(c, FUNDO_CARTAS)

    estilos = _estilos_carta()
    paragrafos = [
        Paragraph("Pré-Processual", estilos["titulo"]),
        Paragraph("Métodos Consensuais de Solução de Conflitos", estilos["titulo"]),
        Paragraph(
            "Convite para Audiência Extrajudicial Administrativa – Ação Revisional",
            estilos["titulo_forte"],
        ),
        Paragraph(f"AUTOR: {convite.autor}<br/>REU: {convite.reu},", estilos["parte_centralizada"]),
        Paragraph(
            "Pela presente, solicitamos o seu comparecimento a participar de "
            "<b>AUDIÊNCIA EXTRAJUDICIAL ADMINISTRATIVA</b>, a ser realizada com a "
            "finalidade de tentativa de composição amigável",
            estilos["corpo"],
        ),
        Paragraph(
            "A audiência de Tentativa de Conciliação está sugerida para o dia "
            f'<font color="#C0392B">{convite.dia.strftime("%d/%m/%Y")}, às {convite.hora}</font>, '
            "a ser realizada na modalidade Virtual, podendo haver ajustes, mediante prévio contato.",
            estilos["destaque"],
        ),
        Paragraph("NÃO ESQUECER DO DOCUMENTO COM FOTO", estilos["aviso"]),
        Paragraph(
            "É OBRIGATÓRIO A PRESENÇA DO TITULAR DO CONTRATO, NÃO SERÁ PERMITIDO A "
            "ENTRADA DE TERCEIROS EM AUDIÊNCIA SEM A PROCURAÇÃO PÚBLICA",
            estilos["aviso"],
        ),
        Paragraph(
            "A ENTRADA DE TERCEIROS SEM A PROCURAÇÃO A AUDIÊNCIA SERÁ CANCELADA",
            estilos["aviso"],
        ),
        Paragraph(
            f"(Segue link abaixo, pela plataforma {convite.plataforma.upper()})<br/>"
            f'<a href="{href_absoluto(convite.link)}"><font color="#1A5276"><u>{convite.link}</u></font></a>',
            estilos["link"],
        ),
        Paragraph(
            "Colocamo-nos à disposição por meio do e-mail: "
            "<b>conciliacao@camaraeximia.com.</b><br/>"
            "<b>Telefone: 55 11 93234-6989</b>",
            estilos["corpo"],
        ),
        Paragraph(
            "Certos da atenção e colaboração, renovamos votos de elevada estima e consideração.",
            estilos["fechamento"],
        ),
        Paragraph("Atenciosamente,", estilos["fechamento"]),
        Paragraph("Eximia Câmara de Mediação Conciliação e Arbitragem.", estilos["fechamento"]),
    ]
    _preencher_carta(c, FUNDO_CARTAS, paragrafos)

    c.showPage()
    c.save()
    return buffer.getvalue()


def gerar_pdf_carta_banco(convite: ConviteBanco) -> bytes:
    """Carta Convite Banco (Fase Cartas, 2026-09-25) — texto fixo do modelo
    NOVA_CARTA_CONVITE_-_BANCO.pdf, com Nome/CPF/Contrato/Data/Hora/Link/
    Banco/CNPJ/plataforma substituídos. Corrige dois erros do próprio
    modelo oficial, aprovados pela Clara (ver DECISIONS.md): "GOGGLE MEET"
    -> plataforma certa e dinâmica, e a pontuação "CNPJ : -" do
    destinatário -> "CNPJ: ..." limpo."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    _fundo(c, FUNDO_CARTAS)

    estilos = _estilos_carta()
    plataforma_caps = convite.plataforma.upper()
    paragrafos = [
        Paragraph(
            "Convite para Audiência Extrajudicial Administrativa – Ação Revisional",
            estilos["titulo_banco"],
        ),
        Paragraph("Ao", estilos["titulo"]),
        Paragraph(f"{convite.banco_nome} – CNPJ: {convite.banco_cnpj},", estilos["parte_centralizada"]),
        Paragraph("Prezados Senhores,", estilos["titulo"]),
        Paragraph(
            f"Por meio da presente, o(a) Sr.(a) <b>{convite.nome},</b> inscrito(a) no "
            f"<b>CPF: {convite.cpf},</b> titular da unidade de n° <b>{convite.contrato},</b> "
            "vem, respeitosamente, CONVIDAR essa instituição financeira para participar de "
            "<b>AUDIÊNCIA EXTRAJUDICIAL ADMINISTRATIVA</b>, a ser realizada com a finalidade "
            "de tentativa de composição amigável.",
            estilos["corpo"],
        ),
        Paragraph(
            "Esclarece-se que, encontra-se em nosso escritório o contrato de financiamento do "
            "Reclamante, acima citado, cujo objetivo consiste na revisão de cláusulas "
            "contratuais reputadas abusivas, notadamente quanto a <b>juros, encargos, "
            "capitalização, tarifas etc</b>.",
            estilos["corpo"],
        ),
        Paragraph(
            "Não obstante, antes da judicialização da demanda, a parte Reclamante demonstra "
            "pleno interesse na solução consensual, em consonância com os princípios da "
            "boa-fé objetiva, da cooperação e da autocomposição, motivo pelo qual propõe a "
            "realização da referida audiência extrajudicial.",
            estilos["corpo"],
        ),
        Paragraph(
            f'A audiência está sugerida para o dia {convite.data.strftime("%d/%m/%Y")}, às '
            f"{convite.hora}, a ser realizada na modalidade Virtual, podendo haver ajustes, "
            "mediante prévio contato.",
            estilos["destaque"],
        ),
        Paragraph(
            f'<a href="{href_absoluto(convite.link)}"><font color="#1A5276">'
            f"<u>{convite.link}</u></font></a>",
            estilos["link_banco"],
        ),
        Paragraph(
            "A Audiência de Tentativa de Conciliação será realizada de forma virtual, através "
            f"do aplicativo {plataforma_caps}.",
            estilos["destaque"],
        ),
        Paragraph(
            "Solicita-se, desde já, que essa Instituição indique representante com poderes "
            "para negociar e transigir, a fim de possibilitar a efetiva resolução do "
            "conflito.",
            estilos["corpo"],
        ),
        Paragraph(
            "Colocamo-nos à disposição por meio do e-mail: "
            "<b>conciliacao@camaraeximia.com.</b>",
            estilos["contato_destaque"],
        ),
        Paragraph(
            "Certos da atenção e colaboração, renovamos votos de elevada estima e consideração.",
            estilos["fechamento"],
        ),
        Paragraph("Atenciosamente,", estilos["fechamento"]),
        Paragraph("EXÍMIA CÂMARA DE CONCILIAÇÃO, MEDIAÇÃO E ARBITRAGEM", estilos["fechamento_caps"]),
    ]
    _preencher_carta(c, FUNDO_CARTAS, paragrafos)

    c.showPage()
    c.save()
    return buffer.getvalue()

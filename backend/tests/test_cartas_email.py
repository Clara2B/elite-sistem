"""Versão em HTML das Cartas-convite, pra ir no corpo do e-mail (Fase 1 —
Solicitação de Audiência, 2026-10-16) — mesmo conteúdo de
formatar_texto_carta_*/gerar_pdf_carta_*, só o formato muda. Assunto do
e-mail: mesmo padrão pros dois (confirmado pela Clara)."""
from __future__ import annotations

from datetime import date

from app.services.cartas import (
    formatar_html_carta_banco,
    formatar_html_carta_cliente,
    montar_assunto_email,
    montar_convite_banco,
    montar_convite_cliente,
)

LINK = "https://meet.google.com/abc-defg-hij"


def test_assunto_email_segue_o_padrao_exato():
    assunto = montar_assunto_email(date(2026, 11, 5), "15:00", "Marcilene Dalbem de Oliveira")
    assert assunto == (
        "AUDIÊNCIA DE TENTATIVA DE CONCILIAÇÃO: 05 DE NOVEMBRO DE 2026 ÀS "
        "15H00 - MARCILENE DALBEM DE OLIVEIRA"
    )


def test_assunto_email_preserva_acento_e_cedilha_do_nome():
    assunto = montar_assunto_email(date(2026, 3, 1), "09:30", "João da Conceição")
    assert "JOÃO DA CONCEIÇÃO" in assunto
    assert "MARÇO" in assunto


def test_assunto_email_dia_sempre_com_dois_digitos():
    assunto = montar_assunto_email(date(2026, 1, 5), "08:00", "Fulano")
    assert assunto.startswith("AUDIÊNCIA DE TENTATIVA DE CONCILIAÇÃO: 05 DE JANEIRO")


def test_assunto_email_hora_no_formato_15h00():
    assunto = montar_assunto_email(date(2026, 1, 1), "08:05", "Fulano")
    assert "ÀS 08H05" in assunto


def test_assunto_email_mesmo_padrao_pros_12_meses():
    meses = [
        "JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO",
        "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO",
    ]
    for i, nome in enumerate(meses, start=1):
        assunto = montar_assunto_email(date(2026, i, 10), "10:00", "Fulano")
        assert f"DE {nome} DE 2026" in assunto


def test_html_carta_cliente_tem_o_mesmo_conteudo_do_texto():
    convite = montar_convite_cliente("Fulano de Tal", "Banco XPTO", date(2026, 11, 5), "15:00", LINK)
    corpo = formatar_html_carta_cliente(convite)
    assert "FULANO DE TAL" in corpo
    assert "BANCO XPTO" in corpo
    assert "05/11/2026" in corpo
    assert "15H00" in corpo  # formatar_hora já converte "15:00" -> "15H00"
    assert LINK in corpo
    assert "GOOGLE MEET" in corpo
    assert "NÃO ESQUECER DO DOCUMENTO COM FOTO" in corpo
    assert "conciliacao@camaraeximia.com" in corpo


def test_html_carta_cliente_link_eh_clicavel():
    convite = montar_convite_cliente("Fulano de Tal", "Banco XPTO", date(2026, 11, 5), "15:00", LINK)
    corpo = formatar_html_carta_cliente(convite)
    assert f'href="{LINK}"' in corpo


def test_html_carta_cliente_destaca_dia_e_hora_em_vermelho():
    convite = montar_convite_cliente("Fulano de Tal", "Banco XPTO", date(2026, 11, 5), "15:00", LINK)
    corpo = formatar_html_carta_cliente(convite)
    assert "#C0392B" in corpo


def test_html_carta_cliente_com_logo_referencia_o_content_id():
    convite = montar_convite_cliente("Fulano de Tal", "Banco XPTO", date(2026, 11, 5), "15:00", LINK)
    corpo = formatar_html_carta_cliente(convite, logo_cid="logo-carta")
    assert 'src="cid:logo-carta"' in corpo


def test_html_carta_cliente_logo_fica_no_rodape_depois_do_texto():
    """A imagem usada antes era a folha inteira do timbrado do PDF
    (cabeçalho + página em branco), deixando um espaço vazio enorme no
    topo do e-mail (reportado pela Clara em 2026-10-26). Agora é um
    logotipo pequeno, no rodapé — depois do fechamento da carta, não
    antes do texto."""
    convite = montar_convite_cliente("Fulano de Tal", "Banco XPTO", date(2026, 11, 5), "15:00", LINK)
    corpo = formatar_html_carta_cliente(convite, logo_cid="logo-carta")
    assert corpo.index('src="cid:logo-carta"') > corpo.index("Eximia Câmara de Mediação")


def test_html_carta_cliente_sem_logo_nao_tem_tag_de_imagem():
    convite = montar_convite_cliente("Fulano de Tal", "Banco XPTO", date(2026, 11, 5), "15:00", LINK)
    corpo = formatar_html_carta_cliente(convite)
    assert "<img" not in corpo


def test_html_carta_cliente_escapa_nomes_com_caracteres_html():
    convite = montar_convite_cliente("Fulano <script> & Cia", "Banco & Tal", date(2026, 11, 5), "15:00", LINK)
    corpo = formatar_html_carta_cliente(convite)
    assert "<script>" not in corpo
    assert "&amp;" in corpo


def test_html_carta_banco_tem_o_mesmo_conteudo_do_texto():
    convite = montar_convite_banco(
        "Banco XPTO", "11.222.333/0001-81", "Fulano de Tal", "529.982.247-25", "12345",
        date(2026, 11, 5), "15:00", LINK,
    )
    corpo = formatar_html_carta_banco(convite)
    assert "BANCO XPTO" in corpo
    assert "11.222.333/0001-81" in corpo
    assert "FULANO DE TAL" in corpo
    assert "529.982.247-25" in corpo
    assert "12345" in corpo
    assert "05/11/2026" in corpo
    assert LINK in corpo


def test_html_carta_banco_link_eh_clicavel():
    convite = montar_convite_banco(
        "Banco XPTO", "11.222.333/0001-81", "Fulano de Tal", "529.982.247-25", "12345",
        date(2026, 11, 5), "15:00", LINK,
    )
    corpo = formatar_html_carta_banco(convite)
    assert f'href="{LINK}"' in corpo


def test_html_carta_banco_com_logo_referencia_o_content_id():
    convite = montar_convite_banco(
        "Banco XPTO", "11.222.333/0001-81", "Fulano de Tal", "529.982.247-25", "12345",
        date(2026, 11, 5), "15:00", LINK,
    )
    corpo = formatar_html_carta_banco(convite, logo_cid="logo-carta")
    assert 'src="cid:logo-carta"' in corpo


def test_html_carta_banco_logo_fica_no_rodape_depois_do_texto():
    convite = montar_convite_banco(
        "Banco XPTO", "11.222.333/0001-81", "Fulano de Tal", "529.982.247-25", "12345",
        date(2026, 11, 5), "15:00", LINK,
    )
    corpo = formatar_html_carta_banco(convite, logo_cid="logo-carta")
    assert corpo.index('src="cid:logo-carta"') > corpo.index("EXÍMIA CÂMARA DE CONCILIAÇÃO")

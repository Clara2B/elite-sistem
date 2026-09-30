"""Cartas — Convite Cliente/Banco: geração de PDF (sem cobertura de testes
até então) e o botão "Copiar texto" (2026-09-29, a pedido da Clara:
"preciso que exatamente o mesmo conteúdo que vem escrito no PDF... venha
escrito em formato de texto pra copiar e colar")."""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select

from app.auth import hash_senha
from app.models import LogAuditoria, Usuario
from app.pdf_export import gerar_pdf_carta_banco
from app.services.cartas import (
    ConviteBanco,
    ConviteCliente,
    formatar_texto_carta_banco,
    formatar_texto_carta_cliente,
    identificar_documento,
)


def _logar_admin(db, client, email="admin.cartas@teste.local"):
    db.add(Usuario(nome="Admin", email=email, senha_hash=hash_senha("certa"), papel_global="ADMIN_SUPERIOR"))
    db.commit()
    client.post("/login", data={"email": email, "senha": "certa"})


# --- formatar_texto_carta_cliente / formatar_texto_carta_banco (unidade) ----


def test_formatar_texto_carta_cliente_contem_os_dados_do_convite():
    convite = ConviteCliente(
        autor="FULANO DA SILVA", reu="BANCO TAL", dia=date(2026, 10, 15),
        hora="14H05", link="meet.google.com/abc-defg-hij", plataforma="Google Meet",
    )
    texto = formatar_texto_carta_cliente(convite)

    assert "AUTOR: FULANO DA SILVA" in texto
    assert "REU: BANCO TAL," in texto
    assert "15/10/2026, às 14H05" in texto
    assert "pela plataforma GOOGLE MEET" in texto
    assert "meet.google.com/abc-defg-hij" in texto
    assert "conciliacao@camaraeximia.com" in texto
    assert texto.startswith("Pré-Processual")
    assert texto.rstrip().endswith("Eximia Câmara de Mediação Conciliação e Arbitragem.")
    # Sem marcação do PDF (a Paragraph do reportlab), só texto puro.
    for marcador in ("<b>", "</b>", "<font", "</font>", "<a ", "</a>", "<u>", "</u>", "<br/>"):
        assert marcador not in texto


def test_formatar_texto_carta_banco_contem_os_dados_do_convite():
    convite = ConviteBanco(
        banco_nome="BANCO TAL S.A.", banco_cnpj="00.000.000/0001-00", nome="FULANA DE TAL",
        documento="529.982.247-25", tipo_documento="CPF", contrato="12345",
        data=date(2026, 11, 3), hora="09H30",
        link="teams.microsoft.com/l/meetup-join/xyz", plataforma="Teams",
    )
    texto = formatar_texto_carta_banco(convite)

    assert "BANCO TAL S.A. – CNPJ: 00.000.000/0001-00," in texto
    assert "FULANA DE TAL, inscrito(a) no CPF: 529.982.247-25" in texto
    assert "titular da unidade de n° 12345," in texto
    assert "03/11/2026, às 09H30" in texto
    assert "teams.microsoft.com/l/meetup-join/xyz" in texto
    assert "através do aplicativo TEAMS." in texto
    assert texto.startswith("Convite para Audiência Extrajudicial Administrativa")
    assert texto.rstrip().endswith("EXÍMIA CÂMARA DE CONCILIAÇÃO, MEDIAÇÃO E ARBITRAGEM")
    for marcador in ("<b>", "</b>", "<font", "</font>", "<a ", "</a>", "<u>", "</u>", "<br/>"):
        assert marcador not in texto


def test_formatar_texto_carta_banco_com_titular_pessoa_juridica_mostra_cnpj():
    """2026-09-30, a pedido da Clara: o titular da unidade pode ser CNPJ, e
    a carta precisa identificar e escrever "CNPJ" no lugar de "CPF"."""
    convite = ConviteBanco(
        banco_nome="BANCO TAL S.A.", banco_cnpj="00.000.000/0001-00", nome="EMPRESA TITULAR LTDA",
        documento="11.222.333/0001-81", tipo_documento="CNPJ", contrato="12345",
        data=date(2026, 11, 3), hora="09H30",
        link="teams.microsoft.com/l/meetup-join/xyz", plataforma="Teams",
    )
    texto = formatar_texto_carta_banco(convite)

    assert "EMPRESA TITULAR LTDA, inscrito(a) no CNPJ: 11.222.333/0001-81" in texto
    assert "inscrito(a) no CPF" not in texto


def test_gerar_pdf_carta_banco_com_titular_pessoa_juridica_nao_quebra():
    """A mesma mudança (CPF -> CPF/CNPJ) também precisa gerar o PDF sem
    erro, não só o texto pra copiar."""
    convite = ConviteBanco(
        banco_nome="BANCO TAL S.A.", banco_cnpj="00.000.000/0001-00", nome="EMPRESA TITULAR LTDA",
        documento="11.222.333/0001-81", tipo_documento="CNPJ", contrato="12345",
        data=date(2026, 11, 3), hora="09H30",
        link="teams.microsoft.com/l/meetup-join/xyz", plataforma="Teams",
    )
    pdf_bytes = gerar_pdf_carta_banco(convite)
    assert pdf_bytes.startswith(b"%PDF")


# --- identificar_documento (CPF ou CNPJ) -------------------------------------


def test_identificar_documento_reconhece_cpf():
    assert identificar_documento("529.982.247-25") == ("CPF", "529.982.247-25")


def test_identificar_documento_reconhece_cnpj():
    assert identificar_documento("11222333000181") == ("CNPJ", "11.222.333/0001-81")


def test_identificar_documento_recusa_cpf_com_digito_verificador_errado():
    with pytest.raises(ValueError, match="CPF inválido"):
        identificar_documento("111.111.111-11")


def test_identificar_documento_recusa_cnpj_com_digito_verificador_errado():
    with pytest.raises(ValueError, match="CNPJ inválido"):
        identificar_documento("11.222.333/0001-00")


def test_identificar_documento_recusa_quantidade_de_digitos_invalida():
    with pytest.raises(ValueError, match="CPF/CNPJ inválido"):
        identificar_documento("123")


# --- Rota /app/cartas/convite-cliente/texto ---------------------------------


def test_rota_texto_convite_cliente_sem_login_nao_acessa(client, db):
    resposta = client.post(
        "/app/cartas/convite-cliente/texto",
        data={"autor": "A", "reu": "B", "dia": "2026-10-15", "hora": "14:05", "link": "meet.google.com/x"},
        follow_redirects=False,
    )
    assert resposta.status_code != 200


def test_rota_texto_convite_cliente_valida_link(client, db):
    _logar_admin(db, client)
    resposta = client.post(
        "/app/cartas/convite-cliente/texto",
        data={"autor": "A", "reu": "B", "dia": "2026-10-15", "hora": "14:05", "link": "site-qualquer.com"},
    )
    assert resposta.status_code == 400
    assert "Link da audiência inválido" in resposta.json()["erro"]


def test_rota_texto_convite_cliente_retorna_o_mesmo_texto_do_servico(client, db):
    _logar_admin(db, client, "admin.cartas2@teste.local")
    resposta = client.post(
        "/app/cartas/convite-cliente/texto",
        data={
            "autor": "fulano da silva", "reu": "banco tal", "dia": "2026-10-15",
            "hora": "14:05", "link": "meet.google.com/abc-defg-hij",
        },
    )
    assert resposta.status_code == 200
    texto = resposta.json()["texto"]
    assert "AUTOR: FULANO DA SILVA" in texto
    assert "REU: BANCO TAL," in texto


# --- Rota /app/cartas/convite-banco/texto ------------------------------------


def test_rota_texto_convite_banco_valida_cpf(client, db):
    _logar_admin(db, client, "admin.cartas3@teste.local")
    resposta = client.post(
        "/app/cartas/convite-banco/texto",
        data={
            "banco_nome": "Banco Tal", "banco_cnpj": "00.000.000/0001-00", "nome": "Fulana",
            "cpf": "111.111.111-11", "contrato": "123", "data": "2026-11-03",
            "hora": "09:30", "link": "meet.google.com/x",
        },
    )
    assert resposta.status_code == 400
    assert "CPF inválido" in resposta.json()["erro"]


def test_rota_texto_convite_banco_retorna_o_mesmo_texto_do_servico(client, db):
    _logar_admin(db, client, "admin.cartas4@teste.local")
    resposta = client.post(
        "/app/cartas/convite-banco/texto",
        data={
            "banco_nome": "Banco Tal", "banco_cnpj": "00.000.000/0001-00", "nome": "Fulana de Tal",
            "cpf": "529.982.247-25", "contrato": "12345", "data": "2026-11-03",
            "hora": "09:30", "link": "teams.microsoft.com/l/meetup-join/xyz",
        },
    )
    assert resposta.status_code == 200
    texto = resposta.json()["texto"]
    assert "FULANA DE TAL, inscrito(a) no CPF: 529.982.247-25" in texto


def test_rota_texto_convite_banco_aceita_cnpj_no_campo_cpf(client, db):
    """2026-09-30, a pedido da Clara: o campo aceita CPF ou CNPJ."""
    _logar_admin(db, client, "admin.cartas5@teste.local")
    resposta = client.post(
        "/app/cartas/convite-banco/texto",
        data={
            "banco_nome": "Banco Tal", "banco_cnpj": "00.000.000/0001-00", "nome": "Empresa Titular Ltda",
            "cpf": "11.222.333/0001-81", "contrato": "12345", "data": "2026-11-03",
            "hora": "09:30", "link": "teams.microsoft.com/l/meetup-join/xyz",
        },
    )
    assert resposta.status_code == 200
    texto = resposta.json()["texto"]
    assert "EMPRESA TITULAR LTDA, inscrito(a) no CNPJ: 11.222.333/0001-81" in texto


# --- Regressão: nome longo não pode quebrar a geração do PDF ----------------
# 2026-09-30 — a Clara reportou a tela genérica de erro ao clicar "Gerar
# PDF". Causa real: `registrar()` grava o nome/autor em `entidade_id`
# (LogAuditoria), coluna que era VARCHAR(40) — em produção (Postgres) isso
# derruba a requisição inteira (`StringDataRightTruncation`) quando o nome
# passa de 40 caracteres, algo comum em nome empresarial/nome completo. O
# SQLite dos testes não aplica limite de VARCHAR de verdade, então esse
# teste não reproduz o crash em si, mas protege a coluna (`Text`, não
# `String(40)` — ver app/models.py) de guardar o valor pela metade.


def test_gerar_convite_cliente_com_nome_longo_nao_trunca_no_log_auditoria(client, db):
    _logar_admin(db, client, "admin.cartas6@teste.local")
    autor_longo = "Construtora e Incorporadora Atlântica Empreendimentos Imobiliários Ltda"
    resposta = client.post(
        "/app/cartas/convite-cliente",
        data={
            "autor": autor_longo, "reu": "Banco Tal", "dia": "2026-10-15",
            "hora": "14:05", "link": "meet.google.com/abc-defg-hij",
        },
    )
    assert resposta.status_code == 200
    assert resposta.headers["content-type"] == "application/pdf"
    log = db.scalar(
        select(LogAuditoria).where(LogAuditoria.acao == "GEROU_CARTA_CONVITE_CLIENTE").order_by(LogAuditoria.id.desc())
    )
    assert log.entidade_id == autor_longo.upper()

"""Cartas — Convite Cliente/Banco: geração de PDF (sem cobertura de testes
até então) e o botão "Copiar texto" (2026-09-29, a pedido da Clara:
"preciso que exatamente o mesmo conteúdo que vem escrito no PDF... venha
escrito em formato de texto pra copiar e colar")."""
from __future__ import annotations

from datetime import date

from app.auth import hash_senha
from app.models import Usuario
from app.services.cartas import (
    ConviteBanco,
    ConviteCliente,
    formatar_texto_carta_banco,
    formatar_texto_carta_cliente,
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
        cpf="529.982.247-25", contrato="12345", data=date(2026, 11, 3), hora="09H30",
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

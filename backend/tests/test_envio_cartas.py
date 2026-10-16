"""Geração e envio das duas Cartas Convite de uma SolicitacaoAudiencia
(Fase 1, 2026-10-16) — e-mail sempre mockado aqui, sem chamada de rede
real nos testes automatizados (ver app/services/email_postmark.py)."""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select

from app.auth import hash_senha
from app.models import EmpresaCliente, EnvioEmail, Usuario
from app.services import envio_cartas as ec
from app.services.bancos import criar_banco
from app.services.email_postmark import ErroEnvioEmail
from app.services.solicitacoes_audiencia import HorarioVago, reservar_horario

CNPJ_VALIDO = "11.222.333/0001-81"
CPF_VALIDO = "529.982.247-25"


@pytest.fixture()
def usuario(db):
    u = Usuario(nome="Fulana", email="fulana.envio@teste.com", senha_hash=hash_senha("x"))
    db.add(u)
    db.flush()
    return u


@pytest.fixture()
def empresa(db):
    e = EmpresaCliente(nome="ASSESSORIA TESTE")
    db.add(e)
    db.flush()
    return e


@pytest.fixture()
def banco(db):
    return criar_banco(db, "Banco Teste", CNPJ_VALIDO, "juridico@banco.com; ouvidoria@banco.com")


@pytest.fixture()
def solicitacao(db, usuario, empresa, banco):
    return reservar_horario(
        db, usuario, empresa.id, "Fulano de Tal", CPF_VALIDO, "fulano@teste.com", "11988887777",
        date(2026, 10, 1), "12345", banco.id, "meet.google.com/abc-defg-hij",
        HorarioVago(numero_linha=888, dia=date(2099, 11, 17), hora="14:30"),
    )


def test_montar_previas_gera_conteudo_esperado(db, solicitacao, banco):
    previas = ec.montar_previas(db, solicitacao)

    assert previas.cliente.destinatarios == ["fulano@teste.com"]
    assert "FULANO DE TAL" in previas.cliente.corpo_html
    assert previas.cliente.assunto == previas.banco.assunto
    assert "17 DE NOVEMBRO DE 2099" in previas.cliente.assunto
    assert "FULANO DE TAL" in previas.cliente.assunto


def test_montar_previas_sem_logo_nao_tem_tag_de_imagem(db, solicitacao):
    previas = ec.montar_previas(db, solicitacao)
    assert "<img" not in previas.cliente.corpo_html
    assert "<img" not in previas.banco.corpo_html


def test_montar_previas_banco_tem_todos_os_emails_separados(db, solicitacao):
    previas = ec.montar_previas(db, solicitacao)
    assert previas.banco.destinatarios == ["juridico@banco.com", "ouvidoria@banco.com"]


def _mock_envio_sucesso(monkeypatch, chamadas):
    def _fake(destinatarios, assunto, corpo_html, corpo_texto, anexos=None, imagens_inline=None):
        chamadas.append({"destinatarios": destinatarios, "anexos": anexos, "imagens_inline": imagens_inline})

    monkeypatch.setattr(ec.email_postmark, "enviar_email", _fake)


def test_enviar_emails_sucesso_registra_dois_envios_e_atualiza_status(db, solicitacao, usuario, monkeypatch):
    chamadas = []
    _mock_envio_sucesso(monkeypatch, chamadas)

    resultado = ec.enviar_emails(db, usuario, solicitacao)

    assert resultado.cliente_enviado is True
    assert resultado.banco_enviado is True
    assert len(chamadas) == 2
    envios = db.scalars(select(EnvioEmail).where(EnvioEmail.solicitacao_id == solicitacao.id)).all()
    assert {e.tipo for e in envios} == {"CLIENTE", "BANCO"}
    assert all(e.status == "ENVIADO" for e in envios)
    assert solicitacao.status == "EMAILS_ENVIADOS"


def test_enviar_emails_inclui_pdf_anexado_nos_dois(db, solicitacao, usuario, monkeypatch):
    chamadas = []
    _mock_envio_sucesso(monkeypatch, chamadas)

    ec.enviar_emails(db, usuario, solicitacao)

    for chamada in chamadas:
        assert len(chamada["anexos"]) == 1
        _nome, conteudo, tipo_mime = chamada["anexos"][0]
        assert tipo_mime == "application/pdf"
        assert conteudo[:4] == b"%PDF"


def test_enviar_emails_falha_no_cliente_nao_impede_envio_do_banco(db, solicitacao, usuario, monkeypatch):
    def _fake(destinatarios, assunto, corpo_html, corpo_texto, anexos=None, imagens_inline=None):
        if "fulano@teste.com" in destinatarios:
            raise ErroEnvioEmail("Postmark recusou (simulado)")

    monkeypatch.setattr(ec.email_postmark, "enviar_email", _fake)

    resultado = ec.enviar_emails(db, usuario, solicitacao)

    assert resultado.cliente_enviado is False
    assert "simulado" in resultado.cliente_erro
    assert resultado.banco_enviado is True
    assert solicitacao.status != "EMAILS_ENVIADOS"
    envio_cliente = db.scalar(select(EnvioEmail).where(EnvioEmail.tipo == "CLIENTE"))
    assert envio_cliente.status == "ERRO"
    assert envio_cliente.erro == "Postmark recusou (simulado)"


def test_enviar_emails_sucesso_atualiza_notificacao_na_planilha(db, solicitacao, usuario, monkeypatch):
    chamadas_sheets = {}
    _mock_envio_sucesso(monkeypatch, [])
    monkeypatch.setattr(
        ec.google_sheets, "escrever_valores",
        lambda spreadsheet_id, aba, numero, valores: chamadas_sheets.update(numero=numero, valores=valores),
    )

    ec.enviar_emails(db, usuario, solicitacao, spreadsheet_id="planilha-fake-id")

    assert chamadas_sheets["numero"] == solicitacao.linha_planilha
    assert chamadas_sheets["valores"] == {"NOTIFICAÇÃO": "CLIENTE E BANCO"}


def test_enviar_emails_falha_parcial_nao_toca_notificacao(db, solicitacao, usuario, monkeypatch):
    chamou_sheets = []

    def _fake_envio(destinatarios, assunto, corpo_html, corpo_texto, anexos=None, imagens_inline=None):
        if "fulano@teste.com" in destinatarios:
            raise ErroEnvioEmail("falhou")

    monkeypatch.setattr(ec.email_postmark, "enviar_email", _fake_envio)
    monkeypatch.setattr(
        ec.google_sheets, "escrever_valores",
        lambda spreadsheet_id, aba, numero, valores: chamou_sheets.append(1),
    )

    ec.enviar_emails(db, usuario, solicitacao, spreadsheet_id="planilha-fake-id")

    assert chamou_sheets == []


def test_enviar_emails_inclui_logo_inline_quando_arquivo_existe(db, solicitacao, usuario, monkeypatch):
    """O arquivo de timbrado é o mesmo já usado no PDF (audiencias_logo_0.jpeg,
    ver app/pdf_export.py) — este teste confia que ele existe de verdade em
    app/assets/, não mocka o caminho."""
    chamadas = []
    _mock_envio_sucesso(monkeypatch, chamadas)

    ec.enviar_emails(db, usuario, solicitacao)

    assert all(c["imagens_inline"] is not None for c in chamadas)
    content_id, _conteudo, tipo_mime = chamadas[0]["imagens_inline"][0]
    assert content_id == "logo-carta"
    assert tipo_mime == "image/jpeg"

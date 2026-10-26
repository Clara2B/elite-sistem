"""Tela /app/bancos (Fase 1 — Solicitação de Audiência, 2026-10-16) — mesmo
acesso de Audiências/Cartas (módulo "AUDIENCIAS"), a pedido da Clara: sem
módulo novo só pra isso."""
from __future__ import annotations

import io

import openpyxl
from sqlalchemy import select

from app.auth import hash_senha
from app.config import settings as app_settings
from app.models import Banco, Setor, Usuario, UsuarioSetor
from app.services import bancos as bancos_service

CNPJ_VALIDO = "11.222.333/0001-81"


def _logar_admin(db, client, email="admin.bancos@teste.com"):
    db.add(Usuario(nome="Admin", email=email, senha_hash=hash_senha("certa"), papel_global="ADMIN_SUPERIOR"))
    db.commit()
    client.post("/login", data={"email": email, "senha": "certa"})


def _logar_colaborador_eximia(db, client, email="colab.eximia.bancos@teste.com"):
    """Setor "Financeiro" da EXIMIA, sem nenhuma linha em SetorModulo —
    estado padrão, libera todos os módulos válidos pra EXIMIA (AUDIENCIAS
    incluído), mesmo sem papel_global nenhum."""
    setor = db.scalar(select(Setor).where(Setor.nome == "Financeiro", Setor.operadora.has(nome="EXIMIA")))
    usuario = Usuario(nome="Colaboradora EXIMIA", email=email, senha_hash=hash_senha("certa"))
    db.add(usuario)
    db.flush()
    db.add(UsuarioSetor(usuario_id=usuario.id, setor_id=setor.id, papel="COLABORADOR"))
    db.commit()
    client.post("/login", data={"email": email, "senha": "certa"})


def _logar_colaborador_sem_setor(db, client, email="colab.sem.setor.bancos@teste.com"):
    db.add(Usuario(nome="Sem Setor", email=email, senha_hash=hash_senha("certa")))
    db.commit()
    client.post("/login", data={"email": email, "senha": "certa"})


def test_acesso_exige_modulo_audiencias(client, db):
    _logar_colaborador_sem_setor(db, client)
    resposta = client.get("/app/bancos")
    assert resposta.status_code == 403


def test_colaborador_com_acesso_a_audiencias_acessa_bancos(client, db):
    _logar_colaborador_eximia(db, client)
    resposta = client.get("/app/bancos")
    assert resposta.status_code == 200


def test_criar_banco_pela_tela(client, db):
    _logar_admin(db, client)
    resposta = client.post(
        "/app/bancos", data={"nome": "Banco XPTO", "cnpj": CNPJ_VALIDO, "email": "contato@xpto.com.br"},
    )
    assert resposta.status_code == 200
    assert "Banco XPTO" in resposta.text
    banco = db.scalar(select(Banco).where(Banco.nome == "Banco XPTO"))
    assert banco is not None
    assert banco.cnpj == CNPJ_VALIDO


def test_criar_banco_com_cnpj_invalido_mostra_erro(client, db):
    _logar_admin(db, client)
    resposta = client.post(
        "/app/bancos", data={"nome": "Banco Invalido", "cnpj": "123", "email": "x@x.com"},
    )
    assert resposta.status_code == 400
    assert "CNPJ" in resposta.text
    assert db.scalar(select(Banco).where(Banco.nome == "Banco Invalido")) is None


def test_editar_banco_pela_tela(client, db):
    _logar_admin(db, client)
    db.add(Banco(nome="Banco Antigo", cnpj=CNPJ_VALIDO, email="antigo@x.com"))
    db.commit()
    banco = db.scalar(select(Banco).where(Banco.nome == "Banco Antigo"))

    resposta = client.post(
        f"/app/bancos/{banco.id}",
        data={"nome": "Banco Novo Nome", "cnpj": CNPJ_VALIDO, "email": "novo@x.com"},
    )
    assert resposta.status_code == 200
    db.refresh(banco)
    assert banco.nome == "Banco Novo Nome"
    assert banco.email == "novo@x.com"


def test_ativar_desativar_banco_pela_tela(client, db):
    _logar_admin(db, client)
    db.add(Banco(nome="Banco Toggle", cnpj=CNPJ_VALIDO, email="toggle@x.com"))
    db.commit()
    banco = db.scalar(select(Banco).where(Banco.nome == "Banco Toggle"))

    resposta = client.post(f"/app/bancos/{banco.id}/ativo?ativo=false", follow_redirects=False)
    assert resposta.status_code == 303
    db.refresh(banco)
    assert banco.ativo is False

    client.post(f"/app/bancos/{banco.id}/ativo?ativo=true", follow_redirects=False)
    db.refresh(banco)
    assert banco.ativo is True


def test_excluir_banco_pela_tela(client, db):
    _logar_admin(db, client)
    db.add(Banco(nome="Banco Excluir", cnpj=CNPJ_VALIDO, email="excluir@x.com"))
    db.commit()
    banco = db.scalar(select(Banco).where(Banco.nome == "Banco Excluir"))

    resposta = client.post(f"/app/bancos/{banco.id}/excluir", follow_redirects=False)
    assert resposta.status_code == 303
    assert db.get(Banco, banco.id) is None


def _planilha_bytes(linhas, cabecalho=("BANCO", "CNPJ", "EMAIL")) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(list(cabecalho))
    for linha in linhas:
        ws.append(list(linha))
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def test_importar_planilha_pela_tela(client, db):
    _logar_admin(db, client)
    arquivo = _planilha_bytes([("Banco XPTO", CNPJ_VALIDO, "contato@xpto.com.br")])

    resposta = client.post(
        "/app/bancos/import",
        files={"arquivo": ("bancos.xlsx", arquivo, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resposta.status_code == 200
    assert "1 criado" in resposta.text
    assert db.scalar(select(Banco).where(Banco.nome == "Banco XPTO")) is not None


def test_importar_da_planilha_google_pela_tela(client, db, monkeypatch):
    """A leitura em si é mockada (sem rede/credencial real nos testes
    automatizados) — só confirma que a rota liga a tela ao serviço certo."""
    _logar_admin(db, client)
    monkeypatch.setattr(app_settings, "google_sheets_id", "planilha-fake-id")
    linha = {"BANCOS ": "Banco XPTO", "E-MAIL": "contato@xpto.com.br", "CNPJ": CNPJ_VALIDO, "2° OPÇÃO CNPJ": ""}
    monkeypatch.setattr(bancos_service.google_sheets, "ler_aba", lambda spreadsheet_id, aba: [linha])

    resposta = client.post("/app/bancos/importar-da-planilha")

    assert resposta.status_code == 200
    assert "1 criado" in resposta.text
    assert db.scalar(select(Banco).where(Banco.nome == "Banco XPTO")) is not None


def test_importar_da_planilha_google_sem_id_configurado_mostra_erro(client, db, monkeypatch):
    _logar_admin(db, client)
    monkeypatch.setattr(app_settings, "google_sheets_id", None)

    resposta = client.post("/app/bancos/importar-da-planilha")

    assert resposta.status_code == 400
    assert "GOOGLE_SHEETS_ID" in resposta.text

"""Tela /app/solicitacoes-audiencia (Fase 1, 2026-10-16) — mesmo acesso de
Audiências/Cartas/Bancos (módulo "AUDIENCIAS"). A leitura/escrita na
planilha de controle é sempre mockada aqui — sem rede/credencial real nos
testes automatizados (ver app/services/google_sheets.py)."""
from __future__ import annotations

from datetime import date

from sqlalchemy import select

from app.auth import hash_senha
from app.config import settings as app_settings
from app.models import EmpresaCliente, EnvioEmail, SolicitacaoAudiencia, Usuario
from app.services import envio_cartas as ec
from app.services import solicitacoes_audiencia as sa
from app.services.bancos import criar_banco
from app.services.email_postmark import ErroEnvioEmail

CNPJ_VALIDO = "11.222.333/0001-81"
CNPJ_VALIDO_2 = "11.444.777/0001-61"
CPF_VALIDO = "529.982.247-25"


def _logar_admin(db, client, email="admin.solicitacao@teste.com"):
    db.add(Usuario(nome="Admin", email=email, senha_hash=hash_senha("certa"), papel_global="ADMIN_SUPERIOR"))
    db.commit()
    client.post("/login", data={"email": email, "senha": "certa"})


def _logar_sem_setor(db, client, email="sem.setor.solicitacao@teste.com"):
    db.add(Usuario(nome="Sem Setor", email=email, senha_hash=hash_senha("certa")))
    db.commit()
    client.post("/login", data={"email": email, "senha": "certa"})


def _preparar(db):
    empresa = EmpresaCliente(nome="ASSESSORIA TESTE")
    db.add(empresa)
    db.flush()
    banco = criar_banco(db, "Banco Teste", CNPJ_VALIDO, "contato@banco.com")
    return empresa, banco


def _dados_form(empresa, banco):
    return {
        "empresa_cliente_id": str(empresa.id),
        "nome_cliente": "Fulano de Tal",
        "cpf_cliente": CPF_VALIDO,
        "email_cliente": "fulano@teste.com",
        "telefone_cliente": "11988887777",
        "data_recebimento": "2026-10-01",
        "numero_contrato": "12345",
        "banco_id": str(banco.id),
        "link_audiencia": "meet.google.com/abc-defg-hij",
    }


def test_acesso_exige_modulo_audiencias(client, db):
    _logar_sem_setor(db, client)
    assert client.get("/app/solicitacoes-audiencia").status_code == 403


def test_tela_mostra_assessorias_e_bancos(client, db):
    empresa, banco = _preparar(db)
    _logar_admin(db, client)

    resposta = client.get("/app/solicitacoes-audiencia")

    assert resposta.status_code == 200
    assert empresa.nome in resposta.text
    assert banco.nome in resposta.text


def test_tela_inclui_cnpj_alternativo_do_banco_na_opcao(client, db):
    _preparar(db)
    banco_dois_cnpjs = criar_banco(db, "Banco Dois CNPJs", CNPJ_VALIDO, "contato@x.com", cnpj_alternativo=CNPJ_VALIDO_2)
    _logar_admin(db, client)

    resposta = client.get("/app/solicitacoes-audiencia")

    assert f'data-cnpj-alt="{CNPJ_VALIDO_2}"' in resposta.text
    assert f'value="{banco_dois_cnpjs.id}"' in resposta.text


def test_buscar_horario_sem_vaga_mostra_erro(client, db, monkeypatch):
    empresa, banco = _preparar(db)
    _logar_admin(db, client)
    monkeypatch.setattr(app_settings, "google_sheets_id", "planilha-fake-id")
    monkeypatch.setattr(sa.google_sheets, "ler_aba_com_numero_linha", lambda spreadsheet_id, aba: [])

    resposta = client.post("/app/solicitacoes-audiencia/buscar-horario", data=_dados_form(empresa, banco))

    assert resposta.status_code == 400
    assert "Não há nenhum horário vago" in resposta.text


def test_buscar_horario_com_campo_faltando_mostra_erro(client, db):
    empresa, banco = _preparar(db)
    _logar_admin(db, client)
    dados = _dados_form(empresa, banco)
    dados["nome_cliente"] = ""

    resposta = client.post("/app/solicitacoes-audiencia/buscar-horario", data=dados)

    assert resposta.status_code == 400
    assert "obrigatórios" in resposta.text.lower()


def test_buscar_horario_encontra_vaga_mostra_previa(client, db, monkeypatch):
    empresa, banco = _preparar(db)
    _logar_admin(db, client)
    monkeypatch.setattr(app_settings, "google_sheets_id", "planilha-fake-id")
    linha_vaga = {"DATA DE AGENDAMENTO": "17/11/2099 - 09:00"}
    monkeypatch.setattr(sa.google_sheets, "ler_aba_com_numero_linha", lambda spreadsheet_id, aba: [(888, linha_vaga)])

    resposta = client.post("/app/solicitacoes-audiencia/buscar-horario", data=_dados_form(empresa, banco))

    assert resposta.status_code == 200
    assert "17/11/2099" in resposta.text
    assert "09:00" in resposta.text
    # a prévia carrega os dados originais como campos ocultos, prontos pra confirmar
    assert 'name="numero_linha" value="888"' in resposta.text


def _dados_confirmar(empresa, banco, numero_linha=888, dia="2099-11-17", hora="09:00"):
    dados = _dados_form(empresa, banco)
    dados.update({"numero_linha": str(numero_linha), "dia": dia, "hora": hora})
    return dados


def test_confirmar_grava_quando_ainda_vaga(client, db, monkeypatch):
    empresa, banco = _preparar(db)
    _logar_admin(db, client)
    monkeypatch.setattr(app_settings, "google_sheets_id", "planilha-fake-id")
    monkeypatch.setattr(
        sa.google_sheets, "ler_linha",
        lambda spreadsheet_id, aba, numero: {"DATA DE AGENDAMENTO": "17/11/2099 - 09:00"},
    )
    chamadas = {}
    monkeypatch.setattr(
        sa.google_sheets, "escrever_valores",
        lambda spreadsheet_id, aba, numero, valores: chamadas.update(numero=numero, valores=valores),
    )

    resposta = client.post("/app/solicitacoes-audiencia/confirmar", data=_dados_confirmar(empresa, banco))

    assert resposta.status_code == 200
    assert "gravada" in resposta.text.lower()
    assert chamadas["numero"] == 888
    assert chamadas["valores"]["NOME COMPLETO"] == "Fulano de Tal"
    solicitacao = db.scalar(select(SolicitacaoAudiencia))
    assert solicitacao.status == "GRAVADA"
    assert solicitacao.linha_planilha == 888
    # Mostra as prévias dos dois e-mails, prontas pra enviar.
    assert "Prévia — E-mail ao Cliente" in resposta.text
    assert "Prévia — E-mail ao Banco" in resposta.text
    assert f'action="/app/solicitacoes-audiencia/{solicitacao.id}/enviar-emails"' in resposta.text


def test_confirmar_com_cnpj_alternativo_grava_a_escolha_e_usa_na_carta(client, db, monkeypatch):
    empresa, _ = _preparar(db)
    banco_dois_cnpjs = criar_banco(db, "Banco Dois CNPJs", CNPJ_VALIDO, "contato@x.com", cnpj_alternativo=CNPJ_VALIDO_2)
    _logar_admin(db, client)
    monkeypatch.setattr(app_settings, "google_sheets_id", "planilha-fake-id")
    monkeypatch.setattr(
        sa.google_sheets, "ler_linha",
        lambda spreadsheet_id, aba, numero: {"DATA DE AGENDAMENTO": "17/11/2099 - 09:00"},
    )
    monkeypatch.setattr(sa.google_sheets, "escrever_valores", lambda *a, **k: None)
    dados = _dados_confirmar(empresa, banco_dois_cnpjs)
    dados["usar_cnpj_alternativo"] = "1"

    resposta = client.post("/app/solicitacoes-audiencia/confirmar", data=dados)

    assert resposta.status_code == 200
    solicitacao = db.scalar(select(SolicitacaoAudiencia))
    assert solicitacao.usar_cnpj_alternativo is True
    assert CNPJ_VALIDO_2 in resposta.text
    assert CNPJ_VALIDO not in resposta.text


def test_confirmar_com_cpf_invalido_nao_cria_solicitacao(client, db, monkeypatch):
    empresa, banco = _preparar(db)
    _logar_admin(db, client)
    monkeypatch.setattr(app_settings, "google_sheets_id", "planilha-fake-id")
    dados = _dados_confirmar(empresa, banco)
    dados["cpf_cliente"] = "123"

    resposta = client.post("/app/solicitacoes-audiencia/confirmar", data=dados)

    assert resposta.status_code == 409
    assert db.query(SolicitacaoAudiencia).count() == 0


def test_confirmar_quando_linha_nao_esta_mais_vaga_busca_proxima(client, db, monkeypatch):
    """Alguém gravou na planilha por fora (ou outra solicitação venceu a
    corrida) — o sistema busca a próxima vaga e mostra de novo, sem o
    usuário perder os dados já digitados."""
    empresa, banco = _preparar(db)
    _logar_admin(db, client)
    monkeypatch.setattr(app_settings, "google_sheets_id", "planilha-fake-id")
    monkeypatch.setattr(
        sa.google_sheets, "ler_linha",
        lambda spreadsheet_id, aba, numero: {"NOME COMPLETO": "Alguem Mais Rapido", "DATA DE AGENDAMENTO": "17/11/2099 - 09:00"},
    )
    monkeypatch.setattr(
        sa.google_sheets, "ler_aba_com_numero_linha",
        lambda spreadsheet_id, aba: [(999, {"DATA DE AGENDAMENTO": "18/11/2099 - 10:00"})],
    )

    resposta = client.post("/app/solicitacoes-audiencia/confirmar", data=_dados_confirmar(empresa, banco))

    assert resposta.status_code == 409
    assert "18/11/2099" in resposta.text
    assert 'name="numero_linha" value="999"' in resposta.text
    # a solicitação perdida fica registrada como falha, não desaparece
    solicitacao = db.scalar(select(SolicitacaoAudiencia))
    assert solicitacao.status == "FALHOU"


def test_confirmar_perde_a_corrida_no_banco_busca_proxima(client, db, monkeypatch):
    """Duas solicitações pra mesma linha: a que chega primeiro aqui (via
    reservar_horario já commitado antes do POST) vence; esta busca a
    vaga seguinte."""
    empresa, banco = _preparar(db)
    _logar_admin(db, client)
    usuario = db.scalar(select(Usuario))
    sa.reservar_horario(
        db, usuario, empresa.id, "Primeiro", CPF_VALIDO, "primeiro@teste.com", "11988887777",
        date.today(), "999", banco.id, "meet.google.com/zzz-yyyy-xxx",
        sa.HorarioVago(numero_linha=888, dia=date(2099, 11, 17), hora="09:00"),
    )
    monkeypatch.setattr(app_settings, "google_sheets_id", "planilha-fake-id")
    monkeypatch.setattr(
        sa.google_sheets, "ler_aba_com_numero_linha",
        lambda spreadsheet_id, aba: [(999, {"DATA DE AGENDAMENTO": "18/11/2099 - 10:00"})],
    )

    resposta = client.post("/app/solicitacoes-audiencia/confirmar", data=_dados_confirmar(empresa, banco))

    assert resposta.status_code == 409
    assert "18/11/2099" in resposta.text
    assert db.query(SolicitacaoAudiencia).count() == 1


def _criar_solicitacao_gravada(db, empresa, banco):
    usuario = db.scalar(select(Usuario))
    return sa.reservar_horario(
        db, usuario, empresa.id, "Fulano de Tal", CPF_VALIDO, "fulano@teste.com", "11988887777",
        date.today(), "12345", banco.id, "meet.google.com/abc-defg-hij",
        sa.HorarioVago(numero_linha=888, dia=date(2099, 11, 17), hora="14:30"),
    )


def test_enviar_emails_sucesso(client, db, monkeypatch):
    empresa, banco = _preparar(db)
    _logar_admin(db, client)
    solicitacao = _criar_solicitacao_gravada(db, empresa, banco)
    monkeypatch.setattr(ec.email_postmark, "enviar_email", lambda *a, **k: None)

    resposta = client.post(f"/app/solicitacoes-audiencia/{solicitacao.id}/enviar-emails")

    assert resposta.status_code == 200
    assert "enviados" in resposta.text.lower()
    db.refresh(solicitacao)
    assert solicitacao.status == "EMAILS_ENVIADOS"
    assert db.query(EnvioEmail).count() == 2


def test_enviar_emails_solicitacao_inexistente(client, db):
    _preparar(db)
    _logar_admin(db, client)

    resposta = client.post("/app/solicitacoes-audiencia/99999/enviar-emails")

    assert resposta.status_code == 404


def test_enviar_emails_falha_mostra_erro_e_permite_tentar_de_novo(client, db, monkeypatch):
    empresa, banco = _preparar(db)
    _logar_admin(db, client)
    solicitacao = _criar_solicitacao_gravada(db, empresa, banco)

    def _falha(destinatarios, *a, **k):
        if "fulano@teste.com" in destinatarios:
            raise ErroEnvioEmail("Postmark indisponível")

    monkeypatch.setattr(ec.email_postmark, "enviar_email", _falha)

    resposta = client.post(f"/app/solicitacoes-audiencia/{solicitacao.id}/enviar-emails")

    assert resposta.status_code == 502
    assert "Postmark indisponível" in resposta.text
    assert "Prévia — E-mail ao Cliente" in resposta.text
    db.refresh(solicitacao)
    assert solicitacao.status != "EMAILS_ENVIADOS"

    # tenta de novo, agora sem falha — reenvio funciona
    monkeypatch.setattr(ec.email_postmark, "enviar_email", lambda *a, **k: None)
    resposta2 = client.post(f"/app/solicitacoes-audiencia/{solicitacao.id}/enviar-emails")
    assert resposta2.status_code == 200
    db.refresh(solicitacao)
    assert solicitacao.status == "EMAILS_ENVIADOS"
    # 1ª tentativa: cliente ERRO + banco ENVIADO; 2ª tentativa: os dois ENVIADO.
    assert db.query(EnvioEmail).count() == 4

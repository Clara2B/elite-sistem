from datetime import date, datetime

import pytest

from app.auth import hash_senha
from app.models import EmpresaCliente, SolicitacaoAudiencia, Usuario
from app.services import solicitacoes_audiencia as sa
from app.services.bancos import criar_banco

CNPJ_VALIDO = "11.222.333/0001-81"
CPF_VALIDO = "529.982.247-25"


def test_parse_data_agendamento_formato_normal():
    assert sa.parse_data_agendamento("30/06/2026 - 14:00") == (date(2026, 6, 30), "14:00")


def test_parse_data_agendamento_tolera_ponto_e_virgula():
    """Erro de digitação real visto na planilha (';' em vez de ':')."""
    assert sa.parse_data_agendamento("01/07/2026 - 14;00") == (date(2026, 7, 1), "14:00")


@pytest.mark.parametrize("texto", ["", "qualquer coisa", "30/06/2026", "32/13/2026 - 14:00", None])
def test_parse_data_agendamento_formato_invalido_devolve_none(texto):
    assert sa.parse_data_agendamento(texto) is None


def test_formatar_data_agendamento_sempre_no_formato_canonico():
    assert sa.formatar_data_agendamento(date(2026, 11, 5), "15:00") == "05/11/2026 - 15:00"


@pytest.mark.parametrize("telefone", ["(31) 97154-6133", "66 8132-1584", "9887809217", "4799925-1107"])
def test_telefone_valido_aceita_formatos_variados(telefone):
    assert sa.telefone_valido(telefone) is True


@pytest.mark.parametrize("telefone", ["", "123", "99999999999999"])
def test_telefone_valido_rejeita_digitos_insuficientes_ou_excessivos(telefone):
    assert sa.telefone_valido(telefone) is False


@pytest.mark.parametrize("email", ["fulano@teste.com", "a.b@x.com.br"])
def test_email_valido_aceita_formatos_basicos(email):
    assert sa.email_valido(email) is True


@pytest.mark.parametrize("email", ["", "fulano", "fulano@", "@teste.com"])
def test_email_valido_rejeita_formatos_invalidos(email):
    assert sa.email_valido(email) is False


def _linha(data_recebimento="", empresa="", nome="", data_agendamento="", link="", cpf="", email="", telefone="", banco="", conciliadora="", advogada=""):
    return {
        "DATA DE RECEBIMENTO": data_recebimento, "EMPRESA": empresa, "NOME COMPLETO": nome,
        "DATA DE AGENDAMENTO": data_agendamento, "LINK": link, "CONCILIADORA": conciliadora,
        "ADVOGADA": advogada, "CPF": cpf, "E-MAIL": email, "TELEFONE": telefone, "BANCO": banco,
    }


def test_encontra_a_primeira_vaga_de_verdade(monkeypatch):
    """Pula a linha ocupada (data passada) e a 'EXTRA', acha a vaga de
    verdade."""
    linhas = [
        (2, _linha(data_agendamento="30/06/2020 - 14:00")),  # data no passado
        (3, _linha(nome="EXTRA", data_agendamento="17/11/2099 - 08:30", conciliadora="SUELY")),  # EXTRA não é vaga
        (4, _linha(data_agendamento="17/11/2099 - 09:00", conciliadora="SUELY")),  # vaga de verdade
        (5, _linha(data_agendamento="17/11/2099 - 09:30")),
    ]
    monkeypatch.setattr(sa.google_sheets, "ler_aba_com_numero_linha", lambda spreadsheet_id, aba: linhas)

    horario = sa.encontrar_proximo_horario_vago("fake-id", datetime(2026, 10, 16, 12, 0))  # noqa: DTZ001

    assert horario == sa.HorarioVago(numero_linha=4, dia=date(2099, 11, 17), hora="09:00")


def test_pula_linha_com_dados_preenchidos_mas_nome_vazio():
    """Regressão real: uma linha da planilha tinha tudo preenchido (empresa,
    link, cpf, e-mail, telefone, banco) menos o nome — erro de digitação
    antigo, não uma vaga."""
    linha = _linha(
        empresa="WNR CONSULTORIA", data_agendamento="17/11/2099 - 14:30", link="meet.google.com/x",
        cpf="000.000.000-01", email="x@x.com", telefone="11999999999", banco="BANCO X",
    )
    assert sa._linha_ainda_vaga(linha) is False


def test_nao_encontra_vaga_quando_todas_as_linhas_estao_ocupadas(monkeypatch):
    linhas = [(2, _linha(nome="Fulano", data_agendamento="17/11/2099 - 09:00"))]
    monkeypatch.setattr(sa.google_sheets, "ler_aba_com_numero_linha", lambda spreadsheet_id, aba: linhas)

    assert sa.encontrar_proximo_horario_vago("fake-id", datetime(2026, 10, 16, 12, 0)) is None  # noqa: DTZ001


def test_ignora_linha_com_data_de_agendamento_nao_reconhecida(monkeypatch):
    linhas = [
        (2, _linha(data_agendamento="texto qualquer")),
        (3, _linha(data_agendamento="17/11/2099 - 09:00")),
    ]
    monkeypatch.setattr(sa.google_sheets, "ler_aba_com_numero_linha", lambda spreadsheet_id, aba: linhas)

    horario = sa.encontrar_proximo_horario_vago("fake-id", datetime(2026, 10, 16, 12, 0))  # noqa: DTZ001
    assert horario.numero_linha == 3


@pytest.fixture()
def usuario(db):
    u = Usuario(nome="Fulana", email="fulana.solicitacao@teste.com", senha_hash=hash_senha("x"))
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
    return criar_banco(db, "Banco Teste", CNPJ_VALIDO, "contato@banco.com")


def _horario():
    return sa.HorarioVago(numero_linha=888, dia=date(2099, 11, 17), hora="14:30")


def test_reservar_horario_cria_solicitacao(db, usuario, empresa, banco):
    solicitacao = sa.reservar_horario(
        db, usuario, empresa.id, "Fulano de Tal", CPF_VALIDO, "fulano@teste.com", "11988887777",
        date.today(), "12345", banco.id, "meet.google.com/abc-defg-hij", _horario(),
    )
    assert solicitacao.id is not None
    assert solicitacao.status == "RESERVADA"
    assert solicitacao.linha_planilha == 888
    assert solicitacao.cpf_cliente == CPF_VALIDO


def test_reservar_horario_com_cpf_invalido_eh_rejeitado(db, usuario, empresa, banco):
    with pytest.raises(ValueError, match="CPF"):
        sa.reservar_horario(
            db, usuario, empresa.id, "Fulano", "123", "fulano@teste.com", "11988887777",
            date.today(), "12345", banco.id, "meet.google.com/abc-defg-hij", _horario(),
        )


def test_reservar_horario_ja_reservado_por_outra_solicitacao_levanta_erro(db, usuario, empresa, banco):
    """O núcleo do travamento otimista: duas solicitações pra mesma linha —
    só a primeira a comitar vence."""
    sa.reservar_horario(
        db, usuario, empresa.id, "Primeiro", CPF_VALIDO, "primeiro@teste.com", "11988887777",
        date.today(), "111", banco.id, "meet.google.com/aaa-bbbb-ccc", _horario(),
    )
    with pytest.raises(sa.HorarioJaOcupado):
        sa.reservar_horario(
            db, usuario, empresa.id, "Segundo", "529.982.247-25", "segundo@teste.com", "11988887777",
            date.today(), "222", banco.id, "meet.google.com/ddd-eeee-fff", _horario(),
        )
    assert db.query(SolicitacaoAudiencia).count() == 1


def test_confirmar_na_planilha_grava_quando_ainda_vaga(db, usuario, empresa, banco, monkeypatch):
    solicitacao = sa.reservar_horario(
        db, usuario, empresa.id, "Fulano de Tal", CPF_VALIDO, "fulano@teste.com", "11988887777",
        date(2026, 10, 1), "12345", banco.id, "meet.google.com/abc-defg-hij", _horario(),
    )
    monkeypatch.setattr(sa.google_sheets, "ler_linha", lambda spreadsheet_id, aba, numero: _linha(data_agendamento="17/11/2099 - 14:30"))
    chamadas = {}
    monkeypatch.setattr(
        sa.google_sheets, "escrever_valores",
        lambda spreadsheet_id, aba, numero, valores: chamadas.update(numero=numero, valores=valores),
    )

    sa.confirmar_na_planilha(db, "fake-id", solicitacao)

    assert solicitacao.status == "GRAVADA"
    assert chamadas["numero"] == 888
    assert chamadas["valores"]["NOME COMPLETO"] == "Fulano de Tal"
    assert chamadas["valores"]["EMPRESA"] == "ASSESSORIA TESTE"
    assert chamadas["valores"]["BANCO"] == "Banco Teste"
    assert chamadas["valores"]["CPF"] == CPF_VALIDO


def test_confirmar_na_planilha_rejeita_quando_linha_nao_esta_mais_vaga(db, usuario, empresa, banco, monkeypatch):
    solicitacao = sa.reservar_horario(
        db, usuario, empresa.id, "Fulano de Tal", CPF_VALIDO, "fulano@teste.com", "11988887777",
        date(2026, 10, 1), "12345", banco.id, "meet.google.com/abc-defg-hij", _horario(),
    )
    monkeypatch.setattr(
        sa.google_sheets, "ler_linha",
        lambda spreadsheet_id, aba, numero: _linha(nome="Alguem Mais Rapido", data_agendamento="17/11/2099 - 14:30"),
    )

    with pytest.raises(sa.HorarioJaOcupado):
        sa.confirmar_na_planilha(db, "fake-id", solicitacao)

    assert solicitacao.status == "FALHOU"

import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

import openpyxl

from app.models import EventoProcesso, Processo
from app.services.empresas import get_or_create_empresa
from app.services.processos import (
    PROCESSO_PARADO_DIAS,
    _mes_referencia_da_aba,
    _pessoa_valida,
    gerar_relatorio,
    importar_planilha,
    marcar_resolvido,
    status_prazo,
)


def _processo(db, numero="5012298-14.2025.8.13.0231", advogada="DRA KELLY", assistente="DANILO"):
    empresa = get_or_create_empresa(db, "ABSOLUTA")
    processo = Processo(
        numero_processo=numero,
        empresa_cliente_id=empresa.id,
        nome_cliente="Fulano de Tal",
        advogada=advogada,
        assistente=assistente,
    )
    db.add(processo)
    db.commit()
    return processo


def test_status_prazo_pendente_quando_ainda_nao_venceu(db):
    processo = _processo(db)
    evento = EventoProcesso(
        processo_id=processo.id, data=date(2026, 9, 1), tipo_evento_nome="CUSTAS",
        prazo_fatal=True, data_prazo=date.today() + timedelta(days=5),
    )
    assert status_prazo(evento) == "PENDENTE"


def test_status_prazo_perdido_quando_vencido_sem_resolver(db):
    processo = _processo(db)
    evento = EventoProcesso(
        processo_id=processo.id, data=date(2026, 9, 1), tipo_evento_nome="CUSTAS",
        prazo_fatal=True, data_prazo=date.today() - timedelta(days=2),
    )
    assert status_prazo(evento) == "PERDIDO"


def test_status_prazo_cumprido_quando_resolvido_antes(db):
    processo = _processo(db)
    prazo = date.today() + timedelta(days=3)
    evento = EventoProcesso(
        processo_id=processo.id, data=date(2026, 9, 1), tipo_evento_nome="CUSTAS",
        prazo_fatal=True, data_prazo=prazo, resolvido=True,
        resolvido_em=datetime.combine(prazo - timedelta(days=1), datetime.min.time()),
    )
    assert status_prazo(evento) == "CUMPRIDO"


def test_status_prazo_cumprido_com_atraso(db):
    processo = _processo(db)
    prazo = date.today() - timedelta(days=1)
    evento = EventoProcesso(
        processo_id=processo.id, data=date(2026, 9, 1), tipo_evento_nome="CUSTAS",
        prazo_fatal=True, data_prazo=prazo, resolvido=True,
        resolvido_em=datetime.combine(date.today(), datetime.min.time()),
    )
    assert status_prazo(evento) == "CUMPRIDO_COM_ATRASO"


def test_status_prazo_none_sem_data_prazo():
    from app.models import EventoProcesso as EP

    evento = EP(processo_id=1, data=date(2026, 9, 1), tipo_evento_nome="CUSTAS", prazo_fatal=True)
    assert status_prazo(evento) is None


def test_marcar_resolvido(db):
    processo = _processo(db)
    evento = EventoProcesso(
        processo_id=processo.id, data=date(2026, 9, 1), tipo_evento_nome="CUSTAS",
        prazo_fatal=True, data_prazo=date.today() + timedelta(days=1),
    )
    db.add(evento)
    db.commit()

    resolvido = marcar_resolvido(db, evento.id)
    assert resolvido.resolvido is True
    assert resolvido.resolvido_em is not None


def test_relatorio_conta_processos_eventos_e_prazos(db):
    processo = _processo(db, assistente="DANILO")
    db.add_all(
        [
            EventoProcesso(
                processo_id=processo.id, data=date(2026, 9, 5), tipo_evento_nome="CUSTAS",
                prazo_fatal=True, data_prazo=date.today() - timedelta(days=1),  # perdido
            ),
            EventoProcesso(
                processo_id=processo.id, data=date(2026, 9, 10), tipo_evento_nome="DOCUMENTOS",
                prazo_fatal=False,
            ),
        ]
    )
    db.commit()

    relatorio = gerar_relatorio(db, date(2026, 9, 1), date(2026, 9, 30))
    assert len(relatorio.linhas) == 1
    linha = relatorio.linhas[0]
    assert linha.pessoa == "DANILO"
    assert linha.processos == 1
    assert linha.eventos == 2
    assert linha.prazos_perdidos == 1
    assert relatorio.total.processos == 1
    assert relatorio.total.eventos == 2
    assert relatorio.total.pessoa == "EQUIPE (GERAL)"


def test_relatorio_filtra_por_pessoa(db):
    p1 = _processo(db, numero="1111111-11.2026.8.11.0001", assistente="DANILO")
    p2 = _processo(db, numero="2222222-22.2026.8.11.0002", assistente="JULIA")
    db.add_all(
        [
            EventoProcesso(processo_id=p1.id, data=date(2026, 9, 5), tipo_evento_nome="CUSTAS"),
            EventoProcesso(processo_id=p2.id, data=date(2026, 9, 5), tipo_evento_nome="CUSTAS"),
        ]
    )
    db.commit()

    relatorio = gerar_relatorio(db, date(2026, 9, 1), date(2026, 9, 30), filtro_pessoa="danilo")
    assert len(relatorio.linhas) == 1
    assert relatorio.linhas[0].pessoa == "DANILO"
    assert relatorio.total.pessoa == "TOTAL"  # não "EQUIPE (GERAL)" — só uma pessoa no relatório


def test_import_prazo_fatal_so_quando_coluna_e_sim(db, tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["CLIENTE", "Nº PROCESSO", "DATA", "EVENTO", "PRAZO FATAL"])
    numeros = [
        "1111111-11.2026.8.11.0001",
        "2222222-22.2026.8.11.0002",
        "3333333-33.2026.8.11.0003",
        "4444444-44.2026.8.11.0004",
    ]
    valores_prazo = ["SIM", "sim ", "NÃO", ""]
    for numero, valor in zip(numeros, valores_prazo, strict=True):
        ws.append(["ABSOLUTA - Fulano de Tal", numero, date(2026, 9, 1), "CUSTAS", valor])
    path = Path(tempfile.mkdtemp()) / "processos.xlsx"
    wb.save(path)

    importar_planilha(db, str(path))

    eventos = {e.processo.numero_processo: e for e in db.query(EventoProcesso).all()}
    assert eventos[numeros[0]].prazo_fatal is True  # "SIM"
    assert eventos[numeros[1]].prazo_fatal is True  # "sim " — normalizado
    assert eventos[numeros[2]].prazo_fatal is False  # "NÃO" não é fatal
    assert eventos[numeros[3]].prazo_fatal is False  # vazio não é fatal


def test_import_preenche_mes_referencia_a_partir_do_nome_da_aba(db):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "SETEMBRO26"
    ws.append(["CLIENTE", "Nº PROCESSO", "DATA", "EVENTO"])
    numero = "5555555-55.2026.8.11.0005"
    ws.append(["ABSOLUTA - Fulano de Tal", numero, date(2026, 9, 1), "CUSTAS"])
    path = Path(tempfile.mkdtemp()) / "processos.xlsx"
    wb.save(path)

    importar_planilha(db, str(path))

    evento = db.query(EventoProcesso).join(Processo).filter(Processo.numero_processo == numero).one()
    assert evento.mes_referencia == "SETEMBRO/2026"


def test_mes_referencia_da_aba():
    assert _mes_referencia_da_aba("SETEMBRO26") == "SETEMBRO/2026"
    assert _mes_referencia_da_aba("Setembro 2026") == "SETEMBRO/2026"
    assert _mes_referencia_da_aba("OUTUBRO-26") == "OUTUBRO/2026"
    assert _mes_referencia_da_aba("MARÇO") == "MARCO"
    assert _mes_referencia_da_aba("DOCS E CUSTAS") is None
    assert _mes_referencia_da_aba("FATAL") is None


def test_mes_referencia_da_aba_aceita_abreviacao_de_3_letras():
    assert _mes_referencia_da_aba("JUN-25") == "JUNHO/2025"
    assert _mes_referencia_da_aba("JUL-25") == "JULHO/2025"
    assert _mes_referencia_da_aba("AGO-25") == "AGOSTO/2025"
    assert _mes_referencia_da_aba("SET- 25") == "SETEMBRO/2025"
    assert _mes_referencia_da_aba("OUT- 25") == "OUTUBRO/2025"
    assert _mes_referencia_da_aba("MAR") == "MARCO"


def test_pessoa_valida_rejeita_valores_parecidos_com_data():
    assert _pessoa_valida("DANILO") == "DANILO"
    assert _pessoa_valida("2025-12-03 00:00:00") is None
    assert _pessoa_valida("2025-12-03") is None
    assert _pessoa_valida("03/12/2025") is None
    assert _pessoa_valida("  ") is None


def test_processo_parado_conta_dias_sem_evento_novo(db):
    processo = _processo(db, assistente="DANILO")
    data_antiga = date.today() - timedelta(days=PROCESSO_PARADO_DIAS + 5)
    db.add(EventoProcesso(processo_id=processo.id, data=data_antiga, tipo_evento_nome="CUSTAS"))
    db.commit()

    relatorio = gerar_relatorio(db, data_antiga, data_antiga)
    assert relatorio.linhas[0].processos_parados == 1

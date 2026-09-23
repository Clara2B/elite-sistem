import tempfile
from datetime import date
from pathlib import Path

import openpyxl
from sqlalchemy import Text

from app.models import Audiencia
from app.services.audiencias import (
    gerar_relatorio,
    importar_planilha,
    periodo_quinzenal,
)
from app.services.empresas import get_or_create_empresa


def _planilha(db, empresa_nome, primeira, segunda, ano=2026, mes=9):
    empresa = get_or_create_empresa(db, empresa_nome)
    for i in range(primeira):
        db.add(
            Audiencia(
                empresa_cliente_id=empresa.id,
                nome_cliente=f"Primeira {i}",
                data_recebimento=date(ano, mes, 1),
            )
        )
    for i in range(segunda):
        db.add(
            Audiencia(
                empresa_cliente_id=empresa.id,
                nome_cliente=f"Segunda {i}",
                data_recebimento=date(ano, mes, 16),
            )
        )
    db.commit()


def test_primeira_quinzena_usa_a_faixa_inicial(db):
    _planilha(db, "ALFA", 10, 5)
    ini, fim = periodo_quinzenal(2026, 9, 1)
    result = gerar_relatorio(db, "ALFA", ini, fim)
    assert (result.quantidade_mes, result.valor_unitario, result.total) == (10, 400.0, 4000.0)


def test_opcao_b_cobra_somente_a_segunda_quinzena_na_nova_faixa(db):
    _planilha(db, "ALFA", 20, 1)
    ini, fim = periodo_quinzenal(2026, 9, 2)
    result = gerar_relatorio(db, "ALFA", ini, fim)
    assert (result.quantidade_mes_anterior, result.quantidade_mes) == (20, 21)
    assert (result.valor_unitario, result.total) == (350.0, 350.0)


def test_faixa_de_39_audiencias(db):
    _planilha(db, "ALFA", 15, 24)
    ini, fim = periodo_quinzenal(2026, 9, 2)
    result = gerar_relatorio(db, "ALFA", ini, fim)
    assert (result.quantidade_mes, result.valor_unitario, result.total) == (39, 350.0, 8400.0)


def test_proxima_faixa(db):
    _planilha(db, "ALFA", 20, 20)
    ini, fim = periodo_quinzenal(2026, 9, 2)
    result = gerar_relatorio(db, "ALFA", ini, fim)
    assert (result.quantidade_mes, result.valor_unitario, result.total) == (40, 300.0, 6000.0)


def test_mes_anterior_nao_entra_no_acumulado(db):
    _planilha(db, "ALFA", 20, 20, ano=2026, mes=9)
    _planilha(db, "ALFA", 0, 1, ano=2026, mes=10)
    ini, fim = periodo_quinzenal(2026, 10, 2)
    result = gerar_relatorio(db, "ALFA", ini, fim)
    assert (result.quantidade_mes, result.valor_unitario, result.total) == (1, 400.0, 400.0)


def test_empresa_normalizada_sem_acento_e_caixa(db):
    _planilha(db, "ALFA", 5, 0)
    ini, fim = periodo_quinzenal(2026, 9, 1)
    result = gerar_relatorio(db, "alfa", ini, fim)
    assert result.quantidade_mes == 5


def test_campos_de_texto_livre_sao_text_nao_varchar():
    """Regressão: `cpf` como VARCHAR(20) foi o que realmente causou
    `StringDataRightTruncation` em produção (log real da Clara — a célula de
    CPF às vezes tem mais que um CPF formatado); os outros quatro
    (nome_cliente/data_agendamento/conciliadora/advogada) foram convertidos
    junto por precaução, mesmo padrão de texto livre da mesma planilha/
    equipe que já estourou em `processos` (`advogada` =
    "HUNTING - Fulana de Tal (CONTR. Beltrano)", 84+ caracteres). O SQLite
    dos testes não aplica limite de VARCHAR de verdade, então só uma
    checagem de schema pega esse tipo de regressão de volta pra VARCHAR(N)."""
    for nome_coluna in ("nome_cliente", "cpf", "data_agendamento", "conciliadora", "advogada"):
        coluna = Audiencia.__table__.c[nome_coluna]
        assert isinstance(coluna.type, Text), f"{nome_coluna} devia ser Text, não {coluna.type}"


def test_import_advogada_com_texto_longo_nao_quebra(db):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["EMPRESA", "NOME COMPLETO", "DATA DE RECEBIMENTO", "ADVOGADA"])
    advogada_longa = "HUNTING - Fulana de Tal da Silva Pereira Santos (CONTRATADA POR Beltrano de Souza)"
    ws.append(["ALFA", "Cliente Teste", date(2026, 9, 1), advogada_longa])
    path = Path(tempfile.mkdtemp()) / "audiencias.xlsx"
    wb.save(path)

    resumo = importar_planilha(db, str(path))
    assert resumo.linhas_novas == 1
    assert db.query(Audiencia).one().advogada == advogada_longa


def test_import_cpf_com_texto_longo_nao_quebra(db):
    """Reprodução do bug real reportado pela Clara: a célula de CPF na
    planilha às vezes tem mais que um CPF formatado (14 caracteres),
    estourando o antigo VARCHAR(20)."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["EMPRESA", "NOME COMPLETO", "DATA DE RECEBIMENTO", "CPF"])
    cpf_longo = "110.883.414-03 / 220.994.525-14 (dois titulares)"
    ws.append(["ALFA", "Cliente Teste", date(2026, 9, 1), cpf_longo])
    path = Path(tempfile.mkdtemp()) / "audiencias.xlsx"
    wb.save(path)

    resumo = importar_planilha(db, str(path))
    assert resumo.linhas_novas == 1
    assert db.query(Audiencia).one().cpf == cpf_longo

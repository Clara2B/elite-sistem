from datetime import date

from app.models import Audiencia
from app.services.audiencias import gerar_relatorio, periodo_quinzenal
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

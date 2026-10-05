"""Correspondências (Fase 9, ELITE, 2026-10-05, a pedido da Clara) — mesmo
padrão de Laudos: upload acumula histórico, relatório filtra por mês +
empresa. Ver DECISIONS.md 2026-10-05 pras decisões tomadas com a Clara
(persistência, fonte da lista de empresas, VALOR inválido, linha de total)."""
from __future__ import annotations

import tempfile
from pathlib import Path

import openpyxl
import pytest

from app.models import Correspondencia
from app.services.correspondencias import (
    apagar_todas_correspondencias,
    gerar_relatorio,
    importar_planilha,
    parse_valor,
)
from app.services.empresas import get_or_create_empresa

# --- parse_valor --------------------------------------------------------


@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("R$ 180,00", 180.0),
        ("R$160,00", 160.0),  # sem espaço depois do "R$" — visto na planilha real
        ("R$ 1.234,56", 1234.56),
        ("R$ 280,00.", 280.0),  # ponto final sobrando — visto na planilha real
        ("  R$ 90,00  ", 90.0),
        ("90,00", 90.0),  # sem "R$" na frente
    ],
)
def test_parse_valor_reconhece_formatos_validos(texto, esperado):
    assert parse_valor(texto) == esperado


@pytest.mark.parametrize("texto", ["a combinar", "", "   ", "R$ --", "grátis"])
def test_parse_valor_devolve_none_pra_texto_nao_numerico(texto):
    assert parse_valor(texto) is None


# --- importar_planilha ---------------------------------------------------


def _planilha(linhas, cabecalho=None, aba="ADV. CONTRATOS"):
    cabecalho = cabecalho or ["MÊS", "ADVOGADO", "AUTOR", "EMPRESA", "ADV / PREPOSTO", "VALOR", "TIPO DE AÇÃO"]
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = aba
    ws.append(cabecalho)
    for linha in linhas:
        ws.append(linha)
    path = Path(tempfile.mkdtemp()) / "correspondencias.xlsx"
    wb.save(path)
    return str(path)


def test_import_le_planilha_tolerando_variacao_de_cabecalho(db):
    path = _planilha(
        [["Janeiro", "Dra. Fulana", "Beltrano", "Eros", "ADVOGADO", "R$ 180,00", "PROCON"]],
        cabecalho=[" mês ", "Advogado", "autor", "EMPRESA", "adv / preposto", "Valor", "TIPO DE AÇÃO"],
    )
    resumo = importar_planilha(db, path)
    assert resumo.linhas_novas == 1

    c = db.query(Correspondencia).one()
    assert c.mes == "JANEIRO"
    assert c.advogado == "Dra. Fulana"
    assert c.valor == 180.0
    assert c.valor_texto == "R$ 180,00"


def test_import_recusa_quando_falta_coluna_obrigatoria(db):
    path = _planilha(
        [["Janeiro", "Fulana", "Beltrano", "Eros", "ADVOGADO", "PROCON"]],  # sem VALOR
        cabecalho=["MÊS", "ADVOGADO", "AUTOR", "EMPRESA", "ADV / PREPOSTO", "TIPO DE AÇÃO"],
    )
    with pytest.raises(ValueError, match='"VALOR"'):
        importar_planilha(db, path)


def test_import_recusa_quando_nenhuma_aba_tem_mes_e_empresa(db):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["NOME", "TELEFONE"])
    ws.append(["Fulano", "11999999999"])
    path = Path(tempfile.mkdtemp()) / "sem_relacao.xlsx"
    wb.save(path)

    with pytest.raises(ValueError, match="MÊS"):
        importar_planilha(db, str(path))


def test_import_mantem_valor_invalido_como_texto_sem_travar(db):
    path = _planilha([["Março", "Fulana", "Beltrano", "Eros", "ADVOGADO", "a combinar", "JUDICIAL"]])
    resumo = importar_planilha(db, path)
    assert resumo.linhas_novas == 1

    c = db.query(Correspondencia).one()
    assert c.valor is None
    assert c.valor_texto == "a combinar"


def test_import_ignora_linha_sem_mes_ou_sem_empresa(db):
    path = _planilha([
        ["", "Fulana", "Beltrano", "Eros", "ADVOGADO", "R$ 100,00", "PROCON"],
        ["Abril", "Fulana", "Beltrano", "", "ADVOGADO", "R$ 100,00", "PROCON"],
        ["Abril", "Fulana", "Beltrano", "Eros", "ADVOGADO", "R$ 100,00", "PROCON"],
    ])
    resumo = importar_planilha(db, path)
    assert resumo.linhas_novas == 1


def test_import_detecta_duplicidade_em_reimport(db):
    path = _planilha([["Janeiro", "Fulana", "Beltrano", "Eros", "ADVOGADO", "R$ 180,00", "PROCON"]])
    importar_planilha(db, path)
    resumo = importar_planilha(db, path)
    assert resumo.linhas_novas == 0
    assert resumo.linhas_ja_existentes == 1


def test_apagar_todas_correspondencias(db):
    path = _planilha([["Janeiro", "Fulana", "Beltrano", "Eros", "ADVOGADO", "R$ 180,00", "PROCON"]])
    importar_planilha(db, path)
    assert apagar_todas_correspondencias(db) == 1
    assert db.query(Correspondencia).count() == 0


# --- gerar_relatorio -------------------------------------------------------


def test_gerar_relatorio_filtra_por_empresa_e_mes(db):
    path = _planilha([
        ["Janeiro", "Dra. A", "Cliente A", "Eros", "ADVOGADO", "R$ 100,00", "PROCON"],
        ["Janeiro", "Dra. B", "Cliente B", "Zenith", "ADVOGADO", "R$ 200,00", "PROCON"],
        ["Fevereiro", "Dra. C", "Cliente C", "Eros", "ADVOGADO", "R$ 300,00", "PROCON"],
    ])
    importar_planilha(db, path)

    r = gerar_relatorio(db, "Eros", "Janeiro")
    assert r.empresa == "Eros"
    assert len(r.linhas) == 1
    assert r.linhas[0].autor == "Cliente A"
    assert r.total == 100.0


def test_gerar_relatorio_soma_so_os_valores_validos(db):
    path = _planilha([
        ["Janeiro", "Dra. A", "Cliente A", "Eros", "ADVOGADO", "R$ 100,00", "PROCON"],
        ["Janeiro", "Dra. B", "Cliente B", "Eros", "ADVOGADO", "a combinar", "PROCON"],
    ])
    importar_planilha(db, path)

    r = gerar_relatorio(db, "Eros", "Janeiro")
    assert len(r.linhas) == 2
    assert r.total == 100.0
    invalido = next(l for l in r.linhas if l.valor is None)
    assert invalido.valor_texto == "a combinar"


def test_gerar_relatorio_empresa_nao_encontrada(db):
    with pytest.raises(ValueError, match="não foi encontrada"):
        gerar_relatorio(db, "Empresa Inexistente", "Janeiro")


def test_gerar_relatorio_sem_correspondencia_devolve_lista_vazia(db):
    get_or_create_empresa(db, "Eros")
    db.commit()
    r = gerar_relatorio(db, "Eros", "Janeiro")
    assert r.linhas == []
    assert r.total == 0.0

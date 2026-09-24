import tempfile
from datetime import date
from pathlib import Path

import openpyxl

from app.models import Laudo
from app.services.empresas import get_or_create_empresa
from app.services.laudos import gerar_relatorio, importar_planilha, periodo_20_a_20


def test_periodo_20_a_20():
    ini, fim = periodo_20_a_20(2026, 1)
    assert ini == date(2026, 1, 21)
    assert fim == date(2026, 2, 20)


def test_periodo_20_a_20_vira_o_ano():
    ini, fim = periodo_20_a_20(2026, 12)
    assert ini == date(2026, 12, 21)
    assert fim == date(2027, 1, 20)


def test_gera_relatorio_soma_valores_por_tipo(db):
    empresa = get_or_create_empresa(db, "ABSOLUTA")
    db.add(
        Laudo(
            empresa_cliente_id=empresa.id,
            tipo_laudo_nome="AUTO",
            data=date(2026, 1, 25),
            nome_cliente="Fulano",
            status="SOLICITAÇÃO",
        )
    )
    db.add(
        Laudo(
            empresa_cliente_id=empresa.id,
            tipo_laudo_nome="IMÓVEL",
            data=date(2026, 2, 1),
            nome_cliente="Beltrano",
            status="CORREÇÃO",
        )
    )
    db.commit()

    ini, fim = periodo_20_a_20(2026, 1)
    resultado = gerar_relatorio(db, "ABSOLUTA", ini, fim, "Solicitação + Corrigido (cobrança)")
    assert resultado.total == 40.0 + 70.0
    assert len(resultado.linhas) == 2


def test_filtro_por_status_exclui_cancelado(db):
    empresa = get_or_create_empresa(db, "ABSOLUTA")
    db.add(
        Laudo(
            empresa_cliente_id=empresa.id,
            tipo_laudo_nome="AUTO",
            data=date(2026, 1, 25),
            nome_cliente="Fulano",
            status="CANCELADO",
        )
    )
    db.commit()
    ini, fim = periodo_20_a_20(2026, 1)
    resultado = gerar_relatorio(db, "ABSOLUTA", ini, fim, "Solicitação + Corrigido (cobrança)")
    assert resultado.linhas == []
    assert resultado.total == 0.0


def test_tipo_sem_valor_cadastrado_fica_marcado(db):
    empresa = get_or_create_empresa(db, "ABSOLUTA")
    db.add(
        Laudo(
            empresa_cliente_id=empresa.id,
            tipo_laudo_nome="PLACA SOLAR",
            data=date(2026, 1, 25),
            nome_cliente="Fulano",
            status="SOLICITAÇÃO",
        )
    )
    db.commit()
    ini, fim = periodo_20_a_20(2026, 1)
    resultado = gerar_relatorio(db, "ABSOLUTA", ini, fim, "Solicitação + Corrigido (cobrança)")
    assert resultado.tipos_sem_valor == ["PLACA SOLAR"]
    assert resultado.total == 0.0


def test_import_usa_coluna_a_como_data_mesmo_com_coluna_extra_de_data(db):
    """A planilha real de laudos tem colunas extras de data (prazo/entrega)
    além da coluna A — a Clara confirmou (relatório da ABSOLUTA com datas
    erradas em algumas linhas) que a data que vale pro sistema é sempre a
    da coluna A, não essas outras. Constrói uma aba com uma segunda coluna
    de data segurando um valor diferente, e confirma que o valor gravado é
    o da coluna A, não o da coluna extra."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["DATA", "EMPRESA", "TIPO DE LAUDO", "NOME DO CLIENTE", "DIA"])
    ws.append([date(2026, 8, 26), "ABSOLUTA", "EMPRÉSTIMO", "JOSE NUNES DA ROSA FILHO", date(2026, 8, 27)])
    path = Path(tempfile.mkdtemp()) / "laudos.xlsx"
    wb.save(path)

    importar_planilha(db, str(path))

    laudo = db.query(Laudo).one()
    assert laudo.data == date(2026, 8, 26)  # coluna A, não a coluna extra (27/08)

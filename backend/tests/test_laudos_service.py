import tempfile
from datetime import date
from pathlib import Path

import openpyxl

from app.models import Laudo, TipoLaudo
from app.services.empresas import get_or_create_empresa
from app.services.laudos import (
    apagar_todos_laudos,
    formatar_texto_resumo_assessorias,
    gerar_relatorio,
    gerar_resumo_por_assessoria,
    importar_planilha,
    periodo_20_a_20,
)


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


def test_apagar_todos_laudos_remove_tudo_e_devolve_a_contagem(db):
    empresa1 = get_or_create_empresa(db, "ABSOLUTA")
    empresa2 = get_or_create_empresa(db, "ALFA")
    db.add_all(
        [
            Laudo(empresa_cliente_id=empresa1.id, tipo_laudo_nome="AUTO", data=date(2026, 1, 25),
                  nome_cliente="Fulano", status="SOLICITAÇÃO"),
            Laudo(empresa_cliente_id=empresa2.id, tipo_laudo_nome="IMÓVEL", data=date(2026, 2, 1),
                  nome_cliente="Beltrano", status="CORREÇÃO"),
        ]
    )
    db.commit()

    apagados = apagar_todos_laudos(db)

    assert apagados == 2
    assert db.query(Laudo).count() == 0
    # não mexe nas empresas-clientes, só nos laudos
    assert get_or_create_empresa(db, "ABSOLUTA").id == empresa1.id


def test_apagar_todos_laudos_com_banco_ja_vazio(db):
    assert apagar_todos_laudos(db) == 0


def test_gerar_resumo_por_assessoria_agrupa_conta_e_ordena(db):
    absoluta = get_or_create_empresa(db, "ABSOLUTA")
    hunting = get_or_create_empresa(db, "HUNTING")
    db.add_all(
        [
            Laudo(empresa_cliente_id=absoluta.id, tipo_laudo_nome="AUTO", data=date(2026, 1, 25),
                  nome_cliente="Fulano", status="SOLICITAÇÃO"),
            Laudo(empresa_cliente_id=absoluta.id, tipo_laudo_nome="AUTO", data=date(2026, 1, 26),
                  nome_cliente="Beltrano", status="SOLICITAÇÃO"),
            Laudo(empresa_cliente_id=absoluta.id, tipo_laudo_nome="IMÓVEL", data=date(2026, 1, 27),
                  nome_cliente="Ciclano", status="CORREÇÃO"),
            Laudo(empresa_cliente_id=hunting.id, tipo_laudo_nome="EMPRÉSTIMO", data=date(2026, 1, 28),
                  nome_cliente="Fulana", status="SOLICITAÇÃO"),
        ]
    )
    db.commit()

    ini, fim = periodo_20_a_20(2026, 1)
    resumo = gerar_resumo_por_assessoria(db, ini, fim, "Solicitação + Corrigido (cobrança)")

    assert [r.assessoria for r in resumo] == ["ABSOLUTA", "HUNTING"]  # ordem alfabética
    absoluta_r = resumo[0]
    assert absoluta_r.total_laudos == 3
    assert [t.tipo for t in absoluta_r.tipos] == ["AUTO", "IMÓVEL"]  # ordem alfabética
    assert absoluta_r.tipos[0].quantidade == 2
    assert absoluta_r.tipos[0].valor_unitario == 40.0
    assert absoluta_r.tipos[1].quantidade == 1
    assert absoluta_r.tipos[1].valor_unitario == 70.0
    assert resumo[1].total_laudos == 1


def test_gerar_resumo_por_assessoria_nao_lista_quem_nao_tem_laudo_no_periodo(db):
    empresa = get_or_create_empresa(db, "ABSOLUTA")
    db.add(Laudo(empresa_cliente_id=empresa.id, tipo_laudo_nome="AUTO", data=date(2026, 1, 25),
                 nome_cliente="Fulano", status="CANCELADO"))
    db.commit()

    ini, fim = periodo_20_a_20(2026, 1)
    resumo = gerar_resumo_por_assessoria(db, ini, fim, "Solicitação + Corrigido (cobrança)")
    assert resumo == []


def test_gerar_resumo_por_assessoria_filtra_por_empresa(db):
    absoluta = get_or_create_empresa(db, "ABSOLUTA")
    hunting = get_or_create_empresa(db, "HUNTING")
    db.add_all(
        [
            Laudo(empresa_cliente_id=absoluta.id, tipo_laudo_nome="AUTO", data=date(2026, 1, 25),
                  nome_cliente="Fulano", status="SOLICITAÇÃO"),
            Laudo(empresa_cliente_id=hunting.id, tipo_laudo_nome="EMPRÉSTIMO", data=date(2026, 1, 25),
                  nome_cliente="Fulana", status="SOLICITAÇÃO"),
        ]
    )
    db.commit()

    ini, fim = periodo_20_a_20(2026, 1)
    resumo = gerar_resumo_por_assessoria(db, ini, fim, "Solicitação + Corrigido (cobrança)", filtro_empresa="ABSOLUTA")
    assert [r.assessoria for r in resumo] == ["ABSOLUTA"]


def test_gerar_resumo_por_assessoria_empresa_inexistente_gera_erro(db):
    ini, fim = periodo_20_a_20(2026, 1)
    try:
        gerar_resumo_por_assessoria(db, ini, fim, "Solicitação + Corrigido (cobrança)", filtro_empresa="NAO EXISTE")
        assert False, "deveria ter levantado ValueError"
    except ValueError as e:
        assert "NAO EXISTE" in str(e)


def test_gerar_resumo_por_assessoria_tipo_sem_valor_cadastrado(db):
    empresa = get_or_create_empresa(db, "ABSOLUTA")
    db.add(Laudo(empresa_cliente_id=empresa.id, tipo_laudo_nome="PLACA SOLAR", data=date(2026, 1, 25),
                 nome_cliente="Fulano", status="SOLICITAÇÃO"))
    db.commit()

    ini, fim = periodo_20_a_20(2026, 1)
    resumo = gerar_resumo_por_assessoria(db, ini, fim, "Solicitação + Corrigido (cobrança)")
    assert resumo[0].tipos[0].valor_unitario is None


def test_gerar_resumo_por_assessoria_respeita_mesmo_filtro_de_status_do_relatorio(db):
    """Os números da lista-resumo precisam bater com o relatório detalhado —
    a Clara pediu explicitamente. Usa exatamente a mesma regra de status
    (`_status_bate`) que `gerar_relatorio` já usa."""
    empresa = get_or_create_empresa(db, "ABSOLUTA")
    db.add_all(
        [
            Laudo(empresa_cliente_id=empresa.id, tipo_laudo_nome="AUTO", data=date(2026, 1, 25),
                  nome_cliente="Fulano", status="SOLICITAÇÃO"),
            Laudo(empresa_cliente_id=empresa.id, tipo_laudo_nome="AUTO", data=date(2026, 1, 26),
                  nome_cliente="Beltrano", status="CORREÇÃO"),
        ]
    )
    db.commit()

    ini, fim = periodo_20_a_20(2026, 1)
    relatorio = gerar_relatorio(db, "ABSOLUTA", ini, fim, "Somente Solicitação")
    resumo = gerar_resumo_por_assessoria(db, ini, fim, "Somente Solicitação")

    assert len(relatorio.linhas) == 1
    assert resumo[0].total_laudos == 1


def test_formatar_texto_resumo_assessorias_segue_o_modelo_da_clara(db):
    empresa = get_or_create_empresa(db, "ABSOLUTA")
    db.add(TipoLaudo(nome="TIPO A", valor_padrao=150.0))
    db.add(TipoLaudo(nome="TIPO B", valor_padrao=200.0))
    db.add_all(
        [
            Laudo(empresa_cliente_id=empresa.id, tipo_laudo_nome="TIPO A", data=date(2026, 1, 25),
                  nome_cliente="A1", status="SOLICITAÇÃO"),
            Laudo(empresa_cliente_id=empresa.id, tipo_laudo_nome="TIPO A", data=date(2026, 1, 25),
                  nome_cliente="A2", status="SOLICITAÇÃO"),
        ]
    )
    db.commit()

    ini, fim = periodo_20_a_20(2026, 1)
    resumo = gerar_resumo_por_assessoria(db, ini, fim, "Solicitação + Corrigido (cobrança)")
    texto = formatar_texto_resumo_assessorias(resumo)

    assert texto == (
        "ASSESSORIA: ABSOLUTA\n"
        "Total de laudos: 2\n"
        "TIPO A: 2 laudos - Valor individual: R$ 150,00"
    )


def test_formatar_texto_resumo_assessorias_tipo_sem_valor():
    from app.services.laudos import LinhaResumoTipo, ResumoAssessoria

    resumo = [ResumoAssessoria(assessoria="ABSOLUTA", total_laudos=1, tipos=[
        LinhaResumoTipo(tipo="PLACA SOLAR", quantidade=1, valor_unitario=None),
    ])]
    texto = formatar_texto_resumo_assessorias(resumo)
    assert "PLACA SOLAR: 1 laudos - Valor individual: (sem valor cadastrado)" in texto

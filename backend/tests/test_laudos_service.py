import tempfile
from datetime import date
from pathlib import Path

import openpyxl

from app.models import Laudo, TipoLaudo
from app.services.empresas import get_or_create_empresa
from app.services.laudos import (
    apagar_todos_laudos,
    detectar_duplicatas,
    excluir_laudo,
    formatar_texto_resumo_assessorias,
    gerar_relatorio,
    gerar_resumo_por_assessoria,
    ids_empresas_com_laudo,
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


def test_gerar_relatorio_junta_laudos_de_sw_e_ews_como_ews(db):
    """A pedido da Clara (2026-11-24): EWS trocou de nome (era "SW") e os
    laudos das duas devem sempre aparecer juntos, num relatório só, com o
    nome "EWS" — mesmo elas sendo EmpresaCliente cadastradas separadamente
    (CNPJs diferentes)."""
    ews = get_or_create_empresa(db, "EWS")
    sw = get_or_create_empresa(db, "SW")
    db.add_all(
        [
            Laudo(empresa_cliente_id=ews.id, tipo_laudo_nome="AUTO", data=date(2026, 1, 25),
                  nome_cliente="Fulano", status="SOLICITAÇÃO"),
            Laudo(empresa_cliente_id=sw.id, tipo_laudo_nome="IMÓVEL", data=date(2026, 1, 26),
                  nome_cliente="Beltrano", status="SOLICITAÇÃO"),
        ]
    )
    db.commit()

    ini, fim = periodo_20_a_20(2026, 1)

    resultado_ews = gerar_relatorio(db, "EWS", ini, fim, "Solicitação + Corrigido (cobrança)")
    assert resultado_ews.empresa == "EWS"
    assert {linha.cliente for linha in resultado_ews.linhas} == {"Fulano", "Beltrano"}

    # Buscar por "SW" devolve o MESMO relatório combinado, já nomeado EWS.
    resultado_sw = gerar_relatorio(db, "SW", ini, fim, "Solicitação + Corrigido (cobrança)")
    assert resultado_sw.empresa == "EWS"
    assert {linha.cliente for linha in resultado_sw.linhas} == {"Fulano", "Beltrano"}


def test_ids_empresas_com_laudo_so_conta_quem_tem_laudo_no_periodo_e_status(db):
    """A pedido da Clara (2026-11-24): usado pra tirar do menu de empresas
    quem não tem laudo nenhum no período/status escolhido (ex.: "Juros
    Justos" não aparece se nunca tiver laudo)."""
    tem_no_periodo = get_or_create_empresa(db, "ABSOLUTA")
    so_fora_do_periodo = get_or_create_empresa(db, "ALFA")
    cancelado = get_or_create_empresa(db, "HUNTING")
    get_or_create_empresa(db, "JUROS JUSTOS")  # nunca tem laudo
    db.add_all(
        [
            Laudo(empresa_cliente_id=tem_no_periodo.id, tipo_laudo_nome="AUTO", data=date(2026, 1, 25),
                  nome_cliente="Fulano", status="SOLICITAÇÃO"),
            Laudo(empresa_cliente_id=so_fora_do_periodo.id, tipo_laudo_nome="AUTO", data=date(2026, 3, 1),
                  nome_cliente="Beltrano", status="SOLICITAÇÃO"),
            Laudo(empresa_cliente_id=cancelado.id, tipo_laudo_nome="AUTO", data=date(2026, 1, 25),
                  nome_cliente="Ciclano", status="CANCELADO"),
        ]
    )
    db.commit()

    ini, fim = periodo_20_a_20(2026, 1)
    ids = ids_empresas_com_laudo(db, ini, fim, "Solicitação + Corrigido (cobrança)")

    assert ids == {tem_no_periodo.id}


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


def test_import_grande_comita_a_cada_2000_linhas_sem_perder_nenhuma(db):
    """Auditoria M19: mesmo problema já corrigido em
    app/services/processos.py — sem commit incremental, um import grande
    fica inteiro numa única transação até o fim do loop. Gera mais de 2000
    linhas novas pra atravessar o ponto de commit no meio do loop e
    confirma que nenhuma linha se perde."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["DATA", "EMPRESA", "TIPO DE LAUDO", "NOME DO CLIENTE"])
    total = 2005
    for i in range(total):
        ws.append([date(2026, 1, 1), "ABSOLUTA", "AUTO", f"Cliente {i}"])
    path = Path(tempfile.mkdtemp()) / "laudos.xlsx"
    wb.save(path)

    resumo = importar_planilha(db, str(path))

    assert resumo.linhas_novas == total
    assert db.query(Laudo).count() == total


def test_reimportacao_nao_duplica_o_mesmo_laudo(db):
    """M31: Laudos não tinha nenhum teste de deduplicação na reimportação
    (Processos tem 4 equivalentes) — identidade do laudo: empresa + data +
    nome do cliente (TIPO DE LAUDO não entra mais na identidade, ver
    `test_reimportacao_com_tipo_corrigido_atualiza_em_vez_de_duplicar`)."""
    def _planilha(nome_arquivo):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["DATA", "EMPRESA", "TIPO DE LAUDO", "NOME DO CLIENTE"])
        ws.append([date(2026, 8, 26), "ABSOLUTA", "AUTO", "Fulano de Tal"])
        path = Path(tempfile.mkdtemp()) / nome_arquivo
        wb.save(path)
        return str(path)

    resumo1 = importar_planilha(db, _planilha("v1.xlsx"))
    assert resumo1.linhas_novas == 1
    assert resumo1.linhas_ja_existentes == 0

    resumo2 = importar_planilha(db, _planilha("v2.xlsx"))
    assert resumo2.linhas_novas == 0
    assert resumo2.linhas_ja_existentes == 1

    assert db.query(Laudo).count() == 1


def test_reimportacao_com_cliente_diferente_nao_e_tratada_como_duplicata(db):
    """A chave de duplicidade inclui NOME DO CLIENTE — dois laudos no mesmo
    dia, mesma empresa e mesmo tipo, mas de clientes diferentes, são dois
    registros, não um só."""
    def _planilha(nome_arquivo, cliente):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["DATA", "EMPRESA", "TIPO DE LAUDO", "NOME DO CLIENTE"])
        ws.append([date(2026, 8, 26), "ABSOLUTA", "AUTO", cliente])
        path = Path(tempfile.mkdtemp()) / nome_arquivo
        wb.save(path)
        return str(path)

    importar_planilha(db, _planilha("v1.xlsx", "Fulano de Tal"))
    resumo2 = importar_planilha(db, _planilha("v2.xlsx", "Beltrano"))

    assert resumo2.linhas_novas == 1
    assert resumo2.linhas_ja_existentes == 0
    assert db.query(Laudo).count() == 2


def test_reimportacao_com_tipo_corrigido_atualiza_em_vez_de_duplicar(db):
    """Bug real reportado pela Clara (2026-11-24, planilha da Guardiã,
    cliente LEANDRO SILVA PESSANHA): o TIPO DE LAUDO fazia parte da chave
    de duplicidade contra o banco, então reimportar com o tipo corrigido
    (de "AUTO" pra "EMPRÉSTIMO") criava um registro NOVO em vez de
    corrigir o existente — o relatório contava os dois, duplicando o
    cliente e inflando o valor a cobrar. Agora a reimportação ATUALIZA o
    tipo (e o status) do registro já existente, sem duplicar."""
    def _planilha(nome_arquivo, tipo, status="Solicitação"):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["DATA", "EMPRESA", "TIPO DE LAUDO", "NOME DO CLIENTE", "ENTRADA DE LAUDO"])
        ws.append([date(2026, 10, 21), "GUARDIÃ", tipo, "LEANDRO SILVA PESSANHA", status])
        path = Path(tempfile.mkdtemp()) / nome_arquivo
        wb.save(path)
        return str(path)

    resumo1 = importar_planilha(db, _planilha("v1.xlsx", "AUTO"))
    assert resumo1.linhas_novas == 1

    resumo2 = importar_planilha(db, _planilha("v2.xlsx", "EMPRÉSTIMO"))
    assert resumo2.linhas_novas == 0
    assert resumo2.linhas_atualizadas == 1
    assert resumo2.linhas_ja_existentes == 0

    assert db.query(Laudo).count() == 1
    laudo = db.query(Laudo).one()
    assert laudo.tipo_laudo_nome == "EMPRÉSTIMO"

    # Reimportar de novo com o mesmo tipo não deve "atualizar" à toa.
    resumo3 = importar_planilha(db, _planilha("v3.xlsx", "EMPRÉSTIMO"))
    assert resumo3.linhas_atualizadas == 0
    assert resumo3.linhas_ja_existentes == 1


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


def test_detectar_duplicatas_agrupa_quem_tem_mesma_identidade_tipo_diferente(db):
    """Caso real reportado pela Clara: Guardiã/LEANDRO SILVA PESSANHA
    apareceu duas vezes no relatório, um como "AUTO" e outro como
    "EMPRÉSTIMO", no mesmo dia — sobra de ANTES do bug de reimportação
    (CHAVE_IDENTIDADE_LAUDO sem TIPO) ser corrigido."""
    guardia = get_or_create_empresa(db, "GUARDIÃ")
    sem_duplicata = get_or_create_empresa(db, "ABSOLUTA")
    duplicado_auto = Laudo(
        empresa_cliente_id=guardia.id, tipo_laudo_nome="AUTO", data=date(2026, 10, 21),
        nome_cliente="LEANDRO SILVA PESSANHA", status="SOLICITAÇÃO",
    )
    duplicado_emprestimo = Laudo(
        empresa_cliente_id=guardia.id, tipo_laudo_nome="EMPRÉSTIMO", data=date(2026, 10, 21),
        nome_cliente="LEANDRO SILVA PESSANHA", status="SOLICITAÇÃO",
    )
    db.add_all([
        duplicado_auto,
        duplicado_emprestimo,
        Laudo(empresa_cliente_id=sem_duplicata.id, tipo_laudo_nome="IMÓVEL", data=date(2026, 10, 21),
              nome_cliente="Fulano", status="SOLICITAÇÃO"),
    ])
    db.commit()

    grupos = detectar_duplicatas(db)

    assert len(grupos) == 1
    grupo = grupos[0]
    assert grupo.empresa == "GUARDIÃ"
    assert grupo.cliente == "LEANDRO SILVA PESSANHA"
    assert {l.tipo_laudo_nome for l in grupo.laudos} == {"AUTO", "EMPRÉSTIMO"}
    assert {l.id for l in grupo.laudos} == {duplicado_auto.id, duplicado_emprestimo.id}


def test_detectar_duplicatas_sem_nenhuma_devolve_lista_vazia(db):
    empresa = get_or_create_empresa(db, "ABSOLUTA")
    db.add(Laudo(empresa_cliente_id=empresa.id, tipo_laudo_nome="AUTO", data=date(2026, 10, 21),
                 nome_cliente="Fulano", status="SOLICITAÇÃO"))
    db.commit()

    assert detectar_duplicatas(db) == []


def test_excluir_laudo_remove_so_o_escolhido(db):
    empresa = get_or_create_empresa(db, "GUARDIÃ")
    manter = Laudo(empresa_cliente_id=empresa.id, tipo_laudo_nome="EMPRÉSTIMO", data=date(2026, 10, 21),
                    nome_cliente="LEANDRO SILVA PESSANHA", status="SOLICITAÇÃO")
    apagar = Laudo(empresa_cliente_id=empresa.id, tipo_laudo_nome="AUTO", data=date(2026, 10, 21),
                   nome_cliente="LEANDRO SILVA PESSANHA", status="SOLICITAÇÃO")
    db.add_all([manter, apagar])
    db.commit()
    apagar_id = apagar.id

    assert excluir_laudo(db, apagar_id) is True

    assert db.query(Laudo).count() == 1
    assert db.get(Laudo, manter.id) is not None
    assert db.get(Laudo, apagar_id) is None


def test_excluir_laudo_inexistente_devolve_false(db):
    assert excluir_laudo(db, 999999) is False


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


def test_gerar_resumo_por_assessoria_junta_sw_e_ews_numa_linha_so(db):
    """Mesma regra de `gerar_relatorio` (2026-11-24): no resumo geral por
    assessoria, SW entra somado junto de EWS numa linha só, não em duas."""
    ews = get_or_create_empresa(db, "EWS")
    sw = get_or_create_empresa(db, "SW")
    db.add_all(
        [
            Laudo(empresa_cliente_id=ews.id, tipo_laudo_nome="AUTO", data=date(2026, 1, 25),
                  nome_cliente="Fulano", status="SOLICITAÇÃO"),
            Laudo(empresa_cliente_id=sw.id, tipo_laudo_nome="AUTO", data=date(2026, 1, 26),
                  nome_cliente="Beltrano", status="SOLICITAÇÃO"),
        ]
    )
    db.commit()

    ini, fim = periodo_20_a_20(2026, 1)
    resumo = gerar_resumo_por_assessoria(db, ini, fim, "Solicitação + Corrigido (cobrança)")

    assert [r.assessoria for r in resumo] == ["EWS"]
    assert resumo[0].total_laudos == 2
    assert resumo[0].tipos[0].quantidade == 2


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

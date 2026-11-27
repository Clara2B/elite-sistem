import tempfile
from datetime import date
from pathlib import Path

import openpyxl
import pytest
from sqlalchemy import Text

from app.models import Audiencia
from app.services.audiencias import (
    apagar_todas_audiencias,
    editar_audiencia,
    excluir_audiencia,
    gerar_relatorio,
    ids_empresas_com_audiencia,
    importar_planilha,
    listar_audiencias,
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


def test_ids_empresas_com_audiencia_so_conta_quem_tem_na_quinzena(db):
    """A pedido da Clara (2026-11-24): usado pra tirar do menu de empresas
    quem não tem audiência naquela quinzena (ex.: "Juros Justos" não
    aparece se nunca tiver uma)."""
    alfa = get_or_create_empresa(db, "ALFA")  # 1ª quinzena
    _planilha(db, "ALFA", 10, 0)
    beta_so_na_segunda = get_or_create_empresa(db, "BETA")
    _planilha(db, "BETA", 0, 5)
    get_or_create_empresa(db, "JUROS JUSTOS")  # nunca tem audiência

    ini, fim = periodo_quinzenal(2026, 9, 1)
    ids = ids_empresas_com_audiencia(db, ini, fim)

    assert ids == {alfa.id}
    assert beta_so_na_segunda.id not in ids


# --- M43: diferencia LookupError (empresa não encontrada, 404 na API) de
# ValueError (regra de negócio, 422 na API) ----------------------------------


def test_empresa_nao_encontrada_levanta_lookup_error(db):
    ini, fim = periodo_quinzenal(2026, 9, 1)
    try:
        gerar_relatorio(db, "NÃO EXISTE", ini, fim)
        assert False, "deveria ter levantado LookupError"
    except LookupError as e:
        assert "NÃO EXISTE" in str(e)


def test_faixa_nao_cadastrada_continua_value_error_puro(db):
    """Acima de 100 audiências acumuladas não tem faixa cadastrada
    (DEFAULT_FAIXAS_AUDIENCIA vai até 100) — regra de negócio, não "recurso
    não encontrado": deve continuar ValueError puro (não LookupError, que
    agora é só pra "empresa não encontrada" — auditoria M43)."""
    _planilha(db, "ALFA", 101, 0)
    ini, fim = periodo_quinzenal(2026, 9, 1)
    try:
        gerar_relatorio(db, "ALFA", ini, fim)
        assert False, "deveria ter levantado ValueError"
    except LookupError:
        assert False, "faixa não cadastrada não deve ser LookupError"
    except ValueError as e:
        assert "faixa de preço" in str(e)


def test_mes_anterior_nao_entra_no_acumulado(db):
    _planilha(db, "ALFA", 20, 20, ano=2026, mes=9)
    _planilha(db, "ALFA", 0, 1, ano=2026, mes=10)
    ini, fim = periodo_quinzenal(2026, 10, 2)
    result = gerar_relatorio(db, "ALFA", ini, fim)
    assert (result.quantidade_mes, result.valor_unitario, result.total) == (1, 400.0, 400.0)


def test_gerar_relatorio_aceita_cnpj_valido_sobrescrito(db):
    """Auditoria M12: o CNPJ sobrescrito via parâmetro precisa ser um CNPJ
    de verdade — antes, qualquer texto era aceito e ia pro PDF/Excel/JSON
    oficial sem checagem."""
    _planilha(db, "ALFA", 10, 5)
    ini, fim = periodo_quinzenal(2026, 9, 1)
    result = gerar_relatorio(db, "ALFA", ini, fim, cnpj="11222333000181")
    assert result.cnpj == "11222333000181"


def test_gerar_relatorio_rejeita_cnpj_invalido_sobrescrito(db):
    _planilha(db, "ALFA", 10, 5)
    ini, fim = periodo_quinzenal(2026, 9, 1)
    with pytest.raises(ValueError, match="CNPJ"):
        gerar_relatorio(db, "ALFA", ini, fim, cnpj="123")


def test_periodo_quinzenal_aceita_1_e_2():
    assert periodo_quinzenal(2026, 9, 1) == (date(2026, 9, 1), date(2026, 9, 15))
    assert periodo_quinzenal(2026, 9, 2) == (date(2026, 9, 16), date(2026, 9, 30))


@pytest.mark.parametrize("quinzena", [0, 3, -1, 99])
def test_periodo_quinzenal_rejeita_valor_invalido(quinzena):
    """Auditoria M13: antes, qualquer valor != 1 caía no else e devolvia o
    período da 2ª quinzena silenciosamente, sem erro."""
    with pytest.raises(ValueError, match="Quinzena inválida"):
        periodo_quinzenal(2026, 9, quinzena)


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


def test_reimportar_mesmo_cpf_com_formatacao_diferente_nao_duplica(db):
    """Auditoria M14: a chave de deduplicação normalizava o nome (sem
    acento/maiúscula) mas comparava o CPF em texto cru — reimportar a
    mesma pessoa com o CPF formatado diferente ("123.456.789-01" vs
    "12345678901") criava uma duplicata silenciosa."""

    def _planilha_com_cpf(cpf_na_celula):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["EMPRESA", "NOME COMPLETO", "DATA DE RECEBIMENTO", "CPF"])
        ws.append(["ALFA", "Cliente Teste", date(2026, 9, 1), cpf_na_celula])
        path = Path(tempfile.mkdtemp()) / "audiencias.xlsx"
        wb.save(path)
        return str(path)

    resumo1 = importar_planilha(db, _planilha_com_cpf("123.456.789-01"))
    assert resumo1.linhas_novas == 1

    resumo2 = importar_planilha(db, _planilha_com_cpf("12345678901"))
    assert resumo2.linhas_novas == 0
    assert resumo2.linhas_ja_existentes == 1
    assert db.query(Audiencia).count() == 1


def test_reimportacao_com_conciliadora_e_advogada_corrigidas_atualiza_em_vez_de_duplicar(db):
    """Bug real reportado pela Clara (2026-11-24): CONCILIADORA/ADVOGADA
    não faziam parte da identidade contra o banco de propósito (não deviam
    criar duplicata), mas o código só verificava "já existe" e ignorava a
    linha — nunca atualizava os dois campos quando eram corrigidos na
    planilha. Mesma classe de bug já corrigida em Laudos (TIPO) e
    Pendências (PAGO)."""

    def _planilha(nome_arquivo, conciliadora, advogada):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["EMPRESA", "NOME COMPLETO", "DATA DE RECEBIMENTO", "CONCILIADORA", "ADVOGADA"])
        ws.append(["ALFA", "Cliente Teste", date(2026, 9, 1), conciliadora, advogada])
        path = Path(tempfile.mkdtemp()) / nome_arquivo
        wb.save(path)
        return str(path)

    resumo1 = importar_planilha(db, _planilha("v1.xlsx", "Conciliadora A", "Dra. A"))
    assert resumo1.linhas_novas == 1

    resumo2 = importar_planilha(db, _planilha("v2.xlsx", "Conciliadora B", "Dra. B"))
    assert resumo2.linhas_novas == 0
    assert resumo2.linhas_atualizadas == 1
    assert resumo2.linhas_ja_existentes == 0

    assert db.query(Audiencia).count() == 1
    audiencia = db.query(Audiencia).one()
    assert audiencia.conciliadora == "Conciliadora B"
    assert audiencia.advogada == "Dra. B"

    # Reimportar de novo sem mudar nada não deve "atualizar" à toa.
    resumo3 = importar_planilha(db, _planilha("v3.xlsx", "Conciliadora B", "Dra. B"))
    assert resumo3.linhas_atualizadas == 0
    assert resumo3.linhas_ja_existentes == 1


def test_apagar_todas_audiencias_remove_tudo_e_devolve_a_contagem(db):
    empresa1 = get_or_create_empresa(db, "ALFA")
    empresa2 = get_or_create_empresa(db, "BETA")
    db.add_all(
        [
            Audiencia(empresa_cliente_id=empresa1.id, nome_cliente="Fulano", data_recebimento=date(2026, 9, 1)),
            Audiencia(empresa_cliente_id=empresa2.id, nome_cliente="Beltrano", data_recebimento=date(2026, 9, 2)),
        ]
    )
    db.commit()

    apagadas = apagar_todas_audiencias(db)

    assert apagadas == 2
    assert db.query(Audiencia).count() == 0
    # não mexe nas empresas-clientes
    assert get_or_create_empresa(db, "ALFA").id == empresa1.id


def test_apagar_todas_audiencias_com_banco_ja_vazio(db):
    assert apagar_todas_audiencias(db) == 0


def test_listar_audiencias_filtra_por_empresa_e_periodo(db):
    """A pedido da Clara (2026-11-25): pra edição/exclusão individual —
    mesmo filtro de `gerar_relatorio` (empresa + período)."""
    empresa = get_or_create_empresa(db, "ALFA")
    outra_empresa = get_or_create_empresa(db, "BETA")
    db.add_all(
        [
            Audiencia(empresa_cliente_id=empresa.id, nome_cliente="Fulano", data_recebimento=date(2026, 9, 5)),
            Audiencia(empresa_cliente_id=empresa.id, nome_cliente="Beltrano", data_recebimento=date(2026, 10, 1)),
            Audiencia(empresa_cliente_id=outra_empresa.id, nome_cliente="Ciclano", data_recebimento=date(2026, 9, 5)),
        ]
    )
    db.commit()

    linhas = listar_audiencias(db, "ALFA", date(2026, 9, 1), date(2026, 9, 30))

    assert [l.nome_cliente for l in linhas] == ["Fulano"]


def test_listar_audiencias_empresa_inexistente_gera_erro(db):
    with pytest.raises(ValueError, match="não foi encontrada"):
        listar_audiencias(db, "NAO EXISTE", date(2026, 9, 1), date(2026, 9, 30))


def test_editar_audiencia_atualiza_campos(db):
    empresa = get_or_create_empresa(db, "ALFA")
    audiencia = Audiencia(empresa_cliente_id=empresa.id, nome_cliente="Fulano", data_recebimento=date(2026, 9, 5))
    db.add(audiencia)
    db.commit()

    editado = editar_audiencia(
        db, audiencia.id, data_recebimento=date(2026, 9, 10), nome_cliente="Fulano Corrigido",
        cpf="123.456.789-01", conciliadora="Conciliadora X", advogada="Dra. Y",
    )

    assert editado is True
    db.refresh(audiencia)
    assert audiencia.data_recebimento == date(2026, 9, 10)
    assert audiencia.nome_cliente == "Fulano Corrigido"
    assert audiencia.cpf == "123.456.789-01"
    assert audiencia.conciliadora == "Conciliadora X"
    assert audiencia.advogada == "Dra. Y"


def test_editar_audiencia_inexistente_devolve_false(db):
    assert editar_audiencia(db, 999999, date(2026, 9, 5), "X", None, None, None) is False


def test_excluir_audiencia_remove_so_o_escolhido(db):
    empresa = get_or_create_empresa(db, "ALFA")
    manter = Audiencia(empresa_cliente_id=empresa.id, nome_cliente="Fulano", data_recebimento=date(2026, 9, 5))
    apagar = Audiencia(empresa_cliente_id=empresa.id, nome_cliente="Beltrano", data_recebimento=date(2026, 9, 6))
    db.add_all([manter, apagar])
    db.commit()
    apagar_id = apagar.id

    assert excluir_audiencia(db, apagar_id) is True
    assert db.query(Audiencia).count() == 1
    assert db.get(Audiencia, manter.id) is not None
    assert db.get(Audiencia, apagar_id) is None


def test_excluir_audiencia_inexistente_devolve_false(db):
    assert excluir_audiencia(db, 999999) is False

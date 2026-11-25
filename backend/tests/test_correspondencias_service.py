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
    editar_correspondencia,
    excluir_correspondencia,
    gerar_relatorio,
    ids_empresas_com_correspondencia,
    importar_planilha,
    parse_valor,
    recalcular_valores_zerados,
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
        ("280.50", 280.5),  # célula de texto simples, ponto decimal — a pedido da Clara, 2026-11-04
        ("280.5", 280.5),
        ("280", 280.0),
        ("-50.5", -50.5),
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


def test_ids_empresas_com_correspondencia_so_conta_quem_tem_no_mes(db):
    """A pedido da Clara (2026-11-24): usado pra tirar do menu de empresas
    quem não tem correspondência naquele mês (ex.: "Juros Justos" não
    aparece se nunca tiver uma)."""
    path = _planilha([
        ["Janeiro", "Dra. A", "Cliente A", "Eros", "ADVOGADO", "R$ 100,00", "PROCON"],
        ["Fevereiro", "Dra. C", "Cliente C", "Zenith", "ADVOGADO", "R$ 300,00", "PROCON"],
    ])
    importar_planilha(db, path)
    sem_correspondencia = get_or_create_empresa(db, "Juros Justos")
    db.commit()

    ids_janeiro = ids_empresas_com_correspondencia(db, "Janeiro")

    eros = get_or_create_empresa(db, "Eros")
    zenith = get_or_create_empresa(db, "Zenith")
    assert ids_janeiro == {eros.id}
    assert zenith.id not in ids_janeiro
    assert sem_correspondencia.id not in ids_janeiro


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


def test_gerar_relatorio_mes_sem_acento_na_planilha_bate_com_mes_acentuado(db):
    """Auditoria M15: a comparação de "mês" era sensível a acento,
    diferente da de empresa (que já usa normalize()) — "MARCO" (erro de
    digitação, sem cedilha, no estilo de outros já vistos neste sistema)
    importado da planilha não batia com "Março" vindo do dropdown da
    tela, e o relatório mostrava "Nenhuma correspondência encontrada"
    mesmo havendo a linha."""
    path = _planilha([
        ["MARCO", "Dra. A", "Cliente A", "Eros", "ADVOGADO", "R$ 100,00", "PROCON"],
    ])
    importar_planilha(db, path)

    r = gerar_relatorio(db, "Eros", "Março")
    assert len(r.linhas) == 1
    assert r.linhas[0].autor == "Cliente A"


def test_recalcular_valores_zerados_corrige_so_quem_tinha_valor_nulo(db):
    """Bug real reportado pela Clara (SIMPLIFICA/Outubro aparecia com Total
    R$ 0,00): registros importados ANTES do bug de "280.50" ser corrigido
    ficaram com valor=None pra sempre — reimportar a planilha sem mudar
    nada não corrige (chave de duplicidade usa o valor_texto original, que
    não mudou). `recalcular_valores_zerados` reaplica o parser atual direto
    nesses registros."""
    empresa = get_or_create_empresa(db, "SIMPLIFICA")
    zerado_mas_corrigivel = Correspondencia(
        empresa_cliente_id=empresa.id, mes="OUTUBRO", advogado="Dra. A", autor="Cliente A",
        adv_preposto="ADVOGADO", valor_texto="280.50", valor=None, tipo_acao="PROCON",
    )
    zerado_sem_conserto = Correspondencia(
        empresa_cliente_id=empresa.id, mes="OUTUBRO", advogado="Dra. B", autor="Cliente B",
        adv_preposto="ADVOGADO", valor_texto="a combinar", valor=None, tipo_acao="PROCON",
    )
    ja_tinha_valor = Correspondencia(
        empresa_cliente_id=empresa.id, mes="OUTUBRO", advogado="Dra. C", autor="Cliente C",
        adv_preposto="ADVOGADO", valor_texto="R$ 100,00", valor=100.0, tipo_acao="PROCON",
    )
    db.add_all([zerado_mas_corrigivel, zerado_sem_conserto, ja_tinha_valor])
    db.commit()

    corrigidos = recalcular_valores_zerados(db)

    assert corrigidos == 1
    db.refresh(zerado_mas_corrigivel)
    db.refresh(zerado_sem_conserto)
    db.refresh(ja_tinha_valor)
    assert zerado_mas_corrigivel.valor == 280.5
    assert zerado_sem_conserto.valor is None  # continua sem valor reconhecível
    assert ja_tinha_valor.valor == 100.0  # não foi tocado


def test_recalcular_valores_zerados_com_banco_sem_pendencia(db):
    assert recalcular_valores_zerados(db) == 0


def test_editar_correspondencia_atualiza_campos_e_recalcula_valor(db):
    """A pedido da Clara (2026-11-25): corrigir um registro errado sem
    precisar reimportar a planilha inteira."""
    path = _planilha([["Janeiro", "Dra. A", "Cliente A", "Eros", "ADVOGADO", "R$ 100,00", "PROCON"]])
    importar_planilha(db, path)
    linha = gerar_relatorio(db, "Eros", "Janeiro").linhas[0]

    editado = editar_correspondencia(
        db, linha.id, advogado="Dra. B", autor="Cliente B", adv_preposto="PREPOSTO",
        valor_texto="R$ 250,00", tipo_acao="EXTRAJUDICIAL",
    )

    assert editado is True
    nova_linha = gerar_relatorio(db, "Eros", "Janeiro").linhas[0]
    assert nova_linha.advogado == "Dra. B"
    assert nova_linha.autor == "Cliente B"
    assert nova_linha.adv_preposto == "PREPOSTO"
    assert nova_linha.valor_texto == "R$ 250,00"
    assert nova_linha.valor == 250.0
    assert nova_linha.tipo_acao == "EXTRAJUDICIAL"


def test_editar_correspondencia_com_valor_nao_reconhecido_zera_valor(db):
    path = _planilha([["Janeiro", "Dra. A", "Cliente A", "Eros", "ADVOGADO", "R$ 100,00", "PROCON"]])
    importar_planilha(db, path)
    linha = gerar_relatorio(db, "Eros", "Janeiro").linhas[0]

    editar_correspondencia(
        db, linha.id, advogado="Dra. A", autor="Cliente A", adv_preposto="ADVOGADO",
        valor_texto="a combinar", tipo_acao="PROCON",
    )

    nova_linha = gerar_relatorio(db, "Eros", "Janeiro").linhas[0]
    assert nova_linha.valor is None
    assert nova_linha.valor_texto == "a combinar"


def test_editar_correspondencia_inexistente_devolve_false(db):
    assert editar_correspondencia(db, 999999, "a", "b", "c", "d", "e") is False


def test_excluir_correspondencia_remove_so_o_escolhido(db):
    path = _planilha([
        ["Janeiro", "Dra. A", "Cliente A", "Eros", "ADVOGADO", "R$ 100,00", "PROCON"],
        ["Janeiro", "Dra. B", "Cliente B", "Eros", "ADVOGADO", "R$ 200,00", "PROCON"],
    ])
    importar_planilha(db, path)
    linhas = gerar_relatorio(db, "Eros", "Janeiro").linhas
    manter_id = next(l.id for l in linhas if l.autor == "Cliente A")
    apagar_id = next(l.id for l in linhas if l.autor == "Cliente B")

    assert excluir_correspondencia(db, apagar_id) is True

    linhas_depois = gerar_relatorio(db, "Eros", "Janeiro").linhas
    assert [l.id for l in linhas_depois] == [manter_id]


def test_excluir_correspondencia_inexistente_devolve_false(db):
    assert excluir_correspondencia(db, 999999) is False

import tempfile
from pathlib import Path

import openpyxl
import pytest

from app.models import Banco
from app.services import bancos as bancos_service
from app.services.bancos import (
    alterar_ativo_banco,
    atualizar_banco,
    criar_banco,
    excluir_banco,
    importar_do_google_sheets,
    importar_planilha_bancos,
    listar_bancos,
)

CNPJ_VALIDO = "11.222.333/0001-81"
CNPJ_VALIDO_2 = "11.444.777/0001-61"


def test_criar_banco_com_cnpj_valido(db):
    banco = criar_banco(db, "Banco XPTO", CNPJ_VALIDO, "contato@xpto.com.br")
    assert banco.nome == "Banco XPTO"
    assert banco.cnpj == CNPJ_VALIDO
    assert banco.email == "contato@xpto.com.br"
    assert banco.ativo is True


def test_criar_banco_com_cnpj_invalido_eh_rejeitado(db):
    with pytest.raises(ValueError, match="CNPJ"):
        criar_banco(db, "Banco Invalido", "123", "contato@xpto.com.br")


def test_criar_banco_com_nome_duplicado_eh_rejeitado(db):
    criar_banco(db, "Banco XPTO", CNPJ_VALIDO, "contato@xpto.com.br")
    with pytest.raises(ValueError, match="Já existe"):
        criar_banco(db, "banco xpto", "11222333000181", "outro@xpto.com.br")


def test_atualizar_banco(db):
    banco = criar_banco(db, "Banco XPTO", CNPJ_VALIDO, "contato@xpto.com.br")
    atualizado = atualizar_banco(db, banco.id, "Banco XPTO S.A.", "11.444.777/0001-61", "novo@xpto.com.br")
    assert atualizado.nome == "Banco XPTO S.A."
    assert atualizado.cnpj == "11.444.777/0001-61"
    assert atualizado.email == "novo@xpto.com.br"


def test_atualizar_banco_inexistente_eh_rejeitado(db):
    with pytest.raises(ValueError, match="não encontrado"):
        atualizar_banco(db, 999, "X", CNPJ_VALIDO, "x@x.com")


def test_listar_bancos_filtra_ativos_por_padrao(db):
    ativo = criar_banco(db, "Banco Ativo", CNPJ_VALIDO, "ativo@x.com")
    inativo = criar_banco(db, "Banco Inativo", "11.444.777/0001-61", "inativo@x.com")
    alterar_ativo_banco(db, inativo.id, False)

    assert [b.id for b in listar_bancos(db)] == [ativo.id]
    assert {b.id for b in listar_bancos(db, apenas_ativos=False)} == {ativo.id, inativo.id}


def test_excluir_banco(db):
    banco = criar_banco(db, "Banco XPTO", CNPJ_VALIDO, "contato@xpto.com.br")
    excluir_banco(db, banco.id)
    assert db.get(Banco, banco.id) is None


def test_criar_banco_com_segunda_opcao_de_cnpj(db):
    """Alguns bancos (ex.: Itaú, na planilha real) têm um segundo CNPJ
    válido — quem monta a Carta Banco escolhe qual se aplica a cada caso."""
    banco = criar_banco(db, "Banco Dois CNPJs", CNPJ_VALIDO, "contato@x.com", cnpj_alternativo=CNPJ_VALIDO_2)
    assert banco.cnpj == CNPJ_VALIDO
    assert banco.cnpj_alternativo == CNPJ_VALIDO_2


def test_criar_banco_com_segunda_opcao_de_cnpj_invalida_eh_rejeitado(db):
    with pytest.raises(ValueError, match="2° opção"):
        criar_banco(db, "Banco Dois CNPJs", CNPJ_VALIDO, "contato@x.com", cnpj_alternativo="123")


def test_banco_aceita_multiplos_emails_separados_por_ponto_e_virgula(db):
    """A planilha real de bancos tem várias linhas com mais de um e-mail de
    notificação na mesma célula (ex.: jurídico + ouvidoria) — não é um
    único endereço."""
    varios = "juridico@banco.com.br; ouvidoria@banco.com.br; contato@banco.com.br"
    banco = criar_banco(db, "Banco Multi Email", CNPJ_VALIDO, varios)
    assert banco.email == varios


def _planilha(linhas, cabecalho=("BANCO", "CNPJ", "EMAIL")):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(list(cabecalho))
    for linha in linhas:
        ws.append(list(linha))
    path = Path(tempfile.mkdtemp()) / "bancos.xlsx"
    wb.save(path)
    return str(path)


def test_importar_planilha_cria_bancos_novos(db):
    path = _planilha([("Banco XPTO", "11.222.333/0001-81", "contato@xpto.com.br")])
    resumo = importar_planilha_bancos(db, path)
    assert resumo.criados == 1
    assert resumo.atualizados == 0
    banco = listar_bancos(db)[0]
    assert banco.nome == "Banco XPTO"
    assert banco.cnpj == "11.222.333/0001-81"
    assert banco.email == "contato@xpto.com.br"


def test_importar_planilha_atualiza_banco_existente_por_nome_normalizado(db):
    criar_banco(db, "Banco XPTO", CNPJ_VALIDO, "velho@xpto.com.br")
    path = _planilha([("banco xpto", "11.444.777/0001-61", "novo@xpto.com.br")])

    resumo = importar_planilha_bancos(db, path)

    assert resumo.criados == 0
    assert resumo.atualizados == 1
    banco = listar_bancos(db)[0]
    assert banco.cnpj == "11.444.777/0001-61"
    assert banco.email == "novo@xpto.com.br"


def test_importar_planilha_nao_apaga_banco_fora_da_planilha(db):
    criar_banco(db, "Banco Antigo", CNPJ_VALIDO, "antigo@x.com")
    path = _planilha([("Banco Novo", "11.444.777/0001-61", "novo@x.com")])

    importar_planilha_bancos(db, path)

    assert {b.nome for b in listar_bancos(db)} == {"Banco Antigo", "Banco Novo"}


def test_importar_planilha_rejeita_linha_com_cnpj_invalido_mas_continua(db):
    path = _planilha(
        [
            ("Banco Com Erro", "123", "erro@x.com"),
            ("Banco Ok", CNPJ_VALIDO, "ok@x.com"),
        ]
    )
    resumo = importar_planilha_bancos(db, path)
    assert resumo.criados == 1
    assert len(resumo.rejeitados) == 1
    assert "Banco Com Erro" in resumo.rejeitados[0]
    assert listar_bancos(db)[0].nome == "Banco Ok"


def test_importar_planilha_sem_coluna_banco_eh_rejeitada(db):
    path = _planilha([("11.222.333/0001-81", "contato@xpto.com.br")], cabecalho=("CNPJ", "EMAIL"))
    with pytest.raises(ValueError, match="BANCO"):
        importar_planilha_bancos(db, path)


def _linha_sheets(banco="", email="", cnpj="", cnpj_alt=""):
    return {"BANCOS ": banco, "E-MAIL": email, "CNPJ": cnpj, "2° OPÇÃO CNPJ": cnpj_alt}


def test_importar_do_google_sheets_cria_bancos_novos(db, monkeypatch):
    """Colunas e aba reais da planilha de controle da Clara: aba "E-MAIL
    BANCO", coluna do nome é "BANCOS" (no plural, com espaço extra no
    cabeçalho de verdade)."""
    linhas = [_linha_sheets("Banco XPTO", "contato@xpto.com.br", CNPJ_VALIDO)]
    monkeypatch.setattr(bancos_service.google_sheets, "ler_aba", lambda spreadsheet_id, aba: linhas)

    resumo = importar_do_google_sheets(db, "planilha-fake-id")

    assert resumo.criados == 1
    banco = listar_bancos(db)[0]
    assert banco.nome == "Banco XPTO"
    assert banco.cnpj == CNPJ_VALIDO
    assert banco.email == "contato@xpto.com.br"


def test_importar_do_google_sheets_ignora_formula_de_ia_nao_resolvida(db, monkeypatch):
    """A coluna "2° OPÇÃO CNPJ" da planilha real vem com a fórmula de
    sugestão de IA do Google Sheets não resolvida (`=AI("Preencha...")`) em
    quase toda linha — não é CNPJ de verdade, tem que ser ignorada, não
    rejeitada como inválida."""
    linha = _linha_sheets(
        "Banco Com Formula", "contato@x.com", CNPJ_VALIDO,
        cnpj_alt='=AI("Preencha com um valor adequado para esta célula com base no contexto da tabela")',
    )
    monkeypatch.setattr(bancos_service.google_sheets, "ler_aba", lambda spreadsheet_id, aba: [linha])

    resumo = importar_do_google_sheets(db, "planilha-fake-id")

    assert resumo.criados == 1
    assert resumo.rejeitados == []
    banco = listar_bancos(db)[0]
    assert banco.cnpj_alternativo is None


def test_importar_do_google_sheets_traz_segunda_opcao_de_cnpj_real(db, monkeypatch):
    linha = _linha_sheets("Banco Itau", "contato@x.com", CNPJ_VALIDO, cnpj_alt=CNPJ_VALIDO_2)
    monkeypatch.setattr(bancos_service.google_sheets, "ler_aba", lambda spreadsheet_id, aba: [linha])

    importar_do_google_sheets(db, "planilha-fake-id")

    banco = listar_bancos(db)[0]
    assert banco.cnpj_alternativo == CNPJ_VALIDO_2


def test_importar_do_google_sheets_atualiza_banco_existente_por_nome(db, monkeypatch):
    criar_banco(db, "Banco XPTO", CNPJ_VALIDO, "velho@x.com")
    linha = _linha_sheets("banco xpto", "novo@x.com", CNPJ_VALIDO_2)
    monkeypatch.setattr(bancos_service.google_sheets, "ler_aba", lambda spreadsheet_id, aba: [linha])

    resumo = importar_do_google_sheets(db, "planilha-fake-id")

    assert resumo.criados == 0
    assert resumo.atualizados == 1
    banco = listar_bancos(db)[0]
    assert banco.cnpj == CNPJ_VALIDO_2
    assert banco.email == "novo@x.com"


def test_importar_do_google_sheets_ignora_linha_sem_nome_de_banco(db, monkeypatch):
    linha = _linha_sheets("", "contato@x.com", CNPJ_VALIDO)
    monkeypatch.setattr(bancos_service.google_sheets, "ler_aba", lambda spreadsheet_id, aba: [linha])

    resumo = importar_do_google_sheets(db, "planilha-fake-id")

    assert resumo.criados == 0
    assert resumo.atualizados == 0
    assert listar_bancos(db, apenas_ativos=False) == []

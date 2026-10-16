import tempfile
from pathlib import Path

import openpyxl
import pytest

from app.models import Banco
from app.services.bancos import (
    alterar_ativo_banco,
    atualizar_banco,
    criar_banco,
    excluir_banco,
    importar_planilha_bancos,
    listar_bancos,
)

CNPJ_VALIDO = "11.222.333/0001-81"


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

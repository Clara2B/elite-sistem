from datetime import date

from app.models import EmpresaCliente, Laudo
from app.services.empresas import (
    LISTA_OFICIAL_EMPRESAS,
    get_or_create_empresa,
    sincronizar_lista_oficial,
)
from app.utils import normalize


def test_sincroniza_cria_atualiza_e_exclui(db):
    existente = get_or_create_empresa(db, "ABSOLUTA")
    obsoleta = get_or_create_empresa(db, "EMPRESA ANTIGA")
    db.commit()

    lista = [("ABSOLUTA", "11.111.111/0001-11"), ("NOVA EMPRESA", "22.222.222/0001-22")]
    resumo = sincronizar_lista_oficial(db, lista)

    assert resumo.atualizadas_cnpj == ["ABSOLUTA"]
    assert resumo.criadas == ["NOVA EMPRESA"]
    assert resumo.excluidas == ["EMPRESA ANTIGA"]
    assert resumo.nao_excluidas_por_vinculo == []

    db.refresh(existente)
    assert existente.cnpj == "11.111.111/0001-11"
    assert db.get(EmpresaCliente, obsoleta.id) is None
    nova = next(e for e in db.query(EmpresaCliente).all() if e.nome == "NOVA EMPRESA")
    assert nova.cnpj == "22.222.222/0001-22"


def test_sincroniza_nao_exclui_empresa_com_vinculo(db):
    com_laudo = get_or_create_empresa(db, "COM LAUDO")
    db.add(Laudo(empresa_cliente_id=com_laudo.id, tipo_laudo_nome="AUTO", data=date(2026, 1, 1), status="SOLICITAÇÃO"))
    db.commit()

    resumo = sincronizar_lista_oficial(db, [("ABSOLUTA", None)])

    assert resumo.nao_excluidas_por_vinculo == ["COM LAUDO"]
    assert resumo.excluidas == []
    # não foi apagada de verdade
    assert db.get(EmpresaCliente, com_laudo.id) is not None


def test_sincroniza_sem_cnpj_na_lista_nao_apaga_cnpj_existente(db):
    """`OPÇÃO1` não tem CNPJ no PDF oficial — sincronizar não pode apagar um
    CNPJ que já estava cadastrado só porque a lista não trouxe um valor pra
    essa entrada."""
    empresa = get_or_create_empresa(db, "OPÇÃO1")
    empresa.cnpj = "33.333.333/0001-33"
    db.commit()

    resumo = sincronizar_lista_oficial(db, [("OPÇÃO1", None)])

    assert resumo.sem_mudanca == ["OPÇÃO1"]
    db.refresh(empresa)
    assert empresa.cnpj == "33.333.333/0001-33"


def test_sincroniza_e_case_insensitive_por_nome(db):
    get_or_create_empresa(db, "absoluta")
    db.commit()

    resumo = sincronizar_lista_oficial(db, [("ABSOLUTA", "11.111.111/0001-11")])

    assert resumo.criadas == []
    assert resumo.atualizadas_cnpj == ["ABSOLUTA"]


def test_lista_oficial_tem_48_empresas_sem_duplicidade():
    assert len(LISTA_OFICIAL_EMPRESAS) == 48
    nomes_normalizados = [normalize(nome) for nome, _ in LISTA_OFICIAL_EMPRESAS]
    assert len(nomes_normalizados) == len(set(nomes_normalizados))


def test_lista_oficial_usa_wnfast_sem_espaco():
    """A planilha real de processos já usa "WNFAST" (sem espaço) nos
    registros existentes — não "WN FAST" (como está escrito no PDF oficial)
    — confirmado pela Clara (2026-09-24), pra não perder o vínculo com
    processos já importados."""
    nomes = {nome for nome, _ in LISTA_OFICIAL_EMPRESAS}
    assert "WNFAST" in nomes
    assert "WN FAST" not in nomes

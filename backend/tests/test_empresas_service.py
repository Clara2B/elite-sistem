from datetime import date

from app.models import Audiencia, Cobranca, EmpresaCliente, Laudo, Processo
from app.services.empresas import (
    LISTA_OFICIAL_EMPRESAS,
    contar_vinculos_empresa,
    excluir_empresa,
    excluir_empresas_inativas,
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


def test_excluir_inativas_apaga_so_as_desativadas(db):
    ativa = get_or_create_empresa(db, "ATIVA")
    inativa1 = get_or_create_empresa(db, "INATIVA UM")
    inativa2 = get_or_create_empresa(db, "INATIVA DOIS")
    inativa1.ativo = False
    inativa2.ativo = False
    db.commit()

    resumo = excluir_empresas_inativas(db)

    assert sorted(resumo.excluidas) == ["INATIVA DOIS", "INATIVA UM"]
    assert resumo.nao_excluidas_por_vinculo == []
    assert db.get(EmpresaCliente, ativa.id) is not None
    assert db.get(EmpresaCliente, inativa1.id) is None
    assert db.get(EmpresaCliente, inativa2.id) is None


def test_excluir_inativas_nao_apaga_vinculada(db):
    inativa_com_laudo = get_or_create_empresa(db, "INATIVA COM LAUDO")
    inativa_com_laudo.ativo = False
    db.add(Laudo(empresa_cliente_id=inativa_com_laudo.id, tipo_laudo_nome="AUTO", data=date(2026, 1, 1), status="SOLICITAÇÃO"))
    db.commit()

    resumo = excluir_empresas_inativas(db)

    assert resumo.excluidas == []
    assert resumo.nao_excluidas_por_vinculo == ["INATIVA COM LAUDO"]
    assert db.get(EmpresaCliente, inativa_com_laudo.id) is not None


def test_excluir_inativas_sem_nenhuma_inativa_nao_faz_nada(db):
    get_or_create_empresa(db, "ATIVA")
    db.commit()

    resumo = excluir_empresas_inativas(db)

    assert resumo.excluidas == []
    assert resumo.nao_excluidas_por_vinculo == []


def test_excluir_empresa_com_vinculo_sem_destino_continua_bloqueada(db):
    origem = get_or_create_empresa(db, "ORIGEM SEM DESTINO")
    db.add(Laudo(empresa_cliente_id=origem.id, tipo_laudo_nome="AUTO", data=date(2026, 1, 1), status="SOLICITAÇÃO"))
    db.commit()

    try:
        excluir_empresa(db, origem.id)
        assert False, "deveria ter recusado"
    except ValueError as e:
        assert "não é possível excluir" in str(e).lower()
    assert db.get(EmpresaCliente, origem.id) is not None


def test_excluir_empresa_com_destino_reatribui_os_quatro_tipos_de_vinculo(db):
    origem = get_or_create_empresa(db, "ORIGEM COM DESTINO")
    destino = get_or_create_empresa(db, "DESTINO")
    db.add(Laudo(empresa_cliente_id=origem.id, tipo_laudo_nome="AUTO", data=date(2026, 1, 1), status="SOLICITAÇÃO"))
    db.add(Audiencia(empresa_cliente_id=origem.id, nome_cliente="Fulano", data_recebimento=date(2026, 1, 1)))
    db.add(Cobranca(empresa_cliente_id=origem.id, data=date(2026, 1, 1), tipo_cobranca="MENSALIDADE", cobrador="ELITE", valor=100.0))
    db.add(Processo(numero_processo="0001", empresa_cliente_id=origem.id))
    db.commit()

    excluir_empresa(db, origem.id, empresa_destino_id=destino.id)

    assert db.get(EmpresaCliente, origem.id) is None
    laudo = db.query(Laudo).one()
    audiencia = db.query(Audiencia).one()
    cobranca = db.query(Cobranca).one()
    processo = db.query(Processo).one()
    assert laudo.empresa_cliente_id == destino.id
    assert audiencia.empresa_cliente_id == destino.id
    assert cobranca.empresa_cliente_id == destino.id
    assert processo.empresa_cliente_id == destino.id


def test_excluir_empresa_destino_precisa_existir(db):
    origem = get_or_create_empresa(db, "ORIGEM DESTINO INEXISTENTE")
    db.add(Laudo(empresa_cliente_id=origem.id, tipo_laudo_nome="AUTO", data=date(2026, 1, 1), status="SOLICITAÇÃO"))
    db.commit()

    try:
        excluir_empresa(db, origem.id, empresa_destino_id=999999)
        assert False, "deveria ter recusado"
    except ValueError as e:
        assert "não encontrada" in str(e).lower()


def test_excluir_empresa_destino_precisa_ser_diferente_da_origem(db):
    origem = get_or_create_empresa(db, "ORIGEM IGUAL DESTINO")
    db.add(Laudo(empresa_cliente_id=origem.id, tipo_laudo_nome="AUTO", data=date(2026, 1, 1), status="SOLICITAÇÃO"))
    db.commit()

    try:
        excluir_empresa(db, origem.id, empresa_destino_id=origem.id)
        assert False, "deveria ter recusado"
    except ValueError as e:
        assert "diferente" in str(e).lower()


def test_excluir_empresa_sem_vinculo_ignora_destino_nao_informado(db):
    sem_vinculo = get_or_create_empresa(db, "SEM VINCULO NENHUM")
    db.commit()

    excluir_empresa(db, sem_vinculo.id)  # nenhum vínculo — não precisa de destino

    assert db.get(EmpresaCliente, sem_vinculo.id) is None


def test_contar_vinculos_empresa(db):
    empresa = get_or_create_empresa(db, "CONTAGEM DE VINCULOS")
    db.add(Laudo(empresa_cliente_id=empresa.id, tipo_laudo_nome="AUTO", data=date(2026, 1, 1), status="SOLICITAÇÃO"))
    db.commit()

    vinculos = contar_vinculos_empresa(db, empresa.id)
    assert vinculos["laudos"] == 1
    assert vinculos["processos"] == 0


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

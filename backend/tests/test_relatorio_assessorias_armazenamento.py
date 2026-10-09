"""Fase 8 (Gerador de Relatórios Mensais das Assessorias) — armazenamento.py."""
from __future__ import annotations

from datetime import date

from app.auth import hash_senha
from app.models import Usuario
from app.relatorio_assessorias import armazenamento
from app.relatorio_assessorias.avisos import Aviso
from app.relatorio_assessorias.leitores.base import Origem
from app.relatorio_assessorias.render import DadosRelatorio
from app.relatorio_assessorias.secoes.contrarias import (
    ProcessoContrario,
    ResultadoContrarias,
)
from app.relatorio_assessorias.secoes.extrajudiciais import (
    ClienteAusente,
    ResultadoExtrajudiciais,
)
from app.relatorio_assessorias.secoes.iniciais import ResultadoIniciais
from app.relatorio_assessorias.secoes.judiciais import ResultadoAudiencias
from app.relatorio_assessorias.secoes.laudos import ResultadoLaudos
from app.relatorio_assessorias.secoes.manuais import (
    CamposManuais,
    PastasRevisionais,
    SentencaProcedente,
)
from app.relatorio_assessorias.secoes.procons import Procon, ResultadoProcons


def _origem(linha: int) -> Origem:
    return Origem("teste", "aba", linha)


def _dados() -> DadosRelatorio:
    return DadosRelatorio(
        assessoria="EWS",
        mes=8,
        ano=2026,
        data_corte=date(2026, 9, 4),
        laudos=ResultadoLaudos(elaborados=14, entregues_dentro_prazo=14, pendentes=0, pendentes_atrasados=0),
        iniciais=ResultadoIniciais(distribuidos_no_mes=2, aguardando_distribuicao=3, faixas={"Até 7 dias": 2}),
        extrajudiciais=ResultadoExtrajudiciais(
            enviadas=16, realizadas=10, pendentes_proximos_meses=19,
            clientes_ausentes=[ClienteAusente("Antonio Beserra da Costa", _origem(1))],
        ),
        audiencias_judiciais=ResultadoAudiencias(quantidade=10),
        audiencias_contrarias=ResultadoAudiencias(quantidade=5),
        contrarias=ResultadoContrarias(
            incluidos_no_mes=3, ativos_total=29, ativos_por_uf={"RJ": 3, "SP": 12},
            lista_judiciais=[
                ProcessoContrario("Fulano", "0000001-11.2026.8.19.0001", "RJ", 1500.0, date(2026, 8, 1), _origem(2))
            ],
            lista_trabalhistas=[],
        ),
        procons=ResultadoProcons(lista=[Procon("Beltrano", "0000002-22.2026.8.13.0001", "EM ANDAMENTO", _origem(3))]),
        manuais=CamposManuais(
            pastas_revisionais=PastasRevisionais(8, 3, 0, 5, 13),
            processos_ativos_revisionais_total=3,
            processos_ativos_revisionais_por_uf={"RJ": 2, "SP": 1},
            sentencas_procedentes=[SentencaProcedente("Ciclano", "0000003-33.2026.8.13.0001", "MG")],
            processos_ganhos_por_uf={},
            sentencas_favoraveis_contrarias=[],
            extrajudiciais_solicitacoes_pendentes_correcao=0,
        ),
        avisos=[Aviso(_origem(4), "processo sem data")],
    )


def test_serializar_e_desserializar_preserva_tudo():
    dados = _dados()
    serializado = armazenamento._serializar(dados)
    reconstruido = armazenamento._desserializar_dict(serializado)

    assert reconstruido == dados


def test_numeros_calculados_cobre_todos_os_campos_sobrescreviveis():
    dados = _dados()
    numeros = armazenamento.numeros_calculados(dados)
    assert set(numeros.keys()) == set(armazenamento.CAMPOS_NUMERICOS_SOBRESCREVIVEIS)
    assert numeros["laudos.elaborados"] == 14
    assert numeros["manuais.pastas_revisionais.acumulado_crm"] == 13


def test_aplicar_sobrescritas_muda_so_os_campos_informados():
    dados = _dados()
    armazenamento.aplicar_sobrescritas(dados, {"laudos.elaborados": 13})
    assert dados.laudos.elaborados == 13
    assert dados.laudos.entregues_dentro_prazo == 14  # não mexeu em outro campo


def test_aplicar_sobrescritas_ignora_campo_fora_da_lista():
    dados = _dados()
    armazenamento.aplicar_sobrescritas(dados, {"laudos.nao_existe": 999})  # não levanta, só ignora
    assert not hasattr(dados.laudos, "nao_existe")


def test_salvar_e_carregar_resultado(db):
    usuario = Usuario(nome="Teste", email="teste@teste.local", senha_hash=hash_senha("x"), papel_global="ADMIN_SUPERIOR")
    db.add(usuario)
    db.commit()

    dados = _dados()
    registro = armazenamento.salvar_resultado(db, dados, usuario)
    assert registro.id is not None

    carregado = armazenamento.carregar_resultado(db, "EWS", 8, 2026)
    assert carregado is not None
    assert carregado.id == registro.id
    reconstruido = armazenamento.dados_efetivos(carregado)
    assert reconstruido == dados


def test_salvar_resultado_duas_vezes_atualiza_sem_duplicar(db):
    usuario = Usuario(nome="Teste", email="teste2@teste.local", senha_hash=hash_senha("x"), papel_global="ADMIN_SUPERIOR")
    db.add(usuario)
    db.commit()

    armazenamento.salvar_resultado(db, _dados(), usuario)
    dados2 = _dados()
    dados2.laudos.elaborados = 20
    armazenamento.salvar_resultado(db, dados2, usuario)

    todos = armazenamento.listar_resultados(db, 8, 2026)
    assert len(todos) == 1
    assert armazenamento.dados_efetivos(todos[0]).laudos.elaborados == 20


def test_sobrescrever_numero_preserva_na_proxima_gravacao(db):
    usuario = Usuario(nome="Teste", email="teste3@teste.local", senha_hash=hash_senha("x"), papel_global="ADMIN_SUPERIOR")
    db.add(usuario)
    db.commit()

    registro = armazenamento.salvar_resultado(db, _dados(), usuario)
    armazenamento.sobrescrever_numero(db, registro, usuario, "laudos.elaborados", 99)
    assert armazenamento.dados_efetivos(registro).laudos.elaborados == 99

    # reprocessar (salvar de novo) não deve apagar a sobrescrita
    armazenamento.salvar_resultado(db, _dados(), usuario)
    recarregado = armazenamento.carregar_resultado(db, "EWS", 8, 2026)
    assert armazenamento.dados_efetivos(recarregado).laudos.elaborados == 99


def test_sobrescrever_numero_fora_da_lista_levanta_erro(db):
    usuario = Usuario(nome="Teste", email="teste4@teste.local", senha_hash=hash_senha("x"), papel_global="ADMIN_SUPERIOR")
    db.add(usuario)
    db.commit()
    registro = armazenamento.salvar_resultado(db, _dados(), usuario)
    try:
        armazenamento.sobrescrever_numero(db, registro, usuario, "laudos.campo_inexistente", 1)
        raise AssertionError("deveria ter levantado ValueError")
    except ValueError:
        pass


def test_reprocessar_preserva_campos_manuais_ja_preenchidos(db):
    usuario = Usuario(nome="Teste", email="teste5@teste.local", senha_hash=hash_senha("x"), papel_global="ADMIN_SUPERIOR")
    db.add(usuario)
    db.commit()

    registro = armazenamento.salvar_resultado(db, _dados(), usuario)
    novos_manuais = CamposManuais(
        pastas_revisionais=PastasRevisionais(1, 1, 1, 1, 1),
        processos_ativos_revisionais_total=5,
        processos_ativos_revisionais_por_uf={"SP": 5},
        sentencas_procedentes=[],
        processos_ganhos_por_uf={},
        sentencas_favoraveis_contrarias=[],
        extrajudiciais_solicitacoes_pendentes_correcao=2,
    )
    armazenamento.salvar_campos_manuais(db, registro, novos_manuais, usuario)

    # reprocessar com manuais "vazios" (como a planilha sempre devolve) não apaga o que foi digitado
    dados_reprocessados = _dados()
    armazenamento.salvar_resultado(db, dados_reprocessados, usuario)
    recarregado = armazenamento.carregar_resultado(db, "EWS", 8, 2026)
    assert armazenamento.dados_efetivos(recarregado).manuais.processos_ativos_revisionais_total == 5

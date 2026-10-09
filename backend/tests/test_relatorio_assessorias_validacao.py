"""Fase 5 (Gerador de Relatórios Mensais das Assessorias) — avisos e
conferências cruzadas. Um teste por função, `LinhaBruta` construídas
diretamente (mesmo padrão da Fase 4)."""
from __future__ import annotations

from datetime import date

from app.relatorio_assessorias import validacao
from app.relatorio_assessorias.leitores.base import LinhaBruta, Origem
from app.relatorio_assessorias.secoes.contrarias import ResultadoContrarias


def _origem(linha: int) -> Origem:
    return Origem("teste", "aba", linha)


# ---------- detectar_empresas_desconhecidas ----------


def test_detectar_empresas_desconhecidas_agrupa_por_nome():
    linhas = [
        LinhaBruta({"empresa": "ANGITU"}, _origem(1)),
        LinhaBruta({"empresa": "ANGITU"}, _origem(2)),
        LinhaBruta({"empresa": "EWS"}, _origem(3)),
    ]
    resultado = validacao.detectar_empresas_desconhecidas(linhas, "empresa", {"EWS": "EWS"})
    assert len(resultado) == 1
    assert resultado[0].nome == "ANGITU"
    assert resultado[0].quantidade == 2
    assert resultado[0].origens == [_origem(1), _origem(2)]


def test_detectar_empresas_desconhecidas_celula_multipla_conta_cada_fragmento():
    linhas = [LinhaBruta({"empresa": "ANGITU/OUTRA"}, _origem(1))]
    resultado = validacao.detectar_empresas_desconhecidas(linhas, "empresa", {})
    nomes = {e.nome for e in resultado}
    assert nomes == {"ANGITU", "OUTRA"}


def test_detectar_empresas_desconhecidas_vazio_quando_tudo_reconhecido():
    linhas = [LinhaBruta({"empresa": "EWS"}, _origem(1))]
    resultado = validacao.detectar_empresas_desconhecidas(linhas, "empresa", {"EWS": "EWS"})
    assert resultado == []


# ---------- conferir_soma_uf ----------


def test_conferir_soma_uf_bate_nao_gera_aviso():
    resultado = ResultadoContrarias(ativos_total=2, ativos_por_uf={"RJ": 1, "SP": 1})
    assert validacao.conferir_soma_uf(resultado) is None


def test_conferir_soma_uf_diferente_gera_aviso():
    # 1 ativo sem UF válida (não entra no mapa) além dos 2 mapeados
    resultado = ResultadoContrarias(ativos_total=3, ativos_por_uf={"RJ": 1, "SP": 1})
    aviso = validacao.conferir_soma_uf(resultado)
    assert aviso is not None
    assert "2" in aviso.mensagem and "3" in aviso.mensagem


# ---------- conferir_cronologia_laudos ----------


def test_cronologia_laudos_pronto_antes_da_entrada_gera_aviso():
    linhas = [LinhaBruta({"data": date(2026, 8, 10), "data_pronto": date(2026, 8, 5)}, _origem(1))]
    avisos = validacao.conferir_cronologia_laudos(linhas)
    assert len(avisos) == 1
    assert avisos[0].origem == _origem(1)


def test_cronologia_laudos_ordem_normal_sem_aviso():
    linhas = [LinhaBruta({"data": date(2026, 8, 5), "data_pronto": date(2026, 8, 10)}, _origem(1))]
    assert validacao.conferir_cronologia_laudos(linhas) == []


def test_cronologia_laudos_sem_data_pronto_sem_aviso():
    linhas = [LinhaBruta({"data": date(2026, 8, 5), "data_pronto": None}, _origem(1))]
    assert validacao.conferir_cronologia_laudos(linhas) == []


# ---------- conferir_cronologia_iniciais ----------


def test_cronologia_iniciais_distribuicao_antes_do_recebimento_gera_aviso():
    linhas = [
        LinhaBruta({"data_recebimento": date(2026, 8, 10), "data_distribuicao": date(2026, 8, 5)}, _origem(1)),
    ]
    avisos = validacao.conferir_cronologia_iniciais(linhas)
    assert len(avisos) == 1


def test_cronologia_iniciais_ordem_normal_sem_aviso():
    linhas = [
        LinhaBruta({"data_recebimento": date(2026, 8, 5), "data_distribuicao": date(2026, 8, 10)}, _origem(1)),
    ]
    assert validacao.conferir_cronologia_iniciais(linhas) == []


# ---------- conferir_campos_essenciais ----------


def test_campos_essenciais_vazio_gera_aviso_com_nome_do_campo():
    linhas = [LinhaBruta({"data_recebimento": date(2026, 8, 5), "numero_processo": "", "estados": None}, _origem(1))]
    avisos = validacao.conferir_campos_essenciais(linhas, ["data_recebimento", "numero_processo", "estados"])
    assert len(avisos) == 1
    assert "numero_processo" in avisos[0].mensagem
    assert "estados" in avisos[0].mensagem
    assert "data_recebimento" not in avisos[0].mensagem


def test_campos_essenciais_todos_preenchidos_sem_aviso():
    linhas = [LinhaBruta({"data_recebimento": date(2026, 8, 5), "numero_processo": "123", "estados": "RJ"}, _origem(1))]
    assert validacao.conferir_campos_essenciais(linhas, ["data_recebimento", "numero_processo", "estados"]) == []

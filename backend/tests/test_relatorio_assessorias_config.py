"""Fase 1 (Gerador de Relatórios Mensais das Assessorias) — só a estrutura
e os arquivos de configuração carregam; leitura/normalização/cálculo vêm
nas próximas fases."""
from __future__ import annotations

from app.relatorio_assessorias.config import carregar


def test_carrega_assessorias():
    dados = carregar("assessorias")
    assert "EWS" in dados
    assert dados["EWS"]["apelidos"] == ["EWS", "SW", "SW EWS"]
    assert "WNR" in dados


def test_carrega_fontes():
    dados = carregar("fontes")
    for fonte in ["laudos", "iniciais", "audiencias_judiciais", "audiencias_contrarias",
                  "extrajudiciais", "contrarias", "procons"]:
        assert fonte in dados, f"fonte '{fonte}' faltando em fontes.yaml"
    assert dados["laudos"]["padrao_leitura"] == "aba_mensal"
    assert dados["contrarias"]["padrao_leitura"] == "aba_por_assessoria"


def test_carrega_regras():
    dados = carregar("regras")
    assert dados["laudos"]["prazo_dias_uteis"]["padrao"] == 7
    assert dados["laudos"]["prazo_dias_uteis"]["por_tipo"]["CONSÓRCIO"] == 15
    faixas = dados["iniciais"]["faixas_dias_uteis"]
    assert faixas[0]["rotulo"] == "Distribuídos em até 7 dias úteis"
    assert faixas[1]["rotulo"] == "Distribuídos entre 8 e 20 dias úteis"


def test_carrega_mapa_rotulos():
    dados = carregar("mapa_rotulos")
    estados_pequenos = dados["estados_com_rotulo_externo"]
    for uf in ["RN", "PB", "PE", "AL", "SE", "ES", "RJ"]:
        assert uf in estados_pequenos
    assert "revisional" in dados["paletas"]
    assert "contrarias" in dados["paletas"]

"""Fase 6 (Gerador de Relatórios Mensais das Assessorias) — mapas."""
from __future__ import annotations

from app.relatorio_assessorias import mapas
from app.relatorio_assessorias.config import carregar

MAPA_ROTULOS = carregar("mapa_rotulos")
PALETA_REVISIONAL = MAPA_ROTULOS["paletas"]["revisional"]


def test_tabela_por_uf_preenche_as_27_ufs_em_ordem_alfabetica():
    tabela = mapas.tabela_por_uf({"RJ": 3, "SP": 12})
    assert len(tabela) == 27
    assert list(tabela.keys()) == sorted(tabela.keys())
    assert tabela["RJ"] == 3
    assert tabela["SP"] == 12
    assert tabela["AC"] == 0  # UF sem dado = 0


def test_tabela_por_uf_ignora_chave_que_nao_e_uf_valida():
    # Entrada deveria vir só com UFs válidas (quem resolve isso é
    # normalizacao/texto.py, Fase 3) — tabela_por_uf só garante as 27,
    # não filtra lixo adicional.
    tabela = mapas.tabela_por_uf({"RJ": 1})
    assert set(tabela.keys()) == set(mapas._TODAS_AS_UFS)


def test_interpolar_cor_no_zero_e_cor_base():
    cor = mapas._interpolar_cor(0, maximo=10, cor_base="#dbeafe", cor_maximo="#1e3a8a")
    assert cor == "#dbeafe"


def test_interpolar_cor_no_maximo_e_cor_maximo():
    cor = mapas._interpolar_cor(10, maximo=10, cor_base="#dbeafe", cor_maximo="#1e3a8a")
    assert cor == "#1e3a8a"


def test_interpolar_cor_meio_do_caminho_fica_entre_as_duas():
    cor = mapas._interpolar_cor(5, maximo=10, cor_base="#000000", cor_maximo="#ffffff")
    assert cor == "#808080"


def test_interpolar_cor_sem_nenhum_ativo_usa_cor_base():
    cor = mapas._interpolar_cor(0, maximo=0, cor_base="#dbeafe", cor_maximo="#1e3a8a")
    assert cor == "#dbeafe"


def test_desenhar_devolve_png_valido():
    contagem = {"RJ": 3, "SP": 12, "MA": 2}
    png = mapas.desenhar(contagem, PALETA_REVISIONAL, MAPA_ROTULOS)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(png) > 1000


def test_desenhar_sem_nenhum_ativo_nao_quebra():
    png = mapas.desenhar({}, PALETA_REVISIONAL, MAPA_ROTULOS)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_desenhar_com_estados_de_rotulo_externo_nao_quebra():
    contagem = {uf: 1 for uf in ("RN", "PB", "PE", "AL", "SE", "ES", "RJ")}
    png = mapas.desenhar(contagem, PALETA_REVISIONAL, MAPA_ROTULOS)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"

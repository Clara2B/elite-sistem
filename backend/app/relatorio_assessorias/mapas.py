"""Dois mapas do Brasil por relatório — revisional e contrárias (Fase 6),
desenhados com matplotlib puro a partir da mesma contagem {UF: quantidade}
que preenche a tabela por UF ao lado (`tabela_por_uf` — nunca divergem,
porque vêm da mesma fonte).

Preparação (uma vez, fora do sistema): `scripts/preparar_mapa_brasil.py`
baixa a malha de estados (GeoJSON público derivado do IBGE — ver docstring
do script pra detalhes de por que não é a API oficial do IBGE direto),
simplifica os contornos e salva `assets/brasil_uf.json`: só os contornos
(lista de polígonos por UF) e o centroide de cada UF, prontos pra desenhar
sem precisar de geopandas/shapely em produção — só este JSON + matplotlib
puro, sem acesso à internet.

Desenho:
- Polígonos com `matplotlib.collections.PolyCollection`, borda branca
  fina, sem eixos.
- Cor por faixa de valor: 0 = cor base clara da paleta; valores maiores
  interpolados linearmente até a cor do máximo (paletas em
  `config/mapa_rotulos.yaml`).
- Rótulo "UF\\nquantidade" no centroide de cada estado.
- Estados pequenos demais pro rótulo caber dentro (RN, PB, PE, AL, SE, ES,
  RJ — `estados_com_rotulo_externo` em `config/mapa_rotulos.yaml`) têm o
  rótulo deslocado pra fora, ligado por uma linha de chamada até o
  centroide.
- Saída PNG em 200 dpi, fundo transparente.
"""
from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # sem display em produção — só gera o PNG em memória
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection

from app.relatorio_assessorias.normalizacao.texto import UFS

_CAMINHO_GEOMETRIAS = Path(__file__).resolve().parent / "assets" / "brasil_uf.json"
_TODAS_AS_UFS = sorted(UFS)


def _carregar_geometrias() -> dict:
    with _CAMINHO_GEOMETRIAS.open(encoding="utf-8") as arquivo:
        return json.load(arquivo)["estados"]


def _hex_para_rgb(cor_hex: str) -> tuple[float, float, float]:
    cor_hex = cor_hex.lstrip("#")
    return tuple(int(cor_hex[i : i + 2], 16) / 255 for i in (0, 2, 4))


def _rgb_para_hex(rgb: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{round(componente * 255):02x}" for componente in rgb)


def _interpolar_cor(valor: int, maximo: int, cor_base: str, cor_maximo: str) -> str:
    if maximo <= 0:
        return cor_base
    fracao = min(valor / maximo, 1.0)
    base = _hex_para_rgb(cor_base)
    topo = _hex_para_rgb(cor_maximo)
    interpolado = tuple(base[i] + (topo[i] - base[i]) * fracao for i in range(3))
    return _rgb_para_hex(interpolado)


def tabela_por_uf(contagem_por_uf: dict[str, int]) -> dict[str, int]:
    """Mesmo dict usado pro mapa, garantindo as 27 UFs em ordem alfabética
    (UF ausente = 0) — a tabela ao lado do mapa sai exatamente daqui, pra
    nunca divergir do que o mapa desenha."""
    return {uf: contagem_por_uf.get(uf, 0) for uf in _TODAS_AS_UFS}


def desenhar(contagem_por_uf: dict[str, int], paleta: dict, rotulos_config: dict) -> bytes:
    """Desenha o mapa do Brasil colorido por `contagem_por_uf` (UF ausente
    conta como 0) com a `paleta` (`cor_base`/`cor_maximo`, de
    `config/mapa_rotulos.yaml::paletas`) e os deslocamentos de rótulo de
    `rotulos_config` (`config/mapa_rotulos.yaml`, raiz — já tem a chave
    `estados_com_rotulo_externo`). Devolve os bytes do PNG (200 dpi, fundo
    transparente)."""
    geometrias = _carregar_geometrias()
    maximo = max(contagem_por_uf.values(), default=0)
    estados_com_rotulo_externo = rotulos_config.get("estados_com_rotulo_externo", {})

    figura, eixo = plt.subplots(figsize=(8, 8))
    poligonos: list[list[list[float]]] = []
    cores: list[str] = []
    for uf, geometria in geometrias.items():
        quantidade = contagem_por_uf.get(uf, 0)
        cor = _interpolar_cor(quantidade, maximo, paleta["cor_base"], paleta["cor_maximo"])
        for poligono in geometria["poligonos"]:
            poligonos.append(poligono)
            cores.append(cor)

    colecao = PolyCollection(poligonos, facecolors=cores, edgecolors="white", linewidths=0.5)
    eixo.add_collection(colecao)

    for uf, geometria in geometrias.items():
        quantidade = contagem_por_uf.get(uf, 0)
        centro_x, centro_y = geometria["centro"]
        texto = f"{uf}\n{quantidade}"
        if uf in estados_com_rotulo_externo:
            deslocamento = estados_com_rotulo_externo[uf]
            eixo.annotate(
                texto,
                xy=(centro_x, centro_y),
                xytext=(deslocamento["offset_x"], deslocamento["offset_y"]),
                textcoords="offset points",
                ha="center",
                va="center",
                fontsize=7,
                arrowprops={"arrowstyle": "-", "color": "#666666", "linewidth": 0.5},
            )
        else:
            eixo.annotate(texto, xy=(centro_x, centro_y), ha="center", va="center", fontsize=7)

    eixo.autoscale()
    eixo.set_aspect("equal")
    eixo.axis("off")

    buffer = BytesIO()
    figura.savefig(buffer, format="png", dpi=200, transparent=True, bbox_inches="tight")
    plt.close(figura)
    return buffer.getvalue()

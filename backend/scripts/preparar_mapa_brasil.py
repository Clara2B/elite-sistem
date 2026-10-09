"""Preparação do mapa do Brasil (Fase 6, rodar UMA VEZ, fora do sistema).

Gera `app/relatorio_assessorias/assets/brasil_uf.json`: os contornos
simplificados das 27 UFs + o centro de cada uma (pra posicionar o rótulo),
num formato que `mapas.py` lê em produção com matplotlib puro — SEM
geopandas e SEM acesso à internet em produção (especificação, "Mapas com
matplotlib").

Fonte dos dados: GeoJSON das fronteiras estaduais do Brasil, do repositório
público `codeforamerica/click_that_hood` — dados derivados do IBGE. A
especificação pedia "pacote geobr ou GeoJSON oficial" (a API de malhas do
IBGE, `servicodados.ibge.gov.br`); a política de rede deste ambiente de
desenvolvimento bloqueia esse domínio especificamente (`curl` devolve 403
do proxy da organização), então usei esta fonte alternativa — mesma malha
estadual, sem precisar de acesso irrestrito à internet. Reportado à Clara.

Dependência só deste script, não do sistema: `pip install shapely` (não
entra em requirements.txt — produção nunca roda este arquivo).

Uso: `python scripts/preparar_mapa_brasil.py`
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

from shapely.geometry import shape

URL_GEOJSON = "https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/brazil-states.geojson"
TOLERANCIA_SIMPLIFICACAO = 0.02  # graus — reduz nº de vértices mantendo a forma reconhecível
CASAS_DECIMAIS = 4
CAMINHO_SAIDA = Path(__file__).resolve().parent.parent / "app" / "relatorio_assessorias" / "assets" / "brasil_uf.json"


def _baixar_geojson() -> dict:
    with urllib.request.urlopen(URL_GEOJSON) as resposta:
        return json.load(resposta)


def _arredondar_coords(coords) -> list[list[float]]:
    return [[round(x, CASAS_DECIMAIS), round(y, CASAS_DECIMAIS)] for x, y in coords]


def _poligonos_e_centro(geometria_bruta: dict) -> tuple[list[list[list[float]]], list[float]]:
    geometria = shape(geometria_bruta)
    simplificada = geometria.simplify(TOLERANCIA_SIMPLIFICACAO, preserve_topology=True)
    centro = [round(simplificada.centroid.x, CASAS_DECIMAIS), round(simplificada.centroid.y, CASAS_DECIMAIS)]

    poligonos_individuais = list(simplificada.geoms) if simplificada.geom_type == "MultiPolygon" else [simplificada]
    # Mapa de relatório, não carta náutica: só o maior polígono por UF —
    # descarta ilhotas da costa que a simplificação reduz a 4-5 vértices
    # (achado real: RJ tinha 1 polígono principal + 35 ilhas assim).
    maior = max(poligonos_individuais, key=lambda p: p.area)
    poligonos = [_arredondar_coords(maior.exterior.coords)]
    return poligonos, centro


def main() -> None:
    geojson = _baixar_geojson()
    estados = {}
    for feature in geojson["features"]:
        uf = feature["properties"]["sigla"]
        poligonos, centro = _poligonos_e_centro(feature["geometry"])
        estados[uf] = {"poligonos": poligonos, "centro": centro}

    assert len(estados) == 27, f"esperava 27 UFs, achei {len(estados)}"

    CAMINHO_SAIDA.parent.mkdir(parents=True, exist_ok=True)
    with CAMINHO_SAIDA.open("w", encoding="utf-8") as arquivo:
        json.dump({"estados": estados}, arquivo, ensure_ascii=False, indent=None, separators=(",", ":"))

    print(f"Gerado {CAMINHO_SAIDA} ({CAMINHO_SAIDA.stat().st_size} bytes, {len(estados)} UFs).")


if __name__ == "__main__":
    main()

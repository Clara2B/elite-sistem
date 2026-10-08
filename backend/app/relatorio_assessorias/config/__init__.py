"""Carregamento dos arquivos de configuração (`*.yaml` nesta pasta) — ponto
único pra achar e ler esses arquivos, pra não espalhar `Path(__file__)...`
por leitores/normalizacao/secoes. Cada chamada relê o arquivo do disco (sem
cache): esses YAMLs são pequenos e lidos poucas vezes por requisição, e não
cachear evita servir uma versão antiga depois de editar um arquivo com o
servidor já no ar."""
from __future__ import annotations

from pathlib import Path

import yaml

_PASTA_CONFIG = Path(__file__).resolve().parent


def carregar(nome: str) -> dict:
    """`nome` sem extensão, ex.: `carregar("regras")` lê `regras.yaml`."""
    caminho = _PASTA_CONFIG / f"{nome}.yaml"
    with caminho.open(encoding="utf-8") as arquivo:
        return yaml.safe_load(arquivo) or {}

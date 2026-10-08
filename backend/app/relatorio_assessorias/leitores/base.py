"""Localização de cabeçalho e leitura comum aos três padrões (Fase 2).

Responsabilidades (especificação, "Regras de leitura comuns"):
- Cabeçalho localizado, não fixo: procura, nas primeiras 10 linhas de uma
  aba, a linha que contém as colunas esperadas (comparação sem acento e
  com sinônimos de `config/fontes.yaml`).
- Colunas duplicadas (ex.: "DATA" duas vezes em Laudos) resolvidas por
  posição relativa, configurada em `fontes.yaml`.
- Linhas vazias e linhas de título no meio da aba são descartadas.
- Toda linha lida devolve, junto com o valor, a origem (planilha, aba,
  número da linha) — usada pelos avisos de validação pra apontar onde
  corrigir.
"""

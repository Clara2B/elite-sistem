"""Padrão de leitura "aba por assessoria" (Fase 2) — fontes Contrárias e
Procons (arquivos CONTRÁRIAS - NOVO e PROCON E EXTRAJUDICIAL, uma aba por
assessoria, nomeada com o apelido dela).

Lê todas as abas cujo nome corresponde a algum apelido cadastrado em
`config/assessorias.yaml` (ex.: pra EWS, lê as abas "SW" e "EWS" e soma os
registros das duas). Aba cujo nome não bate com nenhum apelido conhecido
vira aviso global ("empresa desconhecida: X").
"""

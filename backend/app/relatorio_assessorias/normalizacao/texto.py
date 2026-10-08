"""Normalização de texto livre — nomes de pessoas e UF (Fase 3).

Nomes de pessoas (especificação): tabs e espaços no início, caixa alta e
baixa misturadas. Tratamento: remove espaços extras; mantém a grafia
original (sem mudar caixa) — diferente da normalização usada pra comparar
nomes de assessoria/coluna, que ignora caixa.

UF (especificação): vazia, minúscula. Tratamento: maiúscula; valida contra
as 27 UFs; inválida vira aviso e fica fora do mapa.

Também usado por `leitores/base.py` pra comparar nome de coluna/aba sem
acento, sem espaço extra e em maiúsculas (mesma função, uso diferente).
"""

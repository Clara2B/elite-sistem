"""Resultado mensal calculado (Fase 8) — decisão da Clara, 2026-10-08
("Armazenamento"): fica salvo no banco do sistema (Postgres, tabela nova e
aditiva — nenhuma tabela existente é alterada), por mês (ex.: `2026-08`),
pra não precisar reprocessar.

Os arquivos gerados (.docx/.pdf/.zip) NÃO ficam armazenados — são gerados
sob demanda a cada download, a partir do resultado salvo, igual ao padrão
já usado em Laudos/Audiências/Processos/Correspondências hoje (nada fica
em disco; o disco do Render também não é persistente entre deploys, então
guardar arquivo gerado não seria confiável de qualquer forma).

Campos manuais (ver secoes/manuais.py) e sobrescrita de números na tela de
revisão (ver DECISIONS.md — "Qualquer número pode ser sobrescrito; o valor
sobrescrito fica marcado e registrado") também ficam guardados aqui, por
mês e por assessoria.
"""

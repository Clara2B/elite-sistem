"""Padrão de leitura "aba por mês" (Fase 2) — fontes Laudos e Iniciais.

Aba do mês reconhecida por padrão flexível: nome por extenso ou abreviado +
ano com 2 ou 4 dígitos (ex.: "AGO26", "ABRIL26", "AGOSTO 2026"), ou ausente
quando o arquivo é de um ano só. Aba não encontrada vira erro bloqueante
pra aquela seção (especificação, "Regras de leitura comuns").

Iniciais também lê as abas dos meses anteriores do mesmo ano, pra resolver
"aguardando distribuição" de casos recebidos em mês anterior.
"""

"""Normalização de datas (Fase 3).

Problemas reais encontrados nas planilhas (especificação, "Normalização e
validação dos dados"): texto "30/06/2026 - 14:00", "2026.0", "--", ~40
células com ano digitado errado (serial fora do limite, ano ~20000).

Tratamento: aceita datetime, serial do Excel válido e texto dd/mm/aaaa
(com ou sem hora). Fora disso, vazio + aviso. Datas fora de 2020-2030
também viram aviso (não bloqueia, mas sinaliza pra conferência).
"""

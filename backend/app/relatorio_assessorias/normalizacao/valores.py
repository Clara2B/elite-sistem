"""Normalização de valores monetários (Fase 3) — coluna VALOR DA CAUSA.

Problemas reais encontrados (especificação): "R$ 53.128,60\\t", "$64,000.00",
"21800.0", "R$15.295,68.", "NÃO INFORMADO", "TRABALHISTA".

Tratamento: converte pra Decimal; formato brasileiro (1.234,56) e
americano (1,234.56) detectados pela posição do último separador. Texto
não numérico vira "Não informado" (não bloqueia, não é erro). Saída sempre
formatada "R$ 1.234,56".
"""

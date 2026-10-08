"""Normalização do número de processo, padrão CNJ (Fase 3).

Problemas reais encontrados (especificação): pontos no lugar de hífens,
espaços e tabs no início, dígito faltando.

Tratamento: chave de comparação = só os dígitos. Com 20 dígitos, reformata
no padrão CNJ (NNNNNNN-DD.AAAA.J.TR.OOOO). Diferente de 20 dígitos: mantém
o original e gera aviso (não tenta adivinhar o que falta).

A deduplicação por CNJ entre Contrárias e Procons (mesmo processo não
aparecer duas vezes) usa essa chave de comparação — ver secoes/contrarias.py.
"""

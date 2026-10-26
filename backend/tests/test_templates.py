"""Filtro Jinja `|horario_brasil` (app/web/templates.py) — converte um
`datetime` gravado em UTC (padrão do projeto, `datetime.utcnow()`) pro
fuso de Brasília só na hora de exibir; nada gravado no banco muda. Bug
real reportado pela Clara em 2026-10-19: a tela de Auditoria mostrava o
horário cru em UTC, 3h à frente do horário real da equipe."""
from __future__ import annotations

from datetime import datetime

from app.web.templates import _horario_brasil


def test_converte_utc_para_brasilia():
    # 02:30 UTC do dia 20 == 23:30 do dia 19 em Brasília (UTC-3)
    assert _horario_brasil(datetime(2026, 10, 20, 2, 30)) == "19/10/2026 23:30"


def test_aceita_formato_customizado():
    assert _horario_brasil(datetime(2026, 10, 20, 2, 30), "%H:%M") == "23:30"


def test_none_vira_string_vazia():
    assert _horario_brasil(None) == ""

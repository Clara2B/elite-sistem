"""API de Audiências — validação de `quinzena` (2026-10-13, auditoria M13).
Não existia nenhum teste de API para este módulo antes (só o serviço, em
test_audiencias_service.py)."""
from __future__ import annotations

from datetime import date

from app.models import Audiencia
from app.services.empresas import get_or_create_empresa


def _planilha(db, empresa_nome="ALFA", qtd=5):
    empresa = get_or_create_empresa(db, empresa_nome)
    for i in range(qtd):
        db.add(
            Audiencia(empresa_cliente_id=empresa.id, nome_cliente=f"Cliente {i}", data_recebimento=date(2026, 9, 1))
        )
    db.commit()


def test_relatorio_com_quinzena_invalida_nao_quebra_com_erro_generico(client, db, admin_token):
    """Antes da correção, `quinzena=99` escapava do try/except (a chamada
    a periodo_quinzenal ficava fora dele) e caía no handler genérico de
    exceção — um 500 sem mensagem clara, em vez do 404 com detalhe que as
    outras validações desse endpoint já dão."""
    _planilha(db)
    headers = {"Authorization": f"Bearer {admin_token}"}

    resposta = client.get(
        "/audiencias/relatorio",
        params={"empresa": "ALFA", "ano": 2026, "mes": 9, "quinzena": 99},
        headers=headers,
    )
    assert resposta.status_code == 404
    assert "Quinzena" in resposta.json()["detail"]


def test_relatorio_com_quinzena_valida_funciona(client, db, admin_token):
    _planilha(db)
    headers = {"Authorization": f"Bearer {admin_token}"}

    resposta = client.get(
        "/audiencias/relatorio",
        params={"empresa": "ALFA", "ano": 2026, "mes": 9, "quinzena": 1},
        headers=headers,
    )
    assert resposta.status_code == 200

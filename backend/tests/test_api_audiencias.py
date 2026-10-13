"""API de Audiências — validação do CNPJ sobrescrito via parâmetro
(2026-10-13, auditoria M12). Não existia nenhum teste de API para este
módulo antes (só o serviço, em test_audiencias_service.py)."""
from __future__ import annotations

from datetime import date

from app.models import Audiencia, LogAuditoria
from app.services.empresas import get_or_create_empresa


def _planilha(db, empresa_nome="ALFA", qtd=5):
    empresa = get_or_create_empresa(db, empresa_nome)
    for i in range(qtd):
        db.add(
            Audiencia(empresa_cliente_id=empresa.id, nome_cliente=f"Cliente {i}", data_recebimento=date(2026, 9, 1))
        )
    db.commit()


def test_relatorio_com_cnpj_valido_sobrescreve_e_registra_auditoria(client, db, admin_token):
    _planilha(db)
    headers = {"Authorization": f"Bearer {admin_token}"}

    resposta = client.get(
        "/audiencias/relatorio",
        params={"empresa": "ALFA", "ano": 2026, "mes": 9, "quinzena": 1, "cnpj": "11222333000181"},
        headers=headers,
    )
    assert resposta.status_code == 200
    assert resposta.json()["cnpj"] == "11222333000181"

    log = db.query(LogAuditoria).filter(LogAuditoria.acao == "GEROU_RELATORIO_AUDIENCIAS").order_by(
        LogAuditoria.id.desc()
    ).first()
    assert log is not None
    assert "sobrescrito" in log.detalhes
    assert "11222333000181" in log.detalhes


def test_relatorio_com_cnpj_invalido_eh_rejeitado(client, db, admin_token):
    _planilha(db)
    headers = {"Authorization": f"Bearer {admin_token}"}

    resposta = client.get(
        "/audiencias/relatorio",
        params={"empresa": "ALFA", "ano": 2026, "mes": 9, "quinzena": 1, "cnpj": "123"},
        headers=headers,
    )
    assert resposta.status_code == 404
    assert "CNPJ" in resposta.json()["detail"]


def test_relatorio_sem_cnpj_nao_registra_sobrescrita(client, db, admin_token):
    _planilha(db)
    headers = {"Authorization": f"Bearer {admin_token}"}

    resposta = client.get(
        "/audiencias/relatorio",
        params={"empresa": "ALFA", "ano": 2026, "mes": 9, "quinzena": 1},
        headers=headers,
    )
    assert resposta.status_code == 200

    log = db.query(LogAuditoria).filter(LogAuditoria.acao == "GEROU_RELATORIO_AUDIENCIAS").order_by(
        LogAuditoria.id.desc()
    ).first()
    assert log is not None
    assert log.detalhes is None

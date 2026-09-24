from datetime import date

from app.models import Cobranca
from app.services.empresas import get_or_create_empresa
from app.services.pendencias import apagar_todas_pendencias, gerar_mensagens


def test_classifica_cobrador_por_tipo_e_ignora_pago(db):
    empresa = get_or_create_empresa(db, "NOVA GLOBAL")
    db.add(
        Cobranca(
            empresa_cliente_id=empresa.id,
            data=date(2026, 1, 1),
            tipo_cobranca="MENSALIDADE PROCESSUAL",
            cobrador="ELITE",
            valor=100.0,
            status_pagamento="EM ATRASO",
        )
    )
    db.add(
        Cobranca(
            empresa_cliente_id=empresa.id,
            data=date(2026, 1, 2),
            tipo_cobranca="AUDIENCIA EXTRA",
            cobrador="EXIMIA",
            valor=50.0,
            status_pagamento="PENDENTE",
        )
    )
    db.add(
        Cobranca(
            empresa_cliente_id=empresa.id,
            data=date(2026, 1, 3),
            tipo_cobranca="MENSALIDADE PROCESSUAL",
            cobrador="ELITE",
            valor=999.0,
            status_pagamento="SIM",
        )
    )
    db.commit()

    mensagens = gerar_mensagens(db, "NOVA GLOBAL")
    assert {m.cobrador for m in mensagens} == {"ELITE", "EXIMIA"}
    elite = next(m for m in mensagens if m.cobrador == "ELITE")
    assert elite.total == 100.0  # a paga (SIM) não entra


def test_pago_nao_conta_como_pendente(db):
    """A Clara pediu explicitamente (2026-09-24): PAGO = "Não" também é
    pendência, não só valores como "EM ATRASO"/"PENDENTE". Só "Sim" conta
    como resolvido."""
    empresa = get_or_create_empresa(db, "NOVA GLOBAL")
    db.add(
        Cobranca(
            empresa_cliente_id=empresa.id,
            data=date(2026, 1, 1),
            tipo_cobranca="MENSALIDADE PROCESSUAL",
            cobrador="ELITE",
            valor=150.0,
            status_pagamento="Não",
        )
    )
    db.commit()

    mensagens = gerar_mensagens(db, "NOVA GLOBAL")
    assert len(mensagens) == 1
    assert mensagens[0].total == 150.0


def test_pago_vazio_nao_conta_como_pendente(db):
    empresa = get_or_create_empresa(db, "NOVA GLOBAL")
    db.add(
        Cobranca(
            empresa_cliente_id=empresa.id,
            data=date(2026, 1, 1),
            tipo_cobranca="MENSALIDADE",
            cobrador="ELITE",
            valor=100.0,
            status_pagamento=None,
        )
    )
    db.commit()
    assert gerar_mensagens(db, "NOVA GLOBAL") == []


def test_apagar_todas_pendencias_remove_tudo_e_devolve_a_contagem(db):
    empresa1 = get_or_create_empresa(db, "NOVA GLOBAL")
    empresa2 = get_or_create_empresa(db, "OUTRA")
    db.add_all(
        [
            Cobranca(empresa_cliente_id=empresa1.id, data=date(2026, 1, 1), tipo_cobranca="MENSALIDADE",
                      cobrador="ELITE", valor=100.0, status_pagamento="Não"),
            Cobranca(empresa_cliente_id=empresa2.id, data=date(2026, 1, 2), tipo_cobranca="AUDIENCIA EXTRA",
                      cobrador="EXIMIA", valor=50.0, status_pagamento="SIM"),
        ]
    )
    db.commit()

    apagadas = apagar_todas_pendencias(db)

    assert apagadas == 2
    assert db.query(Cobranca).count() == 0
    # não mexe nas empresas-clientes
    assert get_or_create_empresa(db, "NOVA GLOBAL").id == empresa1.id


def test_apagar_todas_pendencias_com_banco_ja_vazio(db):
    assert apagar_todas_pendencias(db) == 0

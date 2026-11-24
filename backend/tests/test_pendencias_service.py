import tempfile
from datetime import date
from pathlib import Path

import openpyxl

from app.models import Cobranca
from app.services.empresas import get_or_create_empresa
from app.services.pendencias import (
    apagar_todas_pendencias,
    gerar_mensagens,
    importar_planilha,
)


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


def _planilha_pendencias(nome_arquivo, pago):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["DATA", "EMPRESA", "TIPO DE COBRANÇA", "VALOR", "PAGO"])
    ws.append([date(2026, 10, 1), "NOVA GLOBAL", "MENSALIDADE PROCESSUAL", 100.0, pago])
    path = Path(tempfile.mkdtemp()) / nome_arquivo
    wb.save(path)
    return str(path)


def test_reimportacao_com_pago_corrigido_atualiza_em_vez_de_duplicar(db):
    """Bug real corrigido em 2026-11-24 (mesma classe do bug já corrigido
    em Laudos): PAGO fazia parte da identidade da cobrança contra o banco
    — reimportar a planilha depois do cliente pagar (PAGO corrigido de
    "NÃO" pra "SIM") criava uma cobrança NOVA em vez de atualizar a
    existente, e o sistema continuava cobrando uma dívida já quitada.
    Agora a reimportação atualiza o status de pagamento."""
    resumo1 = importar_planilha(db, _planilha_pendencias("v1.xlsx", "NÃO"))
    assert resumo1.linhas_novas == 1

    resumo2 = importar_planilha(db, _planilha_pendencias("v2.xlsx", "SIM"))
    assert resumo2.linhas_novas == 0
    assert resumo2.linhas_atualizadas == 1
    assert resumo2.linhas_ja_existentes == 0

    assert db.query(Cobranca).count() == 1
    cobranca = db.query(Cobranca).one()
    assert cobranca.status_pagamento == "SIM"

    # Reimportar de novo sem mudar nada não deve "atualizar" à toa.
    resumo3 = importar_planilha(db, _planilha_pendencias("v3.xlsx", "SIM"))
    assert resumo3.linhas_atualizadas == 0
    assert resumo3.linhas_ja_existentes == 1


def test_importar_planilha_com_valor_em_texto_simples_nao_infla_100x(db):
    """Bug real corrigido em 2026-11-24: célula de VALOR em texto simples
    com ponto decimal (ex.: "280.50", sem "R$", sem vírgula) era
    interpretada cegamente como formato brasileiro (ponto = separador de
    milhar), virando 28050.0 — 100x maior, sem nenhum aviso. Agora usa
    `parse_valor_monetario` (compartilhada com Correspondências)."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["DATA", "EMPRESA", "TIPO DE COBRANÇA", "VALOR", "PAGO"])
    ws.append([date(2026, 10, 1), "NOVA GLOBAL", "MENSALIDADE PROCESSUAL", "280.50", "NÃO"])
    path = Path(tempfile.mkdtemp()) / "valor_texto_simples.xlsx"
    wb.save(path)

    resumo = importar_planilha(db, str(path))
    assert resumo.linhas_novas == 1

    cobranca = db.query(Cobranca).one()
    assert cobranca.valor == 280.5


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

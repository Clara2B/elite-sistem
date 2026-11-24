import tempfile
from datetime import date
from pathlib import Path

import openpyxl

from app.models import Cobranca
from app.services.empresas import get_or_create_empresa
from app.services.pendencias import (
    apagar_todas_pendencias,
    gerar_mensagens,
    ids_empresas_com_pendencia,
    importar_planilha,
)

_NOME_ABA_ANO_ATUAL = f"{date.today().year} - RECEBIMENTOS EMPRESAS"


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


def test_pago_sim_ou_nao_nao_contam_como_pendente(db):
    """Regra reestruturada em 2026-11-24 a pedido da Clara: só entram na
    mensagem de cobrança os status VERIFICAR/ACORDO/PENDENTE/EM ATRASO.
    "SIM" é pago. "NÃO" foi EXCLUÍDO explicitamente por ela nessa mesma
    conversa — revoga a regra anterior (2026-09-24) que tratava "NÃO"
    como pendência também."""
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
    db.add(
        Cobranca(
            empresa_cliente_id=empresa.id,
            data=date(2026, 1, 2),
            tipo_cobranca="MENSALIDADE PROCESSUAL",
            cobrador="ELITE",
            valor=200.0,
            status_pagamento="Sim",
        )
    )
    db.commit()

    assert gerar_mensagens(db, "NOVA GLOBAL") == []


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


def _planilha_pendencias(nome_arquivo, pago, nome_aba=None):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = nome_aba or _NOME_ABA_ANO_ATUAL
    ws.append(["DATA", "CLIENTE", "CNPJ", "VALOR FALTANTE", "VALOR Á RECEBER", "TIPO DE COBRANÇA", "PAGO"])
    ws.append([date(2026, 10, 1), "NOVA GLOBAL", "00.000.000/0001-00", 100.0, None, "MENSALIDADE PROCESSUAL", pago])
    path = Path(tempfile.mkdtemp()) / nome_arquivo
    wb.save(path)
    return str(path)


def test_importar_planilha_le_so_a_aba_recebimentos_empresas_do_ano_atual(db):
    """Bug real corrigido em 2026-11-24: o import genérico varria qualquer
    aba com cabeçalhos parecidos e sempre acabava lendo a aba do ANO
    PASSADO ("EMPRESA"/"VALOR"/"PAGO (SIM/NÃO)" batiam; "CLIENTE"/"VALOR
    FALTANTE" da aba atual nunca batiam) — o sistema gerava mensagens de
    cobrança com dados desatualizados sem nenhum erro aparecer. Agora só a
    aba "<ano atual> - RECEBIMENTOS EMPRESAS" é lida."""
    wb = openpyxl.Workbook()
    ws_antiga = wb.active
    ws_antiga.title = "2025 - RECEBIMENTOS EMPRESAS"
    ws_antiga.append(["DATA", "EMPRESA", "VALOR", "VALOR RECEBIDO", "TIPO DE COBRANÇA", "PAGO (SIM/NÃO)", "OBS"])
    ws_antiga.append([date(2025, 10, 1), "EMPRESA ANTIGA", 999.0, None, "MENSALIDADE PROCESSUAL", "NÃO", None])
    ws_atual = wb.create_sheet(_NOME_ABA_ANO_ATUAL)
    ws_atual.append(["DATA", "CLIENTE", "CNPJ", "VALOR FALTANTE", "VALOR Á RECEBER", "TIPO DE COBRANÇA", "PAGO"])
    ws_atual.append([date(2026, 10, 1), "NOVA GLOBAL", "00.000.000/0001-00", 100.0, None, "MENSALIDADE PROCESSUAL", "EM ATRASO"])
    path = Path(tempfile.mkdtemp()) / "duas_abas.xlsx"
    wb.save(path)

    resumo = importar_planilha(db, str(path))

    assert resumo.linhas_novas == 1
    cobranca = db.query(Cobranca).one()
    assert cobranca.tipo_cobranca == "MENSALIDADE PROCESSUAL"
    assert cobranca.valor == 100.0  # da aba atual — não o 999.0 da aba de 2025


def test_reimportacao_com_pago_corrigido_atualiza_em_vez_de_duplicar(db):
    """Bug real corrigido em 2026-11-24 (mesma classe do bug já corrigido
    em Laudos): PAGO fazia parte da identidade da cobrança contra o banco
    — reimportar a planilha depois do cliente pagar (PAGO corrigido de
    "EM ATRASO" pra "SIM") criava uma cobrança NOVA em vez de atualizar a
    existente, e o sistema continuava cobrando uma dívida já quitada.
    Agora a reimportação atualiza o status de pagamento."""
    resumo1 = importar_planilha(db, _planilha_pendencias("v1.xlsx", "EM ATRASO"))
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
    """Bug real corrigido em 2026-11-24: célula de VALOR FALTANTE em texto
    simples com ponto decimal (ex.: "280.50", sem "R$", sem vírgula) era
    interpretada cegamente como formato brasileiro (ponto = separador de
    milhar), virando 28050.0 — 100x maior, sem nenhum aviso. Agora usa
    `parse_valor_monetario` (compartilhada com Correspondências)."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = _NOME_ABA_ANO_ATUAL
    ws.append(["DATA", "CLIENTE", "CNPJ", "VALOR FALTANTE", "VALOR Á RECEBER", "TIPO DE COBRANÇA", "PAGO"])
    ws.append([date(2026, 10, 1), "NOVA GLOBAL", "00.000.000/0001-00", "280.50", None, "MENSALIDADE PROCESSUAL", "EM ATRASO"])
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


def test_ids_empresas_com_pendencia_so_conta_quem_tem_pendencia_de_verdade(db):
    """A pedido da Clara (2026-11-24): usado pra tirar do menu de empresas
    quem nunca tem pendência (ex.: "Juros Justos") — só entra quem tem
    cobrança pendente de verdade (mesma regra de `gerar_mensagens`: status
    pendente e valor > 0)."""
    com_pendencia = get_or_create_empresa(db, "NOVA GLOBAL")
    paga = get_or_create_empresa(db, "ABSOLUTA")
    sem_nenhuma_cobranca = get_or_create_empresa(db, "JUROS JUSTOS")
    db.add_all(
        [
            Cobranca(empresa_cliente_id=com_pendencia.id, data=date(2026, 1, 1), tipo_cobranca="MENSALIDADE",
                      cobrador="ELITE", valor=100.0, status_pagamento="EM ATRASO"),
            Cobranca(empresa_cliente_id=paga.id, data=date(2026, 1, 2), tipo_cobranca="MENSALIDADE",
                      cobrador="ELITE", valor=100.0, status_pagamento="SIM"),
        ]
    )
    db.commit()

    ids = ids_empresas_com_pendencia(db)

    assert ids == {com_pendencia.id}
    assert paga.id not in ids
    assert sem_nenhuma_cobranca.id not in ids

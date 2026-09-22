from datetime import date

from app.models import Laudo
from app.services.empresas import get_or_create_empresa
from app.services.laudos import gerar_relatorio, periodo_20_a_20


def test_periodo_20_a_20():
    ini, fim = periodo_20_a_20(2026, 1)
    assert ini == date(2026, 1, 21)
    assert fim == date(2026, 2, 20)


def test_periodo_20_a_20_vira_o_ano():
    ini, fim = periodo_20_a_20(2026, 12)
    assert ini == date(2026, 12, 21)
    assert fim == date(2027, 1, 20)


def test_gera_relatorio_soma_valores_por_tipo(db):
    empresa = get_or_create_empresa(db, "ABSOLUTA")
    db.add(
        Laudo(
            empresa_cliente_id=empresa.id,
            tipo_laudo_nome="AUTO",
            data=date(2026, 1, 25),
            nome_cliente="Fulano",
            status="SOLICITAÇÃO",
        )
    )
    db.add(
        Laudo(
            empresa_cliente_id=empresa.id,
            tipo_laudo_nome="IMÓVEL",
            data=date(2026, 2, 1),
            nome_cliente="Beltrano",
            status="CORREÇÃO",
        )
    )
    db.commit()

    ini, fim = periodo_20_a_20(2026, 1)
    resultado = gerar_relatorio(db, "ABSOLUTA", ini, fim, "Solicitação + Corrigido (cobrança)")
    assert resultado.total == 40.0 + 70.0
    assert len(resultado.linhas) == 2


def test_filtro_por_status_exclui_cancelado(db):
    empresa = get_or_create_empresa(db, "ABSOLUTA")
    db.add(
        Laudo(
            empresa_cliente_id=empresa.id,
            tipo_laudo_nome="AUTO",
            data=date(2026, 1, 25),
            nome_cliente="Fulano",
            status="CANCELADO",
        )
    )
    db.commit()
    ini, fim = periodo_20_a_20(2026, 1)
    resultado = gerar_relatorio(db, "ABSOLUTA", ini, fim, "Solicitação + Corrigido (cobrança)")
    assert resultado.linhas == []
    assert resultado.total == 0.0


def test_tipo_sem_valor_cadastrado_fica_marcado(db):
    empresa = get_or_create_empresa(db, "ABSOLUTA")
    db.add(
        Laudo(
            empresa_cliente_id=empresa.id,
            tipo_laudo_nome="PLACA SOLAR",
            data=date(2026, 1, 25),
            nome_cliente="Fulano",
            status="SOLICITAÇÃO",
        )
    )
    db.commit()
    ini, fim = periodo_20_a_20(2026, 1)
    resultado = gerar_relatorio(db, "ABSOLUTA", ini, fim, "Solicitação + Corrigido (cobrança)")
    assert resultado.tipos_sem_valor == ["PLACA SOLAR"]
    assert resultado.total == 0.0

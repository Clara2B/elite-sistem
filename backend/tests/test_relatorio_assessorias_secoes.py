"""Fase 4 (Gerador de Relatórios Mensais das Assessorias) — seções.

Um módulo de teste por seção, com `LinhaBruta` construídas diretamente
(equivalente a "planilhas pequenas de exemplo": o que entra num módulo de
`secoes/` é sempre uma lista de `LinhaBruta`, já filtrada pra uma
assessoria — não há necessidade de passar por um arquivo .xlsx real pra
testar a regra de negócio isoladamente)."""
from __future__ import annotations

from datetime import date

from app.relatorio_assessorias.config import carregar
from app.relatorio_assessorias.leitores.base import LinhaBruta, Origem
from app.relatorio_assessorias.secoes import (
    contrarias,
    extrajudiciais,
    iniciais,
    judiciais,
    laudos,
    manuais,
    procons,
)

REGRAS = carregar("regras")


def _origem(linha: int) -> Origem:
    return Origem("teste", "aba", linha)


# ---------- laudos.py ----------


def test_laudos_elaborados_exclui_cancelado():
    linhas = [
        LinhaBruta(
            {"data": date(2026, 8, 3), "entrada_laudo": "Cancelado", "tipo_laudo": "", "laudo_pronto": "Não",
             "data_pronto": None, "empresa": "EWS"},
            _origem(1),
        ),
        LinhaBruta(
            {"data": date(2026, 8, 3), "entrada_laudo": "", "tipo_laudo": "", "laudo_pronto": "Não",
             "data_pronto": None, "empresa": "EWS"},
            _origem(2),
        ),
    ]
    resultado = laudos.calcular(linhas, date(2026, 9, 4), REGRAS["laudos"])
    assert resultado.elaborados == 1


def test_laudos_entregue_dentro_do_prazo():
    # segunda 03/08 -> quinta 06/08, mesma semana, sem feriado: 3 dias úteis
    linhas = [
        LinhaBruta(
            {"data": date(2026, 8, 3), "entrada_laudo": "", "tipo_laudo": "", "laudo_pronto": "Sim",
             "data_pronto": date(2026, 8, 6), "empresa": "EWS"},
            _origem(1),
        ),
    ]
    resultado = laudos.calcular(linhas, date(2026, 9, 4), REGRAS["laudos"])
    assert resultado.entregues_dentro_prazo == 1
    assert resultado.pendentes == 0


def test_laudos_prazo_maior_para_consorcio():
    # 10 dias úteis estouraria o prazo padrão (7) mas cabe no de CONSÓRCIO (15)
    linhas = [
        LinhaBruta(
            {"data": date(2026, 8, 3), "entrada_laudo": "", "tipo_laudo": "CONSÓRCIO", "laudo_pronto": "Sim",
             "data_pronto": date(2026, 8, 17), "empresa": "EWS"},
            _origem(1),
        ),
    ]
    resultado = laudos.calcular(linhas, date(2026, 9, 4), REGRAS["laudos"])
    assert resultado.entregues_dentro_prazo == 1


def test_laudos_pendente_atrasado():
    linhas = [
        LinhaBruta(
            {"data": date(2026, 6, 1), "entrada_laudo": "", "tipo_laudo": "", "laudo_pronto": "Não",
             "data_pronto": None, "empresa": "EWS"},
            _origem(1),
        ),
    ]
    resultado = laudos.calcular(linhas, date(2026, 9, 4), REGRAS["laudos"])
    assert resultado.pendentes == 1
    assert resultado.pendentes_atrasados == 1


def test_laudos_pendente_nao_atrasado():
    linhas = [
        LinhaBruta(
            {"data": date(2026, 9, 3), "entrada_laudo": "", "tipo_laudo": "", "laudo_pronto": "Não",
             "data_pronto": None, "empresa": "EWS"},
            _origem(1),
        ),
    ]
    resultado = laudos.calcular(linhas, date(2026, 9, 4), REGRAS["laudos"])
    assert resultado.pendentes == 1
    assert resultado.pendentes_atrasados == 0


# ---------- iniciais.py ----------


def test_iniciais_distribuido_no_mes_entra_na_faixa_ate_7():
    linhas = [
        LinhaBruta(
            {"data_recebimento": date(2026, 8, 3), "data_distribuicao": date(2026, 8, 6),
             "protocolado": "SIM", "estados": "RJ", "numero_processo": "x", "assessoria": "EWS"},
            _origem(1),
        ),
    ]
    resultado = iniciais.calcular(linhas, mes=8, ano=2026, data_corte=date(2026, 9, 4), regras=REGRAS["iniciais"])
    assert resultado.distribuidos_no_mes == 1
    assert resultado.faixas["Distribuídos em até 7 dias úteis"] == 1
    assert resultado.faixas["Distribuídos entre 8 e 20 dias úteis"] == 0


def test_iniciais_distribuido_em_outro_mes_nao_conta_para_este_mes():
    linhas = [
        LinhaBruta(
            {"data_recebimento": date(2026, 7, 20), "data_distribuicao": date(2026, 7, 22),
             "protocolado": "SIM", "estados": "RJ", "numero_processo": "x", "assessoria": "EWS"},
            _origem(1),
        ),
    ]
    resultado = iniciais.calcular(linhas, mes=8, ano=2026, data_corte=date(2026, 9, 4), regras=REGRAS["iniciais"])
    assert resultado.distribuidos_no_mes == 0


def test_iniciais_aguardando_distribuicao_sem_data_distribuicao():
    linhas = [
        LinhaBruta(
            {"data_recebimento": date(2026, 8, 20), "data_distribuicao": None,
             "protocolado": "NÃO", "estados": "RJ", "numero_processo": "x", "assessoria": "EWS"},
            _origem(1),
        ),
    ]
    resultado = iniciais.calcular(linhas, mes=8, ano=2026, data_corte=date(2026, 9, 4), regras=REGRAS["iniciais"])
    assert resultado.aguardando_distribuicao == 1


def test_iniciais_nao_protocolado_mesmo_com_data_de_distribuicao_fica_aguardando():
    linhas = [
        LinhaBruta(
            {"data_recebimento": date(2026, 8, 3), "data_distribuicao": date(2026, 8, 6),
             "protocolado": "NÃO", "estados": "RJ", "numero_processo": "x", "assessoria": "EWS"},
            _origem(1),
        ),
    ]
    resultado = iniciais.calcular(linhas, mes=8, ano=2026, data_corte=date(2026, 9, 4), regras=REGRAS["iniciais"])
    assert resultado.aguardando_distribuicao == 1


def test_iniciais_acima_da_faixa_vira_aviso_sem_entrar_em_faixa():
    linhas = [
        LinhaBruta(
            {"data_recebimento": date(2026, 1, 5), "data_distribuicao": date(2026, 8, 6),
             "protocolado": "SIM", "estados": "RJ", "numero_processo": "x", "assessoria": "EWS"},
            _origem(1),
        ),
    ]
    resultado = iniciais.calcular(linhas, mes=8, ano=2026, data_corte=date(2026, 9, 4), regras=REGRAS["iniciais"])
    assert sum(resultado.faixas.values()) == 0
    assert any("acima da faixa" in a.mensagem for a in resultado.avisos)


# ---------- extrajudiciais.py ----------


def test_extrajudiciais_enviadas_e_realizadas():
    linhas = [
        LinhaBruta(
            {"data_recebimento": date(2026, 8, 5), "empresa": "EWS", "nome_completo": "Fulano",
             "data_agendamento": date(2026, 8, 20), "presenca": "PRESENTE"},
            _origem(1),
        ),
    ]
    resultado = extrajudiciais.calcular(
        linhas, mes=8, ano=2026, data_corte=date(2026, 9, 4), regras=REGRAS["extrajudiciais"]
    )
    assert resultado.enviadas == 1
    assert resultado.realizadas == 1
    assert resultado.clientes_ausentes == []


def test_extrajudiciais_ausente_entra_na_lista():
    linhas = [
        LinhaBruta(
            {"data_recebimento": date(2026, 8, 5), "empresa": "EWS", "nome_completo": "Antonio Beserra da Costa",
             "data_agendamento": date(2026, 8, 20), "presenca": "AUSENTE"},
            _origem(1),
        ),
    ]
    resultado = extrajudiciais.calcular(
        linhas, mes=8, ano=2026, data_corte=date(2026, 9, 4), regras=REGRAS["extrajudiciais"]
    )
    assert resultado.realizadas == 1
    assert [c.nome for c in resultado.clientes_ausentes] == ["Antonio Beserra da Costa"]


def test_extrajudiciais_cancelado_nao_conta_como_realizada():
    linhas = [
        LinhaBruta(
            {"data_recebimento": date(2026, 8, 5), "empresa": "EWS", "nome_completo": "Fulano",
             "data_agendamento": date(2026, 8, 20), "presenca": "CANCELADO"},
            _origem(1),
        ),
    ]
    resultado = extrajudiciais.calcular(
        linhas, mes=8, ano=2026, data_corte=date(2026, 9, 4), regras=REGRAS["extrajudiciais"]
    )
    assert resultado.realizadas == 0


def test_extrajudiciais_pendente_para_proximo_mes():
    linhas = [
        LinhaBruta(
            {"data_recebimento": date(2026, 8, 5), "empresa": "EWS", "nome_completo": "Fulano",
             "data_agendamento": date(2026, 9, 10), "presenca": None},
            _origem(1),
        ),
    ]
    resultado = extrajudiciais.calcular(
        linhas, mes=8, ano=2026, data_corte=date(2026, 9, 4), regras=REGRAS["extrajudiciais"]
    )
    assert resultado.pendentes_proximos_meses == 1


# ---------- judiciais.py (audiências judiciais / contrárias) ----------


def test_audiencias_acumulado_no_ano():
    linhas = [
        LinhaBruta({"data": date(2026, 3, 10), "empresa": "EWS"}, _origem(1)),
        LinhaBruta({"data": date(2026, 8, 20), "empresa": "EWS"}, _origem(2)),
        LinhaBruta({"data": date(2025, 12, 31), "empresa": "EWS"}, _origem(3)),  # ano anterior: fora
        LinhaBruta({"data": date(2026, 9, 10), "empresa": "EWS"}, _origem(4)),  # depois da data de corte: fora
    ]
    resultado = judiciais.calcular(linhas, ano=2026, data_corte=date(2026, 9, 4))
    assert resultado.quantidade == 2


# ---------- contrarias.py ----------


def test_contrarias_incluidos_no_mes_e_ativos():
    linhas = [
        LinhaBruta(
            {"data_recebimento": date(2026, 8, 10), "nome_autor": "Fulano",
             "numero_processo": "0813055-21.2026.8.10.0001", "estado": "RJ", "valor_causa": "1000",
             "status_atual": "EM ANDAMENTO", "tipo_acao": "JUDICIAL"},
            _origem(1),
        ),
    ]
    resultado = contrarias.calcular(
        linhas, mes=8, ano=2026, data_corte=date(2026, 9, 4), regras=REGRAS["contrarias"]
    )
    assert resultado.incluidos_no_mes == 1
    assert resultado.ativos_total == 1
    assert resultado.ativos_por_uf == {"RJ": 1}
    assert len(resultado.lista_judiciais) == 1


def test_contrarias_arquivado_nao_entra_como_ativo():
    linhas = [
        LinhaBruta(
            {"data_recebimento": date(2026, 8, 10), "nome_autor": "Fulano",
             "numero_processo": "0813055-21.2026.8.10.0001", "estado": "RJ", "valor_causa": "1000",
             "status_atual": "ARQUIVADO", "tipo_acao": "JUDICIAL"},
            _origem(1),
        ),
    ]
    resultado = contrarias.calcular(
        linhas, mes=8, ano=2026, data_corte=date(2026, 9, 4), regras=REGRAS["contrarias"]
    )
    assert resultado.ativos_total == 0


def test_contrarias_duplicata_por_cnj_mantem_a_primeira():
    # mesma pessoa nas abas SW e EWS (exemplo real da especificação)
    linhas = [
        LinhaBruta(
            {"data_recebimento": date(2026, 8, 1), "nome_autor": "Dirceu de Oliveira Pires",
             "numero_processo": "0813055-21.2026.8.10.0001", "estado": "RJ", "valor_causa": None,
             "status_atual": "EM ANDAMENTO", "tipo_acao": "JUDICIAL"},
            Origem("contrarias", "SW", 10),
        ),
        LinhaBruta(
            {"data_recebimento": date(2026, 8, 1), "nome_autor": "Dirceu de Oliveira Pires",
             "numero_processo": "0813055-21.2026.8.10.0001", "estado": "RJ", "valor_causa": None,
             "status_atual": "EM ANDAMENTO", "tipo_acao": "JUDICIAL"},
            Origem("contrarias", "EWS", 25),
        ),
    ]
    resultado = contrarias.calcular(
        linhas, mes=8, ano=2026, data_corte=date(2026, 9, 4), regras=REGRAS["contrarias"]
    )
    assert resultado.ativos_total == 1
    assert resultado.ativos_por_uf == {"RJ": 1}
    assert any("duplicado" in a.mensagem for a in resultado.avisos)


def test_contrarias_sem_data_de_recebimento_entra_e_avisa():
    linhas = [
        LinhaBruta(
            {"data_recebimento": None, "nome_autor": "Fulano", "numero_processo": "123",
             "estado": "RJ", "valor_causa": None, "status_atual": "EM ANDAMENTO", "tipo_acao": "JUDICIAL"},
            _origem(1),
        ),
    ]
    resultado = contrarias.calcular(
        linhas, mes=8, ano=2026, data_corte=date(2026, 9, 4), regras=REGRAS["contrarias"]
    )
    assert resultado.ativos_total == 1
    assert any("sem data de recebimento" in a.mensagem for a in resultado.avisos)


def test_contrarias_dedup_cross_arquivo_com_procon():
    linhas = [
        LinhaBruta(
            {"data_recebimento": date(2026, 8, 1), "nome_autor": "Fulano",
             "numero_processo": "0813055-21.2026.8.10.0001", "estado": "RJ", "valor_causa": None,
             "status_atual": "EM ANDAMENTO", "tipo_acao": "TRABALHISTA"},
            _origem(1),
        ),
    ]
    resultado = contrarias.calcular(
        linhas, mes=8, ano=2026, data_corte=date(2026, 9, 4), regras=REGRAS["contrarias"],
        chaves_cnj_de_outras_fontes=frozenset({"08130552120268100001"}),
    )
    assert resultado.ativos_total == 0
    assert any("Procon" in a.mensagem for a in resultado.avisos)


# ---------- procons.py ----------


def test_procons_lista_tipo_incluido_e_nao_encerrado():
    linhas = [
        LinhaBruta(
            {"data_recebimento": date(2026, 8, 10), "nome_autor": "Fulano", "numero_processo": "123",
             "estado": "RJ", "status_atual": "EM ANDAMENTO", "tipo_acao": "PROCON"},
            _origem(1),
        ),
        LinhaBruta(
            {"data_recebimento": date(2026, 8, 10), "nome_autor": "Beltrano", "numero_processo": "456",
             "estado": "RJ", "status_atual": "ARQUIVADO", "tipo_acao": "PROCON"},
            _origem(2),
        ),
        LinhaBruta(
            {"data_recebimento": date(2026, 8, 10), "nome_autor": "Sicrano", "numero_processo": "789",
             "estado": "RJ", "status_atual": "EM ANDAMENTO", "tipo_acao": "TRABALHISTA"},
            _origem(3),
        ),
    ]
    resultado = procons.calcular(linhas, mes=8, ano=2026, regras=REGRAS["procons"])
    assert [p.nome for p in resultado.lista] == ["Fulano"]


def test_procons_recebido_depois_do_fim_do_mes_fica_fora():
    linhas = [
        LinhaBruta(
            {"data_recebimento": date(2026, 9, 1), "nome_autor": "Fulano", "numero_processo": "123",
             "estado": "RJ", "status_atual": "EM ANDAMENTO", "tipo_acao": "MP"},
            _origem(1),
        ),
    ]
    resultado = procons.calcular(linhas, mes=8, ano=2026, regras=REGRAS["procons"])
    assert resultado.lista == []


def test_procons_duplicata_por_cnj_mantem_a_primeira():
    linhas = [
        LinhaBruta(
            {"data_recebimento": date(2026, 8, 1), "nome_autor": "Fulano",
             "numero_processo": "0813055-21.2026.8.10.0001", "estado": "RJ",
             "status_atual": "EM ANDAMENTO", "tipo_acao": "PROCON"},
            Origem("procon", "SW", 10),
        ),
        LinhaBruta(
            {"data_recebimento": date(2026, 8, 1), "nome_autor": "Fulano",
             "numero_processo": "0813055-21.2026.8.10.0001", "estado": "RJ",
             "status_atual": "EM ANDAMENTO", "tipo_acao": "PROCON"},
            Origem("procon", "EWS", 25),
        ),
    ]
    resultado = procons.calcular(linhas, mes=8, ano=2026, regras=REGRAS["procons"])
    assert len(resultado.lista) == 1
    assert any("duplicado" in a.mensagem for a in resultado.avisos)


# ---------- manuais.py ----------


def test_campos_manuais_valores_padrao_zerados():
    campos = manuais.CamposManuais()
    assert campos.pastas_revisionais.recebidas_no_mes == 0
    assert campos.processos_ativos_revisionais_por_uf == {}
    assert campos.sentencas_procedentes == []

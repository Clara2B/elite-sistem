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
            {"data": date(2026, 8, 3), "entrada_laudo": "Cancelado", "tipo_laudo": "", "laudo_pronto": "Sim",
             "data_pronto": date(2026, 8, 5), "empresa": "EWS"},
            _origem(1),
        ),
        LinhaBruta(
            {"data": date(2026, 8, 3), "entrada_laudo": "", "tipo_laudo": "", "laudo_pronto": "Sim",
             "data_pronto": date(2026, 8, 5), "empresa": "EWS"},
            _origem(2),
        ),
    ]
    resultado = laudos.calcular(linhas, date(2026, 9, 4), REGRAS["laudos"])
    assert resultado.elaborados == 1


def test_laudos_elaborados_so_conta_com_data_na_coluna_g():
    """Confirmado pela Clara (2026-10-27): só conta como elaborado quem
    tem a coluna G (DATA de pronto) preenchida — um laudo ainda sem essa
    data (mesmo não cancelado) não é "elaborado" ainda, é pendente."""
    linhas = [
        LinhaBruta(
            {"data": date(2026, 8, 3), "entrada_laudo": "", "tipo_laudo": "", "laudo_pronto": "Não",
             "data_pronto": None, "empresa": "EWS"},
            _origem(1),
        ),
        LinhaBruta(
            {"data": date(2026, 8, 3), "entrada_laudo": "", "tipo_laudo": "", "laudo_pronto": "Sim",
             "data_pronto": date(2026, 8, 5), "empresa": "EWS"},
            _origem(2),
        ),
    ]
    resultado = laudos.calcular(linhas, date(2026, 9, 4), REGRAS["laudos"])
    assert resultado.elaborados == 1
    assert resultado.pendentes == 1


def test_laudos_data_de_pronto_anterior_a_entrada_gera_aviso_e_nao_conta_prazo():
    """Bug real (planilha de produção, 2026-10-27): ano digitado errado na
    data de entrada (ex. 2029 em vez de 2026) fazia a conta de dias úteis
    dar negativo e contar por engano como "dentro do prazo"."""
    linhas = [
        LinhaBruta(
            {"data": date(2029, 9, 22), "entrada_laudo": "", "tipo_laudo": "", "laudo_pronto": "Sim",
             "data_pronto": date(2026, 9, 25), "empresa": "EWS"},
            _origem(1),
        ),
    ]
    resultado = laudos.calcular(linhas, date(2026, 10, 10), REGRAS["laudos"])
    assert resultado.elaborados == 1
    assert resultado.entregues_dentro_prazo == 0
    assert any("anterior à data de entrada" in a.mensagem for a in resultado.avisos)


def test_laudos_pronto_sem_data_de_conclusao_gera_aviso():
    linhas = [
        LinhaBruta(
            {"data": date(2026, 8, 3), "entrada_laudo": "", "tipo_laudo": "", "laudo_pronto": "Sim",
             "data_pronto": None, "empresa": "EWS"},
            _origem(1),
        ),
    ]
    resultado = laudos.calcular(linhas, date(2026, 9, 4), REGRAS["laudos"])
    assert resultado.elaborados == 0
    assert resultado.pendentes == 0
    assert any("sem data de conclusão" in a.mensagem for a in resultado.avisos)


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
    resultado = iniciais.calcular(linhas, mes=8, ano=2026, regras=REGRAS["iniciais"])
    assert resultado.distribuidos_no_mes == 1
    assert resultado.faixas["Distribuídos em até 7 dias úteis"] == 1
    assert resultado.faixas["Distribuídos entre 8 e 20 dias úteis"] == 0


def test_iniciais_recebido_em_outro_mes_nao_conta_para_este_mes():
    linhas = [
        LinhaBruta(
            {"data_recebimento": date(2026, 7, 20), "data_distribuicao": date(2026, 7, 22),
             "protocolado": "SIM", "estados": "RJ", "numero_processo": "x", "assessoria": "EWS"},
            _origem(1),
        ),
    ]
    resultado = iniciais.calcular(linhas, mes=8, ano=2026, regras=REGRAS["iniciais"])
    assert resultado.distribuidos_no_mes == 0


def test_iniciais_distribuidos_no_mes_agrupa_pelo_recebimento_nao_pela_distribuicao():
    """Regra confirmada pela Clara (2026-10-27), contra dado real da
    NEXUS: agrupa pelo mês de RECEBIMENTO, não pelo mês em que a
    distribuição de fato aconteceu — um caso recebido em agosto e só
    distribuído em outubro ainda conta pra agosto (não pra outubro), e
    um caso recebido em julho não conta pra agosto mesmo se distribuído
    em agosto."""
    linhas = [
        LinhaBruta(
            {"data_recebimento": date(2026, 8, 3), "data_distribuicao": date(2026, 10, 1),
             "protocolado": "SIM", "estados": "RJ", "numero_processo": "x", "assessoria": "EWS"},
            _origem(1),
        ),
        LinhaBruta(
            {"data_recebimento": date(2026, 7, 20), "data_distribuicao": date(2026, 8, 3),
             "protocolado": "SIM", "estados": "RJ", "numero_processo": "y", "assessoria": "EWS"},
            _origem(2),
        ),
    ]
    resultado_agosto = iniciais.calcular(linhas, mes=8, ano=2026, regras=REGRAS["iniciais"])
    assert resultado_agosto.distribuidos_no_mes == 1  # só a linha 1 (recebida em agosto)
    resultado_outubro = iniciais.calcular(linhas, mes=10, ano=2026, regras=REGRAS["iniciais"])
    assert resultado_outubro.distribuidos_no_mes == 0  # a linha 1 foi recebida em agosto, não outubro


def test_iniciais_aguardando_distribuicao_sem_data_distribuicao():
    linhas = [
        LinhaBruta(
            {"data_recebimento": date(2026, 8, 20), "data_distribuicao": None,
             "protocolado": "NÃO", "estados": "RJ", "numero_processo": "x", "assessoria": "EWS"},
            _origem(1),
        ),
    ]
    resultado = iniciais.calcular(linhas, mes=8, ano=2026, regras=REGRAS["iniciais"])
    assert resultado.aguardando_distribuicao == 1


def test_iniciais_recebido_em_mes_anterior_nunca_distribuido_nao_conta_aguardando():
    """Bug real corrigido em 2026-10-27 (confirmado contra dado real da
    NEXUS): "aguardando distribuição" não tem limite inferior de data
    antes — um caso recebido em abril e nunca distribuído era contado de
    novo em TODO mês seguinte (maio, junho, ... agosto), inflando o
    número pra sempre. Agora só conta quem foi recebido dentro do mês de
    referência."""
    linhas = [
        LinhaBruta(
            {"data_recebimento": date(2026, 4, 7), "data_distribuicao": None,
             "protocolado": "SIM", "estados": "SP", "numero_processo": "x", "assessoria": "EWS"},
            _origem(1),
        ),
    ]
    resultado = iniciais.calcular(linhas, mes=8, ano=2026, regras=REGRAS["iniciais"])
    assert resultado.aguardando_distribuicao == 0


def test_iniciais_nao_protocolado_mesmo_com_data_de_distribuicao_fica_aguardando():
    linhas = [
        LinhaBruta(
            {"data_recebimento": date(2026, 8, 3), "data_distribuicao": date(2026, 8, 6),
             "protocolado": "NÃO", "estados": "RJ", "numero_processo": "x", "assessoria": "EWS"},
            _origem(1),
        ),
    ]
    resultado = iniciais.calcular(linhas, mes=8, ano=2026, regras=REGRAS["iniciais"])
    assert resultado.aguardando_distribuicao == 1


def test_iniciais_acima_da_faixa_vira_aviso_sem_entrar_em_faixa():
    linhas = [
        LinhaBruta(
            {"data_recebimento": date(2026, 8, 3), "data_distribuicao": date(2026, 10, 1),
             "protocolado": "SIM", "estados": "RJ", "numero_processo": "x", "assessoria": "EWS"},
            _origem(1),
        ),
    ]
    resultado = iniciais.calcular(linhas, mes=8, ano=2026, regras=REGRAS["iniciais"])
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


def test_audiencias_so_do_mes_de_referencia():
    """Confirmado pela Clara (2026-10-27): a regra é só o mês de
    referência, não acumulado no ano — o relatório manual batia
    exatamente com essa contagem, não com a acumulada."""
    linhas = [
        LinhaBruta({"data": date(2026, 3, 10), "empresa": "EWS"}, _origem(1)),  # mês diferente: fora
        LinhaBruta({"data": date(2026, 9, 20), "empresa": "EWS"}, _origem(2)),
        LinhaBruta({"data": date(2025, 9, 15), "empresa": "EWS"}, _origem(3)),  # ano anterior: fora
        LinhaBruta({"data": date(2026, 9, 1), "empresa": "EWS"}, _origem(4)),
    ]
    resultado = judiciais.calcular(linhas, mes=9, ano=2026)
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


def test_contrarias_mesmo_numero_processo_nome_diferente_nao_descarta():
    """Confirmado pela Clara (2026-10-27): processo repetido com nome de
    autor bem diferente provavelmente é erro de digitação do número, não
    duplicata de verdade — o sistema deve apontar isso, não descartar a
    linha (achado real, planilha de Contrárias de produção)."""
    linhas = [
        LinhaBruta(
            {"data_recebimento": date(2026, 8, 1), "nome_autor": "Terezinha Virgilio Da Paz De Castro",
             "numero_processo": "4000122-63.2026.8.26.0347", "estado": "SP", "valor_causa": None,
             "status_atual": "ANDAMENTO", "tipo_acao": "JUDICIAL"},
            Origem("contrarias", "NEXUS", 141),
        ),
        LinhaBruta(
            {"data_recebimento": date(2026, 8, 1), "nome_autor": "Luzimara Fayan",
             "numero_processo": "4000122-63.2026.8.26.0347", "estado": "SP", "valor_causa": None,
             "status_atual": "ANDAMENTO", "tipo_acao": "JUDICIAL"},
            Origem("contrarias", "NEXUS", 148),
        ),
    ]
    resultado = contrarias.calcular(
        linhas, mes=8, ano=2026, data_corte=date(2026, 9, 4), regras=REGRAS["contrarias"]
    )
    assert resultado.ativos_total == 2
    assert any("nome de autor diferente" in a.mensagem for a in resultado.avisos)
    assert not any("mantido só o primeiro" in a.mensagem for a in resultado.avisos)


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


def test_procons_recebido_em_mes_anterior_nao_encerrado_nao_fica_na_lista():
    """Bug real corrigido em 2026-10-27 (mesmo padrão do bug de Iniciais,
    confirmado contra dado real da NEXUS): a regra antiga só tinha limite
    superior ("recebidas até o fim do mês") — um caso recebido em
    qualquer mês anterior e ainda ativo (não ARQUIVADO) era contado de
    novo em TODO mês seguinte."""
    linhas = [
        LinhaBruta(
            {"data_recebimento": date(2026, 4, 7), "nome_autor": "Fulano", "numero_processo": "123",
             "estado": "SP", "status_atual": "EM ANDAMENTO", "tipo_acao": "PROCON"},
            _origem(1),
        ),
    ]
    resultado = procons.calcular(linhas, mes=9, ano=2026, regras=REGRAS["procons"])
    assert resultado.lista == []


def test_procons_duplicata_por_protocolo_mantem_a_primeira():
    linhas = [
        LinhaBruta(
            {"data_recebimento": date(2026, 8, 1), "nome_autor": "Fulano",
             "numero_processo": "0470905/2025", "estado": "RJ",
             "status_atual": "EM ANDAMENTO", "tipo_acao": "PROCON"},
            Origem("procon", "SW", 10),
        ),
        LinhaBruta(
            {"data_recebimento": date(2026, 8, 1), "nome_autor": "Fulano",
             "numero_processo": "0470905/2025", "estado": "RJ",
             "status_atual": "EM ANDAMENTO", "tipo_acao": "PROCON"},
            Origem("procon", "EWS", 25),
        ),
    ]
    resultado = procons.calcular(linhas, mes=8, ano=2026, regras=REGRAS["procons"])
    assert len(resultado.lista) == 1
    assert any("duplicado" in a.mensagem for a in resultado.avisos)


def test_procons_mesmo_numero_protocolo_nome_diferente_nao_descarta():
    linhas = [
        LinhaBruta(
            {"data_recebimento": date(2026, 8, 10), "nome_autor": "Fulano", "numero_processo": "0470905/2025",
             "estado": "RJ", "status_atual": "EM ANDAMENTO", "tipo_acao": "PROCON"},
            _origem(1),
        ),
        LinhaBruta(
            {"data_recebimento": date(2026, 8, 10), "nome_autor": "Beltrano Completamente Diferente",
             "numero_processo": "0470905/2025", "estado": "RJ", "status_atual": "EM ANDAMENTO", "tipo_acao": "PROCON"},
            _origem(2),
        ),
    ]
    resultado = procons.calcular(linhas, mes=8, ano=2026, regras=REGRAS["procons"])
    assert len(resultado.lista) == 2
    assert any("nome de autor diferente" in a.mensagem for a in resultado.avisos)


def test_procons_numero_protocolo_fora_do_padrao_cnj_nao_avisa():
    """Bug real (planilha de Procon de produção, 2026-10-27): protocolo
    administrativo (não CNJ) não deve gerar aviso de 'dígito faltando'."""
    linhas = [
        LinhaBruta(
            {"data_recebimento": date(2026, 8, 10), "nome_autor": "Fulano", "numero_processo": "0470905/2025",
             "estado": "RJ", "status_atual": "EM ANDAMENTO", "tipo_acao": "PROCON"},
            _origem(1),
        ),
        LinhaBruta(
            {"data_recebimento": date(2026, 8, 10), "nome_autor": "Beltrano", "numero_processo": "XERIFE DO CONSUMIDOR",
             "estado": "RJ", "status_atual": "EM ANDAMENTO", "tipo_acao": "PROCON"},
            _origem(2),
        ),
    ]
    resultado = procons.calcular(linhas, mes=8, ano=2026, regras=REGRAS["procons"])
    assert len(resultado.lista) == 2
    assert resultado.avisos == []


# ---------- manuais.py ----------


def test_campos_manuais_valores_padrao_zerados():
    campos = manuais.CamposManuais()
    assert campos.pastas_revisionais.recebidas_no_mes == 0
    assert campos.processos_ativos_revisionais_por_uf == {}
    assert campos.sentencas_procedentes == []

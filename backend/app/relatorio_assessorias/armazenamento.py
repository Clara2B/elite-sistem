"""Resultado mensal calculado (Fase 8) — decisão da Clara, 2026-10-08
("Armazenamento"): fica salvo no banco do sistema (tabela nova e
aditiva — `models.py` deste módulo, nenhuma tabela existente é alterada),
por mês (ex.: `2026-08`), pra não precisar reprocessar.

Os arquivos gerados (.docx/.pdf/.zip) NÃO ficam armazenados — são gerados
sob demanda a cada download, a partir do resultado salvo, igual ao padrão
já usado em Laudos/Audiências/Processos/Correspondências hoje (nada fica
em disco; o disco do Render também não é persistente entre deploys, então
guardar arquivo gerado não seria confiável de qualquer forma).

Serialização explícita (sem reflexão/genérico): `DadosRelatorio` vira um
dict JSON-serializável com `_serializar` e volta com `_desserializar` —
verboso, mas sem mágica (cada dataclass do módulo tem seu par de funções),
e evita o problema de `from __future__ import annotations` transformar os
tipos dos campos em string em tempo de execução, o que quebraria qualquer
reconstrução automática via `dataclasses.fields()`.

Sobrescrita de números (especificação: "Qualquer número pode ser
sobrescrito; o valor sobrescrito fica marcado e registrado"): só os
campos em `CAMPOS_NUMERICOS_SOBRESCREVIVEIS` (uma lista fechada, não
qualquer atributo) podem ser sobrescritos — a validação é posicional
(contra essa lista), não por exceção. O registro de quem/quando/de-quanto-
pra-quanto usa o `LogAuditoria` que já existe (`app.services.auditoria`),
reaproveitado em vez de duplicar um mecanismo de histórico."""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Usuario
from app.relatorio_assessorias.avisos import Aviso
from app.relatorio_assessorias.leitores.base import Origem
from app.relatorio_assessorias.models import RelatorioAssessoriaResultado
from app.relatorio_assessorias.render import DadosRelatorio
from app.relatorio_assessorias.secoes.contrarias import (
    ProcessoContrario,
    ResultadoContrarias,
)
from app.relatorio_assessorias.secoes.extrajudiciais import (
    ClienteAusente,
    ResultadoExtrajudiciais,
)
from app.relatorio_assessorias.secoes.iniciais import ResultadoIniciais
from app.relatorio_assessorias.secoes.judiciais import ResultadoAudiencias
from app.relatorio_assessorias.secoes.laudos import ResultadoLaudos
from app.relatorio_assessorias.secoes.manuais import (
    CamposManuais,
    PastasRevisionais,
    SentencaFavoravel,
    SentencaProcedente,
)
from app.relatorio_assessorias.secoes.procons import Procon, ResultadoProcons
from app.services.auditoria import registrar

# Caminhos (notação com ponto, como um atributo Python) dos únicos campos
# que a tela de revisão pode sobrescrever — totais agregados, não os
# detalhamentos por UF/faixa nem itens de lista (ver docstring do módulo).
CAMPOS_NUMERICOS_SOBRESCREVIVEIS = [
    "laudos.elaborados", "laudos.entregues_dentro_prazo", "laudos.pendentes", "laudos.pendentes_atrasados",
    "iniciais.distribuidos_no_mes", "iniciais.aguardando_distribuicao",
    "extrajudiciais.enviadas", "extrajudiciais.realizadas", "extrajudiciais.pendentes_proximos_meses",
    "audiencias_judiciais.quantidade", "audiencias_contrarias.quantidade",
    "contrarias.incluidos_no_mes", "contrarias.ativos_total",
    "manuais.pastas_revisionais.recebidas_no_mes", "manuais.pastas_revisionais.aprovadas",
    "manuais.pastas_revisionais.aguardando_analise", "manuais.pastas_revisionais.aguardando_correcao_no_mes",
    "manuais.pastas_revisionais.acumulado_crm", "manuais.processos_ativos_revisionais_total",
    "manuais.extrajudiciais_solicitacoes_pendentes_correcao",
]


def _obter_caminho(dados: DadosRelatorio, caminho: str) -> int:
    alvo = dados
    for parte in caminho.split("."):
        alvo = getattr(alvo, parte)
    return alvo


def _definir_caminho(dados: DadosRelatorio, caminho: str, valor: int) -> None:
    partes = caminho.split(".")
    alvo = dados
    for parte in partes[:-1]:
        alvo = getattr(alvo, parte)
    setattr(alvo, partes[-1], valor)


def numeros_calculados(dados: DadosRelatorio) -> dict[str, int]:
    """Os valores ATUAIS de `dados` pra cada campo sobrescrevível — usado
    tanto pra montar o "valor calculado originalmente" mostrado na tela de
    revisão quanto pra extrair o snapshot salvo no banco."""
    return {caminho: _obter_caminho(dados, caminho) for caminho in CAMPOS_NUMERICOS_SOBRESCREVIVEIS}


def aplicar_sobrescritas(dados: DadosRelatorio, sobrescritas: dict[str, int]) -> None:
    """Aplica `sobrescritas` (subconjunto de `CAMPOS_NUMERICOS_SOBRESCREVIVEIS`)
    em `dados`, no lugar (muta os objetos). Ignora silenciosamente uma
    chave fora da lista — nunca deveria acontecer vindo do próprio sistema,
    mas evita que um JSON salvo antes de uma mudança na lista quebre a
    renderização."""
    for caminho, valor in sobrescritas.items():
        if caminho in CAMPOS_NUMERICOS_SOBRESCREVIVEIS:
            _definir_caminho(dados, caminho, valor)


def sobrescrever_numero(
    db: Session,
    registro: RelatorioAssessoriaResultado,
    usuario: Usuario,
    campo: str,
    novo_valor: int,
) -> None:
    """Grava uma sobrescrita e registra no LogAuditoria (valor antigo →
    novo). `campo` precisa estar em `CAMPOS_NUMERICOS_SOBRESCREVIVEIS` —
    quem chama (a rota) é responsável por essa validação antes; aqui só
    uma garantia a mais."""
    if campo not in CAMPOS_NUMERICOS_SOBRESCREVIVEIS:
        raise ValueError(f"campo não sobrescrevível: {campo}")

    dados = _desserializar(registro)
    valor_antigo = aplicado_ou_calculado(registro, dados, campo)

    sobrescritas = json.loads(registro.sobrescritas_json)
    sobrescritas[campo] = novo_valor
    registro.sobrescritas_json = json.dumps(sobrescritas)
    registro.atualizado_por_usuario_id = usuario.id

    registrar(
        db, usuario, "SOBRESCREVEU_NUMERO_RELATORIO_ASSESSORIA",
        entidade="relatorio_assessoria",
        entidade_id=f"{registro.assessoria}-{registro.mes:02d}-{registro.ano}",
        detalhes=f"{campo}: {valor_antigo} → {novo_valor}",
    )
    db.commit()


def aplicado_ou_calculado(registro: RelatorioAssessoriaResultado, dados: DadosRelatorio, campo: str) -> int:
    """O valor EFETIVO de `campo` pra esse registro: a sobrescrita, se
    houver, senão o calculado."""
    sobrescritas = json.loads(registro.sobrescritas_json)
    if campo in sobrescritas:
        return sobrescritas[campo]
    return _obter_caminho(dados, campo)


# ---------- serialização ----------


def _serializar_origem(origem: Origem | None) -> dict | None:
    return None if origem is None else {"planilha": origem.planilha, "aba": origem.aba, "linha": origem.linha}


def _desserializar_origem(valor: dict | None) -> Origem | None:
    return None if valor is None else Origem(**valor)


def _serializar_aviso(aviso: Aviso) -> dict:
    return {"origem": _serializar_origem(aviso.origem), "mensagem": aviso.mensagem}


def _desserializar_aviso(valor: dict) -> Aviso:
    return Aviso(origem=_desserializar_origem(valor["origem"]), mensagem=valor["mensagem"])


def _serializar_processo_contrario(item: ProcessoContrario) -> dict:
    d = asdict(item)
    d["data_recebimento"] = item.data_recebimento.isoformat() if item.data_recebimento else None
    d["origem"] = _serializar_origem(item.origem)
    return d


def _desserializar_processo_contrario(valor: dict) -> ProcessoContrario:
    return ProcessoContrario(
        nome=valor["nome"],
        processo=valor["processo"],
        uf=valor["uf"],
        valor_causa=valor["valor_causa"],
        data_recebimento=date.fromisoformat(valor["data_recebimento"]) if valor["data_recebimento"] else None,
        origem=_desserializar_origem(valor["origem"]),
    )


def _serializar_procon(item: Procon) -> dict:
    d = asdict(item)
    d["origem"] = _serializar_origem(item.origem)
    return d


def _desserializar_procon(valor: dict) -> Procon:
    return Procon(
        nome=valor["nome"], processo=valor["processo"], situacao=valor["situacao"],
        origem=_desserializar_origem(valor["origem"]),
    )


def _serializar_cliente_ausente(item: ClienteAusente) -> dict:
    d = asdict(item)
    d["origem"] = _serializar_origem(item.origem)
    return d


def _desserializar_cliente_ausente(valor: dict) -> ClienteAusente:
    return ClienteAusente(nome=valor["nome"], origem=_desserializar_origem(valor["origem"]))


def _serializar(dados: DadosRelatorio) -> dict:
    return {
        "assessoria": dados.assessoria,
        "mes": dados.mes,
        "ano": dados.ano,
        "data_corte": dados.data_corte.isoformat(),
        "laudos": asdict(dados.laudos),
        "iniciais": asdict(dados.iniciais),
        "extrajudiciais": {
            "enviadas": dados.extrajudiciais.enviadas,
            "realizadas": dados.extrajudiciais.realizadas,
            "pendentes_proximos_meses": dados.extrajudiciais.pendentes_proximos_meses,
            "clientes_ausentes": [_serializar_cliente_ausente(c) for c in dados.extrajudiciais.clientes_ausentes],
        },
        "audiencias_judiciais": asdict(dados.audiencias_judiciais),
        "audiencias_contrarias": asdict(dados.audiencias_contrarias),
        "contrarias": {
            "incluidos_no_mes": dados.contrarias.incluidos_no_mes,
            "ativos_total": dados.contrarias.ativos_total,
            "ativos_por_uf": dados.contrarias.ativos_por_uf,
            "lista_judiciais": [_serializar_processo_contrario(p) for p in dados.contrarias.lista_judiciais],
            "lista_trabalhistas": [_serializar_processo_contrario(p) for p in dados.contrarias.lista_trabalhistas],
        },
        "procons": {"lista": [_serializar_procon(p) for p in dados.procons.lista]},
        "manuais": {
            "pastas_revisionais": asdict(dados.manuais.pastas_revisionais),
            "processos_ativos_revisionais_total": dados.manuais.processos_ativos_revisionais_total,
            "processos_ativos_revisionais_por_uf": dados.manuais.processos_ativos_revisionais_por_uf,
            "sentencas_procedentes": [asdict(s) for s in dados.manuais.sentencas_procedentes],
            "processos_ganhos_por_uf": dados.manuais.processos_ganhos_por_uf,
            "sentencas_favoraveis_contrarias": [asdict(s) for s in dados.manuais.sentencas_favoraveis_contrarias],
            "extrajudiciais_solicitacoes_pendentes_correcao": dados.manuais.extrajudiciais_solicitacoes_pendentes_correcao,
        },
        "avisos": [_serializar_aviso(a) for a in dados.avisos],
    }


def _desserializar_dict(d: dict) -> DadosRelatorio:
    manuais_d = d["manuais"]
    manuais = CamposManuais(
        pastas_revisionais=PastasRevisionais(**manuais_d["pastas_revisionais"]),
        processos_ativos_revisionais_total=manuais_d["processos_ativos_revisionais_total"],
        processos_ativos_revisionais_por_uf=manuais_d["processos_ativos_revisionais_por_uf"],
        sentencas_procedentes=[SentencaProcedente(**s) for s in manuais_d["sentencas_procedentes"]],
        processos_ganhos_por_uf=manuais_d["processos_ganhos_por_uf"],
        sentencas_favoraveis_contrarias=[
            SentencaFavoravel(**s) for s in manuais_d["sentencas_favoraveis_contrarias"]
        ],
        extrajudiciais_solicitacoes_pendentes_correcao=manuais_d["extrajudiciais_solicitacoes_pendentes_correcao"],
    )
    return DadosRelatorio(
        assessoria=d["assessoria"],
        mes=d["mes"],
        ano=d["ano"],
        data_corte=date.fromisoformat(d["data_corte"]),
        laudos=ResultadoLaudos(**d["laudos"]),
        iniciais=ResultadoIniciais(**d["iniciais"]),
        extrajudiciais=ResultadoExtrajudiciais(
            enviadas=d["extrajudiciais"]["enviadas"],
            realizadas=d["extrajudiciais"]["realizadas"],
            pendentes_proximos_meses=d["extrajudiciais"]["pendentes_proximos_meses"],
            clientes_ausentes=[_desserializar_cliente_ausente(c) for c in d["extrajudiciais"]["clientes_ausentes"]],
        ),
        audiencias_judiciais=ResultadoAudiencias(**d["audiencias_judiciais"]),
        audiencias_contrarias=ResultadoAudiencias(**d["audiencias_contrarias"]),
        contrarias=ResultadoContrarias(
            incluidos_no_mes=d["contrarias"]["incluidos_no_mes"],
            ativos_total=d["contrarias"]["ativos_total"],
            ativos_por_uf=d["contrarias"]["ativos_por_uf"],
            lista_judiciais=[_desserializar_processo_contrario(p) for p in d["contrarias"]["lista_judiciais"]],
            lista_trabalhistas=[_desserializar_processo_contrario(p) for p in d["contrarias"]["lista_trabalhistas"]],
        ),
        procons=ResultadoProcons(lista=[_desserializar_procon(p) for p in d["procons"]["lista"]]),
        manuais=manuais,
        avisos=[_desserializar_aviso(a) for a in d["avisos"]],
    )


def _desserializar(registro: RelatorioAssessoriaResultado) -> DadosRelatorio:
    return _desserializar_dict(json.loads(registro.dados_json))


# ---------- CRUD ----------


def salvar_resultado(db: Session, dados: DadosRelatorio, usuario: Usuario) -> RelatorioAssessoriaResultado:
    """Grava (ou sobrescreve) o resultado calculado de uma assessoria/mês —
    chamado pelo processamento (upload das 6 planilhas). Preserva, de um
    resultado já existente: `sobrescritas_json` (reprocessar não deve
    apagar correções manuais já feitas na revisão) e os campos manuais de
    `dados.manuais` (eles não vêm das planilhas — reprocessar não tem como
    recalculá-los, então o valor já digitado antes fica; `dados.manuais`
    recebido aqui só é usado de fato na primeira vez)."""
    registro = db.scalar(
        select(RelatorioAssessoriaResultado).where(
            RelatorioAssessoriaResultado.assessoria == dados.assessoria,
            RelatorioAssessoriaResultado.mes == dados.mes,
            RelatorioAssessoriaResultado.ano == dados.ano,
        )
    )
    if registro is None:
        registro = RelatorioAssessoriaResultado(
            assessoria=dados.assessoria, mes=dados.mes, ano=dados.ano, sobrescritas_json="{}"
        )
        db.add(registro)
    else:
        dados.manuais = _desserializar(registro).manuais

    registro.data_corte = dados.data_corte
    registro.dados_json = json.dumps(_serializar(dados))
    registro.atualizado_por_usuario_id = usuario.id
    registro.atualizado_em = datetime.utcnow()
    db.commit()
    db.refresh(registro)
    return registro


def salvar_campos_manuais(
    db: Session, registro: RelatorioAssessoriaResultado, manuais: CamposManuais, usuario: Usuario
) -> None:
    """Grava os campos manuais (tela de revisão, Fase 8) — diferente de
    `sobrescrever_numero`: isso aqui não é uma correção de um número
    calculado, é o valor de verdade de um campo que nenhuma planilha
    preenche (ver secoes/manuais.py). Registrado no LogAuditoria do mesmo
    jeito, pra manter rastro de quem preencheu/editou."""
    dados = _desserializar(registro)
    dados.manuais = manuais
    registro.dados_json = json.dumps(_serializar(dados))
    registro.atualizado_por_usuario_id = usuario.id
    registro.atualizado_em = datetime.utcnow()
    registrar(
        db, usuario, "EDITOU_CAMPOS_MANUAIS_RELATORIO_ASSESSORIA",
        entidade="relatorio_assessoria",
        entidade_id=f"{registro.assessoria}-{registro.mes:02d}-{registro.ano}",
    )
    db.commit()


def carregar_resultado(db: Session, assessoria: str, mes: int, ano: int) -> RelatorioAssessoriaResultado | None:
    return db.scalar(
        select(RelatorioAssessoriaResultado).where(
            RelatorioAssessoriaResultado.assessoria == assessoria,
            RelatorioAssessoriaResultado.mes == mes,
            RelatorioAssessoriaResultado.ano == ano,
        )
    )


def listar_resultados(db: Session, mes: int, ano: int) -> list[RelatorioAssessoriaResultado]:
    return list(
        db.scalars(
            select(RelatorioAssessoriaResultado)
            .where(RelatorioAssessoriaResultado.mes == mes, RelatorioAssessoriaResultado.ano == ano)
            .order_by(RelatorioAssessoriaResultado.assessoria)
        )
    )


def dados_efetivos(registro: RelatorioAssessoriaResultado) -> DadosRelatorio:
    """`DadosRelatorio` pronto pra render/exibição: o calculado, com as
    sobrescritas já aplicadas por cima."""
    dados = _desserializar(registro)
    aplicar_sobrescritas(dados, json.loads(registro.sobrescritas_json))
    return dados


def numeros_calculados_do_registro(registro: RelatorioAssessoriaResultado) -> dict[str, int]:
    """Os valores ORIGINAIS (sem sobrescrita nenhuma) pra cada campo de
    `CAMPOS_NUMERICOS_SOBRESCREVIVEIS` — pra tela de revisão mostrar "valor
    calculado" ao lado do valor efetivo, quando os dois forem diferentes."""
    return numeros_calculados(_desserializar(registro))

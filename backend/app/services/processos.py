"""Gestão de Processos (Fase 5, ELITE) — ver ARCHITECTURE.md seção 3 e
DATABASE.md seção 6.1.

Cada linha da planilha real é um **andamento** (evento) dentro de um
**processo** — o mesmo número de processo aparece várias vezes ao longo do
tempo. `data_prazo` não é confiável nos dados históricos importados (muitas
vezes só está embutida em texto livre na observação, ex.: "fatal 20/07") —
por isso o import não tenta adivinhar essa data por regex; ela fica
preenchida só quando lançada estruturadamente (manual, dali em diante).
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.excel_reader import load_data_sheets
from app.models import EmpresaCliente, EventoProcesso, Processo, TipoEvento
from app.services.empresas import get_or_create_empresa
from app.utils import cell_text, normalize, parse_date_cell

_logger = logging.getLogger("elite_sistem.import")

REQUIRED_HEADERS = ["CLIENTE", "Nº PROCESSO"]
CHAVE_DUPLICIDADE = ["Nº PROCESSO", "DATA", "EVENTO", "CLIENTE"]

# Formato CNJ (ex.: 5012298-14.2025.8.13.0231). Usado como checagem de
# sanidade: algumas abas da planilha real têm o cabeçalho desalinhado da
# linha de dados (defeito da própria planilha, não do parser) — se o valor
# da coluna "Nº PROCESSO" não parece um número de processo de verdade, a
# linha é descartada em vez de importada errada.
_RE_CNJ = re.compile(r"^\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}$")

# Mesmo defeito de desalinhamento de cabeçalho que o _RE_CNJ protege pode
# jogar uma data (de outra coluna) dentro de ADVOGADA/ASSISTENTE numa linha
# que ainda assim tem um Nº PROCESSO válido na coluna certa. Sem esse filtro,
# uma pessoa no relatório vira literalmente "2025-12-03 00:00:00". Mesmo
# tratamento das outras checagens de sanidade: a linha não é descartada,
# só o valor de advogada/assistente é ignorado (fica None) nesse caso.
_RE_PARECE_DATA = re.compile(r"^\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}(:\d{2})?)?$|^\d{2}/\d{2}/\d{4}$")


def _pessoa_valida(texto: str) -> str | None:
    texto = texto.strip()
    if not texto or _RE_PARECE_DATA.match(texto):
        return None
    return texto


def _separar_assessoria(advogada: str | None) -> str | None:
    """'HUNTING - Fulana de Tal (CONTR. Beltrano)' -> 'HUNTING' — a
    assessoria/escritório terceirizado é sempre a primeira palavra antes do
    nome, na coluna ADVOGADA (confirmado pela Clara). Mesma tolerância de
    formatação que `_separar_empresa_cliente` (não exige espaço ao redor do
    "-"). `advogada` em si não é alterado, fica com o texto original — isso
    só extrai um valor derivado pra permitir filtrar/agrupar relatório por
    assessoria."""
    if not advogada or "-" not in advogada:
        return None
    prefixo, _, resto = advogada.partition("-")
    prefixo, resto = prefixo.strip(), resto.strip()
    if not prefixo or not resto:
        return None
    return prefixo


# Nome de mês (completo ou abreviado 3 letras) + ano de 2/4 dígitos é como
# as abas reais são nomeadas (ex. "SETEMBRO", "SETEMBRO26", "JUNHO 2026",
# "OUTUBRO-26", ou nas abas mais antigas "JUN-25", "SET- 25"). Confirmado
# pela Clara: o mês de referência vem do nome da aba, não de uma coluna.
# Abas que não são nomeadas por mês (ex. "DOCS E CUSTAS", "Dra Galzo", abas
# "fatais") não batem com o regex — ficam sem mês de referência, sem travar
# o import (mesmo espírito das outras checagens de sanidade deste módulo).
_MESES = (
    "JANEIRO", "FEVEREIRO", "MARCO", "ABRIL", "MAIO", "JUNHO",
    "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO",
)
_ABREV_MESES = {
    "JAN": "JANEIRO", "FEV": "FEVEREIRO", "MAR": "MARCO", "ABR": "ABRIL",
    "MAI": "MAIO", "JUN": "JUNHO", "JUL": "JULHO", "AGO": "AGOSTO",
    "SET": "SETEMBRO", "OUT": "OUTUBRO", "NOV": "NOVEMBRO", "DEZ": "DEZEMBRO",
}
_RE_ABA_MES = re.compile(
    rf"^({'|'.join(_MESES)}|{'|'.join(_ABREV_MESES)})[\s\-_/]*(\d{{2,4}})?$"
)


def _mes_referencia_da_aba(nome_aba: str) -> str | None:
    """'SETEMBRO26' -> 'SETEMBRO/2026'; 'JUNHO 2026' -> 'JUNHO/2026';
    'JUN-25' -> 'JUNHO/2025' (abreviação de 3 letras também é reconhecida);
    aba sem ano no nome -> só o mês ('SETEMBRO'); aba que não é um nome de
    mês -> None."""
    m = _RE_ABA_MES.match(normalize(nome_aba))
    if not m:
        return None
    mes, ano_txt = m.group(1), m.group(2)
    mes = _ABREV_MESES.get(mes, mes)
    if not ano_txt:
        return mes
    ano = int(ano_txt)
    if ano < 100:
        ano += 2000
    return f"{mes}/{ano}"


def _col(df, nome: str) -> str:
    for c in df.columns:
        if normalize(c) == normalize(nome):
            return c
    raise KeyError(f"Coluna '{nome}' não encontrada na planilha. Colunas disponíveis: {list(df.columns)}")


def _col_optional(df, nome: str):
    try:
        return _col(df, nome)
    except KeyError:
        return None


def _separar_empresa_cliente(campo: str) -> tuple[str, str] | None:
    """'ABSOLUTA - Jadson Ferreira Braga' -> ('ABSOLUTA', 'Jadson Ferreira Braga').
    Aceita variações sem espaço ao redor do hífen ('DAKAL- Fulano')."""
    if "-" not in campo:
        return None
    empresa, _, resto = campo.partition("-")
    empresa, resto = empresa.strip(), resto.strip()
    if not empresa or not resto:
        return None
    return empresa, resto


@dataclass
class ImportResumo:
    linhas_lidas: int = 0
    linhas_novas: int = 0
    linhas_ja_existentes: int = 0
    linhas_atualizadas: int = 0
    linhas_sem_numero_valido: int = 0
    linhas_sem_empresa_reconhecida: int = 0


def importar_planilha(db: Session, path: str, usuario_id: int | None = None) -> ImportResumo:
    inicio = time.perf_counter()
    df = load_data_sheets(path, REQUIRED_HEADERS, chave_duplicidade=CHAVE_DUPLICIDADE)
    if df.empty:
        raise ValueError(
            "Não encontrei nenhuma aba com as colunas 'CLIENTE' e 'Nº PROCESSO' nesta planilha."
        )

    col_cliente = _col(df, "CLIENTE")
    col_numero = _col(df, "Nº PROCESSO")
    col_data = _col_optional(df, "DATA")
    # Abas mais recentes (ex.: AGOSTO26, SETEMBRO26) passaram a ter a empresa
    # numa coluna própria, separada do cliente — diferente do formato antigo
    # "EMPRESA - Cliente" embutido na coluna CLIENTE (`_separar_empresa_cliente`
    # abaixo). Sem isso, essas linhas não tinham empresa reconhecida e eram
    # descartadas inteiras do import — bug real reportado pela Clara (via
    # relatório de Gestão de Processos com contagem errada, ver DECISIONS.md
    # 2026-09-24).
    col_empresa = _col_optional(df, "EMPRESA")
    col_evento = _col_optional(df, "EVENTO")
    col_prazo = _col_optional(df, "PRAZO FATAL")
    col_observacao = _col_optional(df, "OBSERVAÇÃO")
    col_advogada = _col_optional(df, "ADVOGADA")
    col_assistente = _col_optional(df, "ASSISTENTE")

    processos_existentes = {p.numero_processo: p for p in db.scalars(select(Processo))}
    # Chave por `numero_processo` (não `processo.id`): um processo novo só
    # tem `.id` depois de um flush no banco — chavear por ele forçaria um
    # `db.flush()` logo após criar cada `Processo` só pra conseguir montar a
    # chave do evento na mesma linha, e isso sozinho já foi ~1/3 do tempo
    # total de um import de ~45 mil linhas (medido localmente: um flush por
    # processo novo vira milhares de idas e vindas ao banco em vez de
    # poucas, nas comissões periódicas abaixo). `numero_processo` já está
    # disponível na própria linha, sem custo nenhum. Mapeia pro objeto (não
    # só um set de chaves): uma linha "já existente" ainda pode trazer dado
    # atualizado (observação corrigida, PRAZO FATAL marcado depois, aba
    # renomeada) — sem guardar o objeto não dá pra atualizar, só pra contar.
    # Ver bloco abaixo.
    eventos_existentes = {
        (numero_processo, evento.data, normalize(evento.tipo_evento_nome)): evento
        for evento, numero_processo in db.execute(
            select(EventoProcesso, Processo.numero_processo).join(Processo, EventoProcesso.processo_id == Processo.id)
        )
    }
    # Cache de empresa-cliente pro import inteiro (ver docstring de
    # get_or_create_empresa) — sem isso, cada uma das dezenas de milhares de
    # linhas faria uma consulta ao banco só pra resolver ~43 empresas fixas.
    empresa_cache: dict[str, EmpresaCliente] = {}

    resumo = ImportResumo()
    for _, row in df.iterrows():
        resumo.linhas_lidas += 1

        numero = cell_text(row.get(col_numero))
        if not _RE_CNJ.match(numero):
            resumo.linhas_sem_numero_valido += 1
            continue

        cliente_campo = cell_text(row.get(col_cliente))
        empresa_col_valor = cell_text(row.get(col_empresa)) if col_empresa else ""
        if empresa_col_valor and cliente_campo:
            empresa_nome, nome_cliente = empresa_col_valor, cliente_campo
        else:
            separado = _separar_empresa_cliente(cliente_campo)
            if separado is None:
                resumo.linhas_sem_empresa_reconhecida += 1
                continue
            empresa_nome, nome_cliente = separado

        data_val = parse_date_cell(row.get(col_data)) if col_data else None
        if data_val is None:
            continue  # sem data não dá pra colocar no relatório por período
        # Algumas abas "coringa" (fatais, Dra Galzo, DOCS E CUSTAS etc.) não
        # têm data de andamento real — só a data em que a Dra inseriu o
        # cliente na planilha, que `load_data_sheets` também apelida de
        # "DATA" por falta de outra coluna melhor (ver
        # app/excel_reader.py::_TEXTO_DATA_DE_LIBERACAO). Marca a origem
        # pra `gerar_relatorio` excluir do filtro por período — a Clara
        # confirmou que essas linhas não devem contar como se fossem do mês
        # marcado por essa data (ver DECISIONS.md 2026-09-24).
        data_e_liberacao = bool(row.get("_DATA_E_LIBERACAO", False))

        empresa = get_or_create_empresa(db, empresa_nome, cache=empresa_cache)

        advogada_valida = _pessoa_valida(cell_text(row.get(col_advogada))) if col_advogada else None
        assessoria = _separar_assessoria(advogada_valida)

        processo = processos_existentes.get(numero)
        if processo is None:
            processo = Processo(
                numero_processo=numero,
                empresa_cliente_id=empresa.id,
                nome_cliente=nome_cliente,
                advogada=advogada_valida,
                assistente=_pessoa_valida(cell_text(row.get(col_assistente))) if col_assistente else None,
                assessoria=assessoria,
            )
            db.add(processo)
            processos_existentes[numero] = processo
        else:
            # Atualiza nome/advogada/assistente/assessoria com o lançamento
            # mais recente (planilha real mostra o mesmo cliente/pessoa
            # reatribuída ao longo do tempo; fica sempre com a última
            # informação vista no import — pedido explícito da Clara: mesmo
            # cliente já citado antes, a última atualização é que vale).
            if nome_cliente:
                processo.nome_cliente = nome_cliente
            if advogada_valida:
                processo.advogada = advogada_valida
                processo.assessoria = assessoria
            if col_assistente:
                pessoa = _pessoa_valida(cell_text(row.get(col_assistente)))
                if pessoa:
                    processo.assistente = pessoa

        tipo_evento = cell_text(row.get(col_evento)) if col_evento else ""
        if not tipo_evento:
            tipo_evento = "(SEM TIPO INFORMADO)"

        # Regra confirmada pela Clara: só "SIM" (normalizado) marca prazo
        # fatal — qualquer outro valor (vazio, "NÃO", etc.) não é fatal.
        prazo_fatal = (normalize(cell_text(row.get(col_prazo))) == "SIM") if col_prazo else False
        observacao = (cell_text(row.get(col_observacao)) or None) if col_observacao else None
        aba_nome = row.get("_ABA")
        mes_referencia = _mes_referencia_da_aba(str(aba_nome)) if aba_nome else None

        chave = (numero, data_val, normalize(tipo_evento))
        evento_existente = eventos_existentes.get(chave)
        if evento_existente is not None:
            resumo.linhas_ja_existentes += 1
            # O mesmo andamento (processo+data+tipo) pode voltar numa
            # planilha mais nova com detalhe corrigido/completado — atualiza
            # só o que veio preenchido nessa linha, sem apagar o que já
            # estava lá (ex.: linha sem OBSERVAÇÃO não some com uma já
            # cadastrada) e nunca mexe em `resolvido`/`resolvido_em`/
            # `data_prazo`, que são controlados manualmente dentro do
            # sistema, não pela planilha.
            atualizado = False
            if col_prazo and evento_existente.prazo_fatal != prazo_fatal:
                evento_existente.prazo_fatal = prazo_fatal
                atualizado = True
            if observacao and evento_existente.observacao != observacao:
                evento_existente.observacao = observacao
                atualizado = True
            if mes_referencia and evento_existente.mes_referencia != mes_referencia:
                evento_existente.mes_referencia = mes_referencia
                atualizado = True
            if evento_existente.data_e_liberacao != data_e_liberacao:
                evento_existente.data_e_liberacao = data_e_liberacao
                atualizado = True
            if atualizado:
                resumo.linhas_atualizadas += 1
            continue

        novo_evento = EventoProcesso(
            # `processo=` (relacionamento), não `processo_id=processo.id`:
            # pra um processo recém-criado nesta mesma linha, `.id` só
            # existe depois de um flush no banco — usar o relacionamento
            # deixa o SQLAlchemy resolver a FK sozinho no próximo flush
            # (periódico, não um por linha), sem precisar que o processo já
            # tenha sido gravado antes do evento.
            processo=processo,
            data=data_val,
            tipo_evento_nome=tipo_evento.upper(),
            mes_referencia=mes_referencia,
            data_e_liberacao=data_e_liberacao,
            prazo_fatal=prazo_fatal,
            data_prazo=None,  # não extraído do histórico — ver docstring do módulo
            observacao=observacao,
            criado_por=usuario_id,
        )
        db.add(novo_evento)
        # Guarda o objeto (não só a chave): se uma linha mais adiante nesse
        # mesmo import bater na mesma chave, precisa cair no ramo de
        # atualização acima, não criar outro evento duplicado.
        eventos_existentes[chave] = novo_evento
        resumo.linhas_novas += 1

        # Planilha real tem dezenas de milhares de linhas — sem isso, tudo
        # fica pendente numa única transação/sessão gigante até o fim do
        # loop, o que pesa memória e mantém uma transação aberta por muito
        # tempo no pooler do Supabase. Seguro fazer aqui: nenhuma exceção é
        # levantada dentro do loop por dado ruim (só contadores e "continue").
        if resumo.linhas_novas % 2000 == 0:
            db.commit()

    db.commit()
    _logger.info("import processos: %.1fs total — %s", time.perf_counter() - inicio, resumo)
    return resumo


def apagar_todos_processos(db: Session) -> int:
    """Apaga TODO o histórico de Gestão de Processos (processos + seus
    eventos/andamentos) — mesma "zona de perigo" já disponibilizada em
    Laudos (ver DECISIONS.md 2026-09-24), estendida aqui a pedido da Clara.
    Não há cascade configurado entre `eventos_processo` e `processos`
    (ver app/models.py), então os eventos são apagados primeiro. Devolve a
    contagem de PROCESSOS apagados (não de eventos). Irreversível — a tela
    que chama isso exige confirmação explícita antes. Só Gestão de
    Processos; não mexe em empresas-clientes, tipos de evento cadastrados
    nem em nenhum outro módulo."""
    total = db.scalar(select(func.count()).select_from(Processo)) or 0
    db.execute(delete(EventoProcesso))
    db.execute(delete(Processo))
    db.commit()
    return total


def tipos_evento_cadastrados(db: Session) -> set[str]:
    return {normalize(t.nome) for t in db.scalars(select(TipoEvento))}


def marcar_resolvido(db: Session, evento_id: int, resolvido_em: datetime | None = None) -> EventoProcesso:
    evento = db.get(EventoProcesso, evento_id)
    if evento is None:
        raise ValueError(f"Evento {evento_id} não encontrado.")
    evento.resolvido = True
    evento.resolvido_em = resolvido_em or datetime.utcnow()
    db.commit()
    return evento


def status_prazo(evento: EventoProcesso, hoje: date | None = None) -> str | None:
    """PENDENTE / CUMPRIDO / CUMPRIDO_COM_ATRASO / PERDIDO — None se o
    evento não é de prazo fatal ou não tem data de prazo lançada."""
    if not evento.prazo_fatal or evento.data_prazo is None:
        return None
    hoje = hoje or date.today()
    if evento.resolvido and evento.resolvido_em is not None:
        return "CUMPRIDO" if evento.resolvido_em.date() <= evento.data_prazo else "CUMPRIDO_COM_ATRASO"
    return "PERDIDO" if hoje > evento.data_prazo else "PENDENTE"


@dataclass
class LinhaProcessoGeral:
    assistente: str
    numero_processo: str
    evento: str
    fatal: bool


@dataclass
class LinhaProcessoResumo:
    cliente: str
    numero_processo: str
    evento: str
    observacao: str


@dataclass
class SecaoEmpresaGeral:
    empresa: str
    total_processos: int
    linhas: list[LinhaProcessoGeral] = field(default_factory=list)
    linhas_resumo: list[LinhaProcessoResumo] = field(default_factory=list)


@dataclass
class RelatorioGeral:
    periodo_ini: date
    periodo_fim: date
    secoes: list[SecaoEmpresaGeral] = field(default_factory=list)


@dataclass
class LinhaProcessoPorEmpresa:
    assistente: str
    numero_processo: str
    cliente: str
    evento: str
    observacao: str


@dataclass
class RelatorioPorEmpresa:
    empresa: str
    periodo_ini: date
    periodo_fim: date
    total_processos: int
    linhas: list[LinhaProcessoPorEmpresa] = field(default_factory=list)


def _processos_em_escopo(
    db: Session, periodo_ini: date, periodo_fim: date, empresa_id: int | None = None
) -> list[Processo]:
    """Processos com pelo menos um andamento real (não de "data de
    liberação" — ver `EventoProcesso.data_e_liberacao`) dentro do período —
    mesmo filtro que o relatório antigo já usava pra decidir quais
    processos entram. Só os eventos DENTRO do período (não a tabela inteira
    filtrada em Python depois) — ver nota de performance equivalente que já
    existia aqui antes desta reescrita (2026-09-23/24, ver DECISIONS.md)."""
    query = (
        select(Processo)
        .join(EventoProcesso, EventoProcesso.processo_id == Processo.id)
        .options(selectinload(Processo.empresa_cliente))
        .where(
            EventoProcesso.data >= periodo_ini,
            EventoProcesso.data <= periodo_fim,
            EventoProcesso.data_e_liberacao.is_(False),
        )
        .distinct()
    )
    if empresa_id is not None:
        query = query.where(Processo.empresa_cliente_id == empresa_id)
    return list(db.scalars(query))


def _ultimo_evento_por_processo(db: Session, processo_ids: set[int]) -> dict[int, EventoProcesso]:
    """Andamento mais recente de cada processo — a pedido explícito da
    Clara (2026-09-25): "pela data/hora de registro", ou seja, por
    `criado_em` (quando a linha foi gravada no sistema, com hora), não por
    `data` (a data do andamento em si, sem hora). Considera TODA a história
    do processo, não só o período do relatório — "último evento"/"última
    observação" descrevem o estado atual do processo, não o que aconteceu
    só dentro da janela filtrada. Exclui eventos `data_e_liberacao` (não são
    andamentos de verdade — mesmo motivo de `_processos_em_escopo`), senão
    a data de quando o cliente foi cadastrado numa aba "coringa" apareceria
    como se fosse o andamento mais recente."""
    if not processo_ids:
        return {}
    subq = (
        select(EventoProcesso.processo_id, func.max(EventoProcesso.criado_em).label("max_criado_em"))
        .where(EventoProcesso.processo_id.in_(processo_ids), EventoProcesso.data_e_liberacao.is_(False))
        .group_by(EventoProcesso.processo_id)
        .subquery()
    )
    query = select(EventoProcesso).join(
        subq,
        (EventoProcesso.processo_id == subq.c.processo_id) & (EventoProcesso.criado_em == subq.c.max_criado_em),
    )
    return {evento.processo_id: evento for evento in db.scalars(query)}


def _filtrar_por_assistente(processos: list[Processo], filtro_assistente: str | None) -> list[Processo]:
    if not filtro_assistente:
        return processos
    alvo = normalize(filtro_assistente)
    return [p for p in processos if normalize(p.assistente or "") == alvo]


def gerar_relatorio_geral(
    db: Session, periodo_ini: date, periodo_fim: date, filtro_assistente: str | None = None
) -> RelatorioGeral:
    """Tipo "Geral" (2026-09-25, a pedido da Clara): uma seção por empresa,
    cada uma com duas partes — Parte 1 (Assistente/Nº processo/Evento/Fatal)
    e Parte 2 (Cliente/Nº processo/Último evento/Última observação), uma
    linha por processo em cada parte (não por andamento — por isso o total
    no topo bate com o número de linhas)."""
    processos = _filtrar_por_assistente(_processos_em_escopo(db, periodo_ini, periodo_fim), filtro_assistente)
    ultimos = _ultimo_evento_por_processo(db, {p.id for p in processos})

    por_empresa: dict[str, list[Processo]] = {}
    for p in processos:
        por_empresa.setdefault(p.empresa_cliente.nome, []).append(p)

    secoes = []
    for empresa_nome in sorted(por_empresa, key=normalize):
        procs = por_empresa[empresa_nome]
        linhas_geral = [
            LinhaProcessoGeral(
                assistente=p.assistente or "(sem assistente informado)",
                numero_processo=p.numero_processo,
                evento=ultimos[p.id].tipo_evento_nome if p.id in ultimos else "—",
                fatal=ultimos[p.id].prazo_fatal if p.id in ultimos else False,
            )
            for p in sorted(procs, key=lambda p: (normalize(p.assistente or ""), p.numero_processo))
        ]
        linhas_resumo = [
            LinhaProcessoResumo(
                cliente=p.nome_cliente or "—",
                numero_processo=p.numero_processo,
                evento=ultimos[p.id].tipo_evento_nome if p.id in ultimos else "—",
                observacao=(ultimos[p.id].observacao or "—") if p.id in ultimos else "—",
            )
            for p in sorted(procs, key=lambda p: normalize(p.nome_cliente or ""))
        ]
        secoes.append(
            SecaoEmpresaGeral(
                empresa=empresa_nome, total_processos=len(procs), linhas=linhas_geral, linhas_resumo=linhas_resumo
            )
        )

    return RelatorioGeral(periodo_ini=periodo_ini, periodo_fim=periodo_fim, secoes=secoes)


def gerar_relatorio_por_empresa(
    db: Session,
    empresa_nome: str,
    periodo_ini: date,
    periodo_fim: date,
    filtro_assistente: str | None = None,
) -> RelatorioPorEmpresa:
    """Tipo "Por empresa" (2026-09-25): uma linha por processo dessa
    empresa, com Assistente/Nº processo/Cliente/Último evento/Última
    observação."""
    alvo_empresa = normalize(empresa_nome)
    empresa = next((e for e in db.scalars(select(EmpresaCliente)) if normalize(e.nome) == alvo_empresa), None)
    if empresa is None:
        raise ValueError(f"A empresa '{empresa_nome}' não foi encontrada.")

    processos = _filtrar_por_assistente(
        _processos_em_escopo(db, periodo_ini, periodo_fim, empresa_id=empresa.id), filtro_assistente
    )
    ultimos = _ultimo_evento_por_processo(db, {p.id for p in processos})
    processos.sort(key=lambda p: (normalize(p.assistente or ""), p.numero_processo))

    linhas = [
        LinhaProcessoPorEmpresa(
            assistente=p.assistente or "(sem assistente informado)",
            numero_processo=p.numero_processo,
            cliente=p.nome_cliente or "—",
            evento=ultimos[p.id].tipo_evento_nome if p.id in ultimos else "—",
            observacao=(ultimos[p.id].observacao or "—") if p.id in ultimos else "—",
        )
        for p in processos
    ]

    return RelatorioPorEmpresa(
        empresa=empresa.nome, periodo_ini=periodo_ini, periodo_fim=periodo_fim,
        total_processos=len(processos), linhas=linhas,
    )


def formatar_texto_geral(relatorio: RelatorioGeral) -> str:
    blocos = []
    for secao in relatorio.secoes:
        linhas_txt = [
            f"EMPRESA: {secao.empresa.upper()}",
            f"Total de processos: {secao.total_processos}",
            "",
            f"{'ASSISTENTE':<26}{'Nº PROCESSO':<24}{'EVENTO':<26}{'FATAL':<6}",
        ]
        for l in secao.linhas:
            linhas_txt.append(
                f"{l.assistente[:25]:<26}{l.numero_processo:<24}{l.evento[:25]:<26}{'Sim' if l.fatal else 'Não':<6}"
            )
        linhas_txt.append("")
        linhas_txt.append(f"{'CLIENTE':<32}{'Nº PROCESSO':<24}{'ÚLTIMO EVENTO':<26}{'ÚLTIMA OBSERVAÇÃO'}")
        for l in secao.linhas_resumo:
            linhas_txt.append(f"{l.cliente[:31]:<32}{l.numero_processo:<24}{l.evento[:25]:<26}{l.observacao}")
        blocos.append("\n".join(linhas_txt))
    return "\n\n".join(blocos)


def formatar_texto_por_empresa(relatorio: RelatorioPorEmpresa) -> str:
    linhas_txt = [
        f"EMPRESA: {relatorio.empresa.upper()}",
        f"Total de processos: {relatorio.total_processos}",
        "",
        f"{'ASSISTENTE':<26}{'Nº PROCESSO':<24}{'CLIENTE':<32}{'ÚLTIMO EVENTO':<26}{'ÚLTIMA OBSERVAÇÃO'}",
    ]
    for l in relatorio.linhas:
        linhas_txt.append(
            f"{l.assistente[:25]:<26}{l.numero_processo:<24}{l.cliente[:31]:<32}{l.evento[:25]:<26}{l.observacao}"
        )
    return "\n".join(linhas_txt)


@dataclass
class PrazoProximo:
    evento_id: int
    numero_processo: str
    nome_cliente: str
    tipo_evento_nome: str
    data_prazo: date
    assistente: str | None
    advogada: str | None
    dias_restantes: int
    mes_referencia: str | None


def prazos_proximos(db: Session, dias: int = 7) -> list[PrazoProximo]:
    """Eventos com prazo fatal, não resolvidos, vencendo nos próximos `dias`
    dias (ou já vencidos) — alerta de prazo dentro do sistema (sem envio por
    e-mail, ver DECISIONS.md)."""
    hoje = date.today()
    limite = hoje + timedelta(days=dias)
    resultado = []
    query = select(EventoProcesso).options(selectinload(EventoProcesso.processo)).where(
        EventoProcesso.prazo_fatal.is_(True),
        EventoProcesso.resolvido.is_(False),
        EventoProcesso.data_prazo.isnot(None),
        EventoProcesso.data_prazo <= limite,
    )
    for evento in db.scalars(query):
        resultado.append(
            PrazoProximo(
                evento_id=evento.id,
                numero_processo=evento.processo.numero_processo,
                nome_cliente=evento.processo.nome_cliente,
                tipo_evento_nome=evento.tipo_evento_nome,
                data_prazo=evento.data_prazo,
                assistente=evento.processo.assistente,
                advogada=evento.processo.advogada,
                dias_restantes=(evento.data_prazo - hoje).days,
                mes_referencia=evento.mes_referencia,
            )
        )
    return sorted(resultado, key=lambda p: p.data_prazo)

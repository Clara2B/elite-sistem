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

from sqlalchemy import func, select
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
        separado = _separar_empresa_cliente(cliente_campo)
        if separado is None:
            resumo.linhas_sem_empresa_reconhecida += 1
            continue
        empresa_nome, nome_cliente = separado

        data_val = parse_date_cell(row.get(col_data)) if col_data else None
        if data_val is None:
            continue  # sem data não dá pra colocar no relatório por período

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


PROCESSO_PARADO_DIAS = 15  # ver DATABASE.md seção 6.1 — número inicial, ajustável


@dataclass
class LinhaRelatorioPessoa:
    pessoa: str
    processos: int = 0
    eventos: int = 0
    prazos_cumpridos: int = 0
    prazos_perdidos: int = 0
    prazos_pendentes: int = 0
    processos_parados: int = 0


@dataclass
class RelatorioProcessos:
    periodo_ini: date
    periodo_fim: date
    linhas: list[LinhaRelatorioPessoa] = field(default_factory=list)
    total: LinhaRelatorioPessoa = field(default_factory=lambda: LinhaRelatorioPessoa(pessoa="EQUIPE (GERAL)"))


def _agrupar_por(processo: Processo, agrupar_por: str) -> str:
    valor = getattr(processo, agrupar_por)
    return valor.strip() if valor else f"(sem {agrupar_por} informado)"


def gerar_relatorio(
    db: Session,
    periodo_ini: date,
    periodo_fim: date,
    agrupar_por: str = "assistente",
    filtro_pessoa: str | None = None,
) -> RelatorioProcessos:
    """`agrupar_por`: 'assistente', 'advogada' ou 'assessoria'. `filtro_pessoa`:
    se informado, só essa pessoa/assessoria entra no relatório (relatório
    individual); senão, todas (relatório geral)."""
    if agrupar_por not in {"assistente", "advogada", "assessoria"}:
        raise ValueError("agrupar_por precisa ser 'assistente', 'advogada' ou 'assessoria'.")

    hoje = date.today()
    limite_parado = hoje - timedelta(days=PROCESSO_PARADO_DIAS)

    por_pessoa: dict[str, LinhaRelatorioPessoa] = {}
    processos_contados: dict[str, set[int]] = {}
    processos_parados_contados: dict[str, set[int]] = {}

    # Só os eventos DENTRO do período (não a tabela inteira filtrada em
    # Python depois) — a versão anterior carregava todos os ~5.600
    # processos e todos os ~45 mil eventos em toda geração de relatório,
    # mesmo pedindo só um mês; `selectinload` sozinho ainda divide isso em
    # vários lotes de 500 ids (13 idas e vindas ao banco pra ~5.600
    # processos). Medido com log real do Render: ~14s por carregamento da
    # tela de Gestão de Processos (ela já chama esta função com o período
    # padrão só de abrir a tela, mesmo sem pedir relatório nenhum). Um
    # período típico de um mês é uma fração pequena do total de eventos, e
    # a consulta abaixo só traz esses — normalmente cabe num único lote.
    query_eventos = (
        select(EventoProcesso)
        .options(selectinload(EventoProcesso.processo))
        .where(EventoProcesso.data >= periodo_ini, EventoProcesso.data <= periodo_fim)
    )
    for evento in db.scalars(query_eventos):
        processo = evento.processo
        pessoa = _agrupar_por(processo, agrupar_por)
        if filtro_pessoa and normalize(pessoa) != normalize(filtro_pessoa):
            continue

        linha = por_pessoa.setdefault(pessoa, LinhaRelatorioPessoa(pessoa=pessoa))
        processos_contados.setdefault(pessoa, set()).add(processo.id)
        linha.eventos += 1

        st = status_prazo(evento, hoje)
        if st == "CUMPRIDO":
            linha.prazos_cumpridos += 1
        elif st in ("PERDIDO", "CUMPRIDO_COM_ATRASO"):
            linha.prazos_perdidos += 1
        elif st == "PENDENTE":
            linha.prazos_pendentes += 1

    # "Processo parado" precisa do último evento de TODA a história do
    # processo, não só dentro do período do relatório — por isso é uma
    # consulta separada, agregada (só processo_id + data máxima, nada de
    # observação/tipo/etc.) e restrita só aos processos que já entraram no
    # relatório acima, não a tabela inteira de novo.
    if processos_contados:
        ids_relevantes = {pid for ids in processos_contados.values() for pid in ids}
        ultimo_evento_por_processo = dict(
            db.execute(
                select(EventoProcesso.processo_id, func.max(EventoProcesso.data))
                .where(EventoProcesso.processo_id.in_(ids_relevantes))
                .group_by(EventoProcesso.processo_id)
            ).all()
        )
        for pessoa, ids in processos_contados.items():
            for processo_id in ids:
                if ultimo_evento_por_processo.get(processo_id, hoje) < limite_parado:
                    processos_parados_contados.setdefault(pessoa, set()).add(processo_id)

    # "EQUIPE (GERAL)" só faz sentido no relatório geral (todo mundo); no
    # individual (filtro_pessoa preenchido) a linha de total é só a mesma
    # pessoa duplicada — rótulo "TOTAL" evita a confusão de ler "EQUIPE
    # (GERAL)" com apenas uma pessoa no relatório.
    total = LinhaRelatorioPessoa(pessoa="TOTAL" if filtro_pessoa else "EQUIPE (GERAL)")
    for pessoa, linha in por_pessoa.items():
        linha.processos = len(processos_contados.get(pessoa, ()))
        linha.processos_parados = len(processos_parados_contados.get(pessoa, ()))
        total.processos += linha.processos
        total.eventos += linha.eventos
        total.prazos_cumpridos += linha.prazos_cumpridos
        total.prazos_perdidos += linha.prazos_perdidos
        total.prazos_pendentes += linha.prazos_pendentes
        total.processos_parados += linha.processos_parados

    return RelatorioProcessos(
        periodo_ini=periodo_ini,
        periodo_fim=periodo_fim,
        linhas=sorted(por_pessoa.values(), key=lambda linha: normalize(linha.pessoa)),
        total=total,
    )


def formatar_texto(relatorio: RelatorioProcessos, titulo: str) -> str:
    linhas_txt = [
        titulo,
        f"Período: {relatorio.periodo_ini.strftime('%d/%m/%Y')} a {relatorio.periodo_fim.strftime('%d/%m/%Y')}",
        "",
        f"{'PESSOA':<28}{'PROCESSOS':>11}{'EVENTOS':>10}{'CUMPRIDOS':>11}{'PERDIDOS':>10}{'PENDENTES':>11}{'PARADOS':>10}",
    ]
    for linha in relatorio.linhas:
        linhas_txt.append(
            f"{linha.pessoa[:27]:<28}{linha.processos:>11}{linha.eventos:>10}"
            f"{linha.prazos_cumpridos:>11}{linha.prazos_perdidos:>10}{linha.prazos_pendentes:>11}{linha.processos_parados:>10}"
        )
    linhas_txt.append("-" * 91)
    t = relatorio.total
    linhas_txt.append(
        f"{t.pessoa[:27]:<28}{t.processos:>11}{t.eventos:>10}"
        f"{t.prazos_cumpridos:>11}{t.prazos_perdidos:>10}{t.prazos_pendentes:>11}{t.processos_parados:>10}"
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

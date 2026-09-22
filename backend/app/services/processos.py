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

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.excel_reader import load_data_sheets
from app.models import EventoProcesso, Processo, TipoEvento
from app.services.empresas import get_or_create_empresa
from app.utils import cell_text, normalize, parse_date_cell

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
    linhas_sem_numero_valido: int = 0
    linhas_sem_empresa_reconhecida: int = 0


def importar_planilha(db: Session, path: str, usuario_id: int | None = None) -> ImportResumo:
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
    eventos_existentes = {
        (e.processo_id, e.data, normalize(e.tipo_evento_nome))
        for e in db.scalars(select(EventoProcesso))
    }

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

        empresa = get_or_create_empresa(db, empresa_nome)

        processo = processos_existentes.get(numero)
        if processo is None:
            processo = Processo(
                numero_processo=numero,
                empresa_cliente_id=empresa.id,
                nome_cliente=nome_cliente,
                advogada=_pessoa_valida(cell_text(row.get(col_advogada))) if col_advogada else None,
                assistente=_pessoa_valida(cell_text(row.get(col_assistente))) if col_assistente else None,
            )
            db.add(processo)
            db.flush()
            processos_existentes[numero] = processo
        else:
            # Atualiza advogada/assistente com o lançamento mais recente
            # (planilha real mostra a mesma pessoa reatribuída ao longo do
            # tempo; fica sempre com a última informação vista no import).
            if col_advogada:
                pessoa = _pessoa_valida(cell_text(row.get(col_advogada)))
                if pessoa:
                    processo.advogada = pessoa
            if col_assistente:
                pessoa = _pessoa_valida(cell_text(row.get(col_assistente)))
                if pessoa:
                    processo.assistente = pessoa

        tipo_evento = cell_text(row.get(col_evento)) if col_evento else ""
        if not tipo_evento:
            tipo_evento = "(SEM TIPO INFORMADO)"

        chave = (processo.id, data_val, normalize(tipo_evento))
        if chave in eventos_existentes:
            resumo.linhas_ja_existentes += 1
            continue

        # Regra confirmada pela Clara: só "SIM" (normalizado) marca prazo
        # fatal — qualquer outro valor (vazio, "NÃO", etc.) não é fatal.
        prazo_fatal = (normalize(cell_text(row.get(col_prazo))) == "SIM") if col_prazo else False

        db.add(
            EventoProcesso(
                processo_id=processo.id,
                data=data_val,
                tipo_evento_nome=tipo_evento.upper(),
                prazo_fatal=prazo_fatal,
                data_prazo=None,  # não extraído do histórico — ver docstring do módulo
                observacao=(cell_text(row.get(col_observacao)) or None) if col_observacao else None,
                criado_por=usuario_id,
            )
        )
        eventos_existentes.add(chave)
        resumo.linhas_novas += 1

    db.commit()
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
    return valor.strip() if valor else "(sem assistente informado)"


def gerar_relatorio(
    db: Session,
    periodo_ini: date,
    periodo_fim: date,
    agrupar_por: str = "assistente",
    filtro_pessoa: str | None = None,
) -> RelatorioProcessos:
    """`agrupar_por`: 'assistente' ou 'advogada'. `filtro_pessoa`: se
    informado, só essa pessoa entra no relatório (relatório individual);
    senão, todas (relatório geral)."""
    if agrupar_por not in {"assistente", "advogada"}:
        raise ValueError("agrupar_por precisa ser 'assistente' ou 'advogada'.")

    hoje = date.today()
    limite_parado = hoje - timedelta(days=PROCESSO_PARADO_DIAS)

    por_pessoa: dict[str, LinhaRelatorioPessoa] = {}
    processos_contados: dict[str, set[int]] = {}
    processos_parados_contados: dict[str, set[int]] = {}

    for processo in db.scalars(select(Processo)):
        pessoa = _agrupar_por(processo, agrupar_por)
        if filtro_pessoa and normalize(pessoa) != normalize(filtro_pessoa):
            continue

        eventos_periodo = [e for e in processo.eventos if periodo_ini <= e.data <= periodo_fim]
        if not eventos_periodo:
            continue

        linha = por_pessoa.setdefault(pessoa, LinhaRelatorioPessoa(pessoa=pessoa))
        processos_contados.setdefault(pessoa, set()).add(processo.id)
        linha.eventos += len(eventos_periodo)

        for evento in eventos_periodo:
            st = status_prazo(evento, hoje)
            if st == "CUMPRIDO":
                linha.prazos_cumpridos += 1
            elif st in ("PERDIDO", "CUMPRIDO_COM_ATRASO"):
                linha.prazos_perdidos += 1
            elif st == "PENDENTE":
                linha.prazos_pendentes += 1

        ultimo_evento = max(e.data for e in processo.eventos)
        if ultimo_evento < limite_parado:
            processos_parados_contados.setdefault(pessoa, set()).add(processo.id)

    total = LinhaRelatorioPessoa(pessoa="EQUIPE (GERAL)")
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
        linhas=sorted(por_pessoa.values(), key=lambda l: normalize(l.pessoa)),
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
    numero_processo: str
    nome_cliente: str
    tipo_evento_nome: str
    data_prazo: date
    assistente: str | None
    advogada: str | None
    dias_restantes: int


def prazos_proximos(db: Session, dias: int = 7) -> list[PrazoProximo]:
    """Eventos com prazo fatal, não resolvidos, vencendo nos próximos `dias`
    dias (ou já vencidos) — alerta de prazo dentro do sistema (sem envio por
    e-mail, ver DECISIONS.md)."""
    hoje = date.today()
    limite = hoje + timedelta(days=dias)
    resultado = []
    query = select(EventoProcesso).where(
        EventoProcesso.prazo_fatal.is_(True),
        EventoProcesso.resolvido.is_(False),
        EventoProcesso.data_prazo.isnot(None),
        EventoProcesso.data_prazo <= limite,
    )
    for evento in db.scalars(query):
        resultado.append(
            PrazoProximo(
                numero_processo=evento.processo.numero_processo,
                nome_cliente=evento.processo.nome_cliente,
                tipo_evento_nome=evento.tipo_evento_nome,
                data_prazo=evento.data_prazo,
                assistente=evento.processo.assistente,
                advogada=evento.processo.advogada,
                dias_restantes=(evento.data_prazo - hoje).days,
            )
        )
    return sorted(resultado, key=lambda p: p.data_prazo)

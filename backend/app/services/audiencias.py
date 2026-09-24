"""Regras do fluxo de AUDIÊNCIAS — portado de core/audiencias.py
(leitor-relatorio), adaptado para ler/gravar no banco.

Regras já auditadas em ARCHITECTURE.md seção 1.4: período quinzenal (1-15 /
16-fim), sem status (sempre solicitação), valor definido pela faixa do
acumulado mensal da empresa-cliente — a 2ª quinzena usa a faixa nova só para
as audiências novas, sem recalcular a 1ª quinzena.
"""
from __future__ import annotations

import calendar
import logging
import time
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.excel_reader import load_data_sheets
from app.models import Audiencia, EmpresaCliente, FaixaAudiencia
from app.services.empresas import get_or_create_empresa
from app.utils import cell_text, normalize, parse_date_cell

_logger = logging.getLogger("elite_sistem.import")

REQUIRED_HEADERS = ["EMPRESA", "NOME COMPLETO", "DATA DE RECEBIMENTO"]
CHAVE_DUPLICIDADE = ["DATA DE RECEBIMENTO", "EMPRESA", "NOME COMPLETO", "CPF"]


def periodo_quinzenal(ano: int, mes: int, quinzena: int) -> tuple[date, date]:
    if quinzena == 1:
        return date(ano, mes, 1), date(ano, mes, 15)
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    return date(ano, mes, 16), date(ano, mes, ultimo_dia)


def _col(df, nome: str) -> str:
    for c in df.columns:
        if normalize(c) == normalize(nome):
            return c
    raise KeyError(f"Coluna '{nome}' não encontrada na planilha. Colunas disponíveis: {list(df.columns)}")


def _col_optional(df, nome: str) -> str | None:
    try:
        return _col(df, nome)
    except KeyError:
        return None


@dataclass
class ImportResumo:
    linhas_lidas: int = 0
    linhas_novas: int = 0
    linhas_ja_existentes: int = 0


def importar_planilha(db: Session, path: str) -> ImportResumo:
    inicio = time.perf_counter()
    df = load_data_sheets(path, REQUIRED_HEADERS, chave_duplicidade=CHAVE_DUPLICIDADE)
    if df.empty:
        raise ValueError(
            "Não encontrei nenhuma aba com as colunas 'EMPRESA' e 'NOME COMPLETO' nesta planilha."
        )

    col_empresa = _col(df, "EMPRESA")
    col_cliente = _col(df, "NOME COMPLETO")
    col_data = _col_optional(df, "DATA DE RECEBIMENTO") or _col(df, "DATA")
    col_cpf = _col_optional(df, "CPF")
    col_data_agendamento = _col_optional(df, "DATA DE AGENDAMENTO")
    col_conciliadora = _col_optional(df, "CONCILIADORA")
    col_advogada = _col_optional(df, "ADVOGADA")

    existentes = {
        (a.empresa_cliente_id, a.data_recebimento, normalize(a.nome_cliente), (a.cpf or "").strip())
        for a in db.scalars(select(Audiencia))
    }
    # Cache de empresa-cliente pro import inteiro — ver nota equivalente em
    # app/services/laudos.py e app/services/processos.py.
    empresa_cache: dict = {}

    resumo = ImportResumo()
    for _, row in df.iterrows():
        resumo.linhas_lidas += 1
        empresa_nome = cell_text(row.get(col_empresa))
        if not empresa_nome:
            continue
        data_val = parse_date_cell(row.get(col_data))
        if data_val is None:
            continue
        cliente = cell_text(row.get(col_cliente))
        if not cliente:
            continue
        cpf = cell_text(row.get(col_cpf)) if col_cpf else ""

        empresa = get_or_create_empresa(db, empresa_nome, cache=empresa_cache)
        chave = (empresa.id, data_val, normalize(cliente), cpf)
        if chave in existentes:
            resumo.linhas_ja_existentes += 1
            continue

        db.add(
            Audiencia(
                empresa_cliente_id=empresa.id,
                nome_cliente=cliente,
                cpf=cpf or None,
                data_recebimento=data_val,
                data_agendamento=(cell_text(row.get(col_data_agendamento)) or None) if col_data_agendamento else None,
                conciliadora=(cell_text(row.get(col_conciliadora)) or None) if col_conciliadora else None,
                advogada=(cell_text(row.get(col_advogada)) or None) if col_advogada else None,
            )
        )
        existentes.add(chave)
        resumo.linhas_novas += 1

    db.commit()
    _logger.info("import audiencias: %.1fs total — %s", time.perf_counter() - inicio, resumo)
    return resumo


def apagar_todas_audiencias(db: Session) -> int:
    """Apaga TODO o histórico de audiências — mesma "zona de perigo" já
    disponibilizada em Laudos (ver DECISIONS.md 2026-09-24), estendida aqui
    a pedido da Clara. Irreversível — a tela que chama isso exige
    confirmação explícita antes. Só audiências; não mexe em
    empresas-clientes nem em nenhum outro módulo."""
    total = db.scalar(select(func.count()).select_from(Audiencia)) or 0
    db.execute(delete(Audiencia))
    db.commit()
    return total


@dataclass
class AudienciasResult:
    empresa: str
    cnpj: str | None
    periodo_ini: date
    periodo_fim: date
    valor_unitario: float | None
    clientes: list[str] = field(default_factory=list)
    total: float | None = None
    valor_cadastrado: bool = True
    quantidade_mes_anterior: int = 0
    quantidade_mes: int = 0
    faixa_inicio: int | None = None
    faixa_fim: int | None = None


def _clientes_no_periodo(db: Session, empresa_id: int, periodo_ini: date, periodo_fim: date) -> list[str]:
    query = select(Audiencia).where(
        Audiencia.empresa_cliente_id == empresa_id,
        Audiencia.data_recebimento >= periodo_ini,
        Audiencia.data_recebimento <= periodo_fim,
    )
    clientes = [a.nome_cliente for a in db.scalars(query) if a.nome_cliente]
    return sorted(clientes, key=normalize)


def _faixa_para_quantidade(db: Session, quantidade: int) -> FaixaAudiencia | None:
    for faixa in db.scalars(select(FaixaAudiencia).order_by(FaixaAudiencia.inicio)):
        if faixa.inicio <= quantidade <= faixa.fim:
            return faixa
    return None


def gerar_relatorio(
    db: Session,
    empresa_nome: str,
    periodo_ini: date,
    periodo_fim: date,
    cnpj: str | None = None,
) -> AudienciasResult:
    alvo_empresa = normalize(empresa_nome)
    empresa = None
    for e in db.scalars(select(EmpresaCliente)):
        if normalize(e.nome) == alvo_empresa:
            empresa = e
            break
    if empresa is None:
        raise ValueError(f"A empresa '{empresa_nome}' não foi encontrada.")

    clientes = _clientes_no_periodo(db, empresa.id, periodo_ini, periodo_fim)

    inicio_mes = date(periodo_ini.year, periodo_ini.month, 1)
    clientes_mes_anterior = (
        _clientes_no_periodo(db, empresa.id, inicio_mes, date(periodo_ini.year, periodo_ini.month, periodo_ini.day - 1))
        if periodo_ini.day > 1
        else []
    )
    quantidade_mes_anterior = len(clientes_mes_anterior)
    quantidade_mes = quantidade_mes_anterior + len(clientes)
    faixa = _faixa_para_quantidade(db, quantidade_mes) if clientes else None

    if clientes and faixa is None:
        raise ValueError(f"Não existe faixa de preço cadastrada para {quantidade_mes} audiências acumuladas no mês.")

    valor_unitario = faixa.valor if faixa else None
    total = valor_unitario * len(clientes) if valor_unitario is not None else None

    return AudienciasResult(
        empresa=empresa.nome,
        cnpj=cnpj or empresa.cnpj,
        periodo_ini=periodo_ini,
        periodo_fim=periodo_fim,
        valor_unitario=valor_unitario,
        clientes=clientes,
        total=total,
        valor_cadastrado=faixa is not None or not clientes,
        quantidade_mes_anterior=quantidade_mes_anterior,
        quantidade_mes=quantidade_mes,
        faixa_inicio=faixa.inicio if faixa else None,
        faixa_fim=faixa.fim if faixa else None,
    )


def formatar_texto(result: AudienciasResult) -> str:
    from app.utils import format_brl

    linhas = [f"Empresa: {result.empresa.upper()}"]
    if result.cnpj:
        linhas.append(f"CNPJ: {result.cnpj}")
    linhas.append(f"Período: {result.periodo_ini.strftime('%d/%m/%Y')} -{result.periodo_fim.strftime('%d/%m/%Y')}")
    if result.valor_unitario is not None:
        linhas.append(f"Valor por audiência: {format_brl(result.valor_unitario)}")
    linhas.append(f"Quantidade solicitada no período: {len(result.clientes)}")
    linhas.append(f"Acumulado no mês: {result.quantidade_mes}")
    linhas.append("Clientes:")
    for i, nome in enumerate(result.clientes, start=1):
        linhas.append(f"{i} - {nome.upper()}")
    if result.total is not None:
        linhas.append(f"Total {format_brl(result.total)}")
    return "\n".join(linhas)

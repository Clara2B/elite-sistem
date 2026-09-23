"""Regras do fluxo de LAUDOS — portado de core/laudos.py (leitor-relatorio),
adaptado para ler/gravar no banco em vez de recalcular tudo a cada upload.

Mesmas regras de negócio já auditadas em ARCHITECTURE.md seção 1.4:
- Período: dia 21 de um mês ao dia 20 do mês seguinte (ambas as pontas incluídas).
- Filtra por empresa-cliente e por status (Solicitação/Corrigido), comparado
  com a coluna ENTRADA DE LAUDO / STATUS da planilha.
- Valor por tipo de laudo sempre resolvido a partir da tabela de valores
  ATUAL (tipos_laudo) no momento da geração — igual ao sistema atual, que
  também recalcula a cada geração (não há "congelamento" do valor).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.excel_reader import load_data_sheets
from app.models import Laudo, TipoLaudo
from app.services.empresas import get_or_create_empresa
from app.utils import cell_text, normalize, parse_date_cell

STATUS_MAP = {
    "SOLICITACAO": "SOLICITAÇÃO",
    "SOLICITAÇÃO": "SOLICITAÇÃO",
    "CORRIGIDO": "CORREÇÃO",
    "CORRECAO": "CORREÇÃO",
    "CORREÇÃO": "CORREÇÃO",
}

STATUS_AMBOS = "AMBOS"
STATUS_VALIDOS = {"SOLICITAÇÃO", "CORREÇÃO"}
OPCOES_STATUS = ["Solicitação + Corrigido (cobrança)", "Somente Solicitação", "Somente Corrigido"]
STATUS_OPCAO_MAP = {
    normalize(OPCOES_STATUS[0]): STATUS_AMBOS,
    normalize(OPCOES_STATUS[1]): "SOLICITAÇÃO",
    normalize(OPCOES_STATUS[2]): "CORREÇÃO",
}

REQUIRED_HEADERS = ["EMPRESA", "TIPO DE LAUDO", "DATA"]
CHAVE_DUPLICIDADE = ["DATA", "NOME DO CLIENTE", "EMPRESA", "TIPO DE LAUDO"]


def periodo_20_a_20(ano: int, mes: int) -> tuple[date, date]:
    ini = date(ano, mes, 21)
    if mes == 12:
        prox_ano, prox_mes = ano + 1, 1
    else:
        prox_ano, prox_mes = ano, mes + 1
    fim = date(prox_ano, prox_mes, 20)
    return ini, fim


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
    df = load_data_sheets(path, REQUIRED_HEADERS, chave_duplicidade=CHAVE_DUPLICIDADE)
    if df.empty:
        raise ValueError(
            "Não encontrei nenhuma aba com as colunas 'EMPRESA' e 'TIPO DE LAUDO' nesta planilha."
        )

    col_empresa = _col(df, "EMPRESA")
    col_tipo = _col(df, "TIPO DE LAUDO")
    col_data = _col(df, "DATA")
    col_cliente = _col_optional(df, "NOME DO CLIENTE") or _col_optional(df, "CLIENTE")
    col_status = _col_optional(df, "ENTRADA DE LAUDO") or _col_optional(df, "STATUS")

    existentes = {
        (l.empresa_cliente_id, normalize(l.tipo_laudo_nome), l.data, normalize(l.nome_cliente))
        for l in db.scalars(select(Laudo))
    }
    # Cache de empresa-cliente pro import inteiro — sem isso,
    # get_or_create_empresa faz uma consulta ao banco varrendo todas as
    # empresas a cada linha (N+1 real, mesmo problema já corrigido em
    # app/services/processos.py; aqui é o mesmo bug, encontrado depois da
    # Clara reportar lentidão generalizada no sistema — ver DECISIONS.md).
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
        tipo = cell_text(row.get(col_tipo))
        if not tipo:
            continue

        status_raw = cell_text(row.get(col_status)) if col_status else ""
        status_normalizado = STATUS_MAP.get(normalize(status_raw), status_raw.upper() or "SOLICITAÇÃO")

        cliente = cell_text(row.get(col_cliente)) if col_cliente else ""

        empresa = get_or_create_empresa(db, empresa_nome, cache=empresa_cache)
        chave = (empresa.id, normalize(tipo), data_val, normalize(cliente))
        if chave in existentes:
            resumo.linhas_ja_existentes += 1
            continue

        db.add(
            Laudo(
                empresa_cliente_id=empresa.id,
                tipo_laudo_nome=tipo.upper(),
                data=data_val,
                nome_cliente=cliente,
                status=status_normalizado,
            )
        )
        existentes.add(chave)
        resumo.linhas_novas += 1

    db.commit()
    return resumo


@dataclass
class LinhaLaudo:
    data: date
    cliente: str
    tipo: str
    status: str
    valor: float


@dataclass
class LaudosResult:
    empresa: str
    cnpj: str | None
    periodo_ini: date
    periodo_fim: date
    status: str
    linhas: list[LinhaLaudo] = field(default_factory=list)
    tipos_sem_valor: list[str] = field(default_factory=list)
    total: float = 0.0


def _valor_tipo(db: Session, tipo: str, cache: dict[str, float | None]) -> float | None:
    alvo = normalize(tipo)
    if alvo in cache:
        return cache[alvo]
    for tl in db.scalars(select(TipoLaudo)):
        if normalize(tl.nome) == alvo:
            cache[alvo] = tl.valor_padrao
            return tl.valor_padrao
    cache[alvo] = None
    return None


def gerar_relatorio(
    db: Session,
    empresa_nome: str,
    periodo_ini: date,
    periodo_fim: date,
    status_opcao: str,
    cnpj: str | None = None,
) -> LaudosResult:
    from app.models import EmpresaCliente

    alvo_empresa = normalize(empresa_nome)
    empresa = None
    for e in db.scalars(select(EmpresaCliente)):
        if normalize(e.nome) == alvo_empresa:
            empresa = e
            break
    if empresa is None:
        raise ValueError(f"A empresa '{empresa_nome}' não foi encontrada.")

    status_key = normalize(status_opcao)
    status_normalizado = STATUS_OPCAO_MAP.get(status_key, STATUS_MAP.get(status_key, status_key))

    status_label = {
        STATUS_AMBOS: "Solicitação + Corrigido",
        "SOLICITAÇÃO": "Solicitação",
        "CORREÇÃO": "Corrigido",
    }.get(status_normalizado, status_normalizado)

    query = select(Laudo).where(
        Laudo.empresa_cliente_id == empresa.id,
        Laudo.data >= periodo_ini,
        Laudo.data <= periodo_fim,
    )

    linhas: list[LinhaLaudo] = []
    tipos_sem_valor: set[str] = set()
    valor_cache: dict[str, float | None] = {}

    for laudo in db.scalars(query):
        if status_normalizado == STATUS_AMBOS:
            if laudo.status not in STATUS_VALIDOS:
                continue
        elif laudo.status != status_normalizado:
            continue

        valor = _valor_tipo(db, laudo.tipo_laudo_nome, valor_cache)
        if valor is None:
            tipos_sem_valor.add(laudo.tipo_laudo_nome)
            valor = 0.0

        status_linha_label = {"SOLICITAÇÃO": "Solicitação", "CORREÇÃO": "Corrigido"}.get(laudo.status, "")
        linhas.append(
            LinhaLaudo(
                data=laudo.data,
                cliente=laudo.nome_cliente,
                tipo=laudo.tipo_laudo_nome,
                status=status_linha_label,
                valor=valor,
            )
        )

    linhas.sort(key=lambda l: normalize(l.cliente))
    total = sum(l.valor for l in linhas)

    return LaudosResult(
        empresa=empresa.nome,
        cnpj=cnpj or empresa.cnpj,
        periodo_ini=periodo_ini,
        periodo_fim=periodo_fim,
        status=status_label,
        linhas=linhas,
        tipos_sem_valor=sorted(tipos_sem_valor),
        total=total,
    )


def formatar_texto(result: LaudosResult) -> str:
    from app.utils import format_brl

    linhas_txt = [f"Empresa: {result.empresa.upper()}"]
    if result.cnpj:
        linhas_txt.append(f"CNPJ: {result.cnpj}")
    linhas_txt.append("")
    linhas_txt.append(f"{'DATA':<12}{'CLIENTE':<45}{'TIPO DE LAUDO':<18}{'STATUS':<14}{'VALOR':>10}")
    for linha in result.linhas:
        data_str = linha.data.strftime("%d/%m/%Y")
        linhas_txt.append(
            f"{data_str:<12}{linha.cliente:<45}{linha.tipo:<18}{linha.status:<14}{format_brl(linha.valor):>10}"
        )
    linhas_txt.append("")
    linhas_txt.append(f"Total{' ' * 70}{format_brl(result.total)}")
    return "\n".join(linhas_txt)

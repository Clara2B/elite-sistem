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

import logging
import time
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.excel_reader import load_data_sheets
from app.models import EmpresaCliente, Laudo, TipoLaudo
from app.services.empresas import get_or_create_empresa
from app.utils import cell_text, normalize, parse_date_cell

_logger = logging.getLogger("elite_sistem.import")

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
    inicio = time.perf_counter()
    df = load_data_sheets(path, REQUIRED_HEADERS, chave_duplicidade=CHAVE_DUPLICIDADE)
    if df.empty:
        raise ValueError(
            "Não encontrei nenhuma aba com as colunas 'EMPRESA' e 'TIPO DE LAUDO' nesta planilha."
        )

    col_empresa = _col(df, "EMPRESA")
    col_tipo = _col(df, "TIPO DE LAUDO")
    col_data_nomeada = _col(df, "DATA")
    col_cliente = _col_optional(df, "NOME DO CLIENTE") or _col_optional(df, "CLIENTE")
    col_status = _col_optional(df, "ENTRADA DE LAUDO") or _col_optional(df, "STATUS")

    existentes = {
        (laudo.empresa_cliente_id, normalize(laudo.tipo_laudo_nome), laudo.data, normalize(laudo.nome_cliente))
        for laudo in db.scalars(select(Laudo))
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
        # Prefere a coluna A (posição) quando ela mesma já é uma data válida
        # — a planilha real tem abas onde mais de uma coluna cai no mesmo
        # nome canônico "DATA" (a ordem das colunas varia de aba pra aba),
        # fazendo a busca por nome pegar a data de prazo/entrega em vez da
        # de entrada do laudo, só em algumas abas. A Clara confirmou: a data
        # certa é sempre a da coluna A. Cai pro nome "DATA" só quando a
        # coluna A não é uma data (abas em que a coluna A é outra coisa,
        # ex. EMPRESA) — ver DECISIONS.md e app/excel_reader.py::load_data_sheets.
        data_val = parse_date_cell(row.get("_COL_A"))
        if data_val is None:
            data_val = parse_date_cell(row.get(col_data_nomeada))
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
    _logger.info("import laudos: %.1fs total — %s", time.perf_counter() - inicio, resumo)
    return resumo


def apagar_todos_laudos(db: Session) -> int:
    """Apaga TODO o histórico de laudos — a pedido explícito da Clara, pra
    corrigir de vez os registros com data errada (bug da coluna de data no
    import, já corrigido — ver DECISIONS.md 2026-09-24): reimportar sozinho
    não corrige o que já está errado, porque a data faz parte da chave de
    duplicidade (criaria registro novo em vez de substituir o antigo).
    Irreversível — a tela que chama isso exige confirmação explícita antes.
    Só laudos; não mexe em empresas-clientes, tipos de laudo cadastrados
    nem em nenhum outro módulo."""
    total = db.scalar(select(func.count()).select_from(Laudo)) or 0
    db.execute(delete(Laudo))
    db.commit()
    return total


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


def _resolver_status(status_opcao: str) -> tuple[str, str]:
    """(status_normalizado, rótulo pra exibição) — usado tanto por
    `gerar_relatorio` quanto por `gerar_resumo_por_assessoria`, pra manter
    exatamente a mesma interpretação de status nos dois."""
    status_key = normalize(status_opcao)
    status_normalizado = STATUS_OPCAO_MAP.get(status_key, STATUS_MAP.get(status_key, status_key))
    status_label = {
        STATUS_AMBOS: "Solicitação + Corrigido",
        "SOLICITAÇÃO": "Solicitação",
        "CORREÇÃO": "Corrigido",
    }.get(status_normalizado, status_normalizado)
    return status_normalizado, status_label


def _status_bate(status_laudo: str, status_normalizado: str) -> bool:
    if status_normalizado == STATUS_AMBOS:
        return status_laudo in STATUS_VALIDOS
    return status_laudo == status_normalizado


def _resolver_empresa(db: Session, empresa_nome: str) -> EmpresaCliente | None:
    alvo = normalize(empresa_nome)
    for e in db.scalars(select(EmpresaCliente)):
        if normalize(e.nome) == alvo:
            return e
    return None


def gerar_relatorio(
    db: Session,
    empresa_nome: str,
    periodo_ini: date,
    periodo_fim: date,
    status_opcao: str,
    cnpj: str | None = None,
) -> LaudosResult:
    empresa = _resolver_empresa(db, empresa_nome)
    if empresa is None:
        raise ValueError(f"A empresa '{empresa_nome}' não foi encontrada.")

    status_normalizado, status_label = _resolver_status(status_opcao)

    query = select(Laudo).where(
        Laudo.empresa_cliente_id == empresa.id,
        Laudo.data >= periodo_ini,
        Laudo.data <= periodo_fim,
    )

    linhas: list[LinhaLaudo] = []
    tipos_sem_valor: set[str] = set()
    valor_cache: dict[str, float | None] = {}

    for laudo in db.scalars(query):
        if not _status_bate(laudo.status, status_normalizado):
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

    linhas.sort(key=lambda linha: normalize(linha.cliente))
    total = sum(linha.valor for linha in linhas)

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


@dataclass
class LinhaResumoTipo:
    tipo: str
    quantidade: int
    valor_unitario: float | None  # None = tipo sem valor cadastrado em tipos_laudo


@dataclass
class ResumoAssessoria:
    assessoria: str
    total_laudos: int
    tipos: list[LinhaResumoTipo] = field(default_factory=list)


def gerar_resumo_por_assessoria(
    db: Session,
    periodo_ini: date,
    periodo_fim: date,
    status_opcao: str,
    filtro_empresa: str | None = None,
) -> list[ResumoAssessoria]:
    """Lista-resumo em texto simples (a pedido da Clara, 2026-09-25): pra
    cada assessoria, total de laudos e a quantidade por tipo com o valor
    individual do tipo. Usa EXATAMENTE o mesmo filtro de status
    (`_status_bate`/`_resolver_status`) e valor por tipo (`_valor_tipo`) que
    `gerar_relatorio` já usa — os números batem entre os dois porque é a
    mesma regra, não uma reimplementação separada. `filtro_empresa`: se
    informado, a lista cobre só essa assessoria (mesmo filtro do relatório
    de uma empresa só); se não informado, cobre todas as assessorias com
    laudo no período/status. Um tipo sem valor cadastrado em `tipos_laudo`
    fica com `valor_unitario=None` (não é descartado nem vira R$ 0,00 —
    ver `formatar_texto_resumo_assessorias`)."""
    status_normalizado, _ = _resolver_status(status_opcao)

    empresa_id_filtro = None
    if filtro_empresa:
        empresa = _resolver_empresa(db, filtro_empresa)
        if empresa is None:
            raise ValueError(f"A empresa '{filtro_empresa}' não foi encontrada.")
        empresa_id_filtro = empresa.id

    query = (
        select(Laudo.tipo_laudo_nome, Laudo.status, EmpresaCliente.nome)
        .join(EmpresaCliente, Laudo.empresa_cliente_id == EmpresaCliente.id)
        .where(Laudo.data >= periodo_ini, Laudo.data <= periodo_fim)
    )
    if empresa_id_filtro is not None:
        query = query.where(Laudo.empresa_cliente_id == empresa_id_filtro)

    # assessoria -> tipo -> quantidade. Só entra quem realmente tem laudo
    # contado — sem isso apareceriam assessorias/tipos com zero, que a
    # Clara pediu explicitamente pra não listar.
    contagem: dict[str, dict[str, int]] = {}
    for tipo, status_laudo, empresa_nome in db.execute(query):
        if not _status_bate(status_laudo, status_normalizado):
            continue
        contagem.setdefault(empresa_nome, {}).setdefault(tipo, 0)
        contagem[empresa_nome][tipo] += 1

    valor_cache: dict[str, float | None] = {}
    resultado: list[ResumoAssessoria] = []
    for empresa_nome in sorted(contagem, key=normalize):
        tipos_contagem = contagem[empresa_nome]
        linhas_tipo = [
            LinhaResumoTipo(tipo=tipo, quantidade=qtd, valor_unitario=_valor_tipo(db, tipo, valor_cache))
            for tipo, qtd in sorted(tipos_contagem.items(), key=lambda item: normalize(item[0]))
        ]
        resultado.append(
            ResumoAssessoria(
                assessoria=empresa_nome,
                total_laudos=sum(tipos_contagem.values()),
                tipos=linhas_tipo,
            )
        )
    return resultado


def formatar_texto_resumo_assessorias(resumo: list[ResumoAssessoria]) -> str:
    from app.utils import format_brl

    blocos = []
    for r in resumo:
        linhas_txt = [f"ASSESSORIA: {r.assessoria.upper()}", f"Total de laudos: {r.total_laudos}"]
        for t in r.tipos:
            valor_str = format_brl(t.valor_unitario) if t.valor_unitario is not None else "(sem valor cadastrado)"
            linhas_txt.append(f"{t.tipo}: {t.quantidade} laudos - Valor individual: {valor_str}")
        blocos.append("\n".join(linhas_txt))
    return "\n\n".join(blocos)

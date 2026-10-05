"""Correspondências (Fase 9, ELITE, 2026-10-05, a pedido da Clara) — mesmo
padrão de Laudos: upload de planilha acumula histórico aqui, o relatório
filtra por mês + empresa já importados (sem controle de ano — ver
app/models.py::Correspondencia)."""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.excel_reader import load_data_sheets
from app.models import Correspondencia, EmpresaCliente
from app.services.empresas import get_or_create_empresa
from app.utils import cell_text, normalize

_logger = logging.getLogger("elite_sistem.import")

# Só as duas colunas-filtro ancoram a seleção de aba (ver load_data_sheets)
# — as outras 5 são checadas uma a uma depois, pra dar uma mensagem
# específica de qual coluna falta (a pedido da Clara), em vez da mensagem
# genérica de "nenhuma aba com essas colunas" que load_data_sheets dá.
REQUIRED_HEADERS = ["MÊS", "EMPRESA"]
COLUNAS_OBRIGATORIAS = ["MÊS", "EMPRESA", "ADVOGADO", "AUTOR", "ADV / PREPOSTO", "VALOR", "TIPO DE AÇÃO"]

_RE_NUMERO = re.compile(r"-?\d{1,3}(\.\d{3})*(,\d+)?$|-?\d+(,\d+)?$")


def _col(df, nome: str) -> str | None:
    for c in df.columns:
        if normalize(c) == normalize(nome):
            return c
    return None


def parse_valor(texto: str) -> float | None:
    """"R$ 180,00" / "R$160,00" (sem espaço) / "R$ 1.234,56" -> 180.0 /
    160.0 / 1234.56. `None` quando o texto não é um valor reconhecível
    (ex.: "a combinar") — nesse caso a Clara pediu pra manter o texto
    original da planilha no relatório em vez de zerar ou travar o import
    inteiro (ver `services/correspondencias.py::gerar_relatorio` e
    `LinhaCorrespondencia.valor_texto`)."""
    limpo = (texto or "").strip()
    if not limpo:
        return None
    sem_prefixo = re.sub(r"(?i)^r\$\s*", "", limpo).strip()
    # Ponto final sobrando (típico de digitação, ex.: "R$ 280,00.") não
    # muda o valor pretendido — visto na planilha real da Clara.
    sem_prefixo = sem_prefixo.removesuffix(".")
    if not _RE_NUMERO.match(sem_prefixo):
        return None
    try:
        return float(sem_prefixo.replace(".", "").replace(",", "."))
    except ValueError:
        return None


@dataclass
class ImportResumo:
    linhas_lidas: int = 0
    linhas_novas: int = 0
    linhas_ja_existentes: int = 0


def importar_planilha(db: Session, path: str) -> ImportResumo:
    inicio = time.perf_counter()
    df = load_data_sheets(path, REQUIRED_HEADERS)
    if df.empty:
        raise ValueError("Não encontrei nenhuma aba com as colunas 'MÊS' e 'EMPRESA' nesta planilha.")

    colunas: dict[str, str] = {}
    faltando = []
    for nome in COLUNAS_OBRIGATORIAS:
        coluna = _col(df, nome)
        if coluna is None:
            faltando.append(nome)
        else:
            colunas[nome] = coluna
    if faltando:
        raise ValueError(
            "A planilha está sem a(s) coluna(s) obrigatória(s): " + ", ".join(f'"{c}"' for c in faltando) + "."
        )

    existentes = {
        (
            c.empresa_cliente_id, normalize(c.mes), normalize(c.advogado), normalize(c.autor),
            normalize(c.adv_preposto), normalize(c.valor_texto), normalize(c.tipo_acao),
        )
        for c in db.scalars(select(Correspondencia))
    }
    # Mesmo motivo do cache em laudos.py/processos.py — sem isso,
    # get_or_create_empresa varre a tabela inteira a cada linha.
    empresa_cache: dict = {}

    resumo = ImportResumo()
    for _, row in df.iterrows():
        resumo.linhas_lidas += 1
        mes = cell_text(row.get(colunas["MÊS"])).strip().upper()
        empresa_nome = cell_text(row.get(colunas["EMPRESA"]))
        if not mes or not empresa_nome:
            continue

        advogado = cell_text(row.get(colunas["ADVOGADO"]))
        autor = cell_text(row.get(colunas["AUTOR"]))
        adv_preposto = cell_text(row.get(colunas["ADV / PREPOSTO"]))
        valor_texto = cell_text(row.get(colunas["VALOR"]))
        tipo_acao = cell_text(row.get(colunas["TIPO DE AÇÃO"]))

        valor = parse_valor(valor_texto)
        empresa = get_or_create_empresa(db, empresa_nome, cache=empresa_cache)

        chave = (
            empresa.id, normalize(mes), normalize(advogado), normalize(autor),
            normalize(adv_preposto), normalize(valor_texto), normalize(tipo_acao),
        )
        if chave in existentes:
            resumo.linhas_ja_existentes += 1
            continue

        db.add(
            Correspondencia(
                empresa_cliente_id=empresa.id, mes=mes, advogado=advogado, autor=autor,
                adv_preposto=adv_preposto, valor_texto=valor_texto, valor=valor, tipo_acao=tipo_acao,
            )
        )
        existentes.add(chave)
        resumo.linhas_novas += 1

    db.commit()
    _logger.info("import correspondencias: %.1fs total — %s", time.perf_counter() - inicio, resumo)
    return resumo


def apagar_todas_correspondencias(db: Session) -> int:
    """Apaga TODO o histórico de correspondências — mesmo padrão de
    `laudos.py::apagar_todos_laudos` (zona de perigo, confirmação
    obrigatória na tela antes desse POST)."""
    total = db.scalar(select(func.count()).select_from(Correspondencia)) or 0
    db.execute(delete(Correspondencia))
    db.commit()
    return total


@dataclass
class LinhaCorrespondencia:
    advogado: str
    autor: str
    adv_preposto: str
    valor_texto: str
    valor: float | None  # None = célula não reconhecida como número; valor_texto tem o texto original
    tipo_acao: str


@dataclass
class CorrespondenciasResult:
    empresa: str
    mes: str
    linhas: list[LinhaCorrespondencia] = field(default_factory=list)
    total: float = 0.0


def _resolver_empresa(db: Session, empresa_nome: str) -> EmpresaCliente | None:
    alvo = normalize(empresa_nome)
    for e in db.scalars(select(EmpresaCliente)):
        if normalize(e.nome) == alvo:
            return e
    return None


def gerar_relatorio(db: Session, empresa_nome: str, mes: str) -> CorrespondenciasResult:
    empresa = _resolver_empresa(db, empresa_nome)
    if empresa is None:
        raise ValueError(f"A empresa '{empresa_nome}' não foi encontrada.")

    mes_normalizado = mes.strip().upper()
    query = select(Correspondencia).where(
        Correspondencia.empresa_cliente_id == empresa.id,
        Correspondencia.mes == mes_normalizado,
    )

    linhas = [
        LinhaCorrespondencia(
            advogado=c.advogado, autor=c.autor, adv_preposto=c.adv_preposto,
            valor_texto=c.valor_texto, valor=c.valor, tipo_acao=c.tipo_acao,
        )
        for c in db.scalars(query)
    ]
    linhas.sort(key=lambda l: normalize(l.autor))
    total = sum(l.valor for l in linhas if l.valor is not None)

    return CorrespondenciasResult(empresa=empresa.nome, mes=mes_normalizado, linhas=linhas, total=total)

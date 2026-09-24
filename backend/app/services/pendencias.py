"""Fluxo de PENDÊNCIAS — portado de core/pendencias.py (leitor-relatorio).

Regras já auditadas em ARCHITECTURE.md seção 1.4: pendente = campo PAGO com
qualquer status diferente de SIM (vazio não conta) — inclui "NÃO"
explicitamente como pendência, a pedido da Clara (2026-09-24; antes disso
"NÃO" era tratado como resolvido, igual "SIM", o que estava errado — ver
DECISIONS.md). Dedup por (data+empresa+tipo+valor) com SIM sempre vencendo;
classificação automática do cobrador (tipo contendo "AUDIÊNCIA" -> EXIMIA,
resto -> ELITE).
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.excel_reader import load_data_sheets
from app.models import Cobranca, EmpresaCliente
from app.services.empresas import get_or_create_empresa
from app.utils import cell_text, format_brl, normalize, parse_date_cell

_logger = logging.getLogger("elite_sistem.import")

REQUIRED_HEADERS = ["EMPRESA", "TIPO DE COBRANÇA", "VALOR"]
CHAVE_DUPLICIDADE = ["DATA", "EMPRESA", "TIPO DE COBRANÇA", "VALOR"]
STATUS_PAGO_OK = {normalize("SIM")}
_PRIORIDADE_PAGO = {"SIM": 0}

PIX_EXIMIA = "✅ PIX: CNPJ: 655965130001-52 \nEXIMIA CAMARA DE CONCILIACAO MEDIACAO & ARBITRAGEM LTDA"
PIX_ELITE = "✅ PIX: CNPJ 51.673.385/0001-99\nELITE MEDIAÇÕES LTDA"

_RE_INTERVALO_DATAS = re.compile(r"(\d{1,2}/\d{1,2}(?:/\d{2,4})?)\s*-\s*(\d{1,2}/\d{1,2}(?:/\d{2,4})?)")


def _e_pendente(pago_valor) -> bool:
    if pago_valor is None or (isinstance(pago_valor, float) and pd.isna(pago_valor)):
        return False
    texto = normalize(pago_valor)
    if not texto:
        return False
    return texto not in STATUS_PAGO_OK


def _parse_valor(valor) -> float | None:
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        if isinstance(valor, float) and pd.isna(valor):
            return None
        return float(valor)
    texto = str(valor).strip()
    if not texto:
        return None
    texto = texto.replace("R$", "").replace("r$", "").strip()
    texto = texto.replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return None


def _classificar_cobrador(tipo_cobranca: str) -> str:
    return "EXIMIA" if "AUDIENCIA" in normalize(tipo_cobranca) else "ELITE"


def _formatar_descricao(tipo_cobranca: str) -> str:
    texto = " ".join(str(tipo_cobranca).split())
    return _RE_INTERVALO_DATAS.sub(r"\1 à \2", texto)


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


def _resolver_lancamentos_duplicados(df: pd.DataFrame) -> pd.DataFrame:
    col_pago = _col_optional(df, "PAGO")
    if col_pago is None:
        return df
    colunas_chave = [_col_optional(df, c) for c in CHAVE_DUPLICIDADE]
    colunas_chave = [c for c in colunas_chave if c is not None]
    if not colunas_chave:
        return df

    def _prioridade(v) -> int:
        if v is None or (isinstance(v, float) and pd.isna(v)) or not str(v).strip():
            return 2
        return _PRIORIDADE_PAGO.get(normalize(v), 1)

    prioridade = df[col_pago].apply(_prioridade)
    df = df.assign(_prioridade_pago=prioridade)
    df = df.sort_values("_prioridade_pago", kind="stable")
    df = df.drop_duplicates(subset=colunas_chave, keep="first")
    return df.drop(columns="_prioridade_pago").reset_index(drop=True)


@dataclass
class ImportResumo:
    linhas_lidas: int = 0
    linhas_novas: int = 0
    linhas_ja_existentes: int = 0


def importar_planilha(db: Session, path: str) -> ImportResumo:
    inicio = time.perf_counter()
    df = load_data_sheets(path, REQUIRED_HEADERS)
    if df.empty:
        raise ValueError(
            "Não encontrei nenhuma aba com as colunas 'EMPRESA', 'TIPO DE COBRANÇA' e 'VALOR' "
            "(ou 'VALOR FALTANTE') nesta planilha."
        )
    df = _resolver_lancamentos_duplicados(df)

    col_empresa = _col(df, "EMPRESA")
    col_tipo = _col(df, "TIPO DE COBRANÇA")
    col_valor = _col(df, "VALOR")
    col_pago = _col_optional(df, "PAGO")
    col_data = _col_optional(df, "DATA")

    existentes = {
        (c.empresa_cliente_id, c.data, normalize(c.tipo_cobranca), c.valor)
        for c in db.scalars(select(Cobranca))
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
        tipo = cell_text(row.get(col_tipo))
        valor = _parse_valor(row.get(col_valor))
        if not tipo or valor is None:
            continue
        data_val = parse_date_cell(row.get(col_data)) if col_data else None
        if data_val is None:
            continue  # sem data não dá para gravar (coluna DATA obrigatória no schema)
        status_pago = (cell_text(row.get(col_pago)) or None) if col_pago else None

        empresa = get_or_create_empresa(db, empresa_nome, cache=empresa_cache)
        chave = (empresa.id, data_val, normalize(tipo), valor)
        if chave in existentes:
            resumo.linhas_ja_existentes += 1
            continue

        db.add(
            Cobranca(
                empresa_cliente_id=empresa.id,
                data=data_val,
                tipo_cobranca=tipo,
                cobrador=_classificar_cobrador(tipo),
                valor=valor,
                status_pagamento=status_pago,
            )
        )
        existentes.add(chave)
        resumo.linhas_novas += 1

    db.commit()
    _logger.info("import pendencias: %.1fs total — %s", time.perf_counter() - inicio, resumo)
    return resumo


@dataclass
class ItemPendencia:
    descricao: str
    valor: float


@dataclass
class MensagemPendencia:
    empresa: str
    cobrador: str
    itens: list[ItemPendencia] = field(default_factory=list)
    total: float = 0.0


def gerar_mensagens(db: Session, empresa_nome: str) -> list[MensagemPendencia]:
    alvo_empresa = normalize(empresa_nome)
    empresa = None
    for e in db.scalars(select(EmpresaCliente)):
        if normalize(e.nome) == alvo_empresa:
            empresa = e
            break
    if empresa is None:
        raise ValueError(f"A empresa '{empresa_nome}' não foi encontrada.")

    por_cobrador: dict[str, MensagemPendencia] = {}
    for cobranca in db.scalars(select(Cobranca).where(Cobranca.empresa_cliente_id == empresa.id)):
        if not _e_pendente(cobranca.status_pagamento):
            continue
        if cobranca.valor is None or cobranca.valor <= 0:
            continue
        msg = por_cobrador.setdefault(
            cobranca.cobrador, MensagemPendencia(empresa=empresa.nome, cobrador=cobranca.cobrador)
        )
        msg.itens.append(ItemPendencia(descricao=_formatar_descricao(cobranca.tipo_cobranca), valor=cobranca.valor))
        msg.total += cobranca.valor

    return [por_cobrador[c] for c in ("EXIMIA", "ELITE") if c in por_cobrador]


def formatar_texto(msg: MensagemPendencia) -> str:
    linhas = [
        "Bom dia, tudo bem?!",
        "Notamos que possuem alguns pagamentos pendentes!",
        "Segue mais informações e forma de pagamento:",
        "",
        "Pendências:",
    ]
    for item in msg.itens:
        linhas.append(f"- {item.descricao} - {format_brl(item.valor)}")
    linhas.append("")
    linhas.append(f"Total Pendente: {format_brl(msg.total)}")
    linhas.append("")
    linhas.append(PIX_EXIMIA if msg.cobrador == "EXIMIA" else PIX_ELITE)
    return "\n".join(linhas)

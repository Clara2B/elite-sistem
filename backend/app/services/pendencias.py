"""Fluxo de PENDÊNCIAS — reestruturado em 2026-11-24 a pedido da Clara
("já está errado desde o começo, vamos reestruturar").

Raiz do problema anterior: o import genérico (`load_data_sheets`, que varre
TODAS as abas da planilha e usa a primeira que bater com os cabeçalhos
exigidos) sempre acabava lendo a aba "2025 - RECEBIMENTOS EMPRESAS" — que
tem literalmente as colunas "EMPRESA"/"VALOR"/"PAGO (SIM/NÃO)" — porque a
aba atual, "2026 - RECEBIMENTOS EMPRESAS", usa nomes diferentes ("CLIENTE",
"VALOR FALTANTE") que nunca batiam com os cabeçalhos exigidos. Ou seja: o
gerador de mensagens de cobrança vinha puxando dados do ANO PASSADO, sem
nenhum erro aparecer (a aba de 2025 "servia" pro import, só com os dados
errados) — ver DECISIONS.md.

Agora o import abre SÓ a aba "<ano atual> - RECEBIMENTOS EMPRESAS" (nunca
outra aba da mesma planilha) e lê pelas colunas reais dela: "CLIENTE"
(nome da empresa), "VALOR FALTANTE" (valor a cobrar) e "PAGO".

Pendente = campo PAGO em {"VERIFICAR", "ACORDO", "PENDENTE", "EM ATRASO"}
— lista exata confirmada com a Clara em 2026-11-24. "SIM" é pago (não
cobra) e "NÃO" foi explicitamente excluído da lista por ela nessa mesma
data (revoga a regra anterior, de 2026-09-24, que tratava "NÃO" como
pendência também — ver DECISIONS.md).

Dedup por (data+empresa+tipo+valor) com SIM sempre vencendo;
classificação automática do cobrador (tipo contendo "AUDIÊNCIA" -> EXIMIA,
resto -> ELITE).
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import date

import openpyxl
import pandas as pd
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import Cobranca
from app.services.empresas import get_or_create_empresa, resolver_empresa_por_nome
from app.utils import (
    cell_text,
    format_brl,
    normalize,
    parse_date_cell,
    parse_valor_monetario,
)

_logger = logging.getLogger("elite_sistem.import")

NOME_ABA_SUFIXO = "RECEBIMENTOS EMPRESAS"
COLUNAS_OBRIGATORIAS = ["DATA", "CLIENTE", "TIPO DE COBRANÇA", "VALOR FALTANTE"]
CHAVE_DUPLICIDADE = ["DATA", "CLIENTE", "TIPO DE COBRANÇA", "VALOR FALTANTE"]
STATUS_PENDENTE = {normalize(s) for s in ("VERIFICAR", "ACORDO", "PENDENTE", "EM ATRASO")}
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
    return texto in STATUS_PENDENTE


def _parse_valor(valor) -> float | None:
    """Número já vindo como int/float da planilha (célula numérica de
    verdade) é usado direto; texto passa por `parse_valor_monetario`
    (compartilhada com `services/correspondencias.py` desde 2026-11-24 —
    bug real corrigido: um valor de texto simples com ponto decimal, ex.
    "280.50", era interpretado como formato brasileiro cegamente (ponto =
    separador de milhar), virando 28050.0 — 100x maior, sem nenhum
    aviso)."""
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        if isinstance(valor, float) and pd.isna(valor):
            return None
        return float(valor)
    return parse_valor_monetario(valor)


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


def _nome_aba_esperado(ano: int) -> str:
    return f"{ano} - {NOME_ABA_SUFIXO}"


def _ler_aba_recebimentos(path: str) -> pd.DataFrame:
    """Lê SÓ a aba "<ano atual> - RECEBIMENTOS EMPRESAS" — nunca outra aba
    da mesma planilha (ex.: "PAGAMENTOS", "CNPJs" ou a aba de um ano
    anterior), a pedido explícito da Clara (2026-11-24). `read_only=True`
    pelo mesmo motivo de `excel_reader.load_data_sheets`: não carregar a
    planilha inteira (que tem ~10 abas) na memória."""
    nome_esperado = _nome_aba_esperado(date.today().year)
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    try:
        nome_aba = next((s for s in wb.sheetnames if normalize(s) == normalize(nome_esperado)), None)
        if nome_aba is None:
            raise ValueError(
                f'Não encontrei a aba "{nome_esperado}" nesta planilha. '
                f"Abas disponíveis: {', '.join(wb.sheetnames)}."
            )
        linhas = list(wb[nome_aba].iter_rows(values_only=True))
    finally:
        wb.close()

    linhas = [l for l in linhas if any(v is not None for v in l)]
    if not linhas:
        return pd.DataFrame()
    header = linhas[0]
    largura = len(header)
    dados = [l + (None,) * (largura - len(l)) if len(l) < largura else l[:largura] for l in linhas[1:]]
    cols = [cell_text(c) or f"col_{i}" for i, c in enumerate(header)]
    df = pd.DataFrame(dados, columns=cols)
    return df.dropna(how="all")


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
    linhas_atualizadas: int = 0


def importar_planilha(db: Session, path: str) -> ImportResumo:
    inicio = time.perf_counter()
    df = _ler_aba_recebimentos(path)
    if df.empty:
        raise ValueError(f'A aba "{_nome_aba_esperado(date.today().year)}" está vazia nesta planilha.')

    faltando = [nome for nome in COLUNAS_OBRIGATORIAS if _col_optional(df, nome) is None]
    if faltando:
        raise ValueError(
            f'A aba "{_nome_aba_esperado(date.today().year)}" está sem a(s) coluna(s) obrigatória(s): '
            + ", ".join(f'"{c}"' for c in faltando) + "."
        )

    df = _resolver_lancamentos_duplicados(df)

    col_empresa = _col(df, "CLIENTE")
    col_tipo = _col(df, "TIPO DE COBRANÇA")
    col_valor = _col(df, "VALOR FALTANTE")
    col_pago = _col_optional(df, "PAGO")
    col_data = _col_optional(df, "DATA")

    # Identidade da cobrança contra o que já está no banco — sem PAGO de
    # propósito. Bug real corrigido em 2026-11-24 (mesma classe do bug já
    # corrigido em Laudos): PAGO fazia parte da chave original de
    # duplicidade contra o banco, então reimportar a planilha depois do
    # cliente pagar (PAGO corrigido de "NÃO"/vazio pra "SIM") não era
    # reconhecido como "a mesma cobrança, só que paga agora" — criava um
    # registro NOVO, deixando o antigo (ainda pendente) intacto, e o
    # sistema continuava cobrando o cliente pra sempre por uma dívida já
    # quitada. Agora a reimportação ATUALIZA o status de pagamento do
    # registro existente em vez de duplicar.
    existentes: dict[tuple, Cobranca] = {
        (c.empresa_cliente_id, c.data, normalize(c.tipo_cobranca), c.valor): c
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
        cobranca_existente = existentes.get(chave)
        if cobranca_existente is not None:
            if normalize(cobranca_existente.status_pagamento) != normalize(status_pago):
                cobranca_existente.status_pagamento = status_pago
                resumo.linhas_atualizadas += 1
            else:
                resumo.linhas_ja_existentes += 1
            continue

        nova = Cobranca(
            empresa_cliente_id=empresa.id,
            data=data_val,
            tipo_cobranca=tipo,
            cobrador=_classificar_cobrador(tipo),
            valor=valor,
            status_pagamento=status_pago,
        )
        db.add(nova)
        existentes[chave] = nova
        resumo.linhas_novas += 1

    db.commit()
    _logger.info("import pendencias: %.1fs total — %s", time.perf_counter() - inicio, resumo)
    return resumo


def apagar_todas_pendencias(db: Session) -> int:
    """Apaga TODO o histórico de cobranças (EXÍMIA e ELITE juntas, mesma
    tabela) — mesma "zona de perigo" já disponibilizada em Laudos (ver
    DECISIONS.md 2026-09-24), estendida aqui a pedido da Clara. Irreversível
    — a tela que chama isso exige confirmação explícita antes. Só
    cobranças; não mexe em empresas-clientes nem em nenhum outro módulo."""
    total = db.scalar(select(func.count()).select_from(Cobranca)) or 0
    db.execute(delete(Cobranca))
    db.commit()
    return total


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


def ids_empresas_com_pendencia(db: Session) -> set[int]:
    """IDs de empresa-cliente com pelo menos uma cobrança pendente agora
    — mesma regra de `gerar_mensagens` (status em STATUS_PENDENTE e valor >
    0). Usado pra filtrar o menu de empresas da tela (a pedido da Clara,
    2026-11-24: só mostrar quem tem resultado — ex.: "Juros Justos" não
    aparece se nunca tiver uma cobrança pendente)."""
    ids: set[int] = set()
    for empresa_id, status, valor in db.execute(
        select(Cobranca.empresa_cliente_id, Cobranca.status_pagamento, Cobranca.valor)
    ):
        if _e_pendente(status) and valor is not None and valor > 0:
            ids.add(empresa_id)
    return ids


def gerar_mensagens(db: Session, empresa_nome: str) -> list[MensagemPendencia]:
    empresa = resolver_empresa_por_nome(db, empresa_nome)
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

"""Funções auxiliares de normalização de texto e datas.

Portado de core/utils.py do sistema atual (leitor-relatorio) sem mudança de
comportamento — mesmas regras já validadas em produção.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime

import pandas as pd

_RE_NUMERO_MONETARIO = re.compile(r"-?\d{1,3}(\.\d{3})*(,\d+)?$|-?\d+(,\d+)?$")


def normalize(text) -> str:
    """Remove acentos, espaços extras e diferenças de maiúsculas/minúsculas."""
    if text is None:
        return ""
    text = str(text).strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = " ".join(text.split())
    return text.upper()


def parse_date_cell(value) -> date | None:
    """Converte um valor de célula (datetime, string dd/mm/aaaa, etc.) em date.

    Nota: `pd.isna(value)` (não só `value is None`) é necessário porque
    `pd.NaT` (célula de data vazia) passa em `isinstance(value, datetime)` —
    sem essa checagem primeiro, `.date()` devolveria o próprio `NaT` em vez
    de `None`, e esse valor acabaria sendo gravado no banco mais adiante.
    """
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass  # value não é "isna-ável" (ex.: alguns tipos exóticos) — segue o fluxo normal
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, pd.Timestamp):
        return value.date()
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()  # noqa: DTZ007 — só a data importa, sem timezone
        except ValueError:
            continue
    try:
        parsed = pd.to_datetime(text, dayfirst=True, errors="raise")
        return parsed.date()
    except Exception:  # noqa: BLE001 — fallback genérico: formato não reconhecido = sem data
        return None


def cell_text(value) -> str:
    """Converte uma célula em texto, tratando None/NaN como string vazia.

    Sem isso, uma célula vazia lida pelo pandas (`float('nan')`) vira o
    texto literal `"nan"` ao passar por `str(value)` — bug real encontrado
    na validação de paridade da Fase 3 (coluna PAGO vazia sendo tratada
    como um status "NAN", entrando como pendência por engano; ver
    DECISIONS.md). Use `cell_text(v) or None` onde o campo deve ficar
    `None` (não string vazia) quando a célula estiver em branco.
    """
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def format_brl(value: float) -> str:
    """Formata um número como moeda brasileira: R$ 1.234,56"""
    text = f"{value:,.2f}"
    text = text.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {text}"


def parse_valor_monetario(texto) -> float | None:
    """Converte um valor monetário em texto pra `float`. Aceita o formato
    brasileiro ("R$ 1.234,56" — ponto de milhar, vírgula decimal) E texto
    simples sem "R$" com ponto decimal (ex.: "280.50", "280.5") ou inteiro
    (ex.: "280"). `None` quando o texto não é um valor reconhecível (ex.:
    "a combinar").

    Compartilhada por `services/correspondencias.py` e
    `services/pendencias.py` — extraída em 2026-11-24 depois do mesmo
    bug (ponto decimal de texto simples interpretado como separador de
    milhar) ter sido corrigido primeiro só em Correspondências e só
    depois notado, separadamente, em Pendências — lá o efeito era pior
    (não só "fica de fora do Total" como em Correspondências, e sim um
    valor ERRADO: "280.50" virava 28050.0, 100x maior, sem nenhum aviso).
    Uma função só, usada pelos dois módulos, evita o mesmo bug reaparecer
    de novo num terceiro lugar."""
    if texto is None:
        return None
    limpo = str(texto).strip()
    if not limpo:
        return None
    sem_prefixo = re.sub(r"(?i)^r\$\s*", "", limpo).strip()
    # Ponto final sobrando (típico de digitação, ex.: "R$ 280,00.") não
    # muda o valor pretendido — visto na planilha real da Clara.
    sem_prefixo = sem_prefixo.removesuffix(".")
    if not sem_prefixo:
        return None
    if _RE_NUMERO_MONETARIO.match(sem_prefixo):
        try:
            return float(sem_prefixo.replace(".", "").replace(",", "."))
        except ValueError:
            return None
    try:
        return float(sem_prefixo)
    except ValueError:
        return None


def _nome_arquivo(extensao: str, partes: tuple[str, ...]) -> str:
    limpas = []
    for parte in partes:
        texto = normalize(parte).replace(" ", "_")
        texto = "".join(c for c in texto if c.isalnum() or c in "_-")
        if texto:
            limpas.append(texto)
    return "_".join(limpas) + extensao


def nome_arquivo_pdf(*partes: str) -> str:
    """Monta um nome de arquivo seguro para o cabeçalho `Content-Disposition`
    (Fase 6) a partir de textos livres (ex.: nome de empresa-cliente) — troca
    espaços por "_" e remove caracteres que poderiam quebrar o cabeçalho ou
    virar um nome de arquivo estranho."""
    return _nome_arquivo(".pdf", partes)


def nome_arquivo_xlsx(*partes: str) -> str:
    """Mesma lógica de `nome_arquivo_pdf` (2026-10-05, versão em Excel dos
    relatórios) — ver app/excel_export.py."""
    return _nome_arquivo(".xlsx", partes)


@dataclass
class Pagina:
    itens: list
    pagina_atual: int
    total_paginas: int
    total_itens: int


def paginar(itens: list, pagina: int, por_pagina: int = 30) -> Pagina:
    """Pagina uma lista já carregada em memória — a pedido da Clara
    (2026-11-27), pras listagens administrativas (Empresas/Bancos/
    Funcionários), que nunca passam de algumas centenas de linhas: buscar
    tudo do banco e paginar aqui em Python é mais simples do que replicar
    LIMIT/OFFSET em cada serviço, sem custo real de performance nesse
    tamanho de tabela. `pagina` fora do intervalo (negativa, zero, ou maior
    que o total de páginas) é ajustada pro limite mais próximo em vez de
    devolver uma página vazia ou dar erro."""
    total_itens = len(itens)
    total_paginas = max(1, -(-total_itens // por_pagina))
    pagina_atual = max(1, min(pagina, total_paginas))
    inicio = (pagina_atual - 1) * por_pagina
    return Pagina(
        itens=itens[inicio:inicio + por_pagina], pagina_atual=pagina_atual,
        total_paginas=total_paginas, total_itens=total_itens,
    )

"""Cadastro de bancos (Fase 1 — Solicitação de Audiência, 2026-10-16) —
alimenta o seletor "Banco" da tela de Nova Solicitação de Audiência e
resolve nome/CNPJ/e-mail pra Carta Convite Banco sem digitar de novo. Mesmo
padrão de app/services/funcionarios.py, com CNPJ validado (reaproveita
`cnpj_valido`/`formatar_cnpj` de app/services/cartas.py — mesmo validador já
usado em Empresas-Clientes e na própria Carta Banco, sem duplicar a
checagem de dígito verificador)."""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.excel_reader import load_data_sheets
from app.models import Banco
from app.services import google_sheets
from app.services.cartas import cnpj_valido, formatar_cnpj
from app.utils import cell_text, normalize

REQUIRED_HEADERS = ["BANCO"]

# Aba e colunas da planilha de controle real da Clara (ver DECISIONS.md) —
# a aba se chama "E-MAIL BANCO", mas a coluna do nome do banco é "BANCOS"
# (no plural).
ABA_GOOGLE_SHEETS = "E-MAIL BANCO"


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


def listar_bancos(db: Session, apenas_ativos: bool = True) -> list[Banco]:
    query = select(Banco).order_by(Banco.nome)
    if apenas_ativos:
        query = query.where(Banco.ativo.is_(True))
    return list(db.scalars(query))


def criar_banco(db: Session, nome: str, cnpj: str, email: str, cnpj_alternativo: str = "") -> Banco:
    nome = nome.strip()
    cnpj = cnpj.strip()
    cnpj_alternativo = cnpj_alternativo.strip()
    email = email.strip()
    alvo = normalize(nome)
    for _, existente_nome in db.execute(select(Banco.id, Banco.nome)):
        if normalize(existente_nome) == alvo:
            raise ValueError(f"Já existe um banco chamado '{existente_nome}'.")
    if not cnpj_valido(cnpj):
        raise ValueError(f"CNPJ '{cnpj}' inválido.")
    if cnpj_alternativo and not cnpj_valido(cnpj_alternativo):
        raise ValueError(f"2° opção de CNPJ '{cnpj_alternativo}' inválida.")
    banco = Banco(
        nome=nome, cnpj=formatar_cnpj(cnpj),
        cnpj_alternativo=formatar_cnpj(cnpj_alternativo) if cnpj_alternativo else None,
        email=email,
    )
    db.add(banco)
    db.commit()
    return banco


def atualizar_banco(db: Session, banco_id: int, nome: str, cnpj: str, email: str, cnpj_alternativo: str = "") -> Banco:
    banco = db.get(Banco, banco_id)
    if banco is None:
        raise ValueError(f"Banco {banco_id} não encontrado.")
    nome = nome.strip()
    cnpj = cnpj.strip()
    cnpj_alternativo = cnpj_alternativo.strip()
    email = email.strip()
    alvo = normalize(nome)
    for existente_id, existente_nome in db.execute(select(Banco.id, Banco.nome)):
        if existente_id != banco_id and normalize(existente_nome) == alvo:
            raise ValueError(f"Já existe um banco chamado '{existente_nome}'.")
    if not cnpj_valido(cnpj):
        raise ValueError(f"CNPJ '{cnpj}' inválido.")
    if cnpj_alternativo and not cnpj_valido(cnpj_alternativo):
        raise ValueError(f"2° opção de CNPJ '{cnpj_alternativo}' inválida.")
    banco.nome = nome
    banco.cnpj = formatar_cnpj(cnpj)
    banco.cnpj_alternativo = formatar_cnpj(cnpj_alternativo) if cnpj_alternativo else None
    banco.email = email
    db.commit()
    return banco


def alterar_ativo_banco(db: Session, banco_id: int, ativo: bool) -> Banco:
    banco = db.get(Banco, banco_id)
    if banco is None:
        raise ValueError(f"Banco {banco_id} não encontrado.")
    banco.ativo = ativo
    db.commit()
    return banco


def excluir_banco(db: Session, banco_id: int) -> None:
    """Exclusão definitiva — sem checagem de vínculo porque, nesta fase, nada
    referencia `Banco` por chave estrangeira ainda (a Solicitação de
    Audiência, que vai referenciar, entra numa etapa posterior)."""
    banco = db.get(Banco, banco_id)
    if banco is None:
        raise ValueError(f"Banco {banco_id} não encontrado.")
    db.delete(banco)
    db.commit()


@dataclass
class ImportResumoBancos:
    linhas_lidas: int = 0
    criados: int = 0
    atualizados: int = 0
    rejeitados: list[str] = field(default_factory=list)


def _eh_valor_real(texto: str) -> bool:
    """False pra fórmula do Google Sheets não resolvida (ex.: a "sugestão
    de IA" da célula, tipo `=AI("Preencha com...")`) — a planilha real de
    bancos tem isso em quase toda linha da coluna "2° OPÇÃO CNPJ" (nunca
    aceita pela Clara), não é dado de verdade."""
    return bool(texto) and not texto.startswith("=")


def _upsert_banco_de_linha(
    db: Session,
    existentes: dict[str, Banco],
    resumo: ImportResumoBancos,
    nome: str,
    cnpj: str,
    cnpj_alternativo: str,
    email: str,
) -> None:
    """Upsert por nome normalizado (sem acento/caixa): banco já cadastrado
    tem CNPJ/e-mail atualizados; nome novo cria um banco novo. Nunca apaga
    um banco que não apareça na planilha (reimport parcial não perde
    cadastro já feito na tela). Compartilhado pelos dois caminhos de
    importação (upload de .xlsx e leitura direta do Google Sheets)."""
    if not nome:
        return
    if cnpj and not cnpj_valido(cnpj):
        resumo.rejeitados.append(f"{nome}: CNPJ '{cnpj}' inválido.")
        return
    if cnpj_alternativo and not cnpj_valido(cnpj_alternativo):
        resumo.rejeitados.append(f"{nome}: 2° opção de CNPJ '{cnpj_alternativo}' inválida.")
        return
    cnpj_formatado = formatar_cnpj(cnpj) if cnpj else ""
    cnpj_alt_formatado = formatar_cnpj(cnpj_alternativo) if cnpj_alternativo else None

    alvo = normalize(nome)
    existente = existentes.get(alvo)
    if existente:
        if cnpj_formatado:
            existente.cnpj = cnpj_formatado
        if cnpj_alt_formatado:
            existente.cnpj_alternativo = cnpj_alt_formatado
        if email:
            existente.email = email
        resumo.atualizados += 1
    else:
        novo = Banco(nome=nome, cnpj=cnpj_formatado, cnpj_alternativo=cnpj_alt_formatado, email=email)
        db.add(novo)
        existentes[alvo] = novo
        resumo.criados += 1


def importar_planilha_bancos(db: Session, path: str) -> ImportResumoBancos:
    df = load_data_sheets(path, REQUIRED_HEADERS)
    if df.empty:
        raise ValueError("Não encontrei nenhuma aba com a coluna 'BANCO' nesta planilha.")

    col_nome = _col(df, "BANCO")
    col_cnpj = _col_optional(df, "CNPJ")
    col_email = _col_optional(df, "EMAIL")

    existentes = {normalize(nome): banco for nome, banco in ((b.nome, b) for b in db.scalars(select(Banco)))}

    resumo = ImportResumoBancos()
    for _, row in df.iterrows():
        resumo.linhas_lidas += 1
        nome = cell_text(row.get(col_nome))
        cnpj = cell_text(row.get(col_cnpj)) if col_cnpj else ""
        email = cell_text(row.get(col_email)) if col_email else ""
        _upsert_banco_de_linha(db, existentes, resumo, nome, cnpj, "", email)

    db.commit()
    return resumo


def _valor_coluna(linha: dict[str, str], nome_coluna: str) -> str:
    alvo = normalize(nome_coluna)
    for chave, valor in linha.items():
        if normalize(chave) == alvo:
            return valor.strip() if _eh_valor_real(valor.strip()) else ""
    return ""


def importar_do_google_sheets(db: Session, spreadsheet_id: str) -> ImportResumoBancos:
    """Mesmo upsert de `importar_planilha_bancos`, mas lendo direto da aba
    "E-MAIL BANCO" da planilha de controle (2026-10-16, a pedido da Clara —
    sem precisar exportar/subir arquivo). Colunas reais: BANCOS, E-MAIL,
    CNPJ, 2° OPÇÃO CNPJ (a última quase sempre com uma fórmula de sugestão
    de IA nunca aceita, não dado de verdade — ver `_eh_valor_real`)."""
    linhas = google_sheets.ler_aba(spreadsheet_id, ABA_GOOGLE_SHEETS)
    existentes = {normalize(nome): banco for nome, banco in ((b.nome, b) for b in db.scalars(select(Banco)))}

    resumo = ImportResumoBancos()
    for linha in linhas:
        resumo.linhas_lidas += 1
        nome = _valor_coluna(linha, "BANCOS")
        cnpj = _valor_coluna(linha, "CNPJ")
        cnpj_alternativo = _valor_coluna(linha, "2° OPÇÃO CNPJ")
        email = _valor_coluna(linha, "E-MAIL")
        _upsert_banco_de_linha(db, existentes, resumo, nome, cnpj, cnpj_alternativo, email)

    db.commit()
    return resumo

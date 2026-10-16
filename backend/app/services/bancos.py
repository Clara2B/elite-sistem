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
from app.services.cartas import cnpj_valido, formatar_cnpj
from app.utils import cell_text, normalize

REQUIRED_HEADERS = ["BANCO"]


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


def criar_banco(db: Session, nome: str, cnpj: str, email: str) -> Banco:
    nome = nome.strip()
    cnpj = cnpj.strip()
    email = email.strip()
    alvo = normalize(nome)
    for _, existente_nome in db.execute(select(Banco.id, Banco.nome)):
        if normalize(existente_nome) == alvo:
            raise ValueError(f"Já existe um banco chamado '{existente_nome}'.")
    if not cnpj_valido(cnpj):
        raise ValueError(f"CNPJ '{cnpj}' inválido.")
    banco = Banco(nome=nome, cnpj=formatar_cnpj(cnpj), email=email)
    db.add(banco)
    db.commit()
    return banco


def atualizar_banco(db: Session, banco_id: int, nome: str, cnpj: str, email: str) -> Banco:
    banco = db.get(Banco, banco_id)
    if banco is None:
        raise ValueError(f"Banco {banco_id} não encontrado.")
    nome = nome.strip()
    cnpj = cnpj.strip()
    email = email.strip()
    alvo = normalize(nome)
    for existente_id, existente_nome in db.execute(select(Banco.id, Banco.nome)):
        if existente_id != banco_id and normalize(existente_nome) == alvo:
            raise ValueError(f"Já existe um banco chamado '{existente_nome}'.")
    if not cnpj_valido(cnpj):
        raise ValueError(f"CNPJ '{cnpj}' inválido.")
    banco.nome = nome
    banco.cnpj = formatar_cnpj(cnpj)
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


def importar_planilha_bancos(db: Session, path: str) -> ImportResumoBancos:
    """Upsert por nome normalizado (sem acento/caixa): banco já cadastrado
    tem CNPJ/e-mail atualizados; nome novo cria um banco novo. Nunca apaga
    um banco que não apareça na planilha (reimport parcial não perde
    cadastro já feito na tela)."""
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
        if not nome:
            continue
        cnpj = cell_text(row.get(col_cnpj)) if col_cnpj else ""
        email = cell_text(row.get(col_email)) if col_email else ""

        if cnpj and not cnpj_valido(cnpj):
            resumo.rejeitados.append(f"{nome}: CNPJ '{cnpj}' inválido.")
            continue
        cnpj_formatado = formatar_cnpj(cnpj) if cnpj else ""

        alvo = normalize(nome)
        existente = existentes.get(alvo)
        if existente:
            if cnpj_formatado:
                existente.cnpj = cnpj_formatado
            if email:
                existente.email = email
            resumo.atualizados += 1
        else:
            novo = Banco(nome=nome, cnpj=cnpj_formatado, email=email)
            db.add(novo)
            existentes[alvo] = novo
            resumo.criados += 1

    db.commit()
    return resumo

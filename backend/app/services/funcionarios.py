"""Cadastro de funcionários (assistentes de Gestão de Processos, 2026-09-24)
— alimenta o dropdown "Funcionário" do relatório de Processos. Mesmo padrão
de app/services/empresas.py, sem `get_or_create` porque nada importa isso
automaticamente de planilha: é só cadastro manual (ver ARCHITECTURE.md).
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Funcionario
from app.utils import normalize


def listar_funcionarios(db: Session, apenas_ativos: bool = True) -> list[Funcionario]:
    query = select(Funcionario).order_by(Funcionario.nome)
    if apenas_ativos:
        query = query.where(Funcionario.ativo.is_(True))
    return list(db.scalars(query))


def criar_funcionario(db: Session, nome: str) -> Funcionario:
    nome = nome.strip()
    alvo = normalize(nome)
    # Só id/nome, não os objetos Funcionario completos (2026-10-14,
    # auditoria M20) — mesmo motivo de app/services/empresas.py.
    for _, existente_nome in db.execute(select(Funcionario.id, Funcionario.nome)):
        if normalize(existente_nome) == alvo:
            raise ValueError(f"Já existe um assistente chamado '{existente_nome}'.")
    funcionario = Funcionario(nome=nome)
    db.add(funcionario)
    db.commit()
    return funcionario


def atualizar_funcionario(db: Session, funcionario_id: int, nome: str) -> Funcionario:
    funcionario = db.get(Funcionario, funcionario_id)
    if funcionario is None:
        raise ValueError(f"Assistente {funcionario_id} não encontrado.")
    nome = nome.strip()
    alvo = normalize(nome)
    for existente_id, existente_nome in db.execute(select(Funcionario.id, Funcionario.nome)):
        if existente_id != funcionario_id and normalize(existente_nome) == alvo:
            raise ValueError(f"Já existe um assistente chamado '{existente_nome}'.")
    funcionario.nome = nome
    db.commit()
    return funcionario


def alterar_ativo_funcionario(db: Session, funcionario_id: int, ativo: bool) -> Funcionario:
    funcionario = db.get(Funcionario, funcionario_id)
    if funcionario is None:
        raise ValueError(f"Assistente {funcionario_id} não encontrado.")
    funcionario.ativo = ativo
    db.commit()
    return funcionario


def excluir_funcionario(db: Session, funcionario_id: int) -> None:
    """Exclusão definitiva — sem checagem de vínculo porque `Funcionario`
    não é referenciado por chave estrangeira em lugar nenhum (`Processo.
    assistente` continua texto livre, vindo da planilha; ver docstring do
    modelo). Excluir só tira o nome do dropdown do relatório, não mexe em
    nenhum processo/evento já gravado."""
    funcionario = db.get(Funcionario, funcionario_id)
    if funcionario is None:
        raise ValueError(f"Assistente {funcionario_id} não encontrado.")
    db.delete(funcionario)
    db.commit()

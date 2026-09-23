"""Resolução de empresa-cliente por nome (usada por todos os importadores).

Não confundir com `operadoras` (EXÍMIA/ELITE) — ver ARCHITECTURE.md seção 1.3.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EmpresaCliente
from app.utils import normalize


def get_or_create_empresa(
    db: Session, nome: str, cache: dict[str, EmpresaCliente] | None = None
) -> EmpresaCliente:
    """`cache`: opcional, para imports com muitas linhas (ex.: Gestão de
    Processos, Fase 5) — sem ele, cada chamada faz uma consulta ao banco
    percorrendo todas as empresas-clientes, o que é aceitável para poucas
    linhas mas caro repetido milhares de vezes num único import. Quem chama
    em loop deve passar um dict vazio compartilhado entre as chamadas
    (ver `app/services/processos.py`)."""
    nome = nome.strip()
    alvo = normalize(nome)
    if cache is not None and alvo in cache:
        return cache[alvo]
    for empresa in db.scalars(select(EmpresaCliente)):
        if normalize(empresa.nome) == alvo:
            if cache is not None:
                cache[normalize(empresa.nome)] = empresa
            return empresa
    empresa = EmpresaCliente(nome=nome)
    db.add(empresa)
    db.flush()
    if cache is not None:
        cache[alvo] = empresa
    return empresa


def listar_empresas(db: Session, apenas_ativas: bool = True) -> list[EmpresaCliente]:
    """Usada pelas telas (Fase 6) para montar o seletor de empresa-cliente
    nos módulos de relatório."""
    query = select(EmpresaCliente).order_by(EmpresaCliente.nome)
    if apenas_ativas:
        query = query.where(EmpresaCliente.ativo.is_(True))
    return list(db.scalars(query))


def criar_empresa(db: Session, nome: str, cnpj: str | None = None) -> EmpresaCliente:
    """Cadastro manual (Fase 6, tela de Administração) — os imports usam
    `get_or_create_empresa`; aqui é o caminho explícito, com checagem de
    nome duplicado (a coluna `nome` é `unique`, mas checar antes dá um erro
    claro em vez de deixar o banco recusar sem contexto)."""
    nome = nome.strip()
    alvo = normalize(nome)
    for existente in db.scalars(select(EmpresaCliente)):
        if normalize(existente.nome) == alvo:
            raise ValueError(f"Já existe uma empresa-cliente chamada '{existente.nome}'.")
    empresa = EmpresaCliente(nome=nome, cnpj=(cnpj or "").strip() or None)
    db.add(empresa)
    db.commit()
    return empresa


def atualizar_empresa(db: Session, empresa_id: int, nome: str, cnpj: str | None) -> EmpresaCliente:
    empresa = db.get(EmpresaCliente, empresa_id)
    if empresa is None:
        raise ValueError(f"Empresa-cliente {empresa_id} não encontrada.")
    nome = nome.strip()
    alvo = normalize(nome)
    for existente in db.scalars(select(EmpresaCliente)):
        if existente.id != empresa_id and normalize(existente.nome) == alvo:
            raise ValueError(f"Já existe uma empresa-cliente chamada '{existente.nome}'.")
    empresa.nome = nome
    empresa.cnpj = (cnpj or "").strip() or None
    db.commit()
    return empresa


def alterar_ativo_empresa(db: Session, empresa_id: int, ativo: bool) -> EmpresaCliente:
    empresa = db.get(EmpresaCliente, empresa_id)
    if empresa is None:
        raise ValueError(f"Empresa-cliente {empresa_id} não encontrada.")
    empresa.ativo = ativo
    db.commit()
    return empresa

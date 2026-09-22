"""Resolução de empresa-cliente por nome (usada por todos os importadores).

Não confundir com `operadoras` (EXÍMIA/ELITE) — ver ARCHITECTURE.md seção 1.3.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EmpresaCliente
from app.utils import normalize


def get_or_create_empresa(db: Session, nome: str) -> EmpresaCliente:
    nome = nome.strip()
    alvo = normalize(nome)
    for empresa in db.scalars(select(EmpresaCliente)):
        if normalize(empresa.nome) == alvo:
            return empresa
    empresa = EmpresaCliente(nome=nome)
    db.add(empresa)
    db.flush()
    return empresa

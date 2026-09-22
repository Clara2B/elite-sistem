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

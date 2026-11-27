"""Administração das faixas de preço de Audiências (2026-10-13, auditoria
M05) — antes só existia o seed inicial (`DEFAULT_FAIXAS_AUDIENCIA`,
app/db.py), sem nenhuma tela pra ampliar/corrigir. Se algum cliente
acumulasse mais audiências cobráveis no mês do que a última faixa
cadastrada cobre, `services/audiencias.py::gerar_relatorio` simplesmente
levantava erro pro resto do mês, sem nenhuma forma de corrigir fora de uma
edição direta no banco."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FaixaAudiencia


def listar_faixas(db: Session) -> list[FaixaAudiencia]:
    return list(db.scalars(select(FaixaAudiencia).order_by(FaixaAudiencia.inicio)))


def _validar(db: Session, inicio: int, fim: int, valor: float, ignorar_id: int | None = None) -> None:
    if inicio < 1:
        raise ValueError("O início da faixa deve ser 1 ou maior.")
    if fim < inicio:
        raise ValueError("O fim da faixa não pode ser menor que o início.")
    if valor < 0:
        raise ValueError("O valor não pode ser negativo.")
    for faixa in db.scalars(select(FaixaAudiencia)):
        if faixa.id == ignorar_id:
            continue
        if inicio <= faixa.fim and fim >= faixa.inicio:
            raise ValueError(
                f"A faixa {inicio}-{fim} se sobrepõe à faixa já cadastrada {faixa.inicio}-{faixa.fim}."
            )


def criar_faixa(db: Session, inicio: int, fim: int, valor: float) -> FaixaAudiencia:
    _validar(db, inicio, fim, valor)
    faixa = FaixaAudiencia(inicio=inicio, fim=fim, valor=valor)
    db.add(faixa)
    db.commit()
    return faixa


def atualizar_faixa(db: Session, faixa_id: int, inicio: int, fim: int, valor: float) -> FaixaAudiencia:
    faixa = db.get(FaixaAudiencia, faixa_id)
    if faixa is None:
        raise ValueError(f"Faixa {faixa_id} não encontrada.")
    _validar(db, inicio, fim, valor, ignorar_id=faixa_id)
    faixa.inicio = inicio
    faixa.fim = fim
    faixa.valor = valor
    db.commit()
    return faixa


def excluir_faixa(db: Session, faixa_id: int) -> None:
    faixa = db.get(FaixaAudiencia, faixa_id)
    if faixa is None:
        raise ValueError(f"Faixa {faixa_id} não encontrada.")
    db.delete(faixa)
    db.commit()
